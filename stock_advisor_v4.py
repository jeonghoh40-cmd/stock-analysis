"""
AI 주식 스크리닝 어드바이저 v4 (정밀 분석 강화판)
────────────────────────────────────────────────────────────────
v3 대비 추가 분석 방법론:
  [기술적] ATR(변동성), 스토캐스틱(%K/%D), ADX(추세강도), OBV(거래량추세), 52주 위치
  [가치평가] P/E, P/B, ROE, EPS성장률 → 펀더멘털 점수(±30)
  [시장심리] Fear & Greed Index (alternative.me)
  [손절가]  ATR 기반 동적 손절가 (고정 % 아닌 변동성 비례)
  [섹터]   섹터 ETF 자금 흐름 (XLK/XLF/XLE/XLV/KODEX)

실행 흐름:
  ① 전 종목 기술적 스크리닝 (ATR/Stoch/ADX/OBV 포함)
  ② 상위 후보 펀더멘털 보강 (P/E·P/B·ROE — 병렬 fetch)
  ③ 기술 + 펀더멘털 + 투자자 복합 점수 확정
  ④ 거시 + Fear&Greed + 뉴스 + 섹터 흐름 수집
  ⑤ Claude 심층 분석 (ATR 손절가 포함)
  ⑥ report.txt 저장 + 이메일 + 카카오톡

⚠️ 투자 참고용. 최종 결정은 본인이 직접 판단하세요.
"""

import os
import sys
import time
import json
import smtplib
import requests
import datetime
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import Optional

import yfinance as yf
import pandas as pd
import numpy as np
import feedparser
from dotenv import dotenv_values
from universe import (get_kr_pools, UNIVERSE,
                       get_recent_kr_ipos_auto, get_recent_ipos,
                       SELL_POOL, DELIST_BLACKLIST)
import data_cleaner
from broker_news_collector import get_broker_picks

if sys.stdout.encoding != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

# ── .env 로드 ─────────────────────────────────────────────────
_env_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")
_cfg = dotenv_values(_env_path)

def _get(key: str, default: str = "") -> str:
    return os.environ.get(key) or _cfg.get(key) or default

BASE_DIR    = os.path.dirname(os.path.abspath(__file__))
REPORT_PATH = os.path.join(BASE_DIR, "report_v4.txt")

