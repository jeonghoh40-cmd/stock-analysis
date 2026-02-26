"""
AI 주식 스크리닝 어드바이저 v3 (시장별 분리 버전)
- 코스피 50 개 풀 → 10 개 추천
- 코스닥 50 개 풀 → 5 개 추천
- 미국 60 개 풀 → 10 개 추천
- 유명 투자자 포트폴리오 추적
- 구체적 목표가·손절가 제시

실행 흐름:
  ① 코스피 50 + 코스닥 50 + 미국 60 = 총 160 개 종목 병렬 스크리닝
  ② 기술적 점수 + 투자자 가중치 계산
  ③ 시장별 매수 TOP 선별 (코스피 10, 코스닥 5, 미국 10)
  ④ 거시경제 + 뉴스 + 해외섹터 데이터 수집
  ⑤ Claude AI 심층 분석 → 투자 의견
  ⑥ report.txt 저장 + 이메일 + 카카오톡 발송

cron: 30 6 * * *  (매일 06:30 → 07:00 전 완료)

⚠️ 투자 참고용입니다. 최종 결정은 반드시 본인이 직접 판단하세요.
"""

import os
import sys
import json
import smtplib
import requests
import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import Optional

import yfinance as yf
import pandas as pd
import feedparser
from dotenv import dotenv_values

if sys.stdout.encoding != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

# ── .env 로드 ─────────────────────────────────────────────────
_env_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")
_cfg = dotenv_values(_env_path)

def _get(key: str, default: str = "") -> str:
    return os.environ.get(key) or _cfg.get(key) or default

BASE_DIR    = os.path.dirname(os.path.abspath(__file__))
REPORT_PATH = os.path.join(BASE_DIR, "report.txt")

# ── 알림 설정 ─────────────────────────────────────────────────
SMTP_SERVER = _get("SMTP_SERVER", "smtp.gmail.com")
SMTP_PORT   = int(_get("SMTP_PORT", "587"))
EMAIL_USER  = _get("EMAIL_USER")
EMAIL_PASS  = _get("EMAIL_PASS")
EMAIL_FROM  = _get("EMAIL_FROM", EMAIL_USER)
EMAIL_TO    = _get("EMAIL_TO", "geunho@stic.co.kr")
KAKAO_TOKEN = _get("KAKAO_TOKEN")


# ═══════════════════════════════════════════════════════════════
# 스크리닝 유니버스 (시장별 분리)
# ═══════════════════════════════════════════════════════════════

# ── 코스피 50 개 풀 ──────────────────────────────────────────────
KOSPI_POOL = {
    "삼성전자":          "005930.KS",  "SK 하이닉스":      "000660.KS",
    "LG 에너지솔루션":    "373220.KS",  "삼성바이오로직스":"207940.KS",
    "현대차":            "005380.KS",  "기아":            "000270.KS",
    "NAVER":             "035420.KS",  "셀트리온":        "068270.KS",
    "POSCO 홀딩스":       "005490.KS",  "삼성 SDI":         "006400.KS",
    "LG 화학":           "051910.KS",  "SK 이노베이션":    "096770.KS",
    "현대모비스":        "012330.KS",  "KB 금융":         "105560.KS",
    "신한지주":          "055550.KS",  "하나금융지주":    "086790.KS",
    "삼성물산":          "028260.KS",  "LG 전자":         "066570.KS",
    "SK 텔레콤":         "017670.KS",  "KT":              "030200.KS",
    "두산에너빌리티":    "034020.KS",  "고려아연":        "010130.KS",
    "삼성전기":          "009150.KS",  "포스코퓨처엠":    "003670.KS",
    "엔씨소프트":        "036570.KS",  "한국전력":        "015760.KS",
    "삼성생명":          "032830.KS",  "삼성화재":        "000810.KS",
    "아모레퍼시픽":      "090430.KS",  "LG 생활건강":     "051900.KS",
    "CJ 제일제당":       "097950.KS",  "오리온":          "271560.KS",
    "대한항공":          "003490.KS",  "현대글로비스":    "086280.KS",
    "GS":                "078930.KS",  "SK":              "034730.KS",
    "한국조선해양":      "009540.KS",  "한미반도체":      "042700.KS",
    "현대건설":          "000720.KS",  "삼성중공업":      "010140.KS",
    "대우조선해양":      "042660.KS",  "롯데케미칼":      "011170.KS",
    "S-Oil":             "010950.KS",  "GS 칼텍스":      "078930.KS",
    "한국타이어":        "161390.KS",  "금호타이어":      "180640.KS",
    "삼성카드":          "029780.KS",  "롯데렌탈":        "068670.KS",
    "현대중공업":        "329180.KS",  "두산로보틱스":    "457660.KS",
    "한화에어로스페이스":"012450.KS",  "LIG 넥스원":      "079550.KS",
}

