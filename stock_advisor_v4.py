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
from universe import get_kr_pools, UNIVERSE
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
    "Visa":              "V",     "Mastercard":      "MA",
    "JPMorgan":          "JPM",   "Goldman Sachs":   "GS",
    "Berkshire B":       "BRK-B", "Johnson&Johnson": "JNJ",
    "Eli Lilly":         "LLY",   "UnitedHealth":    "UNH",
    "Exxon Mobil":       "XOM",   "Chevron":         "CVX",
    "Boeing":            "BA",    "Lockheed Martin": "LMT",
    "Caterpillar":       "CAT",   "Walmart":         "WMT",
    "Costco":            "COST",  "Walt Disney":     "DIS",
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

def _obv_trend(close: pd.Series, volume: pd.Series, n: int = 20) -> float:
    """
    OBV 추세: OBV가 20일 MA 대비 위에 있으면 양수, 아래면 음수
    상승 중 OBV 증가 = 강한 매수세 / 상승 중 OBV 감소 = 분산 경고
    """
    direction = close.diff().apply(lambda x: 1 if x > 0 else (-1 if x < 0 else 0))
    obv       = (volume * direction).cumsum()
    obv_ma    = obv.rolling(n).mean()
    diff      = (obv.iloc[-1] - obv_ma.iloc[-1]) / (obv_ma.iloc[-1].clip(1e-9))
    return round(float(diff), 4)

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
# 종합 스코어링
# ═══════════════════════════════════════════════════════════════

def score_technical(rsi, macd_hist, price, ma5, ma20, ma60, mom5,
                    stoch_k, adx, plus_di, minus_di, obv_trend, pos_52w) -> int:
    """
    기술적 종합 점수 –100 ~ +100
    v3 기존 지표 + ATR기반 ADX 신뢰도 + 스토캐스틱 + OBV + 52주 위치
    """
    s = 0

    # RSI (±35)
    if   rsi < 20: s += 35
    elif rsi < 30: s += 20
    elif rsi < 40: s +=  8
    elif rsi > 80: s -= 35
    elif rsi > 70: s -= 20
    elif rsi > 60: s -=  8

    # 스토캐스틱 (±10) — RSI와 교차 확인
    if   stoch_k < 20: s += 10
    elif stoch_k < 30: s +=  5
    elif stoch_k > 80: s -= 10
    elif stoch_k > 70: s -=  5

    # MACD 히스토그램 (±15)
    s += 15 if macd_hist > 0 else -15

    # 이동평균 정배열 (±15)
    if price > ma20 > ma60:   s += 15
    elif price > ma20:        s +=  7
    elif price < ma20 < ma60: s -= 15
    elif price < ma20:        s -=  7

    # MA5 vs MA20 (±8)
    s += 8 if ma5 > ma20 else -8

    # 5일 모멘텀 (±8)
    if   mom5 >  5: s +=  8
    elif mom5 >  2: s +=  4
    elif mom5 < -5: s -=  8
    elif mom5 < -2: s -=  4

    # ADX 추세 강도 보정 (신호 증폭/감쇠)
    # ADX > 25 = 추세 신뢰도 높음 → 신호 강화
    # ADX < 15 = 횡보 → 신호 약화
    if adx > 25:
        trend_dir = 1 if plus_di > minus_di else -1
        s += int(min(adx - 25, 20) * 0.2 * trend_dir)  # 최대 ±4
    elif adx < 15:
        s = int(s * 0.8)  # 횡보 시 신호 20% 감쇠

    # OBV 추세 (±5)
    if   obv_trend >  0.05: s +=  5
    elif obv_trend < -0.05: s -=  5

    # 52주 위치 (±5)
    if   pos_52w > 85: s +=  5   # 신고가 돌파 구간 — 모멘텀
    elif pos_52w < 15: s +=  3   # 52주 저점 — 반등 기대
    elif pos_52w > 70: s +=  2
    elif pos_52w < 30: s -=  2

    return max(-100, min(100, s))


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