# ── 알림 설정 ─────────────────────────────────────────────────
SMTP_SERVER = _get("SMTP_SERVER", "smtp.gmail.com")
SMTP_PORT   = int(_get("SMTP_PORT", "587"))
EMAIL_USER  = _get("EMAIL_USER")
EMAIL_PASS  = _get("EMAIL_PASS")
EMAIL_FROM  = _get("EMAIL_FROM", EMAIL_USER)
EMAIL_TO    = _get("EMAIL_TO", "geunho@stic.co.kr")
TELEGRAM_BOT_TOKEN = _get("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID   = _get("TELEGRAM_CHAT_ID")


# ═══════════════════════════════════════════════════════════════
# 스크리닝 유니버스 — universe.py 단일 소스에서 로드
# KOSPI_POOL / KOSDAQ_POOL: get_kr_pools() 동적 조회 (KOSPI200 + KOSDAQ150)
# US_POOL: UNIVERSE['🇺🇸 미국'] 정적 anchor
# ═══════════════════════════════════════════════════════════════

US_POOL = {
    # ── 빅테크 / AI ─────────────────────────────────────────────────
    "Apple":             "AAPL",  "NVIDIA":          "NVDA",
    "Microsoft":         "MSFT",  "Alphabet":        "GOOGL",
    "Amazon":            "AMZN",  "Meta":            "META",
    "Tesla":             "TSLA",  "Broadcom":        "AVGO",
    "AMD":               "AMD",   "TSMC ADR":        "TSM",
    "Netflix":           "NFLX",  "Salesforce":      "CRM",
    "Oracle":            "ORCL",  "Adobe":           "ADBE",
    "Qualcomm":          "QCOM",  "Intel":           "INTC",
    "Micron":            "MU",    "Applied Materials":"AMAT",
    "Lam Research":      "LRCX",  "KLA Corp":        "KLAC",
    "Palo Alto":         "PANW",  "CrowdStrike":     "CRWD",
    "Palantir":          "PLTR",  "Datadog":         "DDOG",
    "ServiceNow":        "NOW",   "Workday":         "WDAY",
    "Uber":              "UBER",  "Shopify":         "SHOP",
    # ── AI 인프라·반도체 테마 ────────────────────────────────────────
    "ARM Holdings":      "ARM",   "Marvell":         "MRVL",
    "Super Micro":       "SMCI",  "Vertiv":          "VRT",
    "ASML":              "ASML",  "Arista Networks": "ANET",
    # ── 금융 ─────────────────────────────────────────────────────────
    "Visa":              "V",     "Mastercard":      "MA",
    "JPMorgan":          "JPM",   "Goldman Sachs":   "GS",
    "Berkshire B":       "BRK-B", "Bank of America": "BAC",
    "Wells Fargo":       "WFC",   "Schwab":          "SCHW",
    "Blackrock":         "BLK",
    # ── 헬스케어 ─────────────────────────────────────────────────────
    "Johnson&Johnson":   "JNJ",   "Eli Lilly":       "LLY",
    "UnitedHealth":      "UNH",   "Pfizer":          "PFE",
    "Novo Nordisk":      "NVO",
    # ── 에너지 테마 ──────────────────────────────────────────────────
    "Exxon Mobil":       "XOM",   "Chevron":         "CVX",
    "ConocoPhillips":    "COP",   "Occidental":      "OXY",
    "Devon Energy":      "DVN",   "Diamondback":     "FANG",
    "Valero Energy":     "VLO",   "Phillips 66":     "PSX",
    "Halliburton":       "HAL",
    # ── 방산 테마 ────────────────────────────────────────────────────
    "Lockheed Martin":   "LMT",   "RTX":             "RTX",
    "Northrop Grumman":  "NOC",   "General Dynamics": "GD",
    "Boeing":            "BA",    "L3Harris":        "LHX",
    # ── 원전·전력 테마 ───────────────────────────────────────────────
    "Constellation Egy": "CEG",   "Vistra Energy":   "VST",
    "Cameco":            "CCJ",   "NRG Energy":      "NRG",
    "NextEra Energy":    "NEE",
    # ── 소비재·산업재 ────────────────────────────────────────────────
    "Walmart":           "WMT",   "Costco":          "COST",
    "Caterpillar":       "CAT",   "Walt Disney":     "DIS",
    # ── 미국 섹터 ETF ────────────────────────────────────────────────
    "ETF-에너지 XLE":    "XLE",   "ETF-기술 XLK":    "XLK",
    "ETF-금융 XLF":      "XLF",   "ETF-헬스케어 XLV":"XLV",
    "ETF-산업재 XLI":    "XLI",   "ETF-필수소비 XLP":"XLP",
    "ETF-유틸리티 XLU":  "XLU",   "ETF-소재 XLB":    "XLB",
    # ── 테마 ETF ─────────────────────────────────────────────────────
    "ETF-반도체 SMH":    "SMH",   "ETF-방산 ITA":    "ITA",
    "ETF-금 GLD":        "GLD",   "ETF-원유 USO":    "USO",
    "ETF-나스닥 QQQ":    "QQQ",   "ETF-혁신 ARKK":   "ARKK",
}

RECOMMEND_COUNT = {"KOSPI": 5, "KOSDAQ": 3, "US": 5}
SELL_COUNT      = {"KOSPI": 3, "KOSDAQ": 2, "US": 3}


# ═══════════════════════════════════════════════════════════════
# 기술적 지표 계산 — 기존 + 신규
# ═══════════════════════════════════════════════════════════════

def _rsi(close: pd.Series, n: int = 14) -> float:
    d    = close.diff()
    gain = d.where(d > 0, 0.0).rolling(n).mean()
    loss = (-d.where(d < 0, 0.0)).rolling(n).mean()
    return float(100 - 100 / (1 + gain.iloc[-1] / (loss.iloc[-1] + 1e-9)))

def _macd(close: pd.Series):
    e12  = close.ewm(span=12, adjust=False).mean()
    e26  = close.ewm(span=26, adjust=False).mean()
    macd = e12 - e26
    sig  = macd.ewm(span=9, adjust=False).mean()
    hist = macd - sig
    return float(macd.iloc[-1]), float(sig.iloc[-1]), float(hist.iloc[-1])


def _rsi_series(close: pd.Series, n: int = 14, lookback: int = 5) -> list:
    """최근 lookback일의 RSI 값 리스트 반환."""
    d    = close.diff()
    gain = d.where(d > 0, 0.0).rolling(n).mean()
    loss = (-d.where(d < 0, 0.0)).rolling(n).mean()
    rs   = gain / (loss + 1e-9)
    rsi  = 100 - 100 / (1 + rs)
    return [float(v) for v in rsi.iloc[-lookback:]]


def _macd_series(close: pd.Series, lookback: int = 5):
    """최근 lookback일의 (macd, signal, histogram) 리스트 반환."""
    e12  = close.ewm(span=12, adjust=False).mean()
    e26  = close.ewm(span=26, adjust=False).mean()
    macd = e12 - e26
    sig  = macd.ewm(span=9, adjust=False).mean()
    hist = macd - sig
    return ([float(v) for v in macd.iloc[-lookback:]],
            [float(v) for v in sig.iloc[-lookback:]],
            [float(v) for v in hist.iloc[-lookback:]])

def _mas(close: pd.Series):
    return (float(close.rolling(5).mean().iloc[-1]),
            float(close.rolling(20).mean().iloc[-1]),
            float(close.rolling(60).mean().iloc[-1]))

def _mom(close: pd.Series, d: int = 5) -> float:
    return float((close.iloc[-1] / close.iloc[-d] - 1) * 100) if len(close) > d else 0.0

def _bb(close: pd.Series):
    mid = close.rolling(20).mean()
    std = close.rolling(20).std()
    up  = (mid + 2 * std).iloc[-1]
    dn  = (mid - 2 * std).iloc[-1]
    cur = close.iloc[-1]
    pct = (cur - dn) / (up - dn) * 100 if (up - dn) > 0 else 50.0
    return round(up, 2), round(dn, 2), round(pct, 1)

# ── 신규 지표 ─────────────────────────────────────────────────

def _atr(high: pd.Series, low: pd.Series, close: pd.Series, n: int = 14) -> float:
    """ATR: 실제 가격 변동성 측정 → 동적 손절가 계산에 활용"""
    tr = pd.concat([
        high - low,
        (high - close.shift()).abs(),
        (low  - close.shift()).abs(),
    ], axis=1).max(axis=1)
    return float(tr.rolling(n).mean().iloc[-1])

def _stochastic(high: pd.Series, low: pd.Series, close: pd.Series,
                k_period: int = 14, d_period: int = 3):
    """스토캐스틱 %K/%D — RSI와 함께 과매수·과매도 확인"""
    low_k  = low.rolling(k_period).min()
    high_k = high.rolling(k_period).max()
    k = 100 * (close - low_k) / (high_k - low_k + 1e-9)
    d = k.rolling(d_period).mean()
    return float(k.iloc[-1]), float(d.iloc[-1])

def _adx(high: pd.Series, low: pd.Series, close: pd.Series, n: int = 14):
    """
    ADX: 추세 강도 측정
    ADX > 25 → 강한 추세 (방향성 있는 매매 유효)
    ADX < 20 → 횡보 (역추세 전략 유효)
    +DI > -DI: 상승 추세 / +DI < -DI: 하락 추세
    """
    prev_close = close.shift()
    plus_dm  = high.diff().clip(lower=0)
    minus_dm = (-low.diff()).clip(lower=0)
    # +DM 조건: +DM > -DM
    cond = plus_dm <= minus_dm
    plus_dm[cond]  = 0
    cond2 = minus_dm <= plus_dm
    minus_dm[cond2] = 0

    tr = pd.concat([
        high - low,
        (high - prev_close).abs(),
        (low  - prev_close).abs(),
    ], axis=1).max(axis=1)

    atr      = tr.ewm(span=n, adjust=False).mean()
    plus_di  = 100 * plus_dm.ewm(span=n, adjust=False).mean() / (atr + 1e-9)
    minus_di = 100 * minus_dm.ewm(span=n, adjust=False).mean() / (atr + 1e-9)
    dx       = 100 * (plus_di - minus_di).abs() / (plus_di + minus_di + 1e-9)
    adx      = dx.ewm(span=n, adjust=False).mean()
    return float(adx.iloc[-1]), float(plus_di.iloc[-1]), float(minus_di.iloc[-1])

def _lbr_3_10(close: pd.Series):
    """
    린다 라쉬케 LBR 3/10 오실레이터.
    빠른선: EMA(3) - EMA(10)  (MACD처럼 두 이평선의 차이)
    느린선: 빠른선의 SMA(16)  (시그널 라인)
    추세 분류: 빠른선 > 0 AND 느린선 우상향 → 상승 추세
    """
    ema3  = close.ewm(span=3,  adjust=False).mean()
    ema10 = close.ewm(span=10, adjust=False).mean()
    fast  = ema3 - ema10                     # 빠른선 (3/10 오실레이터)
    slow  = fast.rolling(16).mean()          # 느린선 (16일 평균)

    fast_val = float(fast.iloc[-1])
    slow_val = float(slow.iloc[-1])
    # 느린선 우상향: 최근 3일 연속 상승
    slow_recent = slow.dropna().iloc[-3:]
    slow_rising = False
    if len(slow_recent) >= 3:
        slow_rising = bool(
            slow_recent.iloc[-1] > slow_recent.iloc[-2] > slow_recent.iloc[-3]
        )
    # 추세 종목 판정: 빠른선 > 0 AND 느린선 우상향
    is_trending = fast_val > 0 and slow_rising
    return fast_val, slow_val, bool(slow_rising), bool(is_trending)


def _obv_trend(close: pd.Series, volume: pd.Series, n: int = 20) -> float:
    """
    OBV 추세: OBV가 20일 MA 대비 위에 있으면 양수, 아래면 음수
    상승 중 OBV 증가 = 강한 매수세 / 상승 중 OBV 감소 = 분산 경고
    """
    direction = close.diff().apply(lambda x: 1 if x > 0 else (-1 if x < 0 else 0))
    obv       = (volume * direction).cumsum()
    obv_ma    = obv.rolling(n).mean()
    ma_val    = float(obv_ma.iloc[-1])
    if abs(ma_val) < 1e-9:
        return 0.0
    diff      = (float(obv.iloc[-1]) - ma_val) / ma_val
    return round(diff, 4)

def _week52_pos(close: pd.Series) -> float:
    """
    52주(약 252 거래일) 가격대 위치 (%)
    100% = 52주 신고가 / 0% = 52주 신저가
    80% 이상 = 모멘텀 강세 / 20% 이하 = 반등 후보
    """
    length = min(len(close), 252)
    sub    = close.iloc[-length:]
    hi, lo = float(sub.max()), float(sub.min())
    cur    = float(close.iloc[-1])
    return round((cur - lo) / (hi - lo + 1e-9) * 100, 1)


# ═══════════════════════════════════════════════════════════════
# 바닥 반전 시그널 탐지
# ═══════════════════════════════════════════════════════════════

def detect_reversal_signal(close: pd.Series, high: pd.Series,
                           low: pd.Series, volume: pd.Series) -> Optional[dict]:
    """
    바닥 반전 시그널을 탐지한다. 아래 두 경로 중 하나 이상 충족 시 반환.
    경로 A: RSI 반등 + MACD 골든크로스/히스토그램 축소 + 거래량 동반
    경로 B: ADX 하락반전 (하락 추세 종료 — ADX 25 이상에서 하락 전환 + -DI 감소)
    """
    if len(close) < 30:
        return None

    result = {}  # 시그널 상세

    # ── 경로 A: RSI + MACD + 거래량 ──
    path_a = False
    rsi_vals = _rsi_series(close, lookback=5)
    rsi_low = rsi_now = 0.0
    if len(rsi_vals) >= 5:
        rsi_low  = min(rsi_vals)
        rsi_now  = rsi_vals[-1]
        rsi_bounce = rsi_now - rsi_low
        rsi_ok = (rsi_low <= 35 and rsi_now <= 50
                  and (rsi_bounce >= 3 or rsi_now >= 30))
    else:
        rsi_ok = False

    macd_cross_day = None
    hist_shrink_days = 0
    hist_latest = 0.0
    vol_spike = 0.0
    if rsi_ok:
        macd_l, sig_l, hist_l = _macd_series(close, lookback=5)
        if len(hist_l) >= 4:
            for i in range(max(0, len(hist_l) - 3), len(hist_l)):
                if i > 0 and hist_l[i - 1] < 0 and hist_l[i] >= 0:
                    macd_cross_day = len(hist_l) - i
                    break
            hist_shrinking = False
            if hist_l[-1] >= 0:
                hist_shrinking = True
            elif len(hist_l) >= 3:
                recent = [abs(h) for h in hist_l[-3:]]
                if recent[-2] > recent[-1]:
                    hist_shrinking = True
                    hist_shrink_days = 2
                if len(hist_l) >= 4:
                    recent4 = [abs(h) for h in hist_l[-4:]]
                    if recent4[-3] > recent4[-2] > recent4[-1]:
                        hist_shrink_days = 3
            hist_latest = hist_l[-1]
            # MACD 골든크로스는 5일 이내만 유효 (오래된 신호 무효화)
            macd_cross_fresh = macd_cross_day is not None and macd_cross_day <= 5
            macd_ok = macd_cross_fresh or hist_shrinking

            if macd_ok:
                vol_ma20 = float(volume.rolling(20).mean().iloc[-1])
                vol_3d   = [float(v) for v in volume.iloc[-3:]]
                vol_spike = max(v / (vol_ma20 + 1e-9) for v in vol_3d)
                if vol_spike >= 1.0:
                    path_a = True

    # ── 경로 B: ADX 하락반전 (하락 추세 종료) — _adx() 재사용 ──
    adx_reversal = False
    adx_peak = adx_now = plus_di_now = minus_di_now = 0.0
    try:
        adx_val_b, pdi_b, mdi_b = _adx(high, low, close)
        adx_now = adx_val_b
        plus_di_now = pdi_b
        minus_di_now = mdi_b
        # 피크 추정: 최근 10일 ADX 시리즈로 계산
        prev_close_b = close.shift()
        plus_dm_b  = high.diff().clip(lower=0)
        minus_dm_b = (-low.diff()).clip(lower=0)
        cond_b = plus_dm_b <= minus_dm_b
        plus_dm_c_b = plus_dm_b.copy(); plus_dm_c_b[cond_b] = 0
        cond2_b = minus_dm_b <= plus_dm_b
        minus_dm_c_b = minus_dm_b.copy(); minus_dm_c_b[cond2_b] = 0
        tr_b = pd.concat([high - low, (high - prev_close_b).abs(),
                          (low - prev_close_b).abs()], axis=1).max(axis=1)
        atr_b    = tr_b.ewm(span=14, adjust=False).mean()
        pdi_s    = 100 * plus_dm_c_b.ewm(span=14, adjust=False).mean() / (atr_b + 1e-9)
        mdi_s    = 100 * minus_dm_c_b.ewm(span=14, adjust=False).mean() / (atr_b + 1e-9)
        dx_b     = 100 * (pdi_s - mdi_s).abs() / (pdi_s + mdi_s + 1e-9)
        adx_series = dx_b.ewm(span=14, adjust=False).mean()
        adx_recent = adx_series.dropna().iloc[-10:]
        mdi_recent = mdi_s.dropna().iloc[-5:]
        pdi_recent = pdi_s.dropna().iloc[-5:]
        if len(adx_recent) >= 5 and len(mdi_recent) >= 3:
            adx_peak = float(adx_recent.max())
            adx_declining = adx_now < adx_peak - 2
            was_downtrend = minus_di_now > plus_di_now or float(mdi_recent.iloc[-3]) > float(pdi_recent.iloc[-3])
            mdi_weakening = float(mdi_recent.iloc[-1]) < float(mdi_recent.iloc[-2])
            if adx_peak >= 25 and adx_declining and was_downtrend and mdi_weakening:
                adx_reversal = True
    except (IndexError, ValueError, KeyError):
        pass

    if not path_a and not adx_reversal:
        return None

    result = {
        "rsi_low":          round(rsi_low, 1),
        "rsi_now":          round(rsi_now, 1),
        "macd_cross_days":  macd_cross_day,
        "hist_shrink_days": hist_shrink_days,
        "hist_latest":      round(hist_latest, 4),
        "vol_spike":        round(vol_spike, 2),
        "adx_reversal":     adx_reversal,
        "adx_peak":         round(adx_peak, 1),
        "adx_now":          round(adx_now, 1),
        "path_a":           path_a,
    }
    return result


def detect_bearish_signal(close: pd.Series, high: pd.Series,
                          low: pd.Series, volume: pd.Series) -> Optional[dict]:
    """
    천장 반전(매도) 시그널 탐지.
    RSI 70+ 진입 + MACD 데드크로스 + 양의 히스토그램 축소 + 거래량 없는 반등
    동시 충족 시 시그널 dict, 아니면 None.
    """
    if len(close) < 30:
        return None

    # ① RSI 과열: 최근 5일 내 RSI ≥ 65 터치 후, 현재 RSI가 고점 대비 3pt 이상 하락
    #    또는 RSI ≥ 70이되 현재 50~80 범위 (천장권 하락 초기 포착)
    rsi_vals = _rsi_series(close, lookback=5)
    if len(rsi_vals) < 5:
        return None
    rsi_high = max(rsi_vals)
    rsi_now  = rsi_vals[-1]
    rsi_drop = rsi_high - rsi_now
    rsi_ok = (rsi_high >= 65 and rsi_now >= 50
              and (rsi_drop >= 3 or rsi_now <= 70))

    if not rsi_ok:
        return None

    # ② MACD 데드크로스 / ③ 양의 히스토그램 축소
    macd_l, sig_l, hist_l = _macd_series(close, lookback=5)
    if len(hist_l) < 3:
        return None

    # 데드크로스: 최근 3일 내 hist가 양→음 전환
    macd_cross_day = None
    for i in range(max(0, len(hist_l) - 3), len(hist_l)):
        if i > 0 and hist_l[i - 1] > 0 and hist_l[i] <= 0:
            macd_cross_day = len(hist_l) - i
            break

    # 양의 히스토그램 축소: 양수이되 2일+ 절대값 감소, 또는 이미 음전환
    hist_shrinking = False
    hist_shrink_days = 0
    if hist_l[-1] <= 0:
        hist_shrinking = True
        hist_shrink_days = 0
    elif len(hist_l) >= 3:
        recent = [abs(h) for h in hist_l[-3:]]
        if recent[-2] > recent[-1]:
            hist_shrinking = True
            hist_shrink_days = 2
        if len(hist_l) >= 4:
            recent4 = [abs(h) for h in hist_l[-4:]]
            if recent4[-3] > recent4[-2] > recent4[-1]:
                hist_shrink_days = 3

    macd_ok = (macd_cross_day is not None) or hist_shrinking
    if not macd_ok:
        return None

    # ④ 거래량 없는 반등: 최근 3일 중 가격 상승일에 거래량 < 20일 평균
    #    즉, 상승은 있으나 거래량이 뒷받침되지 않음
    vol_ma20 = float(volume.rolling(20).mean().iloc[-1])
    prices_3d = [float(c) for c in close.iloc[-4:]]  # 4일분 (3번 비교)
    vols_3d   = [float(v) for v in volume.iloc[-3:]]
    low_vol_rally = False
    vol_ratio_on_up = 1.0
    for j in range(3):
        if prices_3d[j + 1] > prices_3d[j]:  # 상승일
            ratio = vols_3d[j] / (vol_ma20 + 1e-9)
            if ratio < 1.0:
                low_vol_rally = True
                vol_ratio_on_up = min(vol_ratio_on_up, round(ratio, 2))

    # 거래량 없는 반등이 없어도, 전체 3일 평균 거래량이 낮으면 허용
    avg_vol_3d = sum(vols_3d) / 3
    if not low_vol_rally and avg_vol_3d / (vol_ma20 + 1e-9) < 0.8:
        low_vol_rally = True
        vol_ratio_on_up = round(avg_vol_3d / (vol_ma20 + 1e-9), 2)

    if not low_vol_rally:
        return None

    return {
        "rsi_high":         round(rsi_high, 1),
        "rsi_now":          round(rsi_now, 1),
        "macd_cross_days":  macd_cross_day,
        "hist_shrink_days": hist_shrink_days,
        "hist_latest":      round(hist_l[-1], 4),
        "vol_ratio_on_up":  vol_ratio_on_up,
    }


# ═══════════════════════════════════════════════════════════════
# 2~3일 복합 추세 시그널
# ═══════════════════════════════════════════════════════════════

def detect_multi_day_trend(close: pd.Series, high: pd.Series,
                           low: pd.Series, volume: pd.Series) -> Optional[dict]:
    """
    2~3일 복합 추세 시그널 탐지.
    가격 방향 + RSI 개선/악화 + MACD 히스토그램 방향 + 거래량 뒷받침
    4개 중 3개 이상 일치 시 시그널 반환.
    """
    if len(close) < 30:
        return None

    closes = [float(c) for c in close.iloc[-4:]]  # 4일분 (3번 비교)
    if len(closes) < 4:
        return None

    # ── 상승 방향 체크 ──
    up_days = sum(1 for i in range(1, 4) if closes[i] > closes[i - 1])
    dn_days = sum(1 for i in range(1, 4) if closes[i] < closes[i - 1])
    price_up = up_days >= 2
    price_dn = dn_days >= 2

    if not price_up and not price_dn:
        return None  # 방향 불분명

    # RSI 3일 전 vs 현재
    rsi_vals = _rsi_series(close, lookback=4)
    if len(rsi_vals) < 4:
        return None
    rsi_3d_ago = rsi_vals[-4]
    rsi_now    = rsi_vals[-1]
    rsi_improving = rsi_now > rsi_3d_ago and rsi_now < 60
    rsi_worsening = rsi_now < rsi_3d_ago and rsi_now > 40

    # MACD 히스토그램 3일 방향
    _, _, hist_l = _macd_series(close, lookback=4)
    if len(hist_l) < 3:
        return None
    hist_3d = hist_l[-3:]
    macd_improving = hist_3d[-1] > hist_3d[-2] > hist_3d[-3]   # 연속 증가
    macd_worsening = hist_3d[-1] < hist_3d[-2] < hist_3d[-3]   # 연속 감소

    # 거래량: 상승일 vs 하락일 평균 비교
    vols = [float(v) for v in volume.iloc[-3:]]
    up_vols, dn_vols = [], []
    for i in range(1, 4):
        if closes[i] > closes[i - 1]:
            up_vols.append(vols[i - 1])
        elif closes[i] < closes[i - 1]:
            dn_vols.append(vols[i - 1])
    avg_up = sum(up_vols) / len(up_vols) if up_vols else 0
    avg_dn = sum(dn_vols) / len(dn_vols) if dn_vols else 0
    vol_buy_dominant  = avg_up > avg_dn * 1.0 if avg_dn > 0 else bool(up_vols)
    vol_sell_dominant = avg_dn > avg_up * 1.0 if avg_up > 0 else bool(dn_vols)

    # ── 상승 추세 형성 판정 ──
    if price_up:
        conds = [price_up, rsi_improving, macd_improving, vol_buy_dominant]
        met = sum(conds)
        if met >= 3:
            return {
                "direction":      "up",
                "price_trend":    price_up,
                "rsi_improving":  rsi_improving,
                "rsi_3d_ago":     round(rsi_3d_ago, 1),
                "rsi_now":        round(rsi_now, 1),
                "macd_improving": macd_improving,
                "hist_3d":        [round(h, 4) for h in hist_3d],
                "vol_confirmed":  vol_buy_dominant,
                "conditions_met": met,
                "strength":       "strong" if met == 4 else "moderate",
            }

    # ── 하락 추세 형성 판정 ──
    if price_dn:
        conds = [price_dn, rsi_worsening, macd_worsening, vol_sell_dominant]
        met = sum(conds)
        if met >= 3:
            return {
                "direction":      "down",
                "price_trend":    price_dn,
                "rsi_improving":  rsi_worsening,  # 역방향이므로 "악화"
                "rsi_3d_ago":     round(rsi_3d_ago, 1),
                "rsi_now":        round(rsi_now, 1),
                "macd_improving": macd_worsening,
                "hist_3d":        [round(h, 4) for h in hist_3d],
                "vol_confirmed":  vol_sell_dominant,
                "conditions_met": met,
                "strength":       "strong" if met == 4 else "moderate",
            }

    return None


# ═══════════════════════════════════════════════════════════════
# 상관관계 분석 (섹터 로테이션 감지)
# ═══════════════════════════════════════════════════════════════

def compute_correlations(candidates: list, period: str = "3mo") -> dict:
    """
    매수/매도 후보 종목 vs 벤치마크(KOSPI, S&P500, 환율, 유가)의
    30일 수익률 상관계수를 계산한다.
    디커플링 감지: 최근 10일 vs 이전 20일 상관관계 급변.
    """
    import yfinance as yf

    benchmarks = {
        "KOSPI":  "^KS11",
        "S&P500": "^GSPC",
        "USD/KRW": "KRW=X",
        "WTI":    "CL=F",
    }

    # 벤치마크 수익률 수집
    bm_returns = {}
    try:
        bm_tickers = list(benchmarks.values())
        bm_data = yf.download(bm_tickers, period=period, auto_adjust=True,
                              progress=False, threads=True)
        if "Close" in bm_data.columns or hasattr(bm_data.columns, 'levels'):
            for name, ticker in benchmarks.items():
                try:
                    if len(bm_tickers) == 1:
                        closes = bm_data["Close"]
                    else:
                        closes = bm_data["Close"][ticker]
                    ret = closes.pct_change().dropna()
                    if len(ret) >= 20:
                        bm_returns[name] = ret
                except Exception:
                    continue
    except Exception:
        return {}

    if not bm_returns:
        return {}

    # 종목별 상관관계 계산
    result = {}
    tickers_done = set()
    for r in candidates:
        ticker = r["ticker"]
        if ticker in tickers_done:
            continue
        tickers_done.add(ticker)
        try:
            df = yf.download(ticker, period=period, auto_adjust=True, progress=False)
            if df.empty or len(df) < 20:
                continue
            stock_ret = df["Close"].pct_change().dropna()
            if hasattr(stock_ret, 'columns'):
                stock_ret = stock_ret.iloc[:, 0]

            corrs = {}
            decoupling = []
            for bm_name, bm_ret in bm_returns.items():
                # 공통 인덱스
                common = stock_ret.index.intersection(bm_ret.index)
                if len(common) < 20:
                    continue
                s = stock_ret.loc[common]
                b = bm_ret.loc[common]

                # 전체 30일 상관계수
                corr_30 = float(s.tail(30).corr(b.tail(30)))
                corrs[bm_name] = round(corr_30, 2)

                # 디커플링 감지: 최근 10일 vs 이전 20일
                if len(common) >= 30:
                    corr_recent = float(s.tail(10).corr(b.tail(10)))
                    corr_prev   = float(s.iloc[-30:-10].corr(b.iloc[-30:-10]))
                    diff = corr_recent - corr_prev
                    if abs(diff) >= 0.4:  # 상관관계 급변
                        direction = "디커플링↑" if diff > 0 else "디커플링↓"
                        decoupling.append(f"{bm_name}({direction},{diff:+.2f})")

            if corrs:
                result[ticker] = {
                    "name": r["name"],
                    "corrs": corrs,
                    "decoupling": decoupling,
                }
        except Exception:
            continue

    return result


# ═══════════════════════════════════════════════════════════════
# 종합 스코어링
# ═══════════════════════════════════════════════════════════════

def _lerp(x: float, bp: list, sc: list) -> float:
    """bp(오름차순 breakpoints)와 sc(대응 점수) 사이를 선형 보간."""
    if x <= bp[0]:  return float(sc[0])
    if x >= bp[-1]: return float(sc[-1])
    from bisect import bisect_right
    i = bisect_right(bp, x) - 1
    t = (x - bp[i]) / (bp[i + 1] - bp[i])
    return sc[i] + t * (sc[i + 1] - sc[i])


_REGIME_WEIGHTS = {
    "강세":     {"rsi": 0.7, "stoch": 0.7, "macd": 1.3, "ma_align": 1.3, "ma5v20": 1.0,
                 "mom5": 1.0, "adx": 1.5, "macd_adx": 1.3, "obv": 1.0, "pos52w": 1.0},
    "중립":     {"rsi": 1.0, "stoch": 1.0, "macd": 1.0, "ma_align": 1.0, "ma5v20": 1.0,
                 "mom5": 1.0, "adx": 1.0, "macd_adx": 1.0, "obv": 1.0, "pos52w": 1.0},
    "약세":     {"rsi": 1.0, "stoch": 1.0, "macd": 0.8, "ma_align": 1.0, "ma5v20": 1.0,
                 "mom5": 1.0, "adx": 1.0, "macd_adx": 0.8, "obv": 1.3, "pos52w": 1.3},
    "극도약세": {"rsi": 1.3, "stoch": 1.3, "macd": 0.7, "ma_align": 0.7, "ma5v20": 1.0,
                 "mom5": 1.0, "adx": 0.5, "macd_adx": 0.5, "obv": 1.3, "pos52w": 1.3},
}


def score_technical(rsi, macd_hist, price, ma5, ma20, ma60, mom5,
                    stoch_k, adx, plus_di, minus_di, obv_trend, pos_52w,
                    atr_pct=0.0, regime="중립",
                    return_breakdown=False):
    """
    기술적 종합 점수 -100 ~ +100 (연속값)
    regime: 시장 국면 (강세/중립/약세/극도약세) — 지표별 가중치 조절
    return_breakdown: True이면 지표별 기여도 dict 반환
    """
    _atr_norm = max(atr_pct, 0.5)
    w = _REGIME_WEIGHTS.get(regime, _REGIME_WEIGHTS["중립"])
    bd = {}  # breakdown

    # RSI (±35)
    _rsi = _lerp(rsi, [0, 20, 30, 40, 50, 60, 70, 80, 100],
                      [35, 35, 20, 8,  0, -8, -20, -35, -35])
    bd["RSI"] = round(_rsi * w["rsi"], 1)

    # 스토캐스틱 (±10)
    _stoch = _lerp(stoch_k, [0, 20, 30, 50, 70, 80, 100],
                             [10, 10, 5,  0, -5, -10, -10])
    bd["Stoch"] = round(_stoch * w["stoch"], 1)

    # MACD 히스토그램 (±15)
    macd_norm = macd_hist / (price * _atr_norm / 100) if price > 0 else macd_hist
    _macd = _lerp(macd_norm, [-1.0, -0.1, 0, 0.1, 1.0],
                              [-15,  -15,  0, 15,  15])
    bd["MACD"] = round(_macd * w["macd"], 1)

    # 이동평균 정배열 (±15)
    if ma20 and ma20 > 0:
        gap_pct = (price - ma20) / ma20 * 100
        gap_atr = gap_pct / _atr_norm
        _ma = _lerp(gap_atr, [-3, -1.2, 0, 1.2, 3],
                              [-15, -7,  0, 7,  15])
        if ma60 and ma60 > 0 and ma20 < ma60:
            _ma *= 0.7
    else:
        _ma = 0.0
    bd["MA정배열"] = round(_ma * w["ma_align"], 1)

    # MA5 vs MA20 (±8)
    if ma20 and ma20 > 0 and ma5:
        ma5_gap = (ma5 - ma20) / ma20 * 100
        ma5_atr = ma5_gap / _atr_norm
        _m5 = _lerp(ma5_atr, [-2, -0.6, 0, 0.6, 2],
                              [-8,  -4,  0, 4,   8])
    else:
        _m5 = 0.0
    bd["MA5v20"] = round(_m5 * w["ma5v20"], 1)

    # 5일 모멘텀 (±8)
    mom_atr = mom5 / _atr_norm
    _mom = _lerp(mom_atr, [-3, -1.5, -0.5, 0, 0.5, 1.5, 3],
                           [-8,  -8,   -4,  0, 4,   8,   8])
    bd["모멘텀"] = round(_mom * w["mom5"], 1)

    # ADX 추세 강도 (±4)
    _adx_s = 0.0
    if adx > 25:
        trend_dir = 1 if plus_di > minus_di else -1
        _adx_s = min(adx - 25, 20) * 0.2 * trend_dir
    bd["ADX"] = round(_adx_s * w["adx"], 1)

    # ADX < 15 감쇠는 전체 합산 후 적용 (breakdown에는 개별 표기)
    _adx_damping = 0.8 if adx < 15 else 1.0

    # MACD+ADX 복합 (0~10)
    _madx = 0.0
    if adx > 25:
        _madx += 2
        if plus_di > minus_di:
            _madx += 3
    if macd_hist > 0:
        _madx += 5
    bd["MACD+ADX"] = round(_madx * w["macd_adx"], 1)

    # OBV 추세 (±5)
    _obv = _lerp(obv_trend, [-0.1, -0.05, 0, 0.05, 0.1],
                              [-5,   -5,    0, 5,    5])
    bd["OBV"] = round(_obv * w["obv"], 1)

    # 52주 위치 (±5)
    _52w = _lerp(pos_52w, [0, 15, 30, 50, 70, 85, 100],
                           [3,  3, -2,  0,  2,  5,  5])
    bd["52주"] = round(_52w * w["pos52w"], 1)

    # 합산
    s = sum(bd.values()) * _adx_damping
    total = round(max(-100.0, min(100.0, s)), 1)

    if return_breakdown:
        bd["total"] = total
        bd["regime"] = regime
        return bd
    return total


def score_fundamental(pe, pb, roe, margin, eps_growth) -> int:
    """
    펀더멘털 점수 –30 ~ +30
    가치주(저P/E·고ROE)에 보너스, 고평가·적자 주식에 패널티
    """
    s = 0

    # P/E 비율 (±12)
    if pe is not None and pe > 0:
        if   pe < 10:  s += 12
        elif pe < 15:  s +=  8
        elif pe < 20:  s +=  4
        elif pe < 30:  s +=  0
        elif pe < 50:  s -=  8
        else:          s -= 12

    # P/B 비율 (±8)
    if pb is not None and pb > 0:
        if   pb < 0.8: s += 8
        elif pb < 1.5: s += 4
        elif pb < 3.0: s += 0
        elif pb < 5.0: s -= 4
        else:          s -= 8

    # ROE (±6)
    if roe is not None:
        if   roe > 0.25: s += 6
        elif roe > 0.15: s += 4
        elif roe > 0.10: s += 2
        elif roe < 0:    s -= 6

    # 순이익률 (±4)
    if margin is not None:
        if   margin > 0.20: s += 4
        elif margin > 0.10: s += 2
        elif margin < 0:    s -= 4

    return max(-30, min(30, s))


def score_with_investor_weight(ticker: str, base_score: float) -> float:
    try:
        from investor_scorer import get_investor_score
        inv = get_investor_score(ticker.upper())
        bonus = 0
        if inv['is_pelosi_pick']:         bonus += inv['pelosi_score']
        if inv['is_ark_pick']:            bonus += inv['ark_score']
        if inv['is_korean_investor_pick']: bonus += inv['korean_investor_score']
        if inv['is_pelosi_pick'] and inv['is_ark_pick']:
            both_live = (inv.get('pelosi_source') == 'live'
                         and inv.get('ark_source') == 'live')
            bonus += 5 if both_live else 3
        return max(-100.0, min(100.0, base_score + bonus))
    except Exception:
        return base_score


def apply_regime_weights(all_results: dict, regime: str) -> int:
    """
    레짐 판정 후 전 종목의 기술점수를 국면별 가중치로 재계산한다.
    score_breakdown도 갱신한다. 갱신된 종목 수를 반환.
    """
    updated = 0
    for market, stocks in all_results.items():
        for r in stocks:
            bd = r.get("score_breakdown")
            if not bd or regime == bd.get("regime", "중립"):
                continue
            # 원시 지표값으로 재계산
            new_bd = score_technical(
                r["rsi"], r["macd_hist"], r["price"],
                r["ma5"], r["ma20"], r["ma60"], r["mom5"],
                r["stoch_k"], r["adx"], r["plus_di"], r["minus_di"],
                r["obv_trend"], r["pos_52w"],
                atr_pct=r.get("atr_pct", 0),
                regime=regime, return_breakdown=True,
            )
            # 기존 점수와의 차이를 score에 반영
            old_tech = bd.get("total", 0)
            new_tech = new_bd.get("total", 0)
            diff = new_tech - old_tech
            r["score"] = round(r["score"] + diff, 1)
            r["score_breakdown"] = new_bd
            updated += 1
    return updated


# ═══════════════════════════════════════════════════════════════
# 거시 레짐 평가 — 시장 국면에 따라 전 종목 점수 보정
# ═══════════════════════════════════════════════════════════════

def compute_macro_regime(macro: dict, fear_greed: dict, sector_flows: dict) -> dict:
    """
    VIX · Fear&Greed · 주요 지수 5일 모멘텀 기반으로 현재 시장 국면을 평가.

    Returns:
        regime          : "강세" | "중립" | "약세" | "극도약세"
        regime_score    : 내부 점수 (양수=강세, 음수=약세)
        score_adjustment: 전 종목 점수에 가감할 값 (약세 → 음수)
        reasons         : 판단 근거 리스트
    """
    score = 0
    reasons = []

    # ── VIX ──────────────────────────────────────────────────────
    vix = macro.get("VIX", {}).get("현재", 20)
    if vix < 15:
        score += 10; reasons.append(f"VIX {vix:.1f} (저변동·강세)")
    elif vix < 20:
        score += 4;  reasons.append(f"VIX {vix:.1f} (정상)")
    elif vix < 25:
        score -= 6;  reasons.append(f"VIX {vix:.1f} (경계)")
    elif vix < 30:
        score -= 12; reasons.append(f"VIX {vix:.1f} (위험)")
    else:
        score -= 20; reasons.append(f"VIX {vix:.1f} (극도위험)")

    # ── Fear & Greed ─────────────────────────────────────────────
    fg = fear_greed.get("지수", 50) if fear_greed else 50
    if fg < 25:
        score += 6;  reasons.append(f"F&G {fg} (극도공포→역발상매수)")
    elif fg < 40:
        score -= 4;  reasons.append(f"F&G {fg} (공포)")
    elif fg > 75:
        score -= 5;  reasons.append(f"F&G {fg} (극도탐욕→과열)")
    elif fg > 60:
        score += 2;  reasons.append(f"F&G {fg} (탐욕·주의)")

    # ── 주요 지수 5일 등락 ────────────────────────────────────────
    sp500_chg = macro.get("S&P500", {}).get("등락(%)", 0)
    kospi_chg = macro.get("KOSPI",  {}).get("등락(%)", 0)

    if sp500_chg < -5:
        score -= 12; reasons.append(f"S&P500 {sp500_chg:+.1f}% (급락)")
    elif sp500_chg < -2:
        score -= 6;  reasons.append(f"S&P500 {sp500_chg:+.1f}% (하락)")
    elif sp500_chg > 3:
        score += 5;  reasons.append(f"S&P500 {sp500_chg:+.1f}% (강세)")

    if kospi_chg < -3:
        score -= 6;  reasons.append(f"KOSPI {kospi_chg:+.1f}% (급락)")
    elif kospi_chg < -1:
        score -= 3;  reasons.append(f"KOSPI {kospi_chg:+.1f}% (하락)")
    elif kospi_chg > 2:
        score += 3;  reasons.append(f"KOSPI {kospi_chg:+.1f}% (강세)")

    # ── 레짐 판단 및 점수 보정 ────────────────────────────────────
    if score >= 10:
        regime = "강세";    adj = +5
    elif score >= 2:
        regime = "중립";    adj = 0
    elif score >= -8:
        regime = "약세";    adj = -8
    else:
        regime = "극도약세"; adj = -15

    return {
        "regime":          regime,
        "regime_score":    score,
        "score_adjustment": adj,
        "reasons":         reasons,
    }


# ═══════════════════════════════════════════════════════════════
# 단일 종목 고속 스크리닝 (신규 지표 포함)
# ═══════════════════════════════════════════════════════════════
_last_pool_sizes: dict = {}  # run_screening이 설정 → 리포트에서 "유효/풀" 표시용
_kr_prefetch:    dict = {}  # {ticker: DataFrame} — 국내주 일괄 사전다운로드 결과

# US 개별 호출용 세마포어 (KR 종목은 batch download로 대체)
_YF_SEM = threading.Semaphore(6)


def _prefetch_kr_data(tickers: list, chunk_size: int = 150) -> dict:
    """
    Korean stocks (KOSPI + KOSDAQ) 전종목을 청크별 yf.download()로 일괄 수집.
    개별 Ticker.history() 대신 사용해 Yahoo Finance 레이트리밋을 원천 방지.
    반환: {ticker: DataFrame(OHLCV)}  — 65거래일 미만이거나 빈 경우 제외.
    """
    result: dict = {}
    chunks = [tickers[i:i + chunk_size] for i in range(0, len(tickers), chunk_size)]

    for idx, chunk in enumerate(chunks, 1):
        print(f"    KR 일괄 다운로드 {idx}/{len(chunks)} ({len(chunk)}개)...")
        try:
            raw = yf.download(
                " ".join(chunk),
                period="1y",
                auto_adjust=False,
                group_by="ticker",
                progress=False,
                timeout=60,
                threads=True,
            )
            if raw is None or raw.empty:
                continue

            for t in chunk:
                try:
                    df = raw[t] if len(chunk) > 1 else raw
                    if df is None or df.empty:
                        continue
                    df = df.dropna(how="all")
                    if len(df) >= 65:
                        result[t] = df
                except (KeyError, TypeError):
                    pass
        except Exception as e:
            print(f"    ⚠️ chunk {idx} 다운로드 실패: {e}")

    return result

def screen_one(market: str, name: str, ticker: str) -> Optional[dict]:
    try:
        is_kr = ticker.endswith(".KS") or ticker.endswith(".KQ")
        df = None

        if is_kr and ticker in _kr_prefetch:
            # 일괄 사전다운로드 결과 사용 (레이트리밋 없음)
            df = _kr_prefetch[ticker].copy()
        else:
            # US 주식 또는 prefetch 누락 종목: 개별 요청 (재시도 1회)
            for attempt in range(2 if is_kr else 1):
                with _YF_SEM:
                    df = yf.Ticker(ticker).history(period="1y", auto_adjust=False, timeout=15)
                if df is not None and not df.empty and len(df) >= 65:
                    break
                if attempt == 0 and is_kr:
                    time.sleep(1.5)

        if df is None or df.empty or len(df) < 65:
            return None
        # 12개월 요청에서 130 거래일 미만 → 약 6개월 이내 상장 추정
        is_recently_listed = len(df) < 130

        # yfinance Ticker.history() 는 단층 컬럼 반환 — MultiIndex 처리 불필요
        # 불필요 컬럼 제거 (Dividends, Stock Splits 등)
        for col in ("Dividends", "Stock Splits", "Capital Gains", "Adj Close"):
            if col in df.columns:
                df = df.drop(columns=[col])

        # ── 장 중/마감 후 오늘 행 처리 ──────────────────────────────
        # 장 마감 후(KR 15:30, US 16:00): 오늘 종가를 확정가로 사용
        # 장 중: 오늘 행 분리 → 전일 확정 종가 기반, 장중가는 별도 필드
        today_price: Optional[float] = None
        today_chg:   Optional[float] = None
        if len(df) > 0 and df.index[-1].date() == datetime.date.today():
            now_hour = datetime.datetime.now().hour
            is_kr = ticker.endswith(".KS") or ticker.endswith(".KQ")
            market_closed = (is_kr and now_hour >= 16) or (not is_kr and now_hour >= 6)
            # 장 마감 후 → 오늘 종가를 확정가로 유지 (행 제거 안 함)
            if not market_closed:
                # 장 중 → 오늘 미확정 행 분리
                today_raw = float(df["Close"].iloc[-1])
                df = df.iloc[:-1]
                if len(df) >= 1 and not (today_raw != today_raw):
                    prev_close = float(df["Close"].iloc[-1])
                    today_price = today_raw
                    today_chg   = round((today_raw - prev_close) / prev_close * 100, 2)

        # ── Volume=0 placeholder 행 제거 (장 미개시/yfinance 지연 데이터) ──
        while len(df) > 0:
            last = df.iloc[-1]
            vol = float(last.get("Volume", 1))
            hi  = float(last.get("High", 1))
            lo  = float(last.get("Low", 1))
            op  = float(last.get("Open", 1))
            # OHLC 전부 0이거나, 거래량 0 + flat(고=저=시 동일) placeholder
            if vol == 0 and (hi == 0 or hi == lo == op):
                df = df.iloc[:-1]
            else:
                break

        df = data_cleaner.clean(df, ticker)
        if df is None:
            return None

        close  = df["Close"]
        high   = df["High"]
        low    = df["Low"]
        volume = df["Volume"] if "Volume" in df.columns else pd.Series([0]*len(df))

        price = float(close.iloc[-1])   # 전일 확정 종가
        price_date = df.index[-1].strftime("%m/%d")  # 기준가 날짜
        prev  = float(close.iloc[-2])
        chg   = round((price - prev) / prev * 100, 2)

        # ── 기존 지표 ──
        rsi               = _rsi(close)
        macd_line, _, macd_hist = _macd(close)
        ma5, ma20, ma60   = _mas(close)
        mom5              = _mom(close, 5)
        bb_up, bb_dn, bb_pct = _bb(close)

        # ── 신규 지표 ──
        atr_val             = _atr(high, low, close)
        atr_pct             = round(atr_val / price * 100, 2) if price > 0 else 0.0
        stoch_k, stoch_d    = _stochastic(high, low, close)
        adx_val, plus_di, minus_di = _adx(high, low, close)
        lbr_fast, lbr_slow, lbr_slow_rising, lbr_trending = _lbr_3_10(close)
        obv                 = _obv_trend(close, volume)
        pos_52w             = _week52_pos(close)

        vol_avg   = float(volume.rolling(20).mean().iloc[-1])
        vol_cur   = float(volume.iloc[-1])
        vol_ratio = round(vol_cur / (vol_avg + 1e-9), 2)

        # 거래량 0 종목: 거래정지 또는 데이터 이상 → 점수 대폭 차감
        trading_halted = vol_cur == 0 and vol_avg > 0

        # MACD+ADX 복합 추세 점수 (0~10) — 리포트 표시용 별도 계산
        _ma_score = 0
        if adx_val > 25:
            _ma_score += 2
            if plus_di > minus_di:
                _ma_score += 3
        if macd_hist > 0:
            _ma_score += 5
        macd_adx_score = _ma_score

        # 기술적 점수 (ATR 정규화 적용)
        tech_score = score_technical(
            rsi, macd_hist, price, ma5, ma20, ma60, mom5,
            stoch_k, adx_val, plus_di, minus_di, obv, pos_52w,
            atr_pct=atr_pct,
        )
        # Feature Importance breakdown (레짐 무관 — 레짐 보정은 main에서)
        _bd = score_technical(
            rsi, macd_hist, price, ma5, ma20, ma60, mom5,
            stoch_k, adx_val, plus_di, minus_di, obv, pos_52w,
            atr_pct=atr_pct, return_breakdown=True,
        )
        # 거래정지 감점
        if trading_halted:
            tech_score -= 50

        # 투자자 가중치
        score = score_with_investor_weight(ticker, tech_score)

        # 반전 시그널 탐지
        reversal = detect_reversal_signal(close, high, low, volume)
        bearish  = detect_bearish_signal(close, high, low, volume)
        multi_day = detect_multi_day_trend(close, high, low, volume)

        # ── LBR 3/10 추세 판정 (리포트 표시용, 스크리닝 제외하지 않음) ──
        # lbr_trending 값은 리포트의 "추세 매수 시그널" 섹션에서 활용

        # ── 주봉 20주 이동평균선 우상향 판정 (리포트 표시용) ──────
        weekly_ma20_rising = True  # 기본값: 통과 (데이터 부족 시)
        if not is_recently_listed and len(df) >= 100:  # 약 20주(100 거래일) 이상
            try:
                wk = df.resample("W-FRI").agg({
                    "Open": "first", "High": "max", "Low": "min",
                    "Close": "last", "Volume": "sum",
                }).dropna()
                if len(wk) >= 22:  # 20주 MA + 기울기 판정용 2주 여유
                    wk_ma20 = wk["Close"].rolling(20).mean()
                    # 최근 3주간 MA20이 연속 상승하면 '우상향'
                    recent_ma = wk_ma20.dropna().iloc[-3:]
                    if len(recent_ma) >= 3:
                        weekly_ma20_rising = (
                            recent_ma.iloc[-1] > recent_ma.iloc[-2] > recent_ma.iloc[-3]
                        )
                    else:
                        weekly_ma20_rising = True
            except Exception:
                weekly_ma20_rising = True  # 리샘플 실패 시 판정 생략

        return {
            "market": market, "name": name, "ticker": ticker,
            "price": round(price, 2), "price_date": price_date, "chg": chg,
            "today_price": round(today_price, 2) if today_price is not None and today_price == today_price else None,
            "today_chg":   round(today_chg,   2) if today_chg   is not None and today_chg == today_chg else None,
            # 기존
            "rsi": round(rsi, 1), "macd_hist": round(macd_hist, 4),
            "ma5": round(ma5, 2), "ma20": round(ma20, 2), "ma60": round(ma60, 2),
            "bb_up": bb_up, "bb_dn": bb_dn, "bb_pct": round(bb_pct, 1),
            "mom5": round(mom5, 2), "vol_ratio": vol_ratio,
            # 신규
            "atr": round(atr_val, 2), "atr_pct": atr_pct,
            "stoch_k": round(stoch_k, 1), "stoch_d": round(stoch_d, 1),
            "adx": round(adx_val, 1), "plus_di": round(plus_di, 1), "minus_di": round(minus_di, 1),
            "lbr_fast": round(lbr_fast, 4), "lbr_slow": round(lbr_slow, 4),
            "lbr_trending": lbr_trending,
            "obv_trend": obv, "pos_52w": pos_52w,
            "macd_adx_score": macd_adx_score,   # 0~10: 추세(ADX)+방향(+DI)+타이밍(MACD) 복합
            "score": score,
            "fund": {},  # 펀더멘털은 Phase 2에서 채움
            "is_recently_listed": is_recently_listed,
            "weekly_ma20_rising": bool(weekly_ma20_rising),
            "reversal_signal": reversal,
            "bearish_signal": bearish,
            "multi_day_trend": multi_day,
            "score_breakdown": _bd,
        }
    except Exception:
        return None


# ═══════════════════════════════════════════════════════════════
# Phase 2: 상위 후보 펀더멘털 보강 (주 1회 캐시)
# ═══════════════════════════════════════════════════════════════

_FUND_CACHE: dict = {}           # {ticker: {"cached_at": ISO, "data": {...}}}
_FUND_CACHE_LOCK = threading.Lock()
_FUND_CACHE_DAYS = 3             # 3일 내 캐시 유효 (적시 반영)


def _fund_cache_path() -> str:
    cache_dir = os.path.join(BASE_DIR, "cache")
    os.makedirs(cache_dir, exist_ok=True)
    return os.path.join(cache_dir, "fundamentals.json")


def _load_fundamental_cache() -> None:
    """fundamentals.json → 모듈 레벨 캐시 로드 (1회만)."""
    global _FUND_CACHE
    path = _fund_cache_path()
    try:
        if os.path.exists(path):
            with open(path, encoding="utf-8") as f:
                _FUND_CACHE = json.load(f)
    except Exception:
        _FUND_CACHE = {}


def _save_fundamental_cache() -> None:
    """모듈 캐시 → fundamentals.json 저장."""
    path = _fund_cache_path()
    try:
        with _FUND_CACHE_LOCK:
            snapshot = dict(_FUND_CACHE)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(snapshot, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"  ⚠️ 펀더멘털 캐시 저장 실패: {e}")


def _fetch_fund_one(r: dict) -> dict:
    """yfinance .info에서 펀더멘털 수집 (7일 캐시 우선)."""
    ticker = r["ticker"]

    # ── 캐시 유효성 확인 ─────────────────────────────────────────
    with _FUND_CACHE_LOCK:
        entry = _FUND_CACHE.get(ticker)
    if entry:
        try:
            age_days = (
                datetime.datetime.now()
                - datetime.datetime.fromisoformat(entry["cached_at"])
            ).total_seconds() / 86400
            if age_days < _FUND_CACHE_DAYS:
                return {**r, "fund": entry["data"]}
        except Exception:
            pass

    # ── 캐시 없거나 만료 → yfinance 수집 ─────────────────────────
    try:
        info = yf.Ticker(ticker).info
        pe      = info.get("trailingPE") or info.get("forwardPE")
        pb      = info.get("priceToBook")
        roe     = info.get("returnOnEquity")       # 소수점 (0.15 = 15%)
        margin  = info.get("profitMargins")
        eps_g   = info.get("earningsGrowth")
        de      = info.get("debtToEquity")
        div_y   = info.get("dividendYield")
        sector  = info.get("sector", "")

        fund_s = score_fundamental(pe, pb, roe, margin, eps_g)

        fund_data = {
            "pe": round(pe, 1) if pe else None,
            "pb": round(pb, 2) if pb else None,
            "roe_pct": round(roe * 100, 1) if roe else None,
            "margin_pct": round(margin * 100, 1) if margin else None,
            "eps_growth_pct": round(eps_g * 100, 1) if eps_g else None,
            "de_ratio": round(de, 1) if de else None,
            "div_yield_pct": round(div_y * 100, 2) if div_y else None,
            "sector": sector,
            "fund_score": fund_s,
        }

        with _FUND_CACHE_LOCK:
            _FUND_CACHE[ticker] = {
                "cached_at": datetime.datetime.now().isoformat(),
                "data": fund_data,
            }

        return {**r, "fund": fund_data}
    except Exception:
        return r


def enrich_with_fundamentals(stocks: list) -> list:
    """상위 종목 대상 병렬 펀더멘털 수집 (7일 캐시 활용)."""
    if not stocks:
        return stocks
    _load_fundamental_cache()
    cached_cnt = sum(
        1 for r in stocks
        if r["ticker"] in _FUND_CACHE
        and (datetime.datetime.now() - datetime.datetime.fromisoformat(
            _FUND_CACHE[r["ticker"]].get("cached_at", "2000-01-01")
        )).total_seconds() / 86400 < _FUND_CACHE_DAYS
    )
    print(f"  📊 펀더멘털 수집 ({len(stocks)}개, 캐시 {cached_cnt}개 재사용)...")
    enriched = []
    with ThreadPoolExecutor(max_workers=6) as ex:
        futs = {ex.submit(_fetch_fund_one, r): r for r in stocks}
        for fut in as_completed(futs):
            result = fut.result()
            # 펀더멘털 점수를 종합 점수에 반영
            fund_s = result.get("fund", {}).get("fund_score", 0)
            result["score"] = max(-100, min(100, result["score"] + fund_s))
            enriched.append(result)
    _save_fundamental_cache()
    return enriched


# ═══════════════════════════════════════════════════════════════
# 스크리닝 결과 일별 캐시 (yfinance 데이터 하루 1회만 수집)
# ═══════════════════════════════════════════════════════════════

def _clean_old_screening_caches(max_days: int = 3) -> None:
    """screening_YYYYMMDD.json 파일 중 max_days 이상 된 것 자동 삭제."""
    cache_dir = os.path.join(BASE_DIR, "cache")
    if not os.path.exists(cache_dir):
        return
    cutoff = datetime.datetime.now() - datetime.timedelta(days=max_days)
    for fname in os.listdir(cache_dir):
        if not fname.startswith("screening_") or not fname.endswith(".json"):
            continue
        fpath = os.path.join(cache_dir, fname)
        try:
            mtime = datetime.datetime.fromtimestamp(os.path.getmtime(fpath))
            if mtime < cutoff:
                os.remove(fpath)
        except Exception:
            pass


def _screening_cache_path() -> str:
    today = datetime.datetime.now().strftime("%Y%m%d")
    cache_dir = os.path.join(BASE_DIR, "cache")
    os.makedirs(cache_dir, exist_ok=True)
    return os.path.join(cache_dir, f"screening_{today}.json")


def _load_screening_cache() -> dict:
    """오늘 날짜의 스크리닝 캐시 로드. 없으면 빈 dict 반환."""
    path = _screening_cache_path()
    try:
        if os.path.exists(path):
            with open(path, encoding="utf-8") as f:
                data = json.load(f)
            print(f"  ✓ 오늘 스크리닝 캐시 사용 ({path})")
            return data
    except Exception:
        pass
    return {}


def _save_screening_cache(results: dict):
    """스크리닝 결과를 오늘 날짜 파일로 저장."""
    path = _screening_cache_path()
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(results, f, ensure_ascii=False, indent=2)
        print(f"  ✓ 스크리닝 결과 캐시 저장 ({path})")
    except Exception as e:
        print(f"  ⚠️ 스크리닝 캐시 저장 실패: {e}")


# ═══════════════════════════════════════════════════════════════
# 전체 유니버스 스크리닝
# ═══════════════════════════════════════════════════════════════

def run_screening() -> dict:
    results = {"KOSPI": [], "KOSDAQ": [], "US": [], "IPO": []}

    # 증권사 추천 Pool 로드 (캐시 우선)
    broker_picks = get_broker_picks()
    if broker_picks:
        print(f"  📋 증권사 추천 Pool: {len(broker_picks)}개 편입")
        broker_kospi  = {p["name"]: p["ticker"] for p in broker_picks if p["ticker"].endswith(".KS")}
        broker_kosdaq = {p["name"]: p["ticker"] for p in broker_picks if p["ticker"].endswith(".KQ")}
        broker_us     = {p["name"]: p["ticker"] for p in broker_picks if not p["ticker"].endswith((".KS", ".KQ"))}
    else:
        broker_kospi = broker_kosdaq = broker_us = {}

    kospi_pool, kosdaq_pool = get_kr_pools()  # KOSPI200 + KOSDAQ150 동적 로드

    # 증권사 추천 종목 Pool에 병합 (중복 티커 제외)
    for pool, bp in [(kospi_pool, broker_kospi), (kosdaq_pool, broker_kosdaq)]:
        existing = set(pool.values())
        for n, t in bp.items():
            if t not in existing:
                pool[n] = t

    us_pool = dict(US_POOL)
    existing_us = set(us_pool.values())
    for n, t in broker_us.items():
        if t not in existing_us:
            us_pool[n] = t

    # ── 국내주 일괄 사전 다운로드 (yf.download batch → 레이트리밋 원천 방지) ──
    all_kr_tickers = list(kospi_pool.values()) + list(kosdaq_pool.values())
    print(f"\n  📥 국내주 일괄 사전 다운로드 ({len(all_kr_tickers)}개)...")
    global _kr_prefetch
    _kr_prefetch = _prefetch_kr_data(all_kr_tickers)
    print(f"    ✓ 사전 다운로드 완료: {len(_kr_prefetch)}/{len(all_kr_tickers)}개 성공")

    pool_sizes: dict = {}
    for market, pool, workers in [
        ("KOSPI",  kospi_pool,  5),
        ("KOSDAQ", kosdaq_pool, 4),
        ("US",     us_pool,     6),
    ]:
        pool_sizes[market] = len(pool)
        print(f"  스크리닝: {market} ({len(pool)}개, {workers}스레드)...")
        tasks = [(market, n, t) for n, t in pool.items()]
        with ThreadPoolExecutor(max_workers=workers) as ex:
            futs = {ex.submit(screen_one, m, n, t): (m, n, t) for m, n, t in tasks}
            for fut in as_completed(futs):
                r = fut.result()
                if r:
                    results[market].append(r)
        results[market].sort(key=lambda x: x["score"], reverse=True)
        valid = len(results[market])
        rate = valid / pool_sizes[market] * 100 if pool_sizes[market] else 0
        print(f"    ✓ {market} 유효 {valid}/{pool_sizes[market]}개 ({rate:.0f}%)")

    excluded = data_cleaner.get_excluded_count()
    if excluded:
        print(f"  🗑️  데이터 정제 제외: {excluded}개 (logs/excluded_*.log 참조)")

    # ── IPO 풀: FDR 자동 탐지 + 휴리스틱 + JSON 워치리스트 ─────────────────
    # IPO는 코스피/코스닥 풀과 완전 분리 — 별도 스크리닝 + 별도 추천 슬롯
    ipo_seen: set = set()

    # 방법0: FinanceDataReader KRX-DESC ListingDate 기반 자동 탐지 (가장 정확)
    fdr_ipo_pool = get_recent_kr_ipos_auto(days=180)
    # KOSPI/KOSDAQ 풀에 이미 있는 종목은 제외 (중복 방지)
    all_screened = set()
    for mkt in ("KOSPI", "KOSDAQ", "US"):
        for r in results[mkt]:
            all_screened.add(r["ticker"])
    fdr_ipo_pool = {n: t for n, t in fdr_ipo_pool.items()
                    if t not in all_screened and t not in DELIST_BLACKLIST and t not in SELL_POOL}
    if fdr_ipo_pool:
        print(f"  스크리닝: IPO-FDR ({len(fdr_ipo_pool)}개 — 최근 6개월 KRX 신규상장)...")
        fdr_tasks = []
        for n, t in fdr_ipo_pool.items():
            mkt = "KOSPI" if t.endswith(".KS") else "KOSDAQ"
            fdr_tasks.append((mkt, n, t))
        with ThreadPoolExecutor(max_workers=6) as ex:
            futs = {ex.submit(screen_one, m, n, t): (m, n, t) for m, n, t in fdr_tasks}
            for fut in as_completed(futs):
                r = fut.result()
                if r and r["ticker"] not in ipo_seen:
                    r["is_ipo"] = True
                    r["investor_tags"] = "신규상장"
                    results["IPO"].append(r)
                    ipo_seen.add(r["ticker"])

    # 방법1: KOSPI/KOSDAQ 스크리닝 결과에서 130 거래일 미만 → 6개월 이내 상장 추정
    # FDR ListingDate 기준으로 교차 검증 — yfinance 데이터 누락에 의한 오탐 방지
    fdr_ipo_tickers = set(fdr_ipo_pool.values()) | set(ipo_seen)
    for mkt in ("KOSPI", "KOSDAQ"):
        for r in results[mkt]:
            if (r.get("is_recently_listed", False)
                    and r["ticker"] not in ipo_seen
                    and r["ticker"] in fdr_ipo_tickers):
                ipo_copy = dict(r)
                ipo_copy["is_ipo"] = True
                ipo_copy["investor_tags"] = "신규상장"
                results["IPO"].append(ipo_copy)
                ipo_seen.add(r["ticker"])

    # 방법2: universe_ipo_watchlist.json (수동 등록, 미국 IPO 포함)
    exclude_ipo = set(SELL_POOL.keys()) | DELIST_BLACKLIST | ipo_seen
    watchlist_pool = {n: t for n, t in get_recent_ipos(days=180).items()
                      if t not in exclude_ipo}
    if watchlist_pool:
        print(f"  스크리닝: IPO 워치리스트 ({len(watchlist_pool)}개)...")
        wl_tasks = []
        for n, t in watchlist_pool.items():
            mkt = "KOSPI" if t.endswith(".KS") else ("KOSDAQ" if t.endswith(".KQ") else "US")
            wl_tasks.append((mkt, n, t))
        with ThreadPoolExecutor(max_workers=6) as ex:
            futs = {ex.submit(screen_one, m, n, t): (m, n, t) for m, n, t in wl_tasks}
            for fut in as_completed(futs):
                r = fut.result()
                if r:
                    r["is_ipo"] = True
                    r["investor_tags"] = "신규상장"
                    results["IPO"].append(r)

    results["IPO"].sort(key=lambda x: x["score"], reverse=True)
    if results["IPO"]:
        print(f"    ✓ IPO (최근 6개월 신규상장) {len(results['IPO'])}개 탐지")

    global _last_pool_sizes
    _last_pool_sizes = pool_sizes
    return results


def validate_and_fix(results: dict) -> dict:
    """중복 가격 + 개별 이상 가격 탐지 및 재스크리닝"""
    fixed = {}
    for market, stocks in results.items():
        # 1) 중복 가격 탐지
        price_count: dict = {}
        for r in stocks:
            price_count[r["price"]] = price_count.get(r["price"], 0) + 1
        dup_prices  = {p for p, c in price_count.items() if c > 1}
        dup_tickers = {r["ticker"] for r in stocks if r["price"] in dup_prices}

        # 2) 개별 이상 가격 탐지: price <= 0 또는 한국 종목 100원 미만
        for r in stocks:
            p = r.get("price", 0)
            tk = r.get("ticker", "")
            if p <= 0:
                dup_tickers.add(tk)
            elif (tk.endswith(".KS") or tk.endswith(".KQ")) and p < 100:
                dup_tickers.add(tk)

        if not dup_tickers:
            fixed[market] = stocks
            continue

        rescan_count = len(dup_tickers)
        new_stocks = []
        for r in stocks:
            if r["ticker"] not in dup_tickers:
                new_stocks.append(r)
                continue
            fresh = screen_one(market, r["name"], r["ticker"])
            if fresh:
                new_stocks.append(fresh)
        new_stocks.sort(key=lambda x: x["score"], reverse=True)
        fixed[market] = new_stocks
        print(f"  [{market}] 데이터 검증 완료: {len(new_stocks)}개 (재스캔 {rescan_count}개)")
    return fixed


# ═══════════════════════════════════════════════════════════════
# 거시 / 뉴스 / 해외지표 / 신규: Fear&Greed, 섹터 흐름
# ═══════════════════════════════════════════════════════════════

def collect_macro() -> dict:
    macro = {}
    for name, tk in {
        "USD/KRW": "KRW=X",   "WTI유가": "CL=F",
        "금(Gold)": "GC=F",    "구리": "HG=F",
        "VIX": "^VIX",         "KOSPI": "^KS11",
        "KOSDAQ": "^KQ11",     "S&P500": "^GSPC",
        "나스닥": "^IXIC",      "미10년채": "^TNX",
        "달러인덱스": "DX=F",
    }.items():
        try:
            h = yf.Ticker(tk).history(period="5d", timeout=10)
            if not h.empty:
                cur  = float(h["Close"].squeeze().iloc[-1])
                prev = float(h["Close"].squeeze().iloc[-2]) if len(h) > 1 else cur
                macro[name] = {
                    "현재": round(cur, 2),
                    "등락(%)": round((cur - prev) / prev * 100, 2),
                }
        except Exception:
            pass
    return macro


def collect_fear_greed() -> dict:
    """
    CNN Fear & Greed Index (alternative.me 무료 API)
    0~24: Extreme Fear / 25~49: Fear / 50~74: Greed / 75~100: Extreme Greed
    극도의 공포 = 매수 기회 / 극도의 탐욕 = 매도 고려
    """
    try:
        resp = requests.get("https://api.alternative.me/fng/?limit=3", timeout=10)
        data = resp.json().get("data", [])
        if not data:
            return {}
        return {
            "지수": int(data[0]["value"]),
            "단계": data[0]["value_classification"],
            "전일": int(data[1]["value"]) if len(data) > 1 else None,
            "해석": (
                "극도공포(매수기회)" if int(data[0]["value"]) < 25 else
                "공포(관망)" if int(data[0]["value"]) < 50 else
                "탐욕(신중)" if int(data[0]["value"]) < 75 else
                "극도탐욕(매도고려)"
            ),
        }
    except Exception:
        return {}


# 국내 ETF 유니버스: (티커, 이름, 주요 구성종목 5개)
_KR_ETF_LIST = [
    ("069500.KS", "KODEX 200",           ["삼성전자", "SK하이닉스", "LG에너지솔루션", "현대차", "기아"]),
    ("091160.KS", "KODEX 반도체",        ["삼성전자", "SK하이닉스", "한미반도체", "DB하이텍", "원익IPS"]),
    ("305720.KS", "KODEX 2차전지",       ["LG에너지솔루션", "삼성SDI", "에코프로비엠", "포스코퓨처엠", "엘앤에프"]),
    ("091180.KS", "KODEX 자동차",        ["현대차", "기아", "현대모비스", "현대위아", "HL만도"]),
    ("244580.KS", "KODEX 바이오",        ["삼성바이오로직스", "셀트리온", "한미약품", "유한양행", "종근당"]),
    ("133690.KS", "TIGER 미국나스닥100", ["애플", "MS", "엔비디아", "아마존", "알파벳"]),
    ("379800.KS", "KODEX 미국S&P500",    ["애플", "MS", "아마존", "엔비디아", "메타"]),
    ("232080.KS", "TIGER 코스닥150",     ["에코프로비엠", "HLB", "알테오젠", "리가켐바이오", "크래프톤"]),
    ("463250.KS", "TIGER K방산&우주",     ["한화에어로스페이스", "한국항공우주", "LIG넥스원", "현대로템", "풍산"]),
    ("278540.KS", "KODEX 글로벌AI",      ["엔비디아", "MS", "메타", "TSMC", "삼성전자"]),
    ("364980.KS", "TIGER 글로벌리튬&2차전지", ["앨버말", "SQM", "리벤트", "파일럿 케미컬", "LG에너지솔루션"]),
    ("381170.KS", "TIGER 글로벌반도체",  ["TSMC", "엔비디아", "ASML", "SK하이닉스", "삼성전자"]),
]


def _collect_etf_picks(etf_list: list, top_n: int = 5) -> list:
    """
    ETF 성과 분석 → 모멘텀 기준 상위 N개 반환 (국내/중국 공통).
    각 ETF의 1일·5일·20일 수익률을 계산하고 모멘텀 점수로 정렬.
    """
    results = []
    for ticker, name, holdings in etf_list:
        try:
            h = yf.Ticker(ticker).history(period="30d", timeout=10)
            if h.empty or len(h) < 5:
                continue
            cur  = float(h["Close"].iloc[-1])
            prev = float(h["Close"].iloc[-2])
            w5   = float(h["Close"].iloc[-6]) if len(h) >= 6 else float(h["Close"].iloc[0])
            w20  = float(h["Close"].iloc[-21]) if len(h) >= 21 else float(h["Close"].iloc[0])
            d1   = round((cur - prev) / prev * 100, 2)
            d5   = round((cur - w5)   / w5   * 100, 2)
            d20  = round((cur - w20)  / w20  * 100, 2)
            score = d5 * 2 + d20
            results.append({
                "ticker":   ticker,
                "name":     name,
                "price":    round(cur, 0),
                "price_date": h.index[-1].strftime("%m/%d"),
                "d1":       d1,
                "d5":       d5,
                "d20":      d20,
                "score":    score,
                "holdings": holdings,
            })
        except Exception:
            pass
    results.sort(key=lambda x: x["score"], reverse=True)
    return results[:top_n]


def collect_kr_etf_picks(top_n: int = 5) -> list:
    return _collect_etf_picks(_KR_ETF_LIST, top_n)


# 중국 ETF 풀 (KRX 상장 — 한국 증권사 판매)
_CHINA_ETF_LIST = [
    ("192090.KS", "TIGER 차이나 CSI300", ["중국 A 주 대형주 300 개", "시가총액 가중"]),
    ("371160.KS", "KODEX 차이나항셍테크", ["알리바바", "텐센트", "메이투안"]),
    ("305540.KS", "TIGER 차이나전기차", ["BYD", "CATL", "NIO", "리오토"]),
    ("099140.KS", "KODEX 차이나 H 주", ["중국 블루칩 H 주", "항셍중국기업지수"]),
    ("192720.KS", "TIGER 차이나 CSI500", ["중국 중소형 성장주 500 개"]),
    ("290130.KS", "TIGER 차이나소비테마", ["중국 내수 소비", "중산층 확대 수혜"]),
    ("391600.KS", "KODEX 차이나과창판 STAR50", ["상하이 STAR Market", "반도체·바이오·AI"]),
]


def collect_china_etf_picks(top_n: int = 5) -> list:
    return _collect_etf_picks(_CHINA_ETF_LIST, top_n)


def collect_sector_flows() -> dict:
    """
    섹터 ETF 흐름 분석
    어떤 섹터로 자금이 들어오고 나가는지 파악 → 섹터 로테이션 전략
    """
    snap = {}
    sector_etfs = [
        # 미국 섹터 ETF
        ("XLK", "미국-기술"), ("XLF", "미국-금융"), ("XLE", "미국-에너지"),
        ("XLV", "미국-헬스케어"), ("XLI", "미국-산업재"), ("XLY", "미국-소비재"),
        ("XLP", "미국-필수소비"), ("SOXX", "반도체ETF"), ("ARKK", "ARK혁신"),
        # 한국 섹터 ETF
        ("091160.KS", "KODEX반도체"), ("305720.KS", "KODEX2차전지"),
        ("091180.KS", "KODEX자동차"),
        # 글로벌 지표
        ("GLD", "금ETF"), ("USO", "원유ETF"), ("UUP", "달러ETF"),
    ]
    for tk, label in sector_etfs:
        try:
            h = yf.Ticker(tk).history(period="20d", timeout=10)
            if not h.empty and len(h) >= 5:
                cur   = float(h["Close"].iloc[-1])
                prev  = float(h["Close"].iloc[-2])
                w5    = float(h["Close"].iloc[-6])
                snap[label] = {
                    "현재": round(cur, 2),
                    "전일(%)": round((cur - prev) / prev * 100, 2),
                    "5일(%)": round((cur - w5) / w5 * 100, 2),
                }
        except Exception:
            pass
    return snap


def collect_news() -> list:
    headlines = []
    for rss in [
        "https://www.yonhapnewstv.co.kr/category/news/economy/feed/",
        "https://rss.donga.com/economy.xml",
        "https://feeds.feedburner.com/businessinsider",
    ]:
        try:
            feed = feedparser.parse(rss)
            if feed.entries:
                headlines = [e.title for e in feed.entries[:10]]
                break
        except Exception:
            continue
    return headlines


def collect_overseas_snapshot() -> dict:
    snap = {}
    for tk, label in [
        ("NVDA", "엔비디아"), ("TSM", "TSMC"), ("ASML", "ASML"),
        ("TSLA", "테슬라"), ("META", "메타"), ("MSFT", "MS"),
        ("LMT", "록히드마틴"), ("^TNX", "미10년채"), ("DX=F", "달러인덱스"),
    ]:
        try:
            h = yf.Ticker(tk).history(period="10d", timeout=10)
            if not h.empty:
                cur  = float(h["Close"].iloc[-1])
                prev = float(h["Close"].iloc[-2]) if len(h) > 1 else cur
                snap[label] = {
                    "현재": round(cur, 2),
                    "전일(%)": round((cur - prev) / prev * 100, 2),
                }
        except Exception:
            pass
    return snap


def collect_investor_summary() -> dict:
    """
    국내외 유명 투자자 포트폴리오 TOP5 요약 반환.
    {투자자명: [(티커, 설명, 비중), ...]}
    """
    try:
        from investor_scorer import (
            PELOSI_PORTFOLIO, ARK_TOP_HOLDINGS,
            PARK_SEOIK_PORTFOLIO, JOHN_LEE_PORTFOLIO,
            LEE_CHAEWON_PORTFOLIO, KIM_MINGUK_PORTFOLIO,
            KANG_BANGCHEON_PORTFOLIO,
        )
        def top5(portfolio):
            return sorted(portfolio.items(), key=lambda x: -x[1]["weight"])[:5]

        return {
            "🇺🇸 Pelosi":       [(t, d["note"], d["weight"]) for t, d in top5(PELOSI_PORTFOLIO)],
            "🇺🇸 ARK(Cathie)":  [(t, d["note"], d["weight"]) for t, d in top5(ARK_TOP_HOLDINGS)],
            "🇰🇷 박세익":        [(t, d["note"], d["weight"]) for t, d in top5(PARK_SEOIK_PORTFOLIO)],
            "🇰🇷 존리":          [(t, d["note"], d["weight"]) for t, d in top5(JOHN_LEE_PORTFOLIO)],
            "🇰🇷 이채원":        [(t, d["note"], d["weight"]) for t, d in top5(LEE_CHAEWON_PORTFOLIO)],
            "🇰🇷 김민국":        [(t, d["note"], d["weight"]) for t, d in top5(KIM_MINGUK_PORTFOLIO)],
            "🇰🇷 강방천":        [(t, d["note"], d["weight"]) for t, d in top5(KANG_BANGCHEON_PORTFOLIO)],
        }
    except Exception:
        return {}


def get_theme_picks(all_results: dict, top_n: int = 3) -> dict:
    """
    스크리닝 결과(all_results)에서 국내 테마별 상위 종목 추출.
    테마 정의는 _THEMES 사용. 결과 없는 테마는 생략.
    """
    kr_stocks = all_results.get("KOSPI", []) + all_results.get("KOSDAQ", [])
    theme_picks = {}
    for theme_key, cfg in _THEMES.items():
        if "suffix" in cfg:
            continue  # kr/us 전체 필터는 제외
        tickers = cfg.get("tickers", set())
        picks = [r for r in kr_stocks if r["ticker"] in tickers]
        picks.sort(key=lambda x: x["score"], reverse=True)
        if picks:
            theme_picks[cfg["desc"]] = picks[:top_n]
    return theme_picks


def load_external_events() -> list:
    """external_events.json 에서 활성 이벤트 로드 (파일 없으면 빈 리스트)"""
    try:
        from external_events import get_active_events
        return get_active_events()
    except Exception:
        return []


# ═══════════════════════════════════════════════════════════════
# 신호 레이블
# ═══════════════════════════════════════════════════════════════

def signal_label(score: int) -> str:
    if   score >= 70: return "🟢 강한매수"
    elif score >= 40: return "🔵 매수추천"
    elif score >= 20: return "🔷 약한매수"
    elif score <= -70: return "🔴 강한매도"
    elif score <= -40: return "🟠 매도추천"
    elif score <= -20: return "🔶 약한매도"
    else:              return "⚪ 중립"

def signal_label_buy(score: int) -> str:
    lbl = signal_label(score)
    return "🔷 약한매수(상대우위)" if score <= 0 else lbl


# ═══════════════════════════════════════════════════════════════
# Claude 심층 분석 — v4 강화 프롬프트
# ═══════════════════════════════════════════════════════════════

_MAX_PROMPT_CHARS = 28_000  # ≈ 8,000 토큰 (한+영 혼합 기준 ~3.5자/토큰)
_last_claude_structured: dict = {}  # 최근 Claude JSON 구조화 결과 (선별 반영용)


def _extract_claude_json(text: str) -> "tuple[str, dict]":
    """
    Claude 응답에서 ```json ... ``` 블록을 추출한다.

    Returns
    -------
    (text_without_json, parsed_dict)
        JSON 파싱 실패 시 (원본 텍스트, {}) 반환.
    """
    import re
    pattern = r"```json\s*(\{.*\})\s*```"
    m = re.search(pattern, text, re.DOTALL)
    if not m:
        return text, {}
    json_str = m.group(1)
    # JSON이 앞에 있으면 이후 텍스트, 뒤에 있으면 이전 텍스트 사용
    before = text[:m.start()].rstrip()
    after  = text[m.end():].lstrip()
    clean_text = after if after else before
    try:
        parsed = json.loads(json_str)
        # 필수 필드 검증: 누락 시 빈 리스트 기본값 설정
        if "top_buy" not in parsed:
            parsed["top_buy"] = []
        if "top_sell" not in parsed:
            parsed["top_sell"] = []
        return clean_text, parsed
    except json.JSONDecodeError:
        return text, {}


def _save_claude_structured(data: dict) -> None:
    """구조화 분석 결과를 cache/claude_structured_YYYYMMDD.json 으로 저장."""
    today = datetime.datetime.now().strftime("%Y%m%d")
    cache_dir = os.path.join(BASE_DIR, "cache")
    os.makedirs(cache_dir, exist_ok=True)
    path = os.path.join(cache_dir, f"claude_structured_{today}.json")
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump({"saved_at": datetime.datetime.now().isoformat(), **data}, f,
                      ensure_ascii=False, indent=2)
    except Exception:
        pass


def _stock_line(r: dict, include_fund: bool = True) -> str:
    """Claude 프롬프트용 압축 종목 라인 (핵심 지표만)"""
    stop_loss = round(r["price"] - 2.0 * r["atr"], 2)
    fund      = r.get("fund", {})
    trend     = "▲" if r["plus_di"] > r["minus_di"] else "▼"
    fund_str  = ""
    if include_fund and fund:
        parts = []
        if fund.get("pe"):       parts.append(f"PE:{fund['pe']}")
        if fund.get("roe_pct"):  parts.append(f"ROE:{fund['roe_pct']}%")
        if fund.get("fund_score") is not None: parts.append(f"F:{fund['fund_score']:+d}")
        fund_str = " " + " ".join(parts) if parts else ""

    return (
        f"{r['name']}({r['ticker']}) S:{r['score']:+.1f} "
        f"P:{r['price']:,.0f}({r['chg']:+.1f}%) "
        f"RSI:{r['rsi']:.0f} MACD:{'▲' if r['macd_hist']>0 else '▼'} "
        f"ADX:{r['adx']:.0f}{trend} 52w:{r['pos_52w']:.0f}% "
        f"손절:{stop_loss:,.0f}{fund_str}"
    )


def ask_claude_v4(kospi_buy, kosdaq_buy, us_buy,
                  kospi_sell, kosdaq_sell, us_sell,
                  macro, news, overseas, fear_greed, sector_flows,
                  external_events=None,
                  investor_summary=None,
                  theme_picks=None,
                  **kwargs) -> str:
    global _last_claude_structured
    try:
        import anthropic
        client = anthropic.Anthropic(api_key=_get("ANTHROPIC_API_KEY"))
    except Exception as e:
        return f"[Claude 분석 생략 — ANTHROPIC_API_KEY 없음: {e}]"

    # 캐시 확인
    ext_events = external_events or []

    def _macro_fingerprint() -> str:
        """
        거시·뉴스의 의미 있는 변화만 감지하는 지문.
        소폭 등락은 무시하고 실질적 변화 시에만 Claude 재호출.

        민감도 기준:
          Fear&Greed : 4단계 레이블 기준 (극도공포/공포/탐욕/극도탐욕)
          VIX        : 정수 단위 (1pt 변화)
          USD/KRW    : 50원 단위 (1450~1500 = 동일 버킷)
          뉴스       : 상위 3건 헤드라인 앞 30자
        """
        fg_val = fear_greed.get("지수", 50) if fear_greed else 50
        if fg_val < 25:
            fg_level = "extreme_fear"
        elif fg_val < 50:
            fg_level = "fear"
        elif fg_val < 75:
            fg_level = "greed"
        else:
            fg_level = "extreme_greed"

        vix_r    = round(macro.get("VIX",     {}).get("현재", 20) / 2) * 2    # 2pt 버킷
        usdkrw_r = round(macro.get("USD/KRW", {}).get("현재", 1300) / 50) * 50  # 50원 버킷
        headlines = tuple(
            (n.get("title", "") if isinstance(n, dict) else str(n))[:30]
            for n in (news or [])[:3]
        )
        raw = json.dumps((fg_level, vix_r, usdkrw_r, headlines),
                         ensure_ascii=False)
        import hashlib
        return hashlib.md5(raw.encode()).hexdigest()[:8]

    def _tech_fingerprint(kb, kqb, ub) -> str:
        """상위 5개 종목의 ticker+score(정수) 해시 — 순위 변동 시 캐시 무효화."""
        import hashlib
        top5 = []
        for lst in (kb, kqb, ub):
            for r in (lst or [])[:5]:
                top5.append((r.get("ticker", ""), round(r.get("score", 0))))
        raw = json.dumps(sorted(top5), ensure_ascii=False)
        return hashlib.md5(raw.encode()).hexdigest()[:8]

    # 캐시 키: 날짜 + 외부이벤트 + 거시·뉴스 지문 + 기술점수 상위 지문
    # → 거시·뉴스 또는 기술점수 상위 순위가 바뀌면 Claude 재호출
    cache_data = {
        "date": datetime.datetime.now().strftime("%Y-%m-%d"),
        "external_events": sorted([e.get("id", "") for e in ext_events]),
        "macro_fp": _macro_fingerprint(),
        "tech_fp": _tech_fingerprint(kospi_buy, kosdaq_buy, us_buy),
    }
    try:
        from token_cache import get_cached_analysis, save_analysis_cache
        cached = get_cached_analysis(cache_data, cache_hours=24)
        if cached:
            print(f"  ✓ 캐시 분석 결과 사용 (macro_fp={cache_data['macro_fp']})")
            _, _cached_struct = _extract_claude_json(cached)
            if _cached_struct:
                _last_claude_structured = _cached_struct
            return cached
    except Exception:
        pass

    # 거시 (핵심 7개만)
    MACRO_KEYS = ["USD/KRW", "VIX", "S&P500", "나스닥", "KOSPI", "미10년채", "WTI유가"]
    macro_txt = " | ".join(
        f"{k}:{v['현재']}({v['등락(%)']:+.1f}%)"
        for k, v in macro.items() if k in MACRO_KEYS
    )

    # Fear & Greed 한 줄
    fg_txt = f"F&G:{fear_greed['지수']}/100→{fear_greed['해석']}" if fear_greed else "F&G:없음"

    # 섹터 흐름 (5일 상위 6개만)
    sector_sorted = sorted(sector_flows.items(), key=lambda x: x[1].get("5일(%)", 0), reverse=True)
    sector_txt = " | ".join(
        f"{k}:{v['5일(%)']:+.1f}%" for k, v in sector_sorted[:6]
    )

    # 뉴스 5개
    news_txt = " / ".join(news[:5]) or "(없음)"

    # 해외 (핵심 4개)
    OV_KEYS = ["엔비디아", "TSMC", "달러인덱스", "미10년채"]
    ov_txt = " | ".join(
        f"{k}:{v['현재']}({v['전일(%)']:+.1f}%)"
        for k, v in overseas.items() if k in OV_KEYS
    )

    def block(stocks, label):
        return f"[{label}] " + " / ".join(_stock_line(r) for r in stocks)

    # 외부 이벤트
    ext_txt = ""
    if ext_events:
        ext_txt = "외부변수: " + " | ".join(
            f"[{ev['category']}]{ev['title']}→{ev['impact']}" for ev in ext_events
        ) + "\n"

    # 유명 투자자 포트폴리오
    inv_txt = ""
    if investor_summary:
        lines = []
        for inv, picks in investor_summary.items():
            picks_str = " / ".join(f"{t}({note})" for t, note, w in picks[:3])
            lines.append(f"{inv}: {picks_str}")
        inv_txt = "유명투자자 관심종목:\n" + "\n".join(lines) + "\n"

    # 국내 테마별 상위 종목
    theme_txt = ""
    if theme_picks:
        lines = []
        for theme, stocks in theme_picks.items():
            picks_str = " / ".join(f"{r['name']}({r['score']:+.1f})" for r in stocks)
            lines.append(f"[{theme}] {picks_str}")
        theme_txt = "국내테마 상위종목:\n" + "\n".join(lines) + "\n"

    # 지정학 리스크 (GRI)
    gri_txt = ""
    if kwargs.get("gri") is not None and kwargs.get("recovery") is not None:
        from geopolitical_risk_engine import format_gri_for_claude
        gri_txt = format_gri_for_claude(
            kwargs["gri"], kwargs["recovery"], kwargs.get("war_watchlist", [])
        ) + "\n"

    def _build_prompt(kb, kqb, ub, ks, kqs, us):
        return f"""{datetime.datetime.now().strftime('%Y-%m-%d')} 주식 애널리스트 투자 의견 작성.

{ext_txt}{inv_txt}{theme_txt}{gri_txt}거시: {macro_txt}
심리: {fg_txt}
섹터5일: {sector_txt}
해외: {ov_txt}
뉴스: {news_txt}

{block(kb, 'KR매수')}
{block(kqb, 'KQ매수')}
{block(ub, 'US매수')}
{block(ks, 'KR매도')}
{block(kqs, 'KQ매도')}
{block(us, 'US매도')}

출력 형식 (반드시 아래 구조 그대로):

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🌐 시장 총평
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
시장판단 1줄
강세섹터: XXX / 약세섹터: XXX
핵심전략: XXX
주요리스크: XXX

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🟢 KR 매수 추천
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
① 종목명 (티커) ★★★★★
📌 매수논리 : [기술적 + 펀더멘털 핵심 근거 1~2줄]
🏢 비즈니스 : [실적개선·매출성장·마진확대·신사업·섹터 모멘텀 등 비즈니스 상황 1줄]
💰 분할매수 : 1차 40% @현재가 / 2차 30% @-X% / 3차 30% @-X%
🎯 목표가   : ① XXX  ② XXX  ③ XXX
🛑 손절가   : XXX
📊 펀더멘털 : [P/E·ROE·EPS성장률·이익률 등 핵심 지표 1줄]
─────────────────────────────────────

(매수 종목 없으면 "해당 없음" 한 줄)

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🟢 KQ 매수 추천
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
(동일 구조 반복)

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🟢 US 매수 추천
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
(동일 구조 반복)

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🔴 KR 매도 추천
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
① 종목명 (티커) ▼▼▼
📌 매도논리 : [기술적 + 펀더멘털 핵심 근거 1~2줄]
🔍 리스크요인 : [밸류에이션·실적악화·재무구조·테마 소멸·업황 둔화 등 1줄]
📉 매도전략 : [분할매도 또는 즉시매도]
🎯 하락목표 : XXX
─────────────────────────────────────

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🔴 KQ 매도 추천
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
(동일 구조 반복)

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🔴 US 매도 추천
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
(동일 구조 반복)

규칙: 마크다운(#, >, **) 사용 금지. 들여쓰기(공백) 없이 모든 줄은 맨 왼쪽에서 시작. 위 템플릿 구조와 이모지 그대로 유지.

반드시 분석 텍스트 맨 앞에 아래 JSON을 먼저 출력하라 (선별 기준으로 활용):
```json
{{"top_buy":[{{"ticker":"티커","name":"종목명","grade":"★★★","target1":0,"target2":0,"stop":0}}],"top_sell":[{{"ticker":"티커","name":"종목명","stop":0}}],"market":"시장판단한줄","risk":"핵심리스크한줄","fg_signal":"매수|관망|매도","sentiment":{{"티커":점수}}}}
```
sentiment 규칙: 위 매수/매도 후보 종목별로 오늘 뉴스가 해당 종목/섹터에 미치는 영향을 -2(매우부정)~+2(매우긍정) 정수로 평가. 직접 관련 뉴스 없으면 0. 섹터 전체에 영향주는 뉴스도 반영.
JSON 출력 후 아래 상세 분석을 이어서 출력하라."""

    prompt = _build_prompt(kospi_buy, kosdaq_buy, us_buy, kospi_sell, kosdaq_sell, us_sell)

    # ── 토큰 예산 체크 (최대 8,000 토큰 ≈ 28,000자) ───────────────────
    if len(prompt) > _MAX_PROMPT_CHARS:
        # 매 반복마다 각 블록에서 종목 1개씩 제거
        kb, kqb, ub = list(kospi_buy), list(kosdaq_buy), list(us_buy)
        ks, kqs, us_s = list(kospi_sell), list(kosdaq_sell), list(us_sell)
        while len(prompt) > _MAX_PROMPT_CHARS and any(len(x) > 1 for x in [kb, kqb, ub, ks, kqs, us_s]):
            for lst in [kb, kqb, ub, ks, kqs, us_s]:
                if len(lst) > 1:
                    lst.pop()
            prompt = _build_prompt(kb, kqb, ub, ks, kqs, us_s)
        print(f"  ⚠️ 프롬프트 토큰 초과 → 축소: {len(prompt):,}자 "
              f"(매수 KR{len(kb)}/KQ{len(kqb)}/US{len(ub)}, 매도 KR{len(ks)}/KQ{len(kqs)}/US{len(us_s)})")

    try:
        resp = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=5000,
            temperature=0,
            messages=[{"role": "user", "content": prompt}],
        )
        full_text = resp.content[0].text
        # JSON 블록 추출 후 텍스트 분리
        text_part, structured = _extract_claude_json(full_text)
        if structured:
            # 구조화 데이터 모듈 변수 + 파일 저장
            _last_claude_structured = structured
            _save_claude_structured(structured)
        try:
            save_analysis_cache(cache_data, full_text)
        except Exception:
            pass
        return text_part
    except Exception as e:
        print(f"  ⚠️ Claude API 오류: {e}")
        return f"[Claude 분석 실패 — 기술적 분석만 포함] (사유: {e})"