# ── 코스닥 50 개 풀 ──────────────────────────────────────────────
KOSDAQ_POOL = {
    "에코프로":          "086520.KQ",  "에코프로비엠":    "247540.KQ",
    "크래프톤":          "259960.KS",  "펄어비스":        "263750.KQ",
    "카카오뱅크":        "323410.KS",  "카카오페이":      "377300.KS",
    "셀트리온헬스케어":  "091990.KQ",  "유한양행":        "000100.KS",
    "종근당":            "185750.KS",  "대웅제약":        "069620.KS",
    "알테오젠":          "196170.KQ",  "테라젠이텍스":    "095700.KQ",
    "마크로젠":          "096530.KQ",  "녹십자셀":        "095660.KQ",
    "파나진":            "101140.KQ",  "피씨엘":          "090080.KQ",
    "이수앱지스":        "115610.KQ",  "신라젠":          "215600.KQ",
    "지놈서전":          "188080.KQ",  "메디포스트":      "078160.KQ",
    "차바이오텍":        "068270.KQ",  "코미팜":          "065500.KQ",
    "바이오솔류드":      "101130.KQ",  "제이엘케이":      "277810.KQ",
    "루닛":              "426260.KQ",  "인피니트헬스케어":"099190.KQ",
    "오스코텍":          "078070.KQ",  "디엔에이링크":    "078600.KQ",
    "마이크로디지털":    "071670.KQ",  "유비쿼스":        "032820.KQ",
    "윈스":              "032830.KQ",  "아이엠":          "314500.KQ",
    "네오플":            "053620.KQ",  "위메이드":        "112040.KQ",
    "액토즈소프트":      "053120.KQ",  "조이맥스":        "053660.KQ",
    "게임빌":            "103140.KQ",  "컴투스":          "063080.KQ",
    "넷마블":            "251270.KS",  "카카오게임즈":    "293490.KQ",
    "드래곤플라이":      "030350.KQ",  "그라비티":        "064080.KQ",
    "이엔플러스":        "095610.KQ",  "피에이치씨":      "009440.KQ",
    "이오테크닉스":      "064290.KQ",  "한미반도체":      "042700.KS",
    "디스코코리아":      "064350.KQ",  "유진테크":        "056080.KQ",
    "피에스케이":        "056190.KQ",  "에스에프에이":    "056190.KQ",
    "로보스타":          "090360.KQ",  "두산로보틱스":    "457660.KQ",
    "레인보우로보틱스":  "277810.KQ",  "티로보틱스":      "092400.KQ",
}

# ── 미국 60 개 풀 ────────────────────────────────────────────────
US_POOL = {
    "Apple":             "AAPL",  "NVIDIA":          "NVDA",
    "Microsoft":         "MSFT",  "Alphabet":        "GOOGL",
    "Amazon":            "AMZN",  "Meta":            "META",
    "Tesla":             "TSLA",  "Broadcom":        "AVGO",
    "AMD":               "AMD",   "TSMC ADR":        "TSM",
    "Netflix":           "NFLX",  "Salesforce":      "CRM",
    "Oracle":            "ORCL",  "Adobe":           "ADBE",
    "Qualcomm":          "QCOM",  "Intel":           "INTC",
    "Texas Instruments": "TXN",   "Micron":          "MU",
    "Applied Materials": "AMAT",  "Lam Research":    "LRCX",
    "KLA Corp":          "KLAC",  "Palo Alto":       "PANW",
    "CrowdStrike":       "CRWD",  "Snowflake":       "SNOW",
    "Palantir":          "PLTR",  "Datadog":         "DDOG",
    "ServiceNow":        "NOW",   "Workday":         "WDAY",
    "Uber":              "UBER",  "Airbnb":          "ABNB",
    "Booking":           "BKNG",  "Shopify":         "SHOP",
    "PayPal":            "PYPL",  "Coinbase":        "COIN",
    "Visa":              "V",     "Mastercard":      "MA",
    "JPMorgan":          "JPM",   "Goldman Sachs":   "GS",
    "Morgan Stanley":    "MS",    "Berkshire B":     "BRK-B",
    "Johnson&Johnson":   "JNJ",   "Pfizer":          "PFE",
    "Eli Lilly":         "LLY",   "UnitedHealth":    "UNH",
    "Novo Nordisk":      "NVO",   "Moderna":         "MRNA",
    "Exxon Mobil":       "XOM",   "Chevron":         "CVX",
    "NextEra Energy":    "NEE",   "Rivian":          "RIVN",
    "Boeing":            "BA",    "Lockheed Martin": "LMT",
    "Caterpillar":       "CAT",   "Deere":           "DE",
    "Walmart":           "WMT",   "Costco":          "COST",
    "Nike":              "NKE",   "Starbucks":       "SBUX",
    "Walt Disney":       "DIS",   "McDonald's":      "MCD",
}

