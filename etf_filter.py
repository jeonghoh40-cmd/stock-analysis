"""
etf_filter.py — ETF 전용 필터 엔진

중국 ETF 및 국내 ETF의 품질 기준을 검증한다.
yfinance로 OHLCV를 조회하여 유동성·규모·상장 기간을 확인한다.

필터 기준 (plan.md §ETF 전용 필터 기준):
  - 일 평균 거래대금  ≥ 5억 원 (500_000_000 KRW)
  - 순자산(AUM)      ≥ 100억 원 (10_000_000_000 KRW) — yfinance 불가 시 거래대금으로 대체
  - 상장 후 경과      ≥ 6개월 (약 126 거래일)

오류·타임아웃 시 True 반환 (안전 방향):
  데이터 없다고 좋은 ETF를 제외하면 안 됨.
"""

import sys
import os
import logging
from datetime import date, timedelta

import yfinance as yf
import pandas as pd

sys.stdout.reconfigure(encoding='utf-8')

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

_logger = logging.getLogger('etf_filter')
if not _logger.handlers:
    _logger.setLevel(logging.INFO)
    _handler = logging.StreamHandler(sys.stdout)
    _handler.setFormatter(logging.Formatter('%(asctime)s [%(name)s] %(message)s'))
    _logger.addHandler(_handler)

# ── 필터 기준 상수 ─────────────────────────────────────────────────────────
_MIN_DAILY_TURNOVER_KRW: int = 500_000_000       # 5억 원
_MIN_AUM_KRW: int = 10_000_000_000               # 100억 원
_MIN_LISTED_DAYS: int = 126                       # 6개월 ≈ 126 거래일
_LOOKBACK_DAYS: int = 30                          # 거래대금 평균 산출 기간
_HISTORY_FETCH_DAYS: int = 400                    # 상장 기간 확인용 충분한 기간
_YFINANCE_TIMEOUT: int = 15                       # 초


def _fetch_history(ticker: str) -> pd.DataFrame | None:
    """yfinance로 OHLCV 조회. 실패 시 None."""
    try:
        end = date.today()
        start = end - timedelta(days=_HISTORY_FETCH_DAYS)
        ticker_obj = yf.Ticker(ticker)
        df = ticker_obj.history(
            start=start.strftime('%Y-%m-%d'),
            end=end.strftime('%Y-%m-%d'),
            timeout=_YFINANCE_TIMEOUT,
            auto_adjust=True,
        )
        if df is None or df.empty:
            return None
        return df
    except Exception as e:
        _logger.debug('[etf_filter] %s yfinance 조회 실패: %s', ticker, e)
        return None


def _check_listed_duration(df: pd.DataFrame) -> bool:
    """상장 후 경과 기간 ≥ 6개월(126 거래일) 확인."""
    return len(df) >= _MIN_LISTED_DAYS


def _check_daily_turnover(df: pd.DataFrame) -> bool:
    """
    최근 _LOOKBACK_DAYS 거래일 일 평균 거래대금 ≥ 5억 원 확인.
    거래대금 = Volume × Close (KRW 기준 종목 그대로 사용).
    """
    recent = df.tail(_LOOKBACK_DAYS)
    if recent.empty:
        return False

    if 'Volume' not in recent.columns or 'Close' not in recent.columns:
        return False

    turnover = recent['Volume'] * recent['Close']
    avg_turnover = turnover.mean()

    _logger.debug('[etf_filter] 일 평균 거래대금 %.0f원', avg_turnover)
    return avg_turnover >= _MIN_DAILY_TURNOVER_KRW


def _check_aum_proxy(df: pd.DataFrame) -> bool:
    """
    yfinance는 AUM을 직접 제공하지 않으므로,
    최근 거래대금 합계(30일)를 AUM 프록시로 사용한다.
    30일 누적 거래대금 ≥ 100억 원을 AUM 기준 대체 지표로 설정.

    실제 AUM 데이터가 확보되면 이 함수를 교체할 것.
    """
    recent = df.tail(_LOOKBACK_DAYS)
    if recent.empty:
        return False

    if 'Volume' not in recent.columns or 'Close' not in recent.columns:
        return False

    total_turnover = (recent['Volume'] * recent['Close']).sum()
    _logger.debug('[etf_filter] 30일 누적 거래대금(AUM 프록시) %.0f원', total_turnover)
    return total_turnover >= _MIN_AUM_KRW


def is_valid_etf(ticker: str, name: str = '') -> bool:
    """
    ETF 품질 검증.

    Parameters
    ----------
    ticker : str
        yfinance 티커 (예: '192090.KS').
    name : str, optional
        종목명 (로그 출력용).

    Returns
    -------
    bool
        통과 시 True, 기준 미달 시 False, 오류·타임아웃 시 True(안전 방향).
    """
    label = f'{ticker}({name})' if name else ticker

    try:
        df = _fetch_history(ticker)

        # 데이터 조회 실패 → 안전 방향으로 통과
        if df is None:
            _logger.info('[etf_filter] %s 데이터 조회 실패 → 안전 방향 통과', label)
            return True

        # 상장 기간 검사
        if not _check_listed_duration(df):
            _logger.info(
                '[etf_filter] %s 제외: 상장 기간 부족 (%d 거래일 < %d일)',
                label, len(df), _MIN_LISTED_DAYS,
            )
            return False

        # 일 평균 거래대금 검사
        if not _check_daily_turnover(df):
            _logger.info(
                '[etf_filter] %s 제외: 일 평균 거래대금 < 5억 원',
                label,
            )
            return False

        # AUM 프록시 검사
        if not _check_aum_proxy(df):
            _logger.info(
                '[etf_filter] %s 제외: AUM 프록시(30일 누적 거래대금) < 100억 원',
                label,
            )
            return False

        _logger.info('[etf_filter] %s 통과', label)
        return True

    except Exception as e:
        _logger.warning('[etf_filter] %s 검증 중 예외 → 안전 방향 통과: %s', label, e)
        return True