# ═══════════════════════════════════════════════════════════════
# 규칙 기반 매수/매도 근거 & 리스크 자동 생성
# ═══════════════════════════════════════════════════════════════

def _auto_analysis(r: dict, section: str) -> list[str]:
    """
    지표 데이터만으로 매수/매도 근거·목표가·손절가·리스크를 생성한다.
    Claude API 유무와 관계없이 항상 리포트에 포함된다.
    """
    lines = []
    price   = r["price"]
    rsi     = r["rsi"]
    macd    = r["macd_hist"]
    adx     = r["adx"]
    plus_di = r["plus_di"]
    minus_di= r["minus_di"]
    mom5    = r["mom5"]
    pos_52w = r["pos_52w"]
    stoch_k = r["stoch_k"]
    vol     = r["vol_ratio"]
    bb_pct  = r["bb_pct"]
    bb_up   = r["bb_up"]
    bb_dn   = r["bb_dn"]
    atr     = r["atr"]
    ma20    = r["ma20"]
    ma60    = r["ma60"]
    fund    = r.get("fund", {})
    stop    = round(price - 2.0 * atr, 2)

    if section == "buy":
        # ── 기술적 근거 ──────────────────────────────────────
        tech_reasons = []
        if rsi < 30:
            tech_reasons.append(f"RSI {rsi:.0f} 과매도 — 기술적 반등 신호")
        elif rsi < 40:
            tech_reasons.append(f"RSI {rsi:.0f} 약과매도 — 저가 매수 구간")
        if macd > 0:
            tech_reasons.append("MACD 히스토그램 양전환 — 상승 모멘텀 확인")
        if price > ma20 > ma60:
            tech_reasons.append("이동평균 정배열(가격>MA20>MA60) — 강한 상승 추세")
        elif price > ma20:
            tech_reasons.append("가격이 MA20 상회 — 단기 상승 구조")
        if adx > 25 and plus_di > minus_di:
            tech_reasons.append(f"ADX {adx:.0f} 강한 추세 (+DI{plus_di:.0f}>-DI{minus_di:.0f}) — 방향성 확립")
        if pos_52w < 20:
            tech_reasons.append(f"52주 저점 근처 {pos_52w:.0f}% — 반등 기대")
        elif pos_52w > 80:
            tech_reasons.append(f"52주 고점 구간 {pos_52w:.0f}% — 상승 모멘텀 지속")
        if stoch_k < 20:
            tech_reasons.append(f"스토캐스틱 {stoch_k:.0f} 과매도 — 반등 가능")
        if vol > 1.5:
            tech_reasons.append(f"거래량 {vol:.1f}x 급증 — 수급 유입 신호")
        if mom5 > 3:
            tech_reasons.append(f"5일 모멘텀 +{mom5:.1f}% — 단기 상승 흐름")

        # ── 펀더멘털 & 비즈니스 근거 ──────────────────────────
        fund_reasons = []
        if fund.get("eps_growth_pct") and fund["eps_growth_pct"] > 20:
            fund_reasons.append(f"EPS 성장 +{fund['eps_growth_pct']:.0f}% — 실적 개선 가속")
        elif fund.get("eps_growth_pct") and fund["eps_growth_pct"] > 10:
            fund_reasons.append(f"EPS 성장 +{fund['eps_growth_pct']:.0f}% — 이익 성장 확인")
        if fund.get("roe_pct") and fund["roe_pct"] > 25:
            fund_reasons.append(f"ROE {fund['roe_pct']:.0f}% — 탁월한 자본 효율")
        elif fund.get("roe_pct") and fund["roe_pct"] > 15:
            fund_reasons.append(f"ROE {fund['roe_pct']:.0f}% — 고수익성 비즈니스")
        if fund.get("margin_pct") and fund["margin_pct"] > 20:
            fund_reasons.append(f"순이익률 {fund['margin_pct']:.0f}% — 고마진 구조")
        elif fund.get("margin_pct") and fund["margin_pct"] > 10:
            fund_reasons.append(f"순이익률 {fund['margin_pct']:.0f}% — 견조한 수익성")
        if fund.get("pe") and fund["pe"] < 15:
            fund_reasons.append(f"P/E {fund['pe']} — 저평가 가치 매력")
        if fund.get("pb") and fund["pb"] < 1.0:
            fund_reasons.append(f"P/B {fund['pb']} — 자산 대비 저평가")

        if not tech_reasons and not fund_reasons:
            tech_reasons.append(f"종합점수 {r['score']:+.1f}점 — 상대적 강세 우위")

        if tech_reasons:
            lines.append(f"       ✅ 기술적 근거: {' / '.join(tech_reasons[:3])}")
        if fund_reasons:
            lines.append(f"       📈 펀더멘털: {' / '.join(fund_reasons[:3])}")

        # ── 분할매수 & 목표가 ──────────────────────────────
        buy2 = round(price - 2.0 * atr, 2)
        buy3 = round(price - 3.0 * atr, 2)
        tgt1 = round(bb_up, 2)
        tgt2 = round(price * 1.10, 2)
        tgt3 = round(price * 1.20, 2)
        lines.append(
            f"       💰 분할매수: 1차 현재가(40%) / "
            f"2차 {buy2:,.0f}(ATR×2·30%) / 3차 {buy3:,.0f}(ATR×3·30%)"
        )
        lines.append(
            f"       🎯 목표가: 1차 {tgt1:,.0f}(BB상단) / "
            f"2차 {tgt2:,.0f}(+10%) / 3차 {tgt3:,.0f}(+20%)"
        )
        lines.append(f"       🛑 손절가: {stop:,.0f} (ATR×2 — 변동성 기반 동적 손절)")

        # ── 기술적 리스크 ─────────────────────────────────
        tech_risks = []
        if rsi > 60:
            tech_risks.append(f"RSI {rsi:.0f} — 추가 과열 시 조정 가능")
        if adx < 20:
            tech_risks.append(f"ADX {adx:.0f} 횡보 — 추세 신뢰도 낮음")
        if mom5 < -2:
            tech_risks.append(f"5일 모멘텀 {mom5:.1f}% — 단기 하락 압력")
        if price < ma20:
            tech_risks.append("MA20 하회 — 지지선 붕괴 주의")
        if bb_pct > 85:
            tech_risks.append(f"BB {bb_pct:.0f}% — 상단 근접, 단기 과열")
        if stoch_k > 75:
            tech_risks.append(f"스토캐스틱 {stoch_k:.0f} — 단기 과매수")
        if vol < 0.5:
            tech_risks.append(f"거래량 {vol:.1f}x 위축 — 상승 동력 부족")
        if pos_52w > 90:
            tech_risks.append(f"52주 신고가 {pos_52w:.0f}% — 차익 실현 압력")

        # ── 펀더멘털 & 비즈니스 리스크 ──────────────────────
        fund_risks = []
        if fund.get("pe") and fund["pe"] > 50:
            fund_risks.append(f"P/E {fund['pe']} — 밸류에이션 과부담")
        elif fund.get("pe") and fund["pe"] > 30:
            fund_risks.append(f"P/E {fund['pe']} — 고평가, 실적 미달 시 급락 위험")
        if fund.get("eps_growth_pct") is not None and fund["eps_growth_pct"] < -10:
            fund_risks.append(f"EPS {fund['eps_growth_pct']:.0f}% 역성장 — 실적 악화 추세")
        elif fund.get("eps_growth_pct") is not None and fund["eps_growth_pct"] < 0:
            fund_risks.append(f"EPS 감소 {fund['eps_growth_pct']:.0f}% — 이익 모멘텀 약화")
        if fund.get("roe_pct") is not None and fund["roe_pct"] < 0:
            fund_risks.append("ROE 음수 — 적자 기업 구조")
        elif fund.get("roe_pct") is not None and fund["roe_pct"] < 5:
            fund_risks.append(f"ROE {fund['roe_pct']:.0f}% — 낮은 자본 효율")
        if fund.get("margin_pct") is not None and fund["margin_pct"] < 0:
            fund_risks.append(f"순이익률 {fund['margin_pct']:.0f}% — 수익성 적자")
        if fund.get("de_ratio") and fund["de_ratio"] > 200:
            fund_risks.append(f"부채비율 {fund['de_ratio']:.0f}% — 재무 레버리지 부담")
        if fund.get("pb") and fund["pb"] > 5:
            fund_risks.append(f"P/B {fund['pb']} — 자산 대비 고평가")

        if not tech_risks and not fund_risks:
            tech_risks.append("현재 주요 리스크 없음")

        if tech_risks:
            lines.append(f"       ⚠️ 기술적 리스크: {' / '.join(tech_risks[:3])}")
        if fund_risks:
            lines.append(f"       🔍 펀더멘털 리스크: {' / '.join(fund_risks[:3])}")

    else:  # sell
        # ── 매도 근거 ──────────────────────────────────────
        reasons = []
        if rsi > 70:
            reasons.append(f"RSI {rsi:.0f} 과매수 — 조정 가능성")
        elif rsi > 60:
            reasons.append(f"RSI {rsi:.0f} 과열 진입 — 비중 축소 시점")
        if macd < 0:
            reasons.append("MACD 히스토그램 음전환 — 하락 모멘텀")
        if price < ma20 < ma60:
            reasons.append("이동평균 역배열(가격<MA20<MA60) — 하락 추세 고착")
        elif price < ma20:
            reasons.append("가격이 MA20 하회 — 단기 하락 구조")
        if adx > 25 and minus_di > plus_di:
            reasons.append(f"ADX {adx:.0f} 강한 하락 추세 (-DI{minus_di:.0f}>+DI{plus_di:.0f})")
        if stoch_k > 80:
            reasons.append(f"스토캐스틱 {stoch_k:.0f} 과매수 — 매도 시점")
        if mom5 < -3:
            reasons.append(f"5일 모멘텀 {mom5:.1f}% — 하락 흐름 지속")
        if pos_52w > 90:
            reasons.append(f"52주 신고가 {pos_52w:.0f}% — 차익 실현 구간")
        if not reasons:
            reasons.append(f"종합점수 {r['score']:+.1f}점 — 상대적 약세")

        lines.append(f"       ❌ 매도 근거: {' / '.join(reasons[:3])}")

        # ── 매도 전략 & 하락 목표가 ───────────────────────
        tgt_dn1 = round(bb_dn, 2)
        tgt_dn2 = round(price * 0.90, 2)
        lines.append(
            f"       💸 매도 전략: 즉시 50% 매도 / 반등 시 잔량 정리"
        )
        lines.append(
            f"       📉 하락 목표: 1차 {tgt_dn1:,.0f}(BB하단) / 2차 {tgt_dn2:,.0f}(-10%)"
        )

        # ── 리스크(매도 포지션 관점) ───────────────────────
        risks = []
        if rsi < 30:
            risks.append(f"RSI {rsi:.0f} 과매도 — 기술적 반등 위험")
        if mom5 > 3:
            risks.append(f"단기 급등 {mom5:.1f}% — 숏커버링 주의")
        if vol > 2.0:
            risks.append(f"거래량 {vol:.1f}x 급증 — 반전 가능성")
        if not risks:
            risks.append("현재 주요 반전 리스크 없음")
        lines.append(f"       ⚠️ 리스크: {' / '.join(risks[:2])}")

    return lines