# 시장별 추천 수 설정 (토큰 절감형)
RECOMMEND_COUNT = {
    "KOSPI": 5,    # 코스피 5 개 추천 (기존 10 개 → 50% 절감)
    "KOSDAQ": 3,   # 코스닥 3 개 추천 (기존 5 개 → 40% 절감)
    "US": 5,       # 미국 5 개 추천 (기존 10 개 → 50% 절감)
}

# 시장별 매도 추천 수 설정 (토큰 절감형)
SELL_COUNT = {
    "KOSPI": 3,    # 코스피 3 개 매도 (기존 5 개 → 40% 절감)
    "KOSDAQ": 2,   # 코스닥 2 개 매도 (기존 3 개 → 33% 절감)
    "US": 3,       # 미국 3 개 매도 (기존 5 개 → 40% 절감)
}


# ═══════════════════════════════════════════════════════════════
# 기술적 지표 계산
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

def score_stock(rsi, macd_hist, price, ma5, ma20, ma60, mom5) -> int:
    """기술적 종합 점수 –100 ~ +100"""
    s = 0
    # RSI (±40)
    if   rsi < 20: s += 40
    elif rsi < 30: s += 25
    elif rsi < 40: s += 10
    elif rsi > 80: s -= 40
    elif rsi > 70: s -= 25
    elif rsi > 60: s -= 10
    # MACD (±20)
    s += 20 if macd_hist > 0 else -20
    # 이동평균 정배열 (±20)
    if price > ma20 > ma60:   s += 15
    elif price > ma20:        s += 7
    elif price < ma20 < ma60: s -= 15
    elif price < ma20:        s -= 7
    # MA5 vs MA20 (±10)
    s += 10 if ma5 > ma20 else -10
    # 모멘텀 (±10)
    if   mom5 >  5: s += 10
    elif mom5 >  2: s += 5
    elif mom5 < -5: s -= 10
    elif mom5 < -2: s -= 5
    return max(-100, min(100, s))


def score_with_investor_weight(ticker: str, base_score: int) -> int:
    """
    유명 투자자 포트폴리오 가중치를 적용한 점수 보정
    - Pelosi 보유 종목: +5 ~ +10
    - ARK 보유 종목: +3 ~ +8
    - 한국 투자자 보유: +5 ~ +25
    - 둘 다 해당: 추가 +5
    """
    try:
        from investor_scorer import get_investor_score
        inv_score = get_investor_score(ticker.upper())
        
        bonus = 0
        if inv_score['is_pelosi_pick']:
            bonus += inv_score['pelosi_score']  # 최대 15
        if inv_score['is_ark_pick']:
            bonus += inv_score['ark_score']  # 최대 15
        if inv_score['is_korean_investor_pick']:
            bonus += inv_score['korean_investor_score']  # 최대 25
        if inv_score['is_pelosi_pick'] and inv_score['is_ark_pick']:
            bonus += 5  # 둘 다 해당 시 추가 보너스
        
        return max(-100, min(100, base_score + bonus))
    except Exception:
        return base_score