def score_with_investor_weight(ticker: str, base_score: int) -> int:
    try:
        from investor_scorer import get_investor_score
        inv = get_investor_score(ticker.upper())
        bonus = 0
        if inv['is_pelosi_pick']:         bonus += inv['pelosi_score']
        if inv['is_ark_pick']:            bonus += inv['ark_score']
        if inv['is_korean_investor_pick']: bonus += inv['korean_investor_score']
        if inv['is_pelosi_pick'] and inv['is_ark_pick']: bonus += 5
        return max(-100, min(100, base_score + bonus))
    except Exception:
        return base_score


# ═══════════════════════════════════════════════════════════════
# 단일 종목 고속 스크리닝 (신규 지표 포함)
# ═══════════════════════════════════════════════════════════════
# Lock → Semaphore: 최대 8개 병렬 다운로드 허용 (기존 Lock은 사실상 순차 실행)
_YF_SEM = threading.Semaphore(8)

def screen_one(market: str, name: str, ticker: str) -> Optional[dict]:
    try:
        with _YF_SEM:
            df = yf.download(ticker, period="12mo", interval="1d",
                             progress=False, auto_adjust=True, timeout=10)
        if df is None or df.empty or len(df) < 65:
            return None

        df = data_cleaner.clean(df, ticker)
        if df is None:
            return None

        close  = df["Close"].squeeze()
        high   = df["High"].squeeze()
        low    = df["Low"].squeeze()
        volume = df["Volume"].squeeze() if "Volume" in df.columns else pd.Series([0]*len(df))

        price = float(close.iloc[-1])
        prev  = float(close.iloc[-2])
        chg   = round((price - prev) / prev * 100, 2)

        # ── 기존 지표 ──
        rsi               = _rsi(close)
        _, _, macd_hist   = _macd(close)
        ma5, ma20, ma60   = _mas(close)
        mom5              = _mom(close, 5)
        bb_up, bb_dn, bb_pct = _bb(close)

        # ── 신규 지표 ──
        atr_val             = _atr(high, low, close)
        atr_pct             = round(atr_val / price * 100, 2) if price > 0 else 0.0
        stoch_k, stoch_d    = _stochastic(high, low, close)
        adx_val, plus_di, minus_di = _adx(high, low, close)
        obv                 = _obv_trend(close, volume)
        pos_52w             = _week52_pos(close)

        vol_avg   = float(volume.rolling(20).mean().iloc[-1])
        vol_cur   = float(volume.iloc[-1])
        vol_ratio = round(vol_cur / (vol_avg + 1e-9), 2)

        # 기술적 점수
        tech_score = score_technical(
            rsi, macd_hist, price, ma5, ma20, ma60, mom5,
            stoch_k, adx_val, plus_di, minus_di, obv, pos_52w
        )
        # 투자자 가중치
        score = score_with_investor_weight(ticker, tech_score)

        return {
            "market": market, "name": name, "ticker": ticker,
            "price": round(price, 2), "chg": chg,
            # 기존
            "rsi": round(rsi, 1), "macd_hist": round(macd_hist, 4),
            "ma5": round(ma5, 2), "ma20": round(ma20, 2), "ma60": round(ma60, 2),
            "bb_up": bb_up, "bb_dn": bb_dn, "bb_pct": round(bb_pct, 1),
            "mom5": round(mom5, 2), "vol_ratio": vol_ratio,
            # 신규
            "atr": round(atr_val, 2), "atr_pct": atr_pct,
            "stoch_k": round(stoch_k, 1), "stoch_d": round(stoch_d, 1),
            "adx": round(adx_val, 1), "plus_di": round(plus_di, 1), "minus_di": round(minus_di, 1),
            "obv_trend": obv, "pos_52w": pos_52w,
            "score": score,
            "fund": {},  # 펀더멘털은 Phase 2에서 채움
        }
    except Exception:
        return None


# ═══════════════════════════════════════════════════════════════
# Phase 2: 상위 후보 펀더멘털 보강 (주 1회 캐시)
# ═══════════════════════════════════════════════════════════════