# ═══════════════════════════════════════════════════════════════
# 리포트 생성
# ═══════════════════════════════════════════════════════════════

def _extract_market_summary(claude_text: str) -> str:
    """Claude 텍스트에서 🌐 시장 총평 섹션만 추출한다."""
    import re
    # JSON 블록 이후 텍스트에서 시장 총평 ~ 다음 섹션(🟢/🔴) 직전까지 추출
    m = re.search(r'(━+\n🌐 시장 총평\n━+\n.*?)(?=\n━+\n[🟢🔴]|\Z)', claude_text, re.DOTALL)
    if m:
        return m.group(1).strip()
    # 구분선 없이 🌐로 시작하는 경우 폴백
    m2 = re.search(r'(🌐 시장 총평.*?)(?=🟢|🔴|\Z)', claude_text, re.DOTALL)
    if m2:
        return m2.group(1).strip()
    return ""


def build_report(kospi_buy, kosdaq_buy, us_buy,
                 kospi_sell, kosdaq_sell, us_sell,
                 total: dict, fear_greed: dict, claude_opinion: str,
                 investor_summary: dict = None, theme_picks: dict = None,
                 verification_section: str = "",
                 macro_regime: dict = None,
                 kr_etf_picks: list = None,
                 china_etf_picks: list = None,
                 ipo_buy: list = None,
                 reversal_picks: list = None,
                 trend_picks: list = None,
                 bearish_picks: list = None,
                 gri_summary: str = None,
                 mdt_up_picks: list = None,
                 mdt_dn_picks: list = None,
                 corr_data: dict = None) -> str:
    now = datetime.datetime.now().strftime("%Y년 %m월 %d일 %H:%M")
    L   = []

    # ── 헤더 ──────────────────────────────────────────────────────
    L.append("=" * 80)
    L.append(f"  📊 AI 주식 스크리닝 v4 (정밀 분석판)  |  {now}")
    _ipo_cnt = len(ipo_buy) if ipo_buy else 0
    def _scan_str(mkt):
        valid = total.get(mkt, 0)
        pool  = total.get(f"{mkt}_pool", 0)
        return f"{valid}/{pool}개" if pool else f"{valid}개"
    L.append(f"  스캔: 코스피 {_scan_str('KOSPI')} | 코스닥 {_scan_str('KOSDAQ')} | 미국 {_scan_str('US')} | IPO {total.get('IPO',0)}개")
    fg = fear_greed
    if fg:
        L.append(f"  Fear&Greed: {fg['지수']}/100 [{fg['단계']}] → {fg['해석']}")
    if macro_regime:
        _regime_icon = {"강세": "🟢", "중립": "🟡", "약세": "🔴", "극도약세": "🔴🔴"}.get(
            macro_regime["regime"], "⚪")
        _adj = macro_regime.get("applied_adjustment", macro_regime.get("score_adjustment", 0))
        _bwr = macro_regime.get("buy_win_rate")
        _swr = macro_regime.get("sell_win_rate")
        _wr_str = ""
        if _bwr is not None:
            _wr_str = f" | 최근5일 매수승률:{_bwr:.0f}% 매도승률:{_swr:.0f}%"
        L.append(f"  {_regime_icon} 시장레짐: {macro_regime['regime']}"
                 f"  (레짐점수:{macro_regime['regime_score']:+d}"
                 f", 점수보정:{_adj:+d}점){_wr_str}")
        for _r in macro_regime.get("reasons", []):
            L.append(f"    · {_r}")
    if gri_summary:
        L.append(gri_summary)
    L.append("=" * 80)

    # ── Claude 시장 총평 (헤더 바로 아래) ─────────────────────────
    market_summary = _extract_market_summary(claude_opinion)
    if market_summary:
        L.append("")
        L.append(market_summary)
    L.append("")

    def fmt_block(stocks, header, icon, section="neutral"):
        L.append("\n" + "─" * 80)
        L.append(f"  {icon} {header}")
        L.append("─" * 80)
        for i, r in enumerate(stocks, 1):
            chg_icon = "▲" if r["chg"] >= 0 else "▼"
            lbl = signal_label_buy(r["score"]) if section == "buy" else signal_label(r["score"])
            stop = round(r["price"] - 2.0 * r["atr"], 2)
            fund = r.get("fund", {})
            L.append(f"\n  {i:2d}위  {lbl}  {r['name']} ({r['ticker']})")
            today_str = ""
            if r.get("today_price") is not None:
                t_icon = "▲" if r["today_chg"] >= 0 else "▼"
                today_str = (f"  ⚡장중:{r['today_price']:,.2f}"
                             f"({t_icon}{abs(r['today_chg']):.2f}%)")
            pd_str = f"({r['price_date']})" if r.get('price_date') else ""
            L.append(f"       점수:{r['score']:+.1f}점 | 기준가:{r['price']:>12,.2f}{pd_str} | "
                     f"등락:{chg_icon}{abs(r['chg']):.2f}% | ATR손절:{stop:,.2f}{today_str}")
            L.append(f"       RSI:{r['rsi']:.0f} Stoch:{r['stoch_k']:.0f}/{r['stoch_d']:.0f} | "
                     f"MACD:{r['macd_hist']:+.4f} | BB:{r['bb_pct']:.0f}%")
            L.append(f"       MA5:{r['ma5']:,.2f} MA20:{r['ma20']:,.2f} MA60:{r['ma60']:,.2f} | "
                     f"ADX:{r['adx']:.0f}(+DI:{r['plus_di']:.0f}/-DI:{r['minus_di']:.0f})")
            L.append(f"       52주위치:{r['pos_52w']:.0f}% | 모멘텀:{r['mom5']:+.2f}% | "
                     f"거래량:{r['vol_ratio']:.1f}x | ATR:{r['atr_pct']:.1f}%")
            # 추세 필터 상태
            _lbr = "LBR:상승" if r.get("lbr_trending") else "LBR:비추세"
            _wma = "주봉MA20:상승" if r.get("weekly_ma20_rising") else "주봉MA20:하락"
            _geo = r.get("_geo_sector", "default")
            _geo_adj = r.get("_geo_adj", 0)
            _geo_str = f"섹터:{_geo}({_geo_adj:+d})" if _geo_adj != 0 else f"섹터:{_geo}"
            L.append(f"       추세: {_lbr} | {_wma} | {_geo_str}")
            if fund:
                fparts = []
                if fund.get("pe"):       fparts.append(f"P/E:{fund['pe']}")
                if fund.get("pb"):       fparts.append(f"P/B:{fund['pb']}")
                if fund.get("roe_pct"): fparts.append(f"ROE:{fund['roe_pct']}%")
                if fund.get("sector"):  fparts.append(f"섹터:{fund['sector']}")
                if fparts:
                    L.append(f"       펀더: {' | '.join(fparts)}")
            # 뉴스 감성 점수 (Claude 분석 결과)
            _sent = _last_claude_structured.get("sentiment", {})
            _s = _sent.get(r["ticker"], _sent.get(r["ticker"].split(".")[0], None))
            if _s is not None and _s != 0:
                _si = {2:"🟢🟢", 1:"🟢", -1:"🔴", -2:"🔴🔴"}.get(int(_s), "⚪")
                L.append(f"       뉴스감성: {_si}({_s:+d})")
            # Feature Importance — 상위 기여 지표
            _bd = r.get("score_breakdown", {})
            if _bd:
                _factors = [(k, v) for k, v in _bd.items()
                            if k not in ("total", "regime") and v != 0]
                _factors.sort(key=lambda x: abs(x[1]), reverse=True)
                if _factors:
                    _top = _factors[:3]
                    _fi_str = " > ".join(f"{k}({v:+.0f})" for k, v in _top)
                    _regime_tag = f"[{_bd.get('regime', '중립')}]" if _bd.get("regime", "중립") != "중립" else ""
                    L.append(f"       🔍 핵심요인{_regime_tag}: {_fi_str}")
            # 매수/매도 근거·전략·리스크 (지표 기반, 항상 출력)
            for line in _auto_analysis(r, section):
                L.append(line)

    fmt_block(kospi_buy,  "코스피 매수 TOP", "🇰🇷", "buy")
    fmt_block(kosdaq_buy, "코스닥 매수 TOP", "🇰🇷", "buy")
    if ipo_buy:
        fmt_block(ipo_buy, "신규상장(IPO) 주목 TOP 5 — 최근 6개월 상장", "🆕", "buy")

    # 바닥 반전 시그널 — 기존 fmt_block 포맷 + 시그널 요약
    if reversal_picks:
        fmt_block(reversal_picks,
                  "기술적 반전 매수 시그널 (RSI+MACD+거래량 / ADX하락반전) — 한국만",
                  "🔄", "buy")
        # 시그널 요약 추가
        L.append("")
        L.append("  ※ 위 종목은 기존 매수추천과 별도 — 경로A(RSI+MACD+거래량) 또는 경로B(ADX하락반전) 충족:")
        for i, r in enumerate(reversal_picks, 1):
            sig = r["reversal_signal"]
            parts = []
            if sig.get("path_a"):
                rsi_str = f"RSI:{sig['rsi_low']:.0f}→{sig['rsi_now']:.0f}"
                if sig["macd_cross_days"] is not None:
                    macd_str = f"MACD {sig['macd_cross_days']}일전 GC"
                elif sig["hist_latest"] >= 0:
                    macd_str = "히스토그램 양전환"
                else:
                    macd_str = f"히스토그램 {sig['hist_shrink_days']}일 축소"
                parts.append(f"{rsi_str} | {macd_str} | 거래량 {sig['vol_spike']:.1f}x")
            if sig.get("adx_reversal"):
                parts.append(f"ADX하락반전(peak:{sig['adx_peak']:.0f}→now:{sig['adx_now']:.0f})")
            L.append(f"     {i:2d}. {r['name']:12s} {' + '.join(parts)}")

    # 추세 매수 시그널 — LBR 3/10 추세 + 주봉 20MA 우상향 동시 충족
    if trend_picks:
        fmt_block(trend_picks,
                  "추세 매수 시그널 (LBR 3/10 상승추세 + 주봉 20MA 우상향)",
                  "📈", "buy")
        L.append("")
        L.append("  ※ 위 종목은 기존 매수추천과 별도 — 2가지 추세 조건 동시 충족:")
        L.append("     ① LBR 3/10: EMA(3)-EMA(10) > 0 AND SMA(16) 우상향 → 단기 추세 확립")
        L.append("     ② 주봉 20MA: 최근 3주간 주봉 20주 이동평균 연속 상승 → 중기 추세 확인")
        for i, r in enumerate(trend_picks, 1):
            _lbr = f"LBR:{r['lbr_fast']:+.4f}"
            _wma = "주봉MA20:상승"
            _adx = f"ADX:{r['adx']:.0f}(+DI:{r['plus_di']:.0f}/-DI:{r['minus_di']:.0f})"
            L.append(f"     {i:2d}. {r['name']:12s} 점수:{r['score']:+.1f} | {_lbr} | {_wma} | {_adx}")

    # 2~3일 복합 추세 시그널 — 가격+RSI+MACD+거래량 방향 일치
    if mdt_up_picks:
        fmt_block(mdt_up_picks,
                  "2~3일 상승 추세 형성 (가격↑ + RSI↑ + MACD↑ + 거래량 뒷받침)",
                  "📊", "buy")
        L.append("")
        L.append("  ※ 최근 3일간 4개 조건 중 3개 이상 동시 충족 — 단기 노이즈가 아닌 추세 형성 확인:")
        for i, r in enumerate(mdt_up_picks, 1):
            t = r["multi_day_trend"]
            parts = []
            parts.append("가격↑" if t["price_trend"] else "가격-")
            parts.append(f"RSI{'↑' if t['rsi_improving'] else '-'}({t['rsi_3d_ago']:.0f}→{t['rsi_now']:.0f})")
            parts.append(f"MACD{'↑' if t['macd_improving'] else '-'}")
            parts.append(f"거래량{'✓' if t['vol_confirmed'] else '✗'}")
            strength = "★★" if t["strength"] == "strong" else "★"
            L.append(f"     {i:2d}. {r['name']:12s} {strength} {' | '.join(parts)}")

    if mdt_dn_picks:
        fmt_block(mdt_dn_picks,
                  "2~3일 하락 추세 형성 (가격↓ + RSI↓ + MACD↓ + 매도 거래량)",
                  "📊", "sell")
        L.append("")
        L.append("  ※ 최근 3일간 4개 조건 중 3개 이상 동시 충족 — 하락 추세 형성 확인:")
        for i, r in enumerate(mdt_dn_picks, 1):
            t = r["multi_day_trend"]
            parts = []
            parts.append("가격↓" if t["price_trend"] else "가격-")
            parts.append(f"RSI{'↓' if t['rsi_improving'] else '-'}({t['rsi_3d_ago']:.0f}→{t['rsi_now']:.0f})")
            parts.append(f"MACD{'↓' if t['macd_improving'] else '-'}")
            parts.append(f"매도거래량{'✓' if t['vol_confirmed'] else '✗'}")
            strength = "★★" if t["strength"] == "strong" else "★"
            L.append(f"     {i:2d}. {r['name']:12s} {strength} {' | '.join(parts)}")

    fmt_block(us_buy,     "미국 매수 TOP",   "🇺🇸", "buy")
    fmt_block(kospi_sell,  "코스피 매도 TOP", "🇰🇷", "sell")
    fmt_block(kosdaq_sell, "코스닥 매도 TOP", "🇰🇷", "sell")
    fmt_block(us_sell,     "미국 매도 TOP",   "🇺🇸", "sell")

    # 천장 반전 시그널 — 기존 fmt_block 포맷 + 시그널 요약
    if bearish_picks:
        fmt_block(bearish_picks,
                  "기술적 반전 매도 시그널 (RSI 과열 + MACD 데드크로스 + 거래량 없는 반등)",
                  "📉", "sell")
        L.append("")
        L.append("  ※ 위 종목은 기존 매도추천과 별도 — 4가지 기술적 천장 조건 동시 충족:")
        for i, r in enumerate(bearish_picks, 1):
            sig = r["bearish_signal"]
            rsi_str = f"RSI:{sig['rsi_high']:.0f}→{sig['rsi_now']:.0f}"
            if sig["macd_cross_days"] is not None:
                macd_str = f"MACD {sig['macd_cross_days']}일전 DC"
            elif sig["hist_latest"] <= 0:
                macd_str = "히스토그램 음전환"
            else:
                macd_str = f"히스토그램 {sig['hist_shrink_days']}일 축소"
            L.append(f"     {i:2d}. {r['name']:12s} {rsi_str} | {macd_str} | 상승일 거래량 {sig['vol_ratio_on_up']:.1f}x")

    # 상관관계 분석 섹션
    if corr_data:
        L.append("\n" + "─" * 80)
        L.append("  🔗 상관관계 분석 (종목 vs 벤치마크 30일 수익률)")
        L.append("─" * 80)
        L.append(f"  {'종목':12s} {'KOSPI':>7s} {'S&P500':>7s} {'USD/KRW':>8s} {'WTI':>6s}  디커플링")
        L.append("  " + "─" * 65)
        for ticker, info in corr_data.items():
            c = info["corrs"]
            name = info["name"][:10]
            kospi = f"{c.get('KOSPI', '-'):>7}" if isinstance(c.get('KOSPI'), float) else f"{'—':>7}"
            sp500 = f"{c.get('S&P500', '-'):>7}" if isinstance(c.get('S&P500'), float) else f"{'—':>7}"
            usdkrw = f"{c.get('USD/KRW', '-'):>8}" if isinstance(c.get('USD/KRW'), float) else f"{'—':>8}"
            wti = f"{c.get('WTI', '-'):>6}" if isinstance(c.get('WTI'), float) else f"{'—':>6}"
            dec = " ⚠️ " + ", ".join(info["decoupling"]) if info.get("decoupling") else ""
            L.append(f"  {name:12s} {kospi} {sp500} {usdkrw} {wti}{dec}")
        # 뉴스 감성 요약
        _sent = _last_claude_structured.get("sentiment", {})
        if _sent:
            pos = [(k, v) for k, v in _sent.items() if v > 0]
            neg = [(k, v) for k, v in _sent.items() if v < 0]
            if pos or neg:
                L.append("\n" + "─" * 80)
                L.append("  📰 뉴스 감성 분석 (Claude 평가)")
                L.append("─" * 80)
                if pos:
                    pos_str = " / ".join(f"{k}({v:+d})" for k, v in sorted(pos, key=lambda x: -x[1]))
                    L.append(f"  🟢 긍정: {pos_str}")
                if neg:
                    neg_str = " / ".join(f"{k}({v:+d})" for k, v in sorted(neg, key=lambda x: x[1]))
                    L.append(f"  🔴 부정: {neg_str}")

    # 유명 투자자 포트폴리오 섹션
    if investor_summary:
        L.append("\n" + "─" * 80)
        L.append("  🌟 유명 투자자 포트폴리오 TOP5")
        L.append("─" * 80)
        for inv, picks in investor_summary.items():
            L.append(f"\n  {inv}")
            for t, note, w in picks:
                L.append(f"    {t:12s}  비중:{w:2d}%  {note}")

    # 국내 테마별 상위 종목 섹션
    if theme_picks:
        L.append("\n" + "─" * 80)
        L.append("  🏷️  국내 테마별 스크리닝 상위 종목")
        L.append("─" * 80)
        for theme, stocks in theme_picks.items():
            L.append(f"\n  [{theme}]")
            for i, r in enumerate(stocks, 1):
                stop = round(r["price"] - 2.0 * r["atr"], 2)
                today_str = ""
                if r.get("today_price") is not None:
                    t_icon = "▲" if r["today_chg"] >= 0 else "▼"
                    today_str = f"  ⚡{t_icon}{abs(r['today_chg']):.1f}%"
                L.append(f"    {i}. {r['name']} ({r['ticker']})  점수:{r['score']:+.1f}  "
                         f"RSI:{r['rsi']:.0f}  손절:{stop:,.0f}{today_str}")

    # 국내 유망 ETF TOP 5 섹션
    if kr_etf_picks:
        L.append("\n" + "─" * 80)
        L.append("  📦 국내 유망 ETF TOP 5  (모멘텀: 5일×2 + 20일×1 기준)")
        L.append("─" * 80)
        for i, etf in enumerate(kr_etf_picks, 1):
            d1_icon  = "▲" if etf["d1"]  >= 0 else "▼"
            d5_icon  = "▲" if etf["d5"]  >= 0 else "▼"
            d20_icon = "▲" if etf["d20"] >= 0 else "▼"
            L.append(f"\n  {i}위  {etf['name']} ({etf['ticker']})")
            L.append(
                f"       현재가: {etf['price']:>10,.0f}  "
                f"전일: {d1_icon}{abs(etf['d1']):.2f}%  "
                f"5일: {d5_icon}{abs(etf['d5']):.2f}%  "
                f"20일: {d20_icon}{abs(etf['d20']):.2f}%"
            )
            L.append(f"       주요 구성: {' / '.join(etf['holdings'])}")

    # 중국 ETF 추천 TOP 5 섹션
    if china_etf_picks:
        L.append("\n" + "─" * 80)
        L.append("  🇨🇳 중국 ETF 추천 TOP 5  (모멘텀: 5 일×2 + 20 일×1 기준)")
        L.append("─" * 80)
        for i, etf in enumerate(china_etf_picks, 1):
            d1_icon  = "▲" if etf["d1"]  >= 0 else "▼"
            d5_icon  = "▲" if etf["d5"]  >= 0 else "▼"
            d20_icon = "▲" if etf["d20"] >= 0 else "▼"
            L.append(f"\n  {i}위  {etf['name']} ({etf['ticker']})")
            L.append(
                f"       현재가: {etf['price']:>10,.0f}  "
                f"전일: {d1_icon}{abs(etf['d1']):.2f}%  "
                f"5 일: {d5_icon}{abs(etf['d5']):.2f}%  "
                f"20 일: {d20_icon}{abs(etf['d20']):.2f}%"
            )
            L.append(f"       주요 구성: {' / '.join(etf['holdings'])}")
        L.append("\n  ⚠️ 중국 ETF 리스크: 위안화 환율 변동성 / 중국 정책 리스크 / 지리적 긴장")

    # 추천 검증 섹션 (데이터 있을 때만 삽입)
    if verification_section:
        L.append("")
        L.append(verification_section)

    # 데이터 품질 섹션
    try:
        exc_count = data_cleaner.get_excluded_count()
        if exc_count > 0:
            L.append("")
            L.append("─" * 60)
            L.append(f"📊 데이터 품질: {exc_count}개 종목 제외 (이상치/결측/거래정지)")
            L.append("   상세: logs/excluded_*.log 참조")
    except Exception:
        pass

    L.append("\n" + "=" * 80)
    L.append("  ⚠️  기술적·펀더멘털 분석 참고용 / 투자 손익 책임은 본인에게 있습니다.")
    L.append("=" * 80 + "\n")
    return "\n".join(L)