# ═══════════════════════════════════════════════════════════════
# 단일 종목 고속 스크리닝
# ═══════════════════════════════════════════════════════════════
def screen_one(market: str, name: str, ticker: str) -> Optional[dict]:
    try:
        df = yf.download(ticker, period="6mo", interval="1d",
                         progress=False, auto_adjust=True)
        if df is None or df.empty or len(df) < 65:
            return None
        close = df["Close"].squeeze()
        price = float(close.iloc[-1])
        prev  = float(close.iloc[-2])
        chg   = round((price - prev) / prev * 100, 2)

        rsi               = _rsi(close)
        _, _, macd_hist   = _macd(close)
        ma5, ma20, ma60   = _mas(close)
        mom5              = _mom(close, 5)
        bb_up, bb_dn, bb_pct = _bb(close)
        base_score        = score_stock(rsi, macd_hist, price, ma5, ma20, ma60, mom5)
        
        # 투자자 가중치 적용
        score = score_with_investor_weight(ticker, base_score)

        vol = df["Volume"].squeeze() if "Volume" in df.columns else pd.Series([0]*len(df))
        vol_avg = float(vol.rolling(20).mean().iloc[-1])
        vol_cur = float(vol.iloc[-1])
        vol_ratio = round(vol_cur / (vol_avg + 1e-9), 2)

        return {
            "market": market, "name": name, "ticker": ticker,
            "price": round(price, 2), "chg": chg,
            "rsi": round(rsi, 1), "macd_hist": round(macd_hist, 4),
            "ma5": round(ma5, 2), "ma20": round(ma20, 2), "ma60": round(ma60, 2),
            "bb_up": bb_up, "bb_dn": bb_dn, "bb_pct": bb_pct,
            "mom5": round(mom5, 2), "vol_ratio": vol_ratio,
            "score": score,
        }
    except Exception:
        return None


# ═══════════════════════════════════════════════════════════════
# 전체 유니버스 병렬 스크리닝 (시장별 분리)
# ═══════════════════════════════════════════════════════════════
def run_screening() -> dict:
    """
    시장별로 분리하여 스크리닝 수행.
    Returns:
        {
            "KOSPI": [results...],
            "KOSDAQ": [results...],
            "US": [results...]
        }
    """
    results = {"KOSPI": [], "KOSDAQ": [], "US": []}
    
    # 코스피 스크리닝
    print(f"  🇰🇷 코스피 {len(KOSPI_POOL)}개 종목 스크리닝 중...")
    tasks = [("KOSPI", n, t) for n, t in KOSPI_POOL.items()]
    with ThreadPoolExecutor(max_workers=8) as ex:
        futs = {ex.submit(screen_one, m, n, t): (m, n, t) for m, n, t in tasks}
        for fut in as_completed(futs):
            r = fut.result()
            if r:
                results["KOSPI"].append(r)
    results["KOSPI"].sort(key=lambda x: x["score"], reverse=True)
    print(f"    ✓ 코스피 유효 {len(results['KOSPI'])}개")
    
    # 코스닥 스크리닝
    print(f"  🇰🇷 코스닥 {len(KOSDAQ_POOL)}개 종목 스크리닝 중...")
    tasks = [("KOSDAQ", n, t) for n, t in KOSDAQ_POOL.items()]
    with ThreadPoolExecutor(max_workers=8) as ex:
        futs = {ex.submit(screen_one, m, n, t): (m, n, t) for m, n, t in tasks}
        for fut in as_completed(futs):
            r = fut.result()
            if r:
                results["KOSDAQ"].append(r)
    results["KOSDAQ"].sort(key=lambda x: x["score"], reverse=True)
    print(f"    ✓ 코스닥 유효 {len(results['KOSDAQ'])}개")
    
    # 미국 스크리닝
    print(f"  🇺🇸 미국 {len(US_POOL)}개 종목 스크리닝 중...")
    tasks = [("US", n, t) for n, t in US_POOL.items()]
    with ThreadPoolExecutor(max_workers=8) as ex:
        futs = {ex.submit(screen_one, m, n, t): (m, n, t) for m, n, t in tasks}
        for fut in as_completed(futs):
            r = fut.result()
            if r:
                results["US"].append(r)
    results["US"].sort(key=lambda x: x["score"], reverse=True)
    print(f"    ✓ 미국 유효 {len(results['US'])}개")
    
    return results


def signal_label(score: int) -> str:
    if   score >= 70: return "🟢 강한매수"
    elif score >= 40: return "🔵 매수추천"
    elif score >= 20: return "🔷 약한매수"
    elif score <= -70: return "🔴 강한매도"
    elif score <= -40: return "🟠 매도추천"
    elif score <= -20: return "🔶 약한매도"
    else:              return "⚪ 중립"