_FUND_CACHE: dict = {}           # {ticker: {"cached_at": ISO, "data": {...}}}
_FUND_CACHE_LOCK = threading.Lock()
_FUND_CACHE_DAYS = 7             # 7일(1주) 내 캐시 유효


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
    results = {"KOSPI": [], "KOSDAQ": [], "US": []}

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

    for market, pool, workers in [
        ("KOSPI",  kospi_pool,  8),
        ("KOSDAQ", kosdaq_pool, 6),
        ("US",     us_pool,     8),
    ]:
        print(f"  스크리닝: {market} ({len(pool)}개)...")
        tasks = [(market, n, t) for n, t in pool.items()]
        with ThreadPoolExecutor(max_workers=workers) as ex:
            futs = {ex.submit(screen_one, m, n, t): (m, n, t) for m, n, t in tasks}
            for fut in as_completed(futs):
                r = fut.result()
                if r:
                    results[market].append(r)
        results[market].sort(key=lambda x: x["score"], reverse=True)
        print(f"    ✓ {market} 유효 {len(results[market])}개")

    excluded = data_cleaner.get_excluded_count()
    if excluded:
        print(f"  🗑️  데이터 정제 제외: {excluded}개 (logs/excluded_*.log 참조)")

    return results


def validate_and_fix(results: dict) -> dict:
    """중복 가격 탐지 및 재스크리닝"""
    fixed = {}
    for market, stocks in results.items():
        price_count: dict = {}
        for r in stocks:
            price_count[r["price"]] = price_count.get(r["price"], 0) + 1
        dup_prices  = {p for p, c in price_count.items() if c > 1}
        dup_tickers = {r["ticker"] for r in stocks if r["price"] in dup_prices}

        if not dup_prices:
            fixed[market] = stocks
            continue

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
        print(f"  [{market}] 데이터 검증 완료: {len(new_stocks)}개")
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


def _extract_claude_json(text: str) -> "tuple[str, dict]":
    """
    Claude 응답에서 ```json ... ``` 블록을 추출한다.

    Returns
    -------
    (text_without_json, parsed_dict)
        JSON 파싱 실패 시 (원본 텍스트, {}) 반환.
    """
    import re
    pattern = r"```json\s*(\{.*?\})\s*```"
    m = re.search(pattern, text, re.DOTALL)
    if not m:
        return text, {}
    json_str = m.group(1)
    clean_text = text[:m.start()].rstrip()
    try:
        return clean_text, json.loads(json_str)
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
        f"{r['name']}({r['ticker']}) S:{r['score']:+d} "
        f"P:{r['price']:,.0f}({r['chg']:+.1f}%) "
        f"RSI:{r['rsi']:.0f} MACD:{'▲' if r['macd_hist']>0 else '▼'} "
        f"ADX:{r['adx']:.0f}{trend} 52w:{r['pos_52w']:.0f}% "
        f"손절:{stop_loss:,.0f}{fund_str}"
    )