# ═══════════════════════════════════════════════════════════════
# HTML 이메일 템플릿
# ═══════════════════════════════════════════════════════════════

_HTML_CSS = """
body{font-family:'Apple SD Gothic Neo','Malgun Gothic',sans-serif;margin:0;padding:0;background:#f4f6f8}
.wrap{max-width:800px;margin:0 auto;background:#fff}
.hdr{background:linear-gradient(135deg,#1a237e,#283593);color:#fff;padding:20px 24px}
.hdr h1{margin:0;font-size:18px;font-weight:700}
.hdr .sub{font-size:12px;opacity:.8;margin-top:4px}
.fg-bar{display:inline-block;padding:4px 10px;border-radius:12px;font-size:12px;font-weight:700;margin-top:8px}
.fg-fear{background:#ef5350;color:#fff}
.fg-greed{background:#66bb6a;color:#fff}
.fg-mid{background:#ffa726;color:#fff}
.sec{padding:16px 24px}
.sec-title{font-size:14px;font-weight:700;color:#1a237e;border-left:4px solid #1a237e;
           padding-left:10px;margin:0 0 12px}
table{width:100%;border-collapse:collapse;font-size:12px}
th{background:#e8eaf6;color:#283593;padding:6px 8px;text-align:center;white-space:nowrap}
td{padding:5px 8px;border-bottom:1px solid #f0f0f0;white-space:nowrap}
tr:hover td{background:#fafafa}
.badge-buy{display:inline-block;background:#e8f5e9;color:#2e7d32;border-radius:4px;
           padding:1px 6px;font-weight:700;font-size:11px}
.badge-sell{display:inline-block;background:#ffebee;color:#c62828;border-radius:4px;
            padding:1px 6px;font-weight:700;font-size:11px}
.score-pos{color:#2e7d32;font-weight:700}
.score-neg{color:#c62828;font-weight:700}
.chg-up{color:#c62828}.chg-dn{color:#1565c0}
.claude-box{background:#f3e5f5;border-left:4px solid #7b1fa2;padding:14px 10px 14px 0;
            font-size:12px;line-height:1.7;white-space:pre-wrap;word-break:break-word}
.perf-box{background:#e8f5e9;border-left:4px solid #2e7d32;padding:14px 18px;font-size:12px}
.perf-row{display:flex;gap:24px;flex-wrap:wrap}
.perf-item{flex:1;min-width:120px}
.perf-label{color:#555;font-size:11px}
.perf-val{font-size:16px;font-weight:700;color:#1a237e}
.ftr{background:#eceff1;padding:12px 24px;font-size:11px;color:#777;text-align:center}
"""