# ═══════════════════════════════════════════════════════════════
# 거시경제 / 뉴스 / 해외섹터 데이터 수집
# ═══════════════════════════════════════════════════════════════
def collect_macro() -> dict:
    macro = {}
    for name, tk in {
        "USD/KRW": "KRW=X",  "WTI 유가": "CL=F",
        "금 (Gold)": "GC=F",  "VIX": "^VIX",
        "KOSPI": "^KS11",    "KOSDAQ": "^KQ11",
        "S&P500": "^GSPC",   "나스닥": "^IXIC",
    }.items():
        try:
            h = yf.Ticker(tk).history(period="5d")
            if not h.empty:
                cur  = h["Close"].iloc[-1]
                prev = h["Close"].iloc[-2] if len(h) > 1 else cur
                macro[name] = {
                    "현재": round(cur, 2),
                    "등락 (%)": round((cur-prev)/prev*100, 2),
                }
        except Exception:
            pass
    return macro


def collect_news() -> list:
    headlines = []
    for rss in [
        "https://www.yonhapnewstv.co.kr/category/news/economy/feed/",
        "https://rss.donga.com/economy.xml",
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
        ("NVDA","엔비디아"), ("TSM","TSMC"), ("ASML","ASML"),
        ("SOXX","반도체 ETF"), ("TSLA","테슬라"), ("LIT","리튬 ETF"),
        ("META","메타"), ("GOOGL","알파벳"), ("MSFT","MS"),
        ("LMT","록히드마틴"), ("^TNX","미 10 년채"), ("DX=F","달러인덱스"),
    ]:
        try:
            h = yf.Ticker(tk).history(period="10d")
            if not h.empty:
                cur  = float(h["Close"].iloc[-1])
                prev = float(h["Close"].iloc[-2]) if len(h) > 1 else cur
                snap[label] = {
                    "현재": round(cur, 2),
                    "전일 (%)": round((cur-prev)/prev*100, 2),
                }
        except Exception:
            pass
    return snap


# ═══════════════════════════════════════════════════════════════
# Claude 심층 분석 (시장별 TOP 대상) - 매도 포함 (토큰 절감형)
# ═══════════════════════════════════════════════════════════════
def ask_claude_with_sell(kospi_buy: list, kosdaq_buy: list, us_buy: list,
                         kospi_sell: list, kosdaq_sell: list, us_sell: list,
                         macro: dict, news: list, overseas: dict) -> str:
    try:
        import anthropic
        client = anthropic.Anthropic(api_key=_get("ANTHROPIC_API_KEY"))
    except Exception as e:
        return f"[Claude 분석 생략 — ANTHROPIC_API_KEY 없음: {e}]"

    macro_txt = "\n".join(
        f"  {k}: {v['현재']} ({v['등락 (%)']:+.2f}%)"
        for k, v in macro.items()
    )
    news_txt = "\n".join(f"  - {h}" for h in news[:8]) if news else "  (뉴스 없음)"
    ov_txt   = "\n".join(
        f"  {k}: {v['현재']} ({v['전일 (%)']:+.2f}%)"
        for k, v in overseas.items()
    )

    def stock_block(stocks, label):
        lines = [f"\n[{label}]"]
        for r in stocks:
            # 투자자 스코어 계산 (절대 경로 import)
            import sys
            sys.path.insert(0, BASE_DIR)
            from investor_scorer import get_investor_score
            
            ticker_clean = r['ticker'].replace('.KS', '').replace('.KQ', '')
            inv = get_investor_score(ticker_clean)
            investor_tag = []
            if inv['is_pelosi_pick']: investor_tag.append(f"Pelosi+{inv['pelosi_score']}")
            if inv['is_ark_pick']: investor_tag.append(f"ARK+{inv['ark_score']}")
            if inv['is_korean_investor_pick']: investor_tag.append(f"한국 +{inv['korean_investor_score']}")
            investor_str = ', '.join(investor_tag) if investor_tag else '해당없음'
            
            lines.append(
                f"  {r['name']}({r['ticker']}) | 점수:{r['score']:+d} | "
                f"가격:{r['price']:,.2f} ({r['chg']:+.1f}%) | "
                f"RSI:{r['rsi']:.0f} | MACD:{r['macd_hist']:+.4f} | "
                f"MA5:{r['ma5']:,.2f} MA20:{r['ma20']:,.2f} MA60:{r['ma60']:,.2f} | "
                f"BB:{r['bb_pct']:.0f}% | 모멘텀:{r['mom5']:+.1f}% | "
                f"거래량:{r['vol_ratio']:.1f}x | 투자자:{investor_str}"
            )
        return "\n".join(lines)

    # 캐시 키 생성용 데이터
    cache_data = {
        'date': datetime.datetime.now().strftime('%Y-%m-%d'),
        'kospi_buy': [(r['ticker'], r['score']) for r in kospi_buy],
        'kosdaq_buy': [(r['ticker'], r['score']) for r in kosdaq_buy],
        'us_buy': [(r['ticker'], r['score']) for r in us_buy],
        'macro_keys': list(macro.keys())
    }
    
    # 캐시 확인 (24 시간 이내)
    sys.path.insert(0, BASE_DIR)
    from token_cache import get_cached_analysis, save_analysis_cache
    cached_result = get_cached_analysis(cache_data, cache_hours=24)
    if cached_result:
        print("  ✓ 캐시된 분석 결과 사용 (토큰 절약)")
        return cached_result

    prompt = f"""주식분석. 날짜:{datetime.datetime.now().strftime('%Y-%m-%d')}

■거시경제
{macro_txt}

■해외지표
{ov_txt}

■뉴스
{news_txt}

■매수추천
{stock_block(kospi_buy, '코스피매수')}
{stock_block(kosdaq_buy, '코스닥매수')}
{stock_block(us_buy, '미국매수')}

■매도추천
{stock_block(kospi_sell, '코스피매도')}
{stock_block(kosdaq_sell, '코스닥매도')}
{stock_block(us_sell, '미국매도')}

────────────────
【분석지침】
1. 매수종목:논리 2 개,목표가 3 단계,손절가
2. 매도종목:논리 2 개,전략
3. 시장국면:한국/미국,섹터,전략

간결하게."""

    try:
        resp = client.messages.create(
            model="claude-sonnet-4-6", 
            max_tokens=6000,  # 토큰 절감 (기존 12000 → 50% 절감)
            messages=[{"role": "user", "content": prompt}],
        )
        result = resp.content[0].text
        
        # 캐시 저장
        if save_analysis_cache(cache_data, result):
            print("  ✓ 분석 결과 캐시 저장 완료")
        
        return result
    except Exception as e:
        return f"[Claude API 오류: {e}]"