def ask_claude_v4(kospi_buy, kosdaq_buy, us_buy,
                  kospi_sell, kosdaq_sell, us_sell,
                  macro, news, overseas, fear_greed, sector_flows,
                  external_events=None) -> str:
    try:
        import anthropic
        client = anthropic.Anthropic(api_key=_get("ANTHROPIC_API_KEY"))
    except Exception as e:
        return f"[Claude 분석 생략 — ANTHROPIC_API_KEY 없음: {e}]"

    # 캐시 확인 (외부 이벤트가 바뀌면 캐시 무효화)
    ext_events = external_events or []
    # 캐시 키: 날짜 + 외부이벤트만 사용 (점수 제외 → yfinance 미세 변동으로 캐시 미스 방지)
    cache_data = {
        "date": datetime.datetime.now().strftime("%Y-%m-%d"),
        "external_events": sorted([e.get("id", "") for e in ext_events]),
    }
    try:
        from token_cache import get_cached_analysis, save_analysis_cache
        cached = get_cached_analysis(cache_data, cache_hours=24)
        if cached:
            print("  ✓ 캐시 분석 결과 사용")
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

    def _build_prompt(kb, kqb, ub, ks, kqs, us):
        return f"""{datetime.datetime.now().strftime('%Y-%m-%d')} 주식 애널리스트 투자 의견 작성.

{ext_txt}거시: {macro_txt}
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

지침(간결·수치중심):
1. 매수종목별: [순위.종목] ★등급 / 매수논리2줄 / 분할매수(1차40%·2차·3차) / 목표가3단계 / 손절가(데이터의 손절값) / 펀더멘털1줄
2. 매도종목별: [순위.종목] ▼등급 / 매도논리2줄 / 매도전략 / 하락목표가
3. 시장판단: F&G해석·강세섹터2·약세섹터2·핵심전략·리스크

분석 텍스트 작성 후 반드시 아래 형식 JSON을 마지막에 출력하라:
```json
{{"top_buy":[{{"ticker":"티커","name":"종목명","grade":"★★★","target1":0,"target2":0,"stop":0}}],"top_sell":[{{"ticker":"티커","name":"종목명","stop":0}}],"market":"시장판단한줄","risk":"핵심리스크한줄","fg_signal":"매수|관망|매도"}}
```"""

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
            max_tokens=3500,
            temperature=0,
            messages=[{"role": "user", "content": prompt}],
        )
        full_text = resp.content[0].text
        # JSON 블록 추출 후 텍스트 분리
        text_part, structured = _extract_claude_json(full_text)
        if structured:
            # 구조화 데이터 별도 캐시 저장
            _save_claude_structured(structured)
        try:
            save_analysis_cache(cache_data, full_text)
        except Exception:
            pass
        return text_part
    except Exception as e:
        return f"[Claude API 오류: {e}]"


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
        # ── 매수 근거 ──────────────────────────────────────
        reasons = []
        if rsi < 30:
            reasons.append(f"RSI {rsi:.0f} 과매도 — 기술적 반등 신호")
        elif rsi < 40:
            reasons.append(f"RSI {rsi:.0f} 약과매도 — 저가 매수 구간")
        if macd > 0:
            reasons.append("MACD 히스토그램 양전환 — 상승 모멘텀 확인")
        if price > ma20 > ma60:
            reasons.append("이동평균 정배열(가격>MA20>MA60) — 강한 상승 추세")
        elif price > ma20:
            reasons.append("가격이 MA20 상회 — 단기 상승 구조")
        if adx > 25 and plus_di > minus_di:
            reasons.append(f"ADX {adx:.0f} 강한 추세 (+DI{plus_di:.0f}>-DI{minus_di:.0f}) — 방향성 확립")
        if pos_52w < 20:
            reasons.append(f"52주 저점 근처 {pos_52w:.0f}% — 반등 기대")
        elif pos_52w > 80:
            reasons.append(f"52주 고점 구간 {pos_52w:.0f}% — 상승 모멘텀 지속")
        if stoch_k < 20:
            reasons.append(f"스토캐스틱 {stoch_k:.0f} 과매도 — 반등 가능")
        if vol > 1.5:
            reasons.append(f"거래량 {vol:.1f}x 급증 — 수급 유입 신호")
        if mom5 > 3:
            reasons.append(f"5일 모멘텀 +{mom5:.1f}% — 단기 상승 흐름")
        if fund.get("pe") and fund["pe"] < 15:
            reasons.append(f"P/E {fund['pe']} 저평가 — 가치 매력")
        if fund.get("roe_pct") and fund["roe_pct"] > 15:
            reasons.append(f"ROE {fund['roe_pct']}% 고수익성 — 펀더멘털 우량")
        if not reasons:
            reasons.append(f"종합점수 {r['score']:+d}점 — 상대적 강세 우위")

        lines.append(f"       ✅ 매수 근거: {' / '.join(reasons[:3])}")

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

        # ── 리스크 ────────────────────────────────────────
        risks = []
        if rsi > 60:
            risks.append(f"RSI {rsi:.0f} — 추가 과열 시 조정 가능")
        if adx < 20:
            risks.append(f"ADX {adx:.0f} 횡보 — 추세 신뢰도 낮음")
        if mom5 < -2:
            risks.append(f"5일 모멘텀 {mom5:.1f}% — 단기 하락 압력")
        if price < ma20:
            risks.append("MA20 하회 — 지지선 붕괴 주의")
        if bb_pct > 85:
            risks.append(f"BB {bb_pct:.0f}% — 상단 근접, 단기 과열")
        if stoch_k > 75:
            risks.append(f"스토캐스틱 {stoch_k:.0f} — 단기 과매수")
        if vol < 0.5:
            risks.append(f"거래량 {vol:.1f}x 위축 — 상승 동력 부족")
        if fund.get("pe") and fund["pe"] > 40:
            risks.append(f"P/E {fund['pe']} 고평가 — 밸류에이션 부담")
        if not risks:
            risks.append("현재 주요 기술적 리스크 없음")
        lines.append(f"       ⚠️ 리스크: {' / '.join(risks[:3])}")

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
            reasons.append(f"종합점수 {r['score']:+d}점 — 상대적 약세")

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