def _html_stock_table(stocks: list, section: str) -> str:
    """종목 리스트 → HTML 테이블 문자열."""
    if not stocks:
        return "<p style='color:#999;font-size:12px'>해당 없음</p>"
    badge = 'badge-buy' if section == "buy" else 'badge-sell'
    rows = []
    for i, r in enumerate(stocks, 1):
        stop = round(r["price"] - 2.0 * r["atr"], 2)
        lbl = signal_label_buy(r["score"]) if section == "buy" else signal_label(r["score"])
        sc_cls = "score-pos" if r["score"] >= 0 else "score-neg"
        chg_cls = "chg-up" if r["chg"] >= 0 else "chg-dn"
        chg_sign = "▲" if r["chg"] >= 0 else "▼"
        fund = r.get("fund", {})
        pe_str = f"P/E:{fund['pe']}" if fund.get("pe") else ""
        roe_str = f"ROE:{fund['roe_pct']}%" if fund.get("roe_pct") else ""
        rows.append(
            f"<tr>"
            f"<td style='text-align:center'>{i}</td>"
            f"<td><span class='{badge}'>{lbl}</span> {r['name']}<br>"
            f"<small style='color:#888'>{r['ticker']}</small></td>"
            f"<td class='{sc_cls}' style='text-align:center'>{r['score']:+.1f}</td>"
            f"<td style='text-align:right'>{r['price']:,.0f}"
            f"<br><small style='color:#888'>{r.get('price_date','')}</small></td>"
            f"<td class='{chg_cls}' style='text-align:center'>{chg_sign}{abs(r['chg']):.1f}%</td>"
            f"<td style='text-align:center'>{r['rsi']:.0f}</td>"
            f"<td style='text-align:center'>{r['adx']:.0f}</td>"
            f"<td style='text-align:right'>{stop:,.0f}</td>"
            f"<td style='color:#888;font-size:11px'>{pe_str} {roe_str}</td>"
            f"</tr>"
        )
    return (
        "<table><thead><tr>"
        "<th>#</th><th>종목</th><th>점수</th><th>현재가</th>"
        "<th>등락</th><th>RSI</th><th>ADX</th><th>손절가</th><th>펀더</th>"
        "</tr></thead><tbody>" + "".join(rows) + "</tbody></table>"
    )