# ═══════════════════════════════════════════════════════════════
# 리포트 생성 (시장별 분리) - 매도 포함
# ═══════════════════════════════════════════════════════════════
def build_report_with_sell(kospi_buy: list, kosdaq_buy: list, us_buy: list,
                           kospi_sell: list, kosdaq_sell: list, us_sell: list,
                           total: dict, claude_opinion: str) -> str:
    now = datetime.datetime.now().strftime("%Y년 %m월 %d일 %H:%M")
    L = []

    L.append("=" * 80)
    L.append(f"  📊 AI 주식 스크리닝 리포트 (시장별 분리)  |  {now}")
    L.append(f"  스캔: 코스피 {total['KOSPI']}개 | 코스닥 {total['KOSDAQ']}개 | 미국 {total['US']}개")
    L.append(f"  매수: 코스피 {len(kospi_buy)}개 | 코스닥 {len(kosdaq_buy)}개 | 미국 {len(us_buy)}개")
    L.append(f"  매도: 코스피 {len(kospi_sell)}개 | 코스닥 {len(kosdaq_sell)}개 | 미국 {len(us_sell)}개")
    L.append("=" * 80)

    def fmt_block(stocks, header, market_icon):
        L.append("\n" + "─" * 80)
        L.append(f"  {market_icon} {header}")
        L.append("─" * 80)
        for i, r in enumerate(stocks, 1):
            icon = "▲" if r["chg"] >= 0 else "▼"
            L.append(f"\n  {i:2d}위  {signal_label(r['score'])}  "
                     f"{r['name']} ({r['ticker']})")
            L.append(f"       점수: {r['score']:+d}점  |  "
                     f"현재가: {r['price']:>12,.2f}  |  등락: {icon}{abs(r['chg']):.2f}%")
            L.append(f"       RSI: {r['rsi']:.1f}  |  MACD: {r['macd_hist']:+.4f}  |  "
                     f"5 일모멘텀: {r['mom5']:+.2f}%  |  BB: {r['bb_pct']:.0f}%")
            L.append(f"       MA5: {r['ma5']:,.2f}  MA20: {r['ma20']:,.2f}  "
                     f"MA60: {r['ma60']:,.2f}  |  거래량비: {r['vol_ratio']:.1f}x")

    fmt_block(kospi_buy,  "코스피 매수 추천 TOP 10", "🇰🇷")
    fmt_block(kosdaq_buy, "코스닥 매수 추천 TOP 5", "🇰🇷")
    fmt_block(us_buy,     "미국 매수 추천 TOP 10", "🇺🇸")
    
    fmt_block(kospi_sell,  "코스피 매도 추천 TOP 5", "🇰🇷")
    fmt_block(kosdaq_sell, "코스닥 매도 추천 TOP 3", "🇰🇷")
    fmt_block(us_sell,     "미국 매도 추천 TOP 5", "🇺🇸")

    L.append("\n" + "=" * 80)
    L.append("  🤖 Claude AI 심층 분석 의견")
    L.append("=" * 80)
    L.append(claude_opinion)

    L.append("\n" + "=" * 80)
    L.append("  ⚠️  기술적 분석 참고용 / 투자 손익 책임은 본인에게 있습니다.")
    L.append("=" * 80 + "\n")
    return "\n".join(L)