def build_report(kospi_buy, kosdaq_buy, us_buy,
                 kospi_sell, kosdaq_sell, us_sell,
                 total: dict, fear_greed: dict, claude_opinion: str) -> str:
    now = datetime.datetime.now().strftime("%Y년 %m월 %d일 %H:%M")
    L   = []

    L.append("=" * 80)
    L.append(f"  📊 AI 주식 스크리닝 v4 (정밀 분석판)  |  {now}")
    L.append(f"  스캔: 코스피 {total['KOSPI']}개 | 코스닥 {total['KOSDAQ']}개 | 미국 {total['US']}개")
    fg = fear_greed
    if fg:
        L.append(f"  Fear&Greed: {fg['지수']}/100 [{fg['단계']}] → {fg['해석']}")
    L.append("=" * 80)

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
            L.append(f"       점수:{r['score']:+d}점 | 현재가:{r['price']:>12,.2f} | "
                     f"등락:{chg_icon}{abs(r['chg']):.2f}% | ATR손절:{stop:,.2f}")
            L.append(f"       RSI:{r['rsi']:.0f} Stoch:{r['stoch_k']:.0f}/{r['stoch_d']:.0f} | "
                     f"MACD:{r['macd_hist']:+.4f} | BB:{r['bb_pct']:.0f}%")
            L.append(f"       MA5:{r['ma5']:,.2f} MA20:{r['ma20']:,.2f} MA60:{r['ma60']:,.2f} | "
                     f"ADX:{r['adx']:.0f}(+DI:{r['plus_di']:.0f}/-DI:{r['minus_di']:.0f})")
            L.append(f"       52주위치:{r['pos_52w']:.0f}% | 모멘텀:{r['mom5']:+.2f}% | "
                     f"거래량:{r['vol_ratio']:.1f}x | ATR:{r['atr_pct']:.1f}%")
            if fund:
                fparts = []
                if fund.get("pe"):       fparts.append(f"P/E:{fund['pe']}")
                if fund.get("pb"):       fparts.append(f"P/B:{fund['pb']}")
                if fund.get("roe_pct"): fparts.append(f"ROE:{fund['roe_pct']}%")
                if fund.get("sector"):  fparts.append(f"섹터:{fund['sector']}")
                if fparts:
                    L.append(f"       펀더: {' | '.join(fparts)}")
            # 매수/매도 근거·전략·리스크 (지표 기반, 항상 출력)
            for line in _auto_analysis(r, section):
                L.append(line)

    fmt_block(kospi_buy,  "코스피 매수 TOP", "🇰🇷", "buy")
    fmt_block(kosdaq_buy, "코스닥 매수 TOP", "🇰🇷", "buy")
    fmt_block(us_buy,     "미국 매수 TOP",   "🇺🇸", "buy")
    fmt_block(kospi_sell,  "코스피 매도 TOP", "🇰🇷", "sell")
    fmt_block(kosdaq_sell, "코스닥 매도 TOP", "🇰🇷", "sell")
    fmt_block(us_sell,     "미국 매도 TOP",   "🇺🇸", "sell")

    L.append("\n" + "=" * 80)
    L.append("  🤖 Claude AI 심층 분석")
    L.append("=" * 80)
    L.append(claude_opinion)
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
.claude-box{background:#f3e5f5;border-left:4px solid #7b1fa2;padding:14px 18px;
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
            f"<td class='{sc_cls}' style='text-align:center'>{r['score']:+d}</td>"
            f"<td style='text-align:right'>{r['price']:,.0f}</td>"
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
                      perf_summary: str = "") -> str:
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

    sections = [
        section("🇰🇷 코스피 매수 TOP", _html_stock_table(kospi_buy, "buy")),
        section("🇰🇷 코스닥 매수 TOP", _html_stock_table(kosdaq_buy, "buy")),
        section("🇺🇸 미국 매수 TOP",   _html_stock_table(us_buy, "buy")),
        section("🇰🇷 코스피 매도 TOP", _html_stock_table(kospi_sell, "sell")),
        section("🇰🇷 코스닥 매도 TOP", _html_stock_table(kosdaq_sell, "sell")),
        section("🇺🇸 미국 매도 TOP",   _html_stock_table(us_sell, "sell")),
    ]

    # Claude 분석
    import html as _html
    claude_esc = _html.escape(claude_opinion or "")
    sections.append(section("🤖 Claude AI 심층 분석",
                             f"<div class='claude-box'>{claude_esc}</div>"))

    # 성과 요약 (있을 때만)
    if perf_summary:
        perf_esc = _html.escape(perf_summary)
        sections.append(section("📈 최근 30일 성과",
                                 f"<div class='perf-box'><pre style='margin:0;font-size:11px'>{perf_esc}</pre></div>"))

    body = "".join(sections)
    scan_info = (f"스캔: 코스피 {total.get('KOSPI',0)}개 | "
                 f"코스닥 {total.get('KOSDAQ',0)}개 | 미국 {total.get('US',0)}개")

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
        msg = MIMEMultipart("alternative")
        msg["Subject"] = (
            f"📊 AI 주식 v4 {datetime.datetime.now().strftime('%Y-%m-%d')} "
            f"| 기술+펀더멘털+Fear&Greed"
        )
        msg["From"] = EMAIL_FROM
        msg["To"]   = EMAIL_TO
        # plain text 먼저 (폴백), HTML 나중에 (이메일 클라이언트가 마지막 part를 선호)
        msg.attach(MIMEText(report_text, "plain", "utf-8"))
        if html_report:
            msg.attach(MIMEText(html_report, "html", "utf-8"))
        with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as srv:
            srv.starttls()
            srv.login(EMAIL_USER, EMAIL_PASS)
            srv.sendmail(EMAIL_FROM, EMAIL_TO, msg.as_string())
        print(f"[이메일] ✅ {EMAIL_TO} HTML+Text 발송 완료")
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
            lines.append(f"  {i}. {r['name']} {r['score']:+d}점 "
                         f"RSI:{r['rsi']:.0f} 손절:{stop:,.0f}")

    lines.append("\n─────────────")
    for header, stocks in [
        ("🇰🇷 코스피 매도", kospi_sell),
        ("🇰🇷 코스닥 매도", kosdaq_sell),
        ("🇺🇸 미국 매도",   us_sell),
    ]:
        lines.append(f"\n<b>{header}</b>")
        for i, r in enumerate(stocks, 1):
            lines.append(f"  {i}. {r['name']} {r['score']:+d}점 "
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

    # ① 기술적 스크리닝 (오늘 캐시 있으면 재사용)
    print("① 전 종목 기술적 스크리닝...")
    cached_screening = _load_screening_cache()
    if cached_screening:
        all_results = cached_screening
        print("   (캐시 재사용 — yfinance 재수집 생략)")
    else:
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

    # ③ 최종 매수/매도 선별
    kospi_buy   = all_results["KOSPI"][:RECOMMEND_COUNT["KOSPI"]]
    kosdaq_buy  = all_results["KOSDAQ"][:RECOMMEND_COUNT["KOSDAQ"]]
    us_buy      = all_results["US"][:RECOMMEND_COUNT["US"]]
    kospi_sell  = all_results["KOSPI"][-SELL_COUNT["KOSPI"]:][::-1]
    kosdaq_sell = all_results["KOSDAQ"][-SELL_COUNT["KOSDAQ"]:][::-1]
    us_sell     = all_results["US"][-SELL_COUNT["US"]:][::-1]

    total_valid = sum(len(v) for v in all_results.values())
    print(f"\n   ✅ 총 {total_valid}개 유효 종목")
    print(f"   매수: 코스피 {len(kospi_buy)} | 코스닥 {len(kosdaq_buy)} | 미국 {len(us_buy)}")
    print(f"   매도: 코스피 {len(kospi_sell)} | 코스닥 {len(kosdaq_sell)} | 미국 {len(us_sell)}")

    # ③-a 외부 변수 로드
    external_events = load_external_events()
    if external_events:
        print(f"\n   외부 변수 {len(external_events)}개 로드됨:")
        for ev in external_events:
            print(f"   · [{ev['category']}] {ev['title']} → {ev['impact']}")
    else:
        print("\n   외부 변수 없음 (추가: python external_events.py add)")

    # ④ 보조 데이터 수집 (병렬)
    print("\n③ 거시·심리·섹터·뉴스 수집...")
    macro = overseas = fear_greed = sector_flows = news = None
    results_bag = {}

    def _collect(key, fn, *args):
        results_bag[key] = fn(*args)

    threads = [
        threading.Thread(target=_collect, args=("macro",   collect_macro)),
        threading.Thread(target=_collect, args=("fear",    collect_fear_greed)),
        threading.Thread(target=_collect, args=("sector",  collect_sector_flows)),
        threading.Thread(target=_collect, args=("overseas",collect_overseas_snapshot)),
        threading.Thread(target=_collect, args=("news",    collect_news)),
    ]
    for t in threads: t.start()
    for t in threads: t.join()

    macro        = results_bag.get("macro", {})
    fear_greed   = results_bag.get("fear", {})
    sector_flows = results_bag.get("sector", {})
    overseas     = results_bag.get("overseas", {})
    news         = results_bag.get("news", [])

    fg_str = f"Fear&Greed:{fear_greed.get('지수','?')}" if fear_greed else "Fear&Greed:없음"
    print(f"   거시 {len(macro)}개 | {fg_str} | 섹터ETF {len(sector_flows)}개 | 뉴스 {len(news)}건")

    # ⑤ Claude 심층 분석
    print("\n④ Claude 심층 분석 요청...")
    claude_opinion = ask_claude_v4(
        kospi_buy, kosdaq_buy, us_buy,
        kospi_sell, kosdaq_sell, us_sell,
        macro, news, overseas, fear_greed, sector_flows,
        external_events=external_events
    )

    # ⑥ 리포트 저장
    report = build_report(
        kospi_buy, kosdaq_buy, us_buy,
        kospi_sell, kosdaq_sell, us_sell,
        {k: len(v) for k, v in all_results.items()},
        fear_greed, claude_opinion
    )
    with open(REPORT_PATH, "w", encoding="utf-8") as f:
        f.write(report)
    print(f"⑤ 리포트 저장: {REPORT_PATH}")

    # ⑦ 성능 추적 + 성과 요약
    perf_summary = ""
    print("\n⑤ 성능 추적 업데이트...")
    try:
        from performance_tracker import (
            init_database, save_daily_recommendations,
            update_price_tracking, generate_performance_report,
        )
        init_database()
        today_str = datetime.datetime.now().strftime("%Y-%m-%d")
        save_daily_recommendations(today_str, {
            "kospi_buy": kospi_buy, "kospi_sell": kospi_sell,
            "kosdaq_buy": kosdaq_buy, "kosdaq_sell": kosdaq_sell,
            "us_buy": us_buy, "us_sell": us_sell,
        })
        update_price_tracking()
        # 30일 성과 요약 생성
        perf_summary = generate_performance_report(30)
        perf_path = os.path.join(BASE_DIR, "performance_report.txt")
        with open(perf_path, "w", encoding="utf-8") as f:
            f.write(perf_summary)
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
    )
    html_path = os.path.join(BASE_DIR, "report_v4.html")
    with open(html_path, "w", encoding="utf-8") as f:
        f.write(html_report)
    print(f"⑥ HTML 리포트 저장: {html_path}")

    # ⑨ 알림 발송
    print("\n⑦ 알림 발송...")
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