def build_html_report(kospi_buy, kosdaq_buy, us_buy,
                      kospi_sell, kosdaq_sell, us_sell,
                      total: dict, fear_greed: dict,
                      claude_opinion: str,
                      perf_summary: str = "",
                      ipo_buy: list = None,
                      kr_etf_picks: list = None,
                      china_etf_picks: list = None,
                      reversal_picks: list = None,
                      trend_picks: list = None,
                      bearish_picks: list = None,
                      mdt_up_picks: list = None,
                      mdt_dn_picks: list = None,
                 corr_data: dict = None) -> str:
    """HTML 이메일 본문 생성."""
    now = datetime.datetime.now().strftime("%Y년 %m월 %d일 %H:%M")
    fg = fear_greed or {}
    fg_idx = fg.get("지수", "?")
    fg_txt = fg.get("해석", "")
    if isinstance(fg_idx, int):
        if fg_idx < 40:
            fg_cls = "fg-fear"
        elif fg_idx > 60:
            fg_cls = "fg-greed"
        else:
            fg_cls = "fg-mid"
    else:
        fg_cls = "fg-mid"

    def section(title: str, content: str) -> str:
        return (
            f"<div class='sec'>"
            f"<div class='sec-title'>{title}</div>"
            f"{content}</div>"
        )

    import html as _html

    # Claude 시장 총평 → 헤더 바로 아래 섹션
    market_summary = _extract_market_summary(claude_opinion or "")
    market_summary_esc = _html.escape(market_summary)

    sections = []
    if market_summary:
        sections.append(section("🌐 시장 총평 (Claude AI)",
                                 f"<div class='claude-box'>{market_summary_esc}</div>"))

    sections += [
        section("🇰🇷 코스피 매수 TOP", _html_stock_table(kospi_buy, "buy")),
        section("🇰🇷 코스닥 매수 TOP", _html_stock_table(kosdaq_buy, "buy")),
    ]
    if ipo_buy:
        sections.append(section("🆕 신규상장(IPO) 주목 TOP 5 — 최근 6개월 상장", _html_stock_table(ipo_buy, "buy")))

    # 바닥 반전 시그널 — 기존 stock table 포맷 사용
    if reversal_picks:
        sections.append(section(
            "🔄 기술적 반전 매수 시그널 (RSI+MACD+거래량 / ADX하락반전) — 한국만",
            "<p style='font-size:11px;color:#555'>기존 매수추천과 별도 — "
            "경로A(RSI+MACD+거래량) 또는 경로B(ADX하락반전) 충족</p>"
            + _html_stock_table(reversal_picks, "buy")))

    # 추세 매수 시그널 — LBR + 주봉 20MA 동시 충족
    if trend_picks:
        sections.append(section(
            "📈 추세 매수 시그널 (LBR 3/10 상승추세 + 주봉 20MA 우상향)",
            "<p style='font-size:11px;color:#555'>기존 매수추천과 별도 — "
            "LBR 3/10 상승추세 + 주봉 20주 이동평균 우상향 동시 충족</p>"
            + _html_stock_table(trend_picks, "buy")))

    # 2~3일 복합 추세 시그널
    if mdt_up_picks:
        sections.append(section(
            "📊 2~3일 상승 추세 형성 (가격↑ + RSI↑ + MACD↑ + 거래량)",
            "<p style='font-size:11px;color:#555'>최근 3일간 4개 조건 중 3개 이상 동시 충족</p>"
            + _html_stock_table(mdt_up_picks, "buy")))
    if mdt_dn_picks:
        sections.append(section(
            "📊 2~3일 하락 추세 형성 (가격↓ + RSI↓ + MACD↓ + 매도거래량)",
            "<p style='font-size:11px;color:#555'>최근 3일간 4개 조건 중 3개 이상 동시 충족</p>"
            + _html_stock_table(mdt_dn_picks, "sell")))

    sections += [
        section("🇺🇸 미국 매수 TOP",   _html_stock_table(us_buy, "buy")),
    ]
    sections += [
        section("🇰🇷 코스피 매도 TOP", _html_stock_table(kospi_sell, "sell")),
        section("🇰🇷 코스닥 매도 TOP", _html_stock_table(kosdaq_sell, "sell")),
        section("🇺🇸 미국 매도 TOP",   _html_stock_table(us_sell, "sell")),
    ]

    # 천장 반전 시그널 — 기존 stock table 포맷 사용
    if bearish_picks:
        sections.append(section(
            "📉 기술적 반전 매도 시그널 (RSI 과열 + MACD 데드크로스 + 거래량 없는 반등)",
            "<p style='font-size:11px;color:#555'>기존 매도추천과 별도 — "
            "4가지 기술적 천장 조건 동시 충족</p>"
            + _html_stock_table(bearish_picks, "sell")))

    # 국내 유망 ETF TOP 5
    if kr_etf_picks:
        rows = []
        for i, etf in enumerate(kr_etf_picks, 1):
            d1_icon  = "▲" if etf["d1"]  >= 0 else "▼"
            d5_icon  = "▲" if etf["d5"]  >= 0 else "▼"
            d20_icon = "▲" if etf["d20"] >= 0 else "▼"
            d1_cls  = "pos" if etf["d1"]  >= 0 else "neg"
            d5_cls  = "pos" if etf["d5"]  >= 0 else "neg"
            d20_cls = "pos" if etf["d20"] >= 0 else "neg"
            rows.append(
                f"<tr><td>{i}</td><td>{_html.escape(etf['name'])}</td>"
                f"<td>{etf['ticker']}</td><td style='text-align:right'>{etf['price']:,.0f}</td>"
                f"<td class='{d1_cls}'>{d1_icon}{abs(etf['d1']):.2f}%</td>"
                f"<td class='{d5_cls}'>{d5_icon}{abs(etf['d5']):.2f}%</td>"
                f"<td class='{d20_cls}'>{d20_icon}{abs(etf['d20']):.2f}%</td>"
                f"<td style='font-size:11px'>{' / '.join(etf['holdings'][:3])}</td></tr>"
            )
        etf_html = (
            "<table style='width:100%;border-collapse:collapse;font-size:12px'>"
            "<tr style='background:#f0f0f0'><th>#</th><th>ETF명</th><th>티커</th>"
            "<th>현재가</th><th>전일</th><th>5일</th><th>20일</th><th>주요 구성</th></tr>"
            + "".join(rows) + "</table>"
        )
        sections.append(section("📦 국내 유망 ETF TOP 5 (모멘텀 기준)", etf_html))

    # 중국 ETF 추천 TOP 5
    if china_etf_picks:
        rows = []
        for i, etf in enumerate(china_etf_picks, 1):
            d1_icon  = "▲" if etf["d1"]  >= 0 else "▼"
            d5_icon  = "▲" if etf["d5"]  >= 0 else "▼"
            d20_icon = "▲" if etf["d20"] >= 0 else "▼"
            d1_cls  = "pos" if etf["d1"]  >= 0 else "neg"
            d5_cls  = "pos" if etf["d5"]  >= 0 else "neg"
            d20_cls = "pos" if etf["d20"] >= 0 else "neg"
            rows.append(
                f"<tr><td>{i}</td><td>{_html.escape(etf['name'])}</td>"
                f"<td>{etf['ticker']}</td><td style='text-align:right'>{etf['price']:,.0f}</td>"
                f"<td class='{d1_cls}'>{d1_icon}{abs(etf['d1']):.2f}%</td>"
                f"<td class='{d5_cls}'>{d5_icon}{abs(etf['d5']):.2f}%</td>"
                f"<td class='{d20_cls}'>{d20_icon}{abs(etf['d20']):.2f}%</td>"
                f"<td style='font-size:11px'>{' / '.join(etf['holdings'][:3])}</td></tr>"
            )
        china_html = (
            "<table style='width:100%;border-collapse:collapse;font-size:12px'>"
            "<tr style='background:#f0f0f0'><th>#</th><th>ETF명</th><th>티커</th>"
            "<th>현재가</th><th>전일</th><th>5일</th><th>20일</th><th>주요 구성</th></tr>"
            + "".join(rows) + "</table>"
            "<div style='margin-top:6px;font-size:11px;color:#c00'>⚠️ 중국 ETF 리스크: 위안화 환율 변동성 / 중국 정책 리스크 / 지리적 긴장</div>"
        )
        sections.append(section("🇨🇳 중국 ETF 추천 TOP 5 (모멘텀 기준)", china_html))

    # 성과 요약 (있을 때만)
    if perf_summary:
        perf_esc = _html.escape(perf_summary)
        sections.append(section("📈 최근 30일 성과",
                                 f"<div class='perf-box'><pre style='margin:0;font-size:11px'>{perf_esc}</pre></div>"))

    body = "".join(sections)
    def _s(mkt):
        v = total.get(mkt, 0); p = total.get(f"{mkt}_pool", 0)
        return f"{v}/{p}개" if p else f"{v}개"
    scan_info = f"스캔: 코스피 {_s('KOSPI')} | 코스닥 {_s('KOSDAQ')} | 미국 {_s('US')}"

    return f"""<!DOCTYPE html>
<html lang="ko"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>AI 주식 스크리닝 v4</title>
<style>{_HTML_CSS}</style></head>
<body><div class="wrap">
<div class="hdr">
  <h1>📊 AI 주식 스크리닝 v4 &nbsp;&nbsp;{now}</h1>
  <div class="sub">{scan_info}</div>
  <span class="{fg_cls} fg-bar">Fear&amp;Greed {fg_idx}/100 — {fg_txt}</span>
</div>
{body}
<div class="ftr">⚠️ 기술적·펀더멘털 분석 참고용 / 투자 손익 책임은 본인에게 있습니다.</div>
</div></body></html>"""


# ═══════════════════════════════════════════════════════════════
# 이메일 / 텔레그램
# ═══════════════════════════════════════════════════════════════

def send_email(report_text: str, html_report: str = ""):
    if not EMAIL_USER or not EMAIL_PASS:
        print("[이메일] EMAIL_USER / EMAIL_PASS 미설정 — 건너뜀")
        return
    try:
        msg = MIMEText(report_text, "plain", "utf-8")
        msg["Subject"] = (
            f"AI 주식 v4 {datetime.datetime.now().strftime('%Y-%m-%d')} "
            f"| 기술+펀더멘털+Fear&Greed"
        )
        msg["From"] = EMAIL_FROM
        msg["To"]   = EMAIL_TO
        with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as srv:
            srv.starttls()
            srv.login(EMAIL_USER, EMAIL_PASS)
            srv.sendmail(EMAIL_FROM, EMAIL_TO, msg.as_string())
        print(f"[이메일] ✅ {EMAIL_TO} 텍스트 발송 완료")
    except Exception as e:
        print(f"[이메일] ❌ 실패: {e}")


def send_telegram(kospi_buy, kosdaq_buy, us_buy, kospi_sell, kosdaq_sell, us_sell,
                  fear_greed: dict):
    """텔레그램 봇으로 스크리닝 요약 발송"""
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        print("[텔레그램] TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_ID 미설정 — 건너뜀")
        return

    today = datetime.datetime.now().strftime("%m/%d")
    lines = [f"<b>📊 [{today}] AI 주식 v4</b>"]

    if fear_greed:
        lines.append(f"😱 Fear&Greed: {fear_greed['지수']}/100 {fear_greed['해석']}")

    for header, stocks in [
        ("🇰🇷 코스피 매수", kospi_buy),
        ("🇰🇷 코스닥 매수", kosdaq_buy),
        ("🇺🇸 미국 매수",   us_buy),
    ]:
        lines.append(f"\n<b>{header}</b>")
        for i, r in enumerate(stocks, 1):
            stop = round(r["price"] - 2.0 * r["atr"], 2)
            lines.append(f"  {i}. {r['name']} {r['score']:+.1f}점 "
                         f"RSI:{r['rsi']:.0f} 손절:{stop:,.0f}")

    lines.append("\n─────────────")
    for header, stocks in [
        ("🇰🇷 코스피 매도", kospi_sell),
        ("🇰🇷 코스닥 매도", kosdaq_sell),
        ("🇺🇸 미국 매도",   us_sell),
    ]:
        lines.append(f"\n<b>{header}</b>")
        for i, r in enumerate(stocks, 1):
            lines.append(f"  {i}. {r['name']} {r['score']:+.1f}점 "
                         f"RSI:{r['rsi']:.0f} {r['chg']:+.1f}%")

    lines.append("\n📄 상세 내용은 이메일 확인")
    text = "\n".join(lines)
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
        resp = requests.post(
            url,
            json={"chat_id": TELEGRAM_CHAT_ID, "text": text, "parse_mode": "HTML"},
            timeout=10,
        )
        if resp.status_code == 200:
            print("[텔레그램] ✅ 발송 완료")
        else:
            print(f"[텔레그램] ❌ {resp.status_code}: {resp.text[:200]}")
    except Exception as e:
        print(f"[텔레그램] ❌ {e}")


# ═══════════════════════════════════════════════════════════════
# 메인
# ═══════════════════════════════════════════════════════════════