# ═══════════════════════════════════════════════════════════════
# 이메일 발송
# ═══════════════════════════════════════════════════════════════
def send_email(report_text: str):
    if not EMAIL_USER or not EMAIL_PASS:
        print("[이메일] EMAIL_USER / EMAIL_PASS 미설정 — 건너뜀")
        return
    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = (
            f"📊 AI 주식 스크리닝 {datetime.datetime.now().strftime('%Y-%m-%d')} "
            f"| 코스피 10|코스닥 5|미국 10"
        )
        msg["From"] = EMAIL_FROM
        msg["To"]   = EMAIL_TO
        msg.attach(MIMEText(report_text, "plain", "utf-8"))
        with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as srv:
            srv.starttls()
            srv.login(EMAIL_USER, EMAIL_PASS)
            srv.sendmail(EMAIL_FROM, EMAIL_TO, msg.as_string())
        print(f"[이메일] ✅ {EMAIL_TO} 발송 완료")
    except Exception as e:
        print(f"[이메일] ❌ 실패: {e}")


# ═══════════════════════════════════════════════════════════════
# 카카오톡 나에게 보내기 - 매도 포함
# ═══════════════════════════════════════════════════════════════
def send_kakao_with_sell(kospi_buy: list, kosdaq_buy: list, us_buy: list,
                         kospi_sell: list, kosdaq_sell: list, us_sell: list):
    if not KAKAO_TOKEN:
        print("[카카오톡] KAKAO_TOKEN 미설정 — 건너뜀")
        return
    today = datetime.datetime.now().strftime("%m/%d")
    lines = [f"📊 [{today}] AI 주식 스크리닝\n"]
    
    lines.append("\n🇰🇷 코스피 매수 TOP 10")
    for i, r in enumerate(kospi_buy, 1):
        lines.append(f"  {i}. {r['name']} {r['score']:+d}점 "
                     f"RSI:{r['rsi']:.0f} {r['chg']:+.1f}%")
    
    lines.append("\n🇰🇷 코스닥 매수 TOP 5")
    for i, r in enumerate(kosdaq_buy, 1):
        lines.append(f"  {i}. {r['name']} {r['score']:+d}점 "
                     f"RSI:{r['rsi']:.0f} {r['chg']:+.1f}%")
    
    lines.append("\n🇺🇸 미국 매수 TOP 10")
    for i, r in enumerate(us_buy, 1):
        lines.append(f"  {i}. {r['name']} {r['score']:+d}점 "
                     f"RSI:{r['rsi']:.0f} {r['chg']:+.1f}%")
    
    lines.append("\n─────────────────────────────")
    lines.append("\n🇰🇷 코스피 매도 TOP 5")
    for i, r in enumerate(kospi_sell, 1):
        lines.append(f"  {i}. {r['name']} {r['score']:+d}점 "
                     f"RSI:{r['rsi']:.0f} {r['chg']:+.1f}%")
    
    lines.append("\n🇰🇷 코스닥 매도 TOP 3")
    for i, r in enumerate(kosdaq_sell, 1):
        lines.append(f"  {i}. {r['name']} {r['score']:+d}점 "
                     f"RSI:{r['rsi']:.0f} {r['chg']:+.1f}%")
    
    lines.append("\n🇺🇸 미국 매도 TOP 5")
    for i, r in enumerate(us_sell, 1):
        lines.append(f"  {i}. {r['name']} {r['score']:+d}점 "
                     f"RSI:{r['rsi']:.0f} {r['chg']:+.1f}%")
    
    lines.append("\n📄 상세 내용은 이메일 확인")
    text = "\n".join(lines)
    try:
        resp = requests.post(
            "https://kapi.kakao.com/v2/api/talk/memo/default/send",
            headers={"Authorization": f"Bearer {KAKAO_TOKEN}"},
            data={"template_object": json.dumps({
                "object_type": "text", "text": text,
                "link": {"web_url": "", "mobile_web_url": ""},
            })},
            timeout=10,
        )
        print("[카카오톡] ✅ 발송 완료" if resp.status_code == 200
              else f"[카카오톡] ❌ {resp.status_code}: {resp.text[:100]}")
    except Exception as e:
        print(f"[카카오톡] ❌ {e}")


