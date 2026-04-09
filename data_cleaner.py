"""
data_cleaner.py — OHLCV DataFrame 정제 모듈

수집 직후 호출하여 결측치·이상치·거래정지일을 제거하고,
제외 조건 충족 종목은 None을 반환하며 logs/ 에 이력을 기록한다.

처리 원칙 (plan.md §데이터 결측치 처리 원칙):
  - 결측치 1~4일: 선형 보간
  - 결측치 연속 5일+: 종목 제외
  - 거래량 = 0: 해당 봉 제거 (거래정지일)
  - 종가 이상치 전일 대비 ±30% 초과: 제외
  - 전체 데이터 < 65일: 제외
"""

import sys
import os
import logging
from datetime import date

import pandas as pd

sys.stdout.reconfigure(encoding='utf-8')

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
LOG_DIR = os.path.join(BASE_DIR, 'logs')
os.makedirs(LOG_DIR, exist_ok=True)

# ── 세션 내 제외 종목 카운터 ──────────────────────────────────────────────
_excluded_count: int = 0

# ── 로거 설정 ─────────────────────────────────────────────────────────────
_logger = logging.getLogger('data_cleaner')
if not _logger.handlers:
    _logger.setLevel(logging.INFO)
    _formatter = logging.Formatter('%(message)s')
    _stream_handler = logging.StreamHandler(sys.stdout)
    _stream_handler.setFormatter(_formatter)
    _logger.addHandler(_stream_handler)


def _log_excluded(ticker: str, reason: str) -> None:
    """logs/excluded_YYYYMMDD.log 에 제외 이력 기록."""
    today_str = date.today().strftime('%Y%m%d')
    log_path = os.path.join(LOG_DIR, f'excluded_{today_str}.log')

    timestamp = date.today().strftime('%Y-%m-%d')
    line = f'{timestamp} | {ticker} | {reason}'

    try:
        with open(log_path, 'a', encoding='utf-8') as f:
            f.write(line + '\n')
        _logger.info('[data_cleaner] 제외: %s', line)
    except OSError as e:
        _logger.warning('[data_cleaner] 로그 기록 실패 (%s): %s', log_path, e)


def _max_consecutive_nulls(series: pd.Series) -> int:
    """Series 내 연속 결측치 최대 길이 반환."""
    max_run = 0
    current_run = 0
    for val in series:
        if pd.isna(val):
            current_run += 1
            if current_run > max_run:
                max_run = current_run
        else:
            current_run = 0
    return max_run


def clean(df: pd.DataFrame, ticker: str) -> 'pd.DataFrame | None':
    """
    OHLCV DataFrame 정제.

    Parameters
    ----------
    df : pd.DataFrame
        컬럼 Open·High·Low·Close·Volume 포함. DatetimeIndex 권장.
    ticker : str
        종목 코드 (로그 기록용).

    Returns
    -------
    pd.DataFrame | None
        정제된 DataFrame. 제외 조건 충족 시 None.
    """
    global _excluded_count

    if df is None or df.empty:
        _log_excluded(ticker, 'DataFrame 비어있음')
        _excluded_count += 1
        return None

    result = df.copy()

    # ── 1. 거래량 = 0 봉 제거 ─────────────────────────────────────────────
    if 'Volume' in result.columns:
        before = len(result)
        result = result[result['Volume'] > 0]
        removed = before - len(result)
        if removed > 0:
            _logger.info('[data_cleaner] %s: 거래량=0 봉 %d개 제거', ticker, removed)

    if result.empty:
        _log_excluded(ticker, '거래량=0 봉 제거 후 데이터 없음')
        _excluded_count += 1
        return None

    # ── 2. 전체 데이터 길이 검사 (< 65일 제외) ───────────────────────────
    if len(result) < 65:
        _log_excluded(ticker, f'데이터 부족 ({len(result)}일 < 65일)')
        _excluded_count += 1
        return None

    # ── 3. 결측치 처리 ────────────────────────────────────────────────────
    ohlcv_cols = [c for c in ['Open', 'High', 'Low', 'Close', 'Volume'] if c in result.columns]

    for col in ohlcv_cols:
        max_consec = _max_consecutive_nulls(result[col])
        if max_consec >= 5:
            _log_excluded(ticker, f'{col} 연속 결측치 {max_consec}일 (≥5일 기준)')
            _excluded_count += 1
            return None

    # 연속 결측치 < 5일: 선형 보간
    result[ohlcv_cols] = result[ohlcv_cols].interpolate(method='linear', limit=4)

    # 보간 후에도 남은 결측치(앞/뒤 경계) forward/backward fill
    result[ohlcv_cols] = result[ohlcv_cols].ffill().bfill()

    # ── 4. 종가 이상치 검사 ────────────────────────────────────────────
    # 한국 시장(KS/KQ)은 가격제한폭 ±30%이므로 임계값 35%로 완화
    # 이상치 3건 이하: 해당 행만 제거 (종목 유지)
    # 이상치 4건+: 종목 전체 제외
    if 'Close' in result.columns:
        is_kr = ticker.endswith('.KS') or ticker.endswith('.KQ')
        outlier_threshold = 0.35 if is_kr else 0.30
        close = result['Close']
        pct_change = close.pct_change()
        abs_change = pct_change.abs()
        outlier_mask = abs_change > outlier_threshold

        # 주식분할/병합 오탐 방지: 큰 변동 후 다음날 역방향 20%+ 회복이면 분할로 간주
        if outlier_mask.any():
            outlier_indices = outlier_mask[outlier_mask].index.tolist()
            false_positives = set()
            for idx in outlier_indices:
                pos = result.index.get_loc(idx)
                if pos + 1 < len(result):
                    next_chg = pct_change.iloc[pos + 1] if pos + 1 < len(pct_change) else 0
                    curr_chg = pct_change.iloc[pos] if pos < len(pct_change) else 0
                    # 역방향 회복: 부호 반대 + 20% 이상 되돌림
                    if curr_chg != 0 and next_chg != 0:
                        if (curr_chg > 0 and next_chg < -0.20) or (curr_chg < 0 and next_chg > 0.20):
                            false_positives.add(idx)
            # 분할 의심 건 제외
            outlier_mask.loc[list(false_positives)] = False

        if outlier_mask.any():
            outlier_count = int(outlier_mask.sum())
            if outlier_count <= 3:
                # 소수 이상치: 해당 행만 제거하고 종목은 유지
                result = result[~outlier_mask]
                _log_excluded(
                    ticker,
                    f'종가 이상치 {outlier_count}건 제거 (행 삭제, 종목 유지)'
                )
            else:
                _log_excluded(
                    ticker,
                    f'종가 이상치 {outlier_count}건 (전일 대비 ±{int(outlier_threshold*100)}% 초과)'
                )
                _excluded_count += 1
                return None

    # ── 5. 최종 길이 재검사 ───────────────────────────────────────────────
    if len(result) < 65:
        _log_excluded(ticker, f'정제 후 데이터 부족 ({len(result)}일 < 65일)')
        _excluded_count += 1
        return None

    return result


def get_excluded_count() -> int:
    """현재 세션에서 제외된 종목 수 반환."""
    return _excluded_count