def main():
    start = datetime.datetime.now()
    print(f"\n🚀 AI 주식 스크리닝 v4 시작 — {start.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"   [신규] ATR손절가 / 스토캐스틱 / ADX / OBV / 52주위치 / 펀더멘털 / Fear&Greed\n")

    # 캐시 자동 정리 (7일 이상 된 Claude 캐시 / 3일 이상 된 스크리닝 캐시)
    try:
        from token_cache import clear_old_cache
        deleted = clear_old_cache(7)
        if deleted > 0:
            print(f"  🧹 오래된 Claude 캐시 {deleted}개 삭제")
    except Exception:
        pass
    _clean_old_screening_caches(max_days=3)

    # ① 기술적 스크리닝 (오늘 캐시 있으면 가격 검증 후 재사용)
    print("① 전 종목 기술적 스크리닝...")
    cached_screening = _load_screening_cache()
    if cached_screening:
        # 캐시 가격 sanity check: 상위 5개 종목의 가격을 5d 데이터로 검증
        _cache_ok = True
        _check_tickers = []
        for mkt in ("KOSPI", "KOSDAQ", "US"):
            for r in cached_screening.get(mkt, [])[:2]:
                _check_tickers.append((r.get("ticker", ""), r.get("price", 0)))
        for _tk, _cached_p in _check_tickers[:5]:
            if not _tk or _cached_p <= 0:
                _cache_ok = False
                break
            try:
                _df5 = yf.Ticker(_tk).history(period="5d", timeout=8)
                if _df5 is not None and not _df5.empty:
                    _df5v = _df5[_df5["Volume"] > 0] if "Volume" in _df5.columns else _df5
                    if not _df5v.empty:
                        _ref = float(_df5v["Close"].iloc[-1])
                        if _ref > 0 and abs(_cached_p - _ref) / _ref > 0.15:
                            print(f"  ⚠️ 캐시 가격 불일치: {_tk} "
                                  f"캐시={_cached_p:,.0f} vs 실제={_ref:,.0f} → 캐시 무효화")
                            _cache_ok = False
                            break
            except Exception:
                pass
        if _cache_ok:
            all_results = cached_screening
            print("   (캐시 재사용 — yfinance 재수집 생략)")
        else:
            print("   ⚠️ 캐시 가격 이상 감지 → 전체 재스크리닝")
            cached_screening = {}
    if not cached_screening:
        all_results = run_screening()
        all_results = validate_and_fix(all_results)

        # ② 상위 후보 펀더멘털 보강 (매수 후보 20개 대상)
        print("\n② 상위 후보 펀더멘털 보강...")
        for market in ["KOSPI", "KOSDAQ", "US"]:
            top_n = 10  # 20→10: 펀더멘털 수집 시간 절반 단축
            enriched = enrich_with_fundamentals(all_results[market][:top_n])
            enriched.sort(key=lambda x: x["score"], reverse=True)
            all_results[market][:top_n] = enriched
        print("   ✓ 펀더멘털 점수 반영 완료")
        _save_screening_cache(all_results)

    # ③ 보조 데이터 수집 (병렬, 항상 신규 수집 — 재시도 2회) — 선별 전 실시
    print("\n③ 거시·심리·섹터·뉴스 수집 (실시간, 선별 전)...")
    results_bag = {}
    _EMPTY = {"macro": {}, "fear": {}, "sector": {}, "overseas": {}, "news": [], "kr_etf": [], "china_etf": []}

    def _collect_with_retry(key, fn, retries=2):
        empty = _EMPTY[key]
        for attempt in range(retries):
            try:
                result = fn()
                if result:
                    results_bag[key] = result
                    return
            except Exception:
                pass
        results_bag[key] = empty
        print(f"   ⚠️ [{key}] 수집 실패 — {retries}회 재시도 후 빈 데이터")

    threads = [
        threading.Thread(target=_collect_with_retry, args=("macro",    collect_macro)),
        threading.Thread(target=_collect_with_retry, args=("fear",     collect_fear_greed)),
        threading.Thread(target=_collect_with_retry, args=("sector",   collect_sector_flows)),
        threading.Thread(target=_collect_with_retry, args=("overseas", collect_overseas_snapshot)),
        threading.Thread(target=_collect_with_retry, args=("news",     collect_news)),
        threading.Thread(target=_collect_with_retry, args=("kr_etf",   collect_kr_etf_picks)),
        threading.Thread(target=_collect_with_retry, args=("china_etf", collect_china_etf_picks)),
    ]
    for t in threads: t.start()
    for t in threads: t.join()

    macro        = results_bag.get("macro", {})
    fear_greed   = results_bag.get("fear", {})
    sector_flows = results_bag.get("sector", {})
    overseas     = results_bag.get("overseas", {})
    news         = results_bag.get("news", [])
    kr_etf_picks = results_bag.get("kr_etf", [])
    china_etf_picks = results_bag.get("china_etf", [])

    # 수집 결과 검증
    fg_str = f"Fear&Greed:{fear_greed.get('지수','?')}" if fear_greed else "Fear&Greed:❌미수집"
    print(f"   거시 {len(macro)}개 | {fg_str} | 섹터ETF {len(sector_flows)}개 | 뉴스 {len(news)}건")
    if not macro:      print("   ⚠️ 거시지표 미수집 — Claude 분석 정확도 저하 가능")
    if not fear_greed: print("   ⚠️ Fear&Greed 미수집 — Claude 분석 정확도 저하 가능")

    # ③-b 거시 레짐 평가 → 전 종목 점수 보정
    print("\n③-b 거시 레짐 평가...")
    macro_regime = compute_macro_regime(macro, fear_greed, sector_flows)
    adj = macro_regime["score_adjustment"]

    # 과거 승률 피드백 — DB에서 5일 매수 승률 조회해 추가 보정
    try:
        from performance_tracker import verify_past_recommendations
        _vr = verify_past_recommendations()
        _p5 = _vr.get("by_period", {}).get(5, {})
        buy_wr_hist  = _p5.get("buy_win_rate",  50.0)
        sell_wr_hist = _p5.get("sell_win_rate", 50.0)
        macro_regime["buy_win_rate"]  = buy_wr_hist
        macro_regime["sell_win_rate"] = sell_wr_hist
        if buy_wr_hist < 40:
            adj -= 5
            macro_regime["reasons"].append(f"최근 5일 매수승률 {buy_wr_hist:.0f}% → 추가 -5")
        if sell_wr_hist > 65:
            adj -= 3   # 전체 score 하향 → sell pool 강화
            macro_regime["reasons"].append(f"최근 5일 매도승률 {sell_wr_hist:.0f}% → 추가 -3")
    except Exception:
        macro_regime["buy_win_rate"]  = None
        macro_regime["sell_win_rate"] = None

    macro_regime["applied_adjustment"] = adj
    print(f"   레짐: {macro_regime['regime']} (레짐점수:{macro_regime['regime_score']:+d}"
          f", 점수보정:{adj:+d})")
    for r in macro_regime["reasons"]:
        print(f"   · {r}")

    # ③-c 지정학 리스크 인덱스 (GRI)
    from geopolitical_risk_engine import (
        compute_geopolitical_risk_index,
        compute_crash_recovery_signal,
        apply_sector_differential_adjustment,
        get_war_beneficiary_watchlist,
        format_gri_summary,
        format_gri_for_claude,
    )
    gri = compute_geopolitical_risk_index(macro, sector_flows)
    print(f"\n③-c 지정학 리스크: GRI {gri['gri_score']}/100 [{gri['gri_label']}]")
    comps = gri.get("components", {})
    comp_parts = []
    for cn, cd in comps.items():
        if cd.get("score", 0) > 0:
            comp_parts.append(f"{cn}={cd['score']}")
    if comp_parts:
        print(f"   구성: {' | '.join(comp_parts)}")
    adj_parts = [f"{k}:{v:+d}" for k, v in gri["sector_adjustments"].items()
                 if k != "default" and v != 0]
    if adj_parts:
        print(f"   섹터보정: {' / '.join(adj_parts)}")

    # ③-d 급락 반등 시그널
    recovery = compute_crash_recovery_signal(macro, fear_greed)
    if recovery["recovery_active"]:
        print(f"   반등시그널: {recovery['signals_fired']} -> 전종목 +{recovery['recovery_adjustment']}점")
    elif recovery["signals_fired"]:
        print(f"   반등징후(약): {recovery['signals_fired']} (2개 미만, 보너스 미적용)")

    # 섹터별 차등 보정 적용 (기존 균일 보정 대체)
    apply_sector_differential_adjustment(all_results, gri, recovery, adj)
    print(f"   ✓ 섹터별 차등 보정 완료 (기본:{adj:+d} + 섹터별 + 반등:{recovery.get('recovery_adjustment', 0):+d})")

    # ③-d 국면별 가중치 적용 (레짐에 따라 지표 가중치 재계산)
    _regime_name = macro_regime["regime"]
    if _regime_name != "중립":
        _rwc = apply_regime_weights(all_results, _regime_name)
        if _rwc:
            print(f"   ✓ 국면별 가중치 적용: {_regime_name} → {_rwc}개 종목 점수 재계산")
            for mkt in all_results:
                all_results[mkt].sort(key=lambda x: x["score"], reverse=True)

    # 전쟁 수혜주 워치리스트 — high_escalation 시 +5 보너스
    war_watchlist = get_war_beneficiary_watchlist(gri)
    if war_watchlist:
        war_tickers = {w["ticker"].split(".")[0].upper() for w in war_watchlist}
        if gri["gri_label"] == "high_escalation":
            war_boosted = 0
            for mkt in all_results:
                for r in all_results[mkt]:
                    tk = r["ticker"].split(".")[0].upper()
                    if tk in war_tickers:
                        r["score"] += 5
                        r["_war_bonus"] = 5
                        war_boosted += 1
            print(f"   전쟁 수혜주 워치리스트: {len(war_watchlist)}개 (high_escalation → {war_boosted}개 +5점)")
        else:
            print(f"   전쟁 수혜주 워치리스트: {len(war_watchlist)}개 (보너스 미적용: {gri['gri_label']})")

    # ④ 외부 변수 로드
    external_events = load_external_events()
    if external_events:
        print(f"\n   외부 변수 {len(external_events)}개 로드됨:")
        for ev in external_events:
            print(f"   · [{ev['category']}] {ev['title']} → {ev['impact']}")
    else:
        print("\n   외부 변수 없음 (추가: python external_events.py add)")

    # ④-a 유명 투자자 포트폴리오 수집 → 선별 전 가산점 반영
    print("\n④ 유명 투자자 포트폴리오 + 국내 테마 수집 (선별 전)...")
    investor_summary = collect_investor_summary()
    if investor_summary:
        print(f"   ✓ 투자자 {len(investor_summary)}명 포트폴리오 로드")
        # 투자자 관심 종목 세트 (단축 티커, e.g. 'NVDA', '005930')
        investor_tickers: set = set()
        for inv, picks in investor_summary.items():
            for t, note, w in picks:
                investor_tickers.add(t.upper())
        # 가산점 +5 부여 후 재정렬
        boosted = 0
        for market in all_results:
            for r in all_results[market]:
                tk_base = r["ticker"].split(".")[0].upper()
                if tk_base in investor_tickers or r["ticker"].upper() in investor_tickers:
                    r["score"] = r["score"] + 5
                    boosted += 1
            all_results[market].sort(key=lambda x: x["score"], reverse=True)
        if boosted:
            print(f"   ✓ 투자자 관심 종목 {boosted}개 가산점(+5) 반영 → 풀 재정렬")

    # ④-b 국내 테마별 상위 종목 추출
    theme_picks = get_theme_picks(all_results)
    if theme_picks:
        print(f"   ✓ 국내 테마 {len(theme_picks)}개 상위 종목 추출")

    # ④-c IPO 신규상장 가산점 (+10) — 데이터 부족 불이익 보완
    if all_results.get("IPO"):
        for r in all_results["IPO"]:
            r["score"] = r["score"] + 10
        all_results["IPO"].sort(key=lambda x: x["score"], reverse=True)
        print(f"   ✓ 신규상장 IPO {len(all_results['IPO'])}개 +10점 보정")

    # ⑤ Claude 심층 분석 — 최종 선별 전, 확대 후보군(TOP 10) 기반
    _PRE_N = {"KOSPI": 10, "KOSDAQ": 6, "US": 10}
    total_valid = sum(len(v) for k, v in all_results.items() if k != "IPO")
    print(f"\n⑤ Claude 심층 분석 (총 {total_valid}개 유효 종목 중 확대 후보 분석)...")
    kospi_pre      = all_results["KOSPI"][:_PRE_N["KOSPI"]]
    kosdaq_pre     = all_results["KOSDAQ"][:_PRE_N["KOSDAQ"]]
    us_pre         = all_results["US"][:_PRE_N["US"]]
    ipo_pre        = all_results.get("IPO", [])[:8]  # Claude 분석 별도 — 점수순 선별
    kospi_sell_pre  = all_results["KOSPI"][-_PRE_N["KOSPI"]:][::-1]
    kosdaq_sell_pre = all_results["KOSDAQ"][-_PRE_N["KOSDAQ"]:][::-1]
    us_sell_pre     = all_results["US"][-_PRE_N["US"]:][::-1]

    claude_opinion = ask_claude_v4(
        kospi_pre, kosdaq_pre, us_pre,
        kospi_sell_pre, kosdaq_sell_pre, us_sell_pre,
        macro, news, overseas, fear_greed, sector_flows,
        external_events=external_events,
        investor_summary=investor_summary,
        theme_picks=theme_picks,
        gri=gri, recovery=recovery, war_watchlist=war_watchlist,
    )

    # ⑥ 최종 선별 — Claude 추천 종목에 보너스 반영 후 종합점수 순 정렬
    # ─────────────────────────────────────────────────────────────────
    # 순위 결정 단일 기준: 종합점수 = 기술점수 + 펀더멘털 + 레짐보정 + 투자자가산 + Claude보너스
    # Claude 추천 종목: +20점 보너스 추가 후 재정렬 → 점수가 곧 순위의 근거
    # Claude 미추천 슬롯: 보너스 없이 점수순으로 자연스럽게 편입
    # ─────────────────────────────────────────────────────────────────
    print("\n⑥ 최종 선별 (Claude 보너스 반영 → 종합점수 순 정렬)...")
    claude_buy_tickers  = [x["ticker"] for x in _last_claude_structured.get("top_buy",  [])]
    claude_sell_tickers = [x["ticker"] for x in _last_claude_structured.get("top_sell", [])]
    _CLAUDE_BUY_BONUS  = 20   # Claude 매수 추천 가산점
    _CLAUDE_SELL_BONUS = 20   # Claude 매도 추천 가산점

    def _apply_claude_bonus(pool: list, claude_tickers: list, bonus: int) -> list:
        """Claude 추천 종목에 보너스 추가 후 종합점수 내림차순 재정렬.
        rank_source 필드: 'Claude추천' | '점수순' — 리포트 순위 근거 표시용."""
        claude_set = set(claude_tickers)
        for r in pool:
            if r["ticker"] in claude_set:
                r["score"]       = r["score"] + bonus
                r["rank_source"] = "Claude추천"
            else:
                r.setdefault("rank_source", "점수순")
        return sorted(pool, key=lambda x: x["score"], reverse=True)

    kospi_pre       = _apply_claude_bonus(kospi_pre,       claude_buy_tickers,  _CLAUDE_BUY_BONUS)
    kosdaq_pre      = _apply_claude_bonus(kosdaq_pre,      claude_buy_tickers,  _CLAUDE_BUY_BONUS)
    us_pre          = _apply_claude_bonus(us_pre,          claude_buy_tickers,  _CLAUDE_BUY_BONUS)
    ipo_pre         = _apply_claude_bonus(ipo_pre,         claude_buy_tickers,  _CLAUDE_BUY_BONUS)
    kospi_sell_pre  = _apply_claude_bonus(kospi_sell_pre,  claude_sell_tickers, _CLAUDE_SELL_BONUS)
    kosdaq_sell_pre = _apply_claude_bonus(kosdaq_sell_pre, claude_sell_tickers, _CLAUDE_SELL_BONUS)
    us_sell_pre     = _apply_claude_bonus(us_sell_pre,     claude_sell_tickers, _CLAUDE_SELL_BONUS)

    _MIN_BUY_SCORE = 38   # 연속점수 전환 후 하향 조정
    kospi_buy   = [r for r in kospi_pre  if r["score"] >= _MIN_BUY_SCORE][:RECOMMEND_COUNT["KOSPI"]]
    kosdaq_buy  = [r for r in kosdaq_pre if r["score"] >= _MIN_BUY_SCORE][:RECOMMEND_COUNT["KOSDAQ"]]
    us_buy      = [r for r in us_pre     if r["score"] >= _MIN_BUY_SCORE][:RECOMMEND_COUNT["US"]]
    # IPO: 데이터 부족으로 점수 임계값 없이 상위 5개 선정 (점수순 정렬)
    ipo_buy     = ipo_pre[:5]
    kospi_sell  = kospi_sell_pre[:SELL_COUNT["KOSPI"]]
    kosdaq_sell = kosdaq_sell_pre[:SELL_COUNT["KOSDAQ"]]
    us_sell     = us_sell_pre[:SELL_COUNT["US"]]

    claude_cnt = sum(1 for r in kospi_buy + kosdaq_buy + us_buy
                     if r.get("rank_source") == "Claude추천")
    score_cnt  = sum(1 for r in kospi_buy + kosdaq_buy + us_buy
                     if r.get("rank_source") == "점수순")
    if claude_buy_tickers:
        print(f"   Claude 보너스(+{_CLAUDE_BUY_BONUS}) 적용: Claude추천 {claude_cnt}개 / 점수순 {score_cnt}개")
    else:
        print("   Claude JSON 없음 — 점수 순 유지")
    print(f"   매수: 코스피 {len(kospi_buy)} | 코스닥 {len(kosdaq_buy)} | 미국 {len(us_buy)} | IPO {len(ipo_buy)}")
    print(f"   매도: 코스피 {len(kospi_sell)} | 코스닥 {len(kosdaq_sell)} | 미국 {len(us_sell)}")

    # ⑥-b 반전 시그널 종목 수집 (전 시장)
    all_flat = []
    for mkt_list in all_results.values():
        all_flat.extend(mkt_list)
    reversal_picks = [r for r in all_flat if r.get("reversal_signal") and r["market"] != "US"]
    reversal_picks.sort(key=lambda x: x["score"], reverse=True)
    reversal_picks = reversal_picks[:10]
    if reversal_picks:
        print(f"   🔄 바닥 반전(매수) 시그널: {len(reversal_picks)}개 탐지")

    # 추세 매수 시그널: LBR 추세 + 주봉 20MA 우상향 동시 충족 종목
    trend_picks = [r for r in all_flat
                   if r.get("lbr_trending") and r.get("weekly_ma20_rising")
                   and r["score"] > 0]
    trend_picks.sort(key=lambda x: x["score"], reverse=True)
    trend_picks = trend_picks[:10]
    if trend_picks:
        print(f"   📈 추세 매수 시그널 (LBR+주봉MA20): {len(trend_picks)}개 탐지")

    bearish_picks = [r for r in all_flat if r.get("bearish_signal")]
    bearish_picks.sort(key=lambda x: x["score"])  # 점수 낮은 순 (매도 우선)
    bearish_picks = bearish_picks[:10]
    if bearish_picks:
        print(f"   📉 천장 반전(매도) 시그널: {len(bearish_picks)}개 탐지")

    # 2~3일 복합 추세 시그널
    mdt_up_picks = [r for r in all_flat
                    if r.get("multi_day_trend") and r["multi_day_trend"]["direction"] == "up"]
    mdt_up_picks.sort(key=lambda x: x["score"], reverse=True)
    mdt_up_picks = mdt_up_picks[:10]
    mdt_dn_picks = [r for r in all_flat
                    if r.get("multi_day_trend") and r["multi_day_trend"]["direction"] == "down"]
    mdt_dn_picks.sort(key=lambda x: x["score"])
    mdt_dn_picks = mdt_dn_picks[:10]
    if mdt_up_picks:
        print(f"   📊 2~3일 상승 추세 형성: {len(mdt_up_picks)}개 탐지")
    if mdt_dn_picks:
        print(f"   📊 2~3일 하락 추세 형성: {len(mdt_dn_picks)}개 탐지")

    # ⑥-c 상관관계 분석 (매수/매도 후보 vs 벤치마크)
    print("   상관관계 분석 중...")
    _corr_candidates = (kospi_buy + kosdaq_buy + us_buy +
                        kospi_sell + kosdaq_sell + us_sell)[:20]
    corr_data = {}
    try:
        corr_data = compute_correlations(_corr_candidates)
        decoup_cnt = sum(1 for v in corr_data.values() if v.get("decoupling"))
        print(f"   ✓ 상관관계 {len(corr_data)}개 종목 | 디커플링 {decoup_cnt}개 감지")
    except Exception as e:
        print(f"   ⚠️ 상관관계 분석 실패: {e}")

    # ⑥ 리포트 저장
    _gri_summary = format_gri_summary(gri, recovery)
    _total_dict = {**{k: len(v) for k, v in all_results.items()},
                   **{f"{k}_pool": v for k, v in _last_pool_sizes.items()}}
    report = build_report(
        kospi_buy, kosdaq_buy, us_buy,
        kospi_sell, kosdaq_sell, us_sell,
        _total_dict,
        fear_greed, claude_opinion,
        investor_summary=investor_summary,
        theme_picks=theme_picks,
        macro_regime=macro_regime,
        kr_etf_picks=kr_etf_picks,
        china_etf_picks=china_etf_picks,
        ipo_buy=ipo_buy,
        reversal_picks=reversal_picks,
        trend_picks=trend_picks,
        bearish_picks=bearish_picks,
        gri_summary=_gri_summary,
        mdt_up_picks=mdt_up_picks,
        mdt_dn_picks=mdt_dn_picks,
        corr_data=corr_data,
    )
    with open(REPORT_PATH, "w", encoding="utf-8") as f:
        f.write(report)
    print(f"⑦ 리포트 저장: {REPORT_PATH}")

    # 성능 추적 + 성과 요약
    perf_summary = ""
    verification_section = ""
    print("\n⑧ 성능 추적 업데이트...")
    try:
        from performance_tracker import (
            init_database, save_daily_recommendations,
            update_price_tracking, generate_performance_report,
            format_verification_section,
        )
        init_database()
        today_str = datetime.datetime.now().strftime("%Y-%m-%d")
        save_daily_recommendations(today_str, {
            "kospi_buy": kospi_buy, "kospi_sell": kospi_sell,
            "kosdaq_buy": kosdaq_buy, "kosdaq_sell": kosdaq_sell,
            "us_buy": us_buy, "us_sell": us_sell,
            "ipo_buy": ipo_buy,
        })
        # 먼저 누락된 day_after를 채운 뒤 성과 리포트 생성
        update_price_tracking()
        # 30일 성과 요약 생성
        perf_summary = generate_performance_report(30)
        perf_path = os.path.join(BASE_DIR, "performance_report.txt")
        with open(perf_path, "w", encoding="utf-8") as f:
            f.write(perf_summary)
        # 추천 검증 섹션 생성 후 리포트에 반영
        verification_section = format_verification_section()
        if verification_section:
            updated_report = build_report(
                kospi_buy, kosdaq_buy, us_buy,
                kospi_sell, kosdaq_sell, us_sell,
                _total_dict,
                fear_greed, claude_opinion,
                investor_summary=investor_summary,
                theme_picks=theme_picks,
                verification_section=verification_section,
                macro_regime=macro_regime,
                kr_etf_picks=kr_etf_picks,
                china_etf_picks=china_etf_picks,
                ipo_buy=ipo_buy,
                reversal_picks=reversal_picks,
                trend_picks=trend_picks,
                bearish_picks=bearish_picks,
                gri_summary=_gri_summary,
                mdt_up_picks=mdt_up_picks,
                mdt_dn_picks=mdt_dn_picks,
                corr_data=corr_data,
            )
            with open(REPORT_PATH, "w", encoding="utf-8") as f:
                f.write(updated_report)
            report = updated_report
        print(f"   ✓ 성능 추적 완료 / 성과 리포트: {perf_path}")
    except Exception as e:
        print(f"   ⚠️ 성능 추적 실패: {e}")

    # ⑧ HTML 이메일 빌드
    html_report = build_html_report(
        kospi_buy, kosdaq_buy, us_buy,
        kospi_sell, kosdaq_sell, us_sell,
        {k: len(v) for k, v in all_results.items()},
        fear_greed, claude_opinion,
        perf_summary=perf_summary,
        ipo_buy=ipo_buy,
        kr_etf_picks=kr_etf_picks,
        china_etf_picks=china_etf_picks,
        reversal_picks=reversal_picks,
        trend_picks=trend_picks,
        bearish_picks=bearish_picks,
        mdt_up_picks=mdt_up_picks,
        mdt_dn_picks=mdt_dn_picks,
    )
    html_path = os.path.join(BASE_DIR, "report_v4.html")
    with open(html_path, "w", encoding="utf-8") as f:
        f.write(html_report)
    print(f"⑨ HTML 리포트 저장: {html_path}")

    # 알림 발송
    print("\n⑩ 알림 발송...")
    send_email(report, html_report=html_report)
    send_telegram(kospi_buy, kosdaq_buy, us_buy, kospi_sell, kosdaq_sell, us_sell, fear_greed)

    elapsed = int((datetime.datetime.now() - start).total_seconds())
    print(f"\n✅ 완료! 소요시간 {elapsed // 60}분 {elapsed % 60}초\n")


# ═══════════════════════════════════════════════════════════════
# 테마별 유니버스 필터
# ═══════════════════════════════════════════════════════════════

_THEMES: dict = {
    "ai": {
        "desc": "AI·반도체·클라우드",
        "tickers": {
            "NVDA","AMD","AVGO","TSM","INTC","QCOM","AMAT","LRCX","KLAC","MU",
            "SNOW","DDOG","PLTR","NOW","CRWD","PANW","MSFT","GOOGL","META","AMZN",
            "005930.KS","000660.KS","009150.KS","011070.KS","042700.KS",  # 반도체 KR
            "CRWV","CBRS",  # AI IPO
        },
    },
    "defense": {
        "desc": "방위산업",
        "tickers": {
            "LMT","RTX","GD","NOC","BA","HII","LDOS",
            "012450.KS","079550.KS","047810.KS","034020.KS",  # 한화에어로, LIG, KAI, 두산에너빌
            "214430.KQ","274090.KQ","065150.KQ","013810.KQ","010820.KQ",  # 코스닥 방산
            "099440.KQ",  # 쎄트렉아이
        },
    },
    "bio": {
        "desc": "바이오·헬스케어",
        "tickers": {
            "LLY","UNH","JNJ","PFE","MRNA","NVO","ABBV","MRK","ABT","REGN",
            "207940.KS","068270.KS","323410.KS",  # 삼성바이오, 셀트리온, 카카오뱅크
        },
    },
    "energy": {
        "desc": "에너지·전력",
        "tickers": {
            "XOM","CVX","COP","NEE","BP","SLB","EOG",
            "034020.KS","015760.KS","096770.KS","373220.KS","006400.KS","051910.KS",
        },
    },
    "finance": {
        "desc": "금융·핀테크",
        "tickers": {
            "JPM","GS","MS","BAC","WFC","V","MA","AXP","BLK","COIN","PYPL",
            "105560.KS","055550.KS","086790.KS","032830.KS","000810.KS",  # 금융 KR
            "KLAR",
        },
    },
    "kr": {"desc": "국내(코스피+코스닥) 전용", "suffix": (".KS", ".KQ")},
    "us": {"desc": "미국 전용",                "suffix": ("",)},
}


def _apply_theme(pool: dict, theme: str) -> dict:
    """pool {name: ticker}를 테마 기준으로 필터링."""
    if theme == "all" or theme not in _THEMES:
        return pool
    cfg = _THEMES[theme]
    if "suffix" in cfg:
        suffixes = cfg["suffix"]
        return {
            n: t for n, t in pool.items()
            if any(t.endswith(s) for s in suffixes)
            or (not suffixes[0] and not t.endswith((".KS", ".KQ")))
        }
    tickers = cfg.get("tickers", set())
    return {n: t for n, t in pool.items() if t in tickers}


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(
        description="AI 주식 스크리닝 v4",
        formatter_class=argparse.RawTextHelpFormatter,
    )
    parser.add_argument(
        "--theme",
        choices=["all", "ai", "defense", "bio", "energy", "finance", "kr", "us"],
        default="all",
        help=(
            "스크리닝 테마 선택 (기본: all)\n"
            + "\n".join(f"  {k:10s} — {v['desc']}" for k, v in _THEMES.items())
        ),
    )
    args = parser.parse_args()

    # 테마 적용: run_screening 내부 pool을 래핑
    if args.theme != "all":
        _orig_screen_one = screen_one
        _theme_cfg = _THEMES[args.theme]
        print(f"\n[테마] {args.theme} — {_theme_cfg['desc']}")

        _orig_run_screening = run_screening

        def run_screening():
            results = _orig_run_screening()
            # 테마 필터: 각 시장 결과를 ticker 기준으로 걸러냄
            cfg = _THEMES[args.theme]
            if "tickers" in cfg:
                keep = cfg["tickers"]
                for mkt in results:
                    results[mkt] = [r for r in results[mkt] if r["ticker"] in keep]
            elif "suffix" in cfg:
                suf = cfg["suffix"]
                for mkt in results:
                    results[mkt] = [
                        r for r in results[mkt]
                        if any(r["ticker"].endswith(s) for s in suf)
                        or (not suf[0] and not r["ticker"].endswith((".KS", ".KQ")))
                    ]
            return results

    main()