# ═══════════════════════════════════════════════════════════════
# 메인
# ═══════════════════════════════════════════════════════════════
def main():
    start = datetime.datetime.now()
    print(f"\n🚀 AI 주식 스크리닝 시작 (시장별 분리) — {start.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"   수신: {EMAIL_TO}\n")

    # ① 시장별 스크리닝
    print("① 시장별 스크리닝...")
    all_results = run_screening()
    
    # 시장별 매수 TOP 선별
    kospi_buy  = all_results["KOSPI"][:RECOMMEND_COUNT["KOSPI"]]
    kosdaq_buy = all_results["KOSDAQ"][:RECOMMEND_COUNT["KOSDAQ"]]
    us_buy     = all_results["US"][:RECOMMEND_COUNT["US"]]
    
    # 시장별 매도 TOP 선별 (점수가 낮은 순)
    kospi_sell  = all_results["KOSPI"][-SELL_COUNT["KOSPI"]:][::-1]
    kosdaq_sell = all_results["KOSDAQ"][-SELL_COUNT["KOSDAQ"]:][::-1]
    us_sell     = all_results["US"][-SELL_COUNT["US"]:][::-1]
    
    total_valid = sum(len(v) for v in all_results.values())
    print(f"   ✅ 총 {total_valid}개 유효 → 매수:코스피 {len(kospi_buy)}개 | 코스닥 {len(kosdaq_buy)}개 | 미국 {len(us_buy)}개")
    print(f"      매도:코스피 {len(kospi_sell)}개 | 코스닥 {len(kosdaq_sell)}개 | 미국 {len(us_sell)}개")

    # ② 보조 데이터 수집
    print("② 거시경제 · 해외 · 뉴스 수집...")
    macro   = collect_macro()
    news    = collect_news()
    overseas = collect_overseas_snapshot()
    print(f"   거시 {len(macro)}개 · 뉴스 {len(news)}건 · 해외지표 {len(overseas)}개")

    # ③ Claude 심층 분석 (매수 + 매도 모두 전달)
    print("③ Claude 심층 분석 요청...")
    claude_opinion = ask_claude_with_sell(kospi_buy, kosdaq_buy, us_buy, kospi_sell, kosdaq_sell, us_sell, macro, news, overseas)

    # ④ 리포트 저장 (매수 + 매도)
    report = build_report_with_sell(kospi_buy, kosdaq_buy, us_buy, kospi_sell, kosdaq_sell, us_sell,
                          {k: len(v) for k, v in all_results.items()}, 
                          claude_opinion)
    with open(REPORT_PATH, "w", encoding="utf-8") as f:
        f.write(report)
    print(f"④ 리포트 저장: {REPORT_PATH}")

    # ④-1. 성능 추적용 데이터 저장 (새로운 기능)
    print("④-1. 성능 추적 데이터 저장 중...")
    try:
        from performance_tracker import init_database, save_daily_recommendations
        
        # 데이터베이스 초기화
        init_database()
        
        # 오늘 날짜
        today = datetime.datetime.now().strftime('%Y-%m-%d')
        
        # 추천 데이터 저장
        recommendations = {
            'kospi_buy': kospi_buy,
            'kospi_sell': kospi_sell,
            'kosdaq_buy': kosdaq_buy,
            'kosdaq_sell': kosdaq_sell,
            'us_buy': us_buy,
            'us_sell': us_sell,
        }
        save_daily_recommendations(today, recommendations)
        
        # 가격 추적 업데이트
        from performance_tracker import update_price_tracking
        update_price_tracking()
        
        print("  ✓ 성능 데이터 저장 완료")
    except Exception as e:
        print(f"  ⚠️ 성능 추적 저장 실패: {e}")

    # ⑤ 알림 발송 (매수 + 매도)
    print("⑤ 알림 발송...")
    send_email(report)
    send_kakao_with_sell(kospi_buy, kosdaq_buy, us_buy, kospi_sell, kosdaq_sell, us_sell)

    elapsed = int((datetime.datetime.now() - start).total_seconds())
    print(f"\n✅ 완료! 소요시간 {elapsed // 60}분 {elapsed % 60}초\n")


if __name__ == "__main__":
    main()
