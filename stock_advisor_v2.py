"""
AI 주식 스크리닝 어드바이저 (동적 TOP10 선별판)
- 유명 투자자 포트폴리오 추적 (Damodaran, Howard Marks, Cathie Wood, Nancy Pelosi 등)
- 기술적 분석 + 투자자 스코어링 통합
- 구체적 목표가·손절가 제시

실행 흐름:
  ① 국내50 + 미국60 + 중국40 = 약 150 개 전종목 병렬 스크리닝
  ② 기술적 점수 계산 + 투자자 포트폴리오 가중치 → 매수 TOP10 / 매도 TOP10 자동 선별
  ③ 거시경제 + 뉴스 + 해외섹터 + DART 재무 데이터 수집
  ④ Claude 가 선별된 20 개 종목 심층 분석 → 투자 의견 (구체적 목표가·손절가)
  ⑤ report.txt 저장 + 이메일 + 카카오톡 알림 발송

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
# 스크리닝 유니버스  (국내 50 + 미국 60 + 중국 40)
# ═══════════════════════════════════════════════════════════════
UNIVERSE = {
    "🇰🇷 국내": {
        "삼성전자":          "005930.KS",  "SK 하이닉스":      "000660.KS",
        "LG 에너지솔루션":    "373220.KS",  "삼성바이오로직스":"207940.KS",
        "현대차":            "005380.KS",  "기아":            "000270.KS",
        "NAVER":             "035420.KS",  "카카오":          "035720.KS",
        "셀트리온":          "068270.KS",  "POSCO 홀딩스":     "005490.KS",
        "삼성 SDI":           "006400.KS",  "LG 화학":          "051910.KS",
        "한화에어로스페이스":"012450.KS",  "크래프톤":        "259960.KS",
        "SK 이노베이션":      "096770.KS",  "현대모비스":      "012330.KS",
        "KB 금융":            "105560.KS",  "신한지주":        "055550.KS",
        "하나금융지주":      "086790.KS",  "삼성물산":        "028260.KS",
        "LG 전자":            "066570.KS",  "SK 텔레콤":        "017670.KS",
        "KT":                "030200.KS",  "두산에너빌리티":  "034020.KS",
        "카카오뱅크":        "323410.KS",  "카카오페이":      "377300.KS",
        "HMM":               "011200.KS",  "고려아연":        "010130.KS",
        "LG 이노텍":          "011070.KS",  "삼성전기":        "009150.KS",
        "에코프로비엠":      "247540.KQ",  "에코프로":        "086520.KQ",
        "포스코퓨처엠":      "003670.KS",  "엔씨소프트":      "036570.KS",
        "넷마블":            "251270.KS",  "펄어비스":        "263750.KQ",
        "현대건설":          "000720.KS",  "한국전력":        "015760.KS",
        "삼성생명":          "032830.KS",  "삼성화재":        "000810.KS",
        "아모레퍼시픽":      "090430.KS",  "LG 생활건강":      "051900.KS",
        "CJ 제일제당":        "097950.KS",  "오리온":          "271560.KS",
        "대한항공":          "003490.KS",  "현대글로비스":    "086280.KS",
        "GS":                "078930.KS",  "SK":              "034730.KS",
        "한국조선해양":      "009540.KS",  "한미반도체":      "042700.KS",
    },
    "🇺🇸 미국": {
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
    },
    "🇨🇳 중국": {
        "알리바바":    "BABA",  "징둥닷컴":  "JD",    "바이두":      "BIDU",
        "핀둬둬":      "PDD",   "넷이즈":    "NTES",  "비리비리":    "BILI",
        "샤오펑":      "XPEV",  "니오":      "NIO",   "리오토":      "LI",
        "ZTO Express": "ZTO",   "Trip.com":  "TCOM",  "Vipshop":     "VIPS",
        "Ke Holdings": "BEKE",  "iQIYI":     "IQ",    "Weibo":       "WB",
        "360 Finance": "QFIN",  "Lufax":     "LU",    "Full Truck":  "YMM",
        "Kanzhun":     "BZ",    "New Orient":"EDU",   "TAL Education":"TAL",
        "Daqo Energy": "DQ",    "JinkoSolar":"JKS",   "ACM Research":"ACMR",
        "Himax Tech":  "HIMX",  "Agora":     "API",   "OneConnect":  "OCFT",
        "Kingsoft Cloud":"KC",  "iSoftStone":"ISS",   "Tuya Smart":  "TUYA",
        "Liqtech Intl":"LIQT",  "Moxian":    "MOXC",  "UTStarcom":   "UTSI",
        "GreenPower":  "GP",    "Sohu.com":  "SOHU",  "Remark Hdgs": "MARK",
        "Ebang Intl":  "EBON",  "Nano-X":    "NNOX",  "CIFS Capital":"CIFS",
        "ChinaNet":    "CNET",
    },
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
def screen_one(group: str, name: str, ticker: str) -> Optional[dict]:
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
            "group": group, "name": name, "ticker": ticker,
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
# 전체 유니버스 병렬 스크리닝
# ═══════════════════════════════════════════════════════════════
def run_screening() -> list:
    tasks = [(g, n, t) for g, stocks in UNIVERSE.items()
             for n, t in stocks.items()]
    results = []
    print(f"  총 {len(tasks)}개 종목 병렬 스크리닝 (12 스레드)...")
    with ThreadPoolExecutor(max_workers=12) as ex:
        futs = {ex.submit(screen_one, g, n, t): (g, n, t) for g, n, t in tasks}
        done = 0
        for fut in as_completed(futs):
            done += 1
            r = fut.result()
            if r:
                results.append(r)
            if done % 30 == 0:
                print(f"    진행 {done}/{len(tasks)} | 유효 {len(results)}개")
    results.sort(key=lambda x: x["score"], reverse=True)
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
# 거시경제 / 뉴스 / 해외섹터 데이터 수집 (Claude 분석 입력용)
# ═══════════════════════════════════════════════════════════════
def collect_macro() -> dict:
    macro = {}
    for name, tk in {
        "USD/KRW": "KRW=X",  "WTI 유가": "CL=F",
        "금 (Gold)": "GC=F",  "VIX": "^VIX",
        "KOSPI": "^KS11",    "S&P500": "^GSPC",
        "나스닥": "^IXIC",
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
# Claude 심층 분석 (TOP20 대상) - 구체적 목표가·손절가 제시
# ═══════════════════════════════════════════════════════════════
def ask_claude(buy_top: list, sell_top: list,
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
            # 투자자 스코어 계산
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

    prompt = f"""당신은 한국·미국·중국 주식시장 전문 애널리스트입니다.
오늘 {datetime.datetime.now().strftime('%Y년 %m월 %d일')} 기준 데이터를 바탕으로
기술적 스크리닝으로 선별된 20 개 종목에 대해 **구체적인 투자 의견**을 작성하세요.

■ 거시경제 현황
{macro_txt}

■ 해외 핵심 지표
{ov_txt}

■ 오늘의 시장 뉴스
{news_txt}

■ 기술적 스크리닝 결과
{stock_block(buy_top, '매수 추천 TOP 10 (점수 높은 순)')}
{stock_block(sell_top, '매도 추천 TOP 10 (점수 낮은 순)')}

─────────────────────────────────────────
【작성 지침 - 매우 중요】

## 1. 매수 추천 TOP 10 종목별 (각 6~8 줄, **구체적인 숫자 명시**)

[순위. 종목명 (티커)] 투자의견: ★★★ (강력매수) / ★★ (매수) / ★ (약한매수)

✅ **매수 논리** (2 개 이상, 기술적 지표 기반):
   · 예: "RSI 28 로 과매도 구간, MACD 히스토그램 +0.12 로 전환되며 골든크로스 임박"
   · 예: "주가 BB 하단 (0%) 터치 후 반등, 5 일 모멘텀 +3.2% 로 가속화"

✅ **유명 투자자 포트폴리오** (해당 시):
   · 예: "Nancy Pelosi 보유종목 (+3 점), 박세익·존리 동시 보유 (+8 점)"

💰 **매수 전략** (3 단계 분할매수):
   · 1 차 매수: 현재가 (비중 40%)
   · 2 차 매수: -5% 추가 하락시 (비중 30%)
   · 3 차 매수: -10% 추가 하락시 (비중 30%)

🎯 **목표가** (3 단계):
   · 1 차 목표가: +10% (BB 상단 근접)
   · 2 차 목표가: +20% (전고점 돌파)
   · 3 차 목표가: +30% (과매수 구간)

🛑 **손절가**: -8% (MA60 하향 돌파 시)

⚠️ **리스크 요인**: (1~2 줄)

---

## 2. 매도 추천 TOP 10 종목별 (각 5~6 줄, **구체적인 숫자 명시**)

[순위. 종목명 (티커)] 투자의견: ▼▼▼ (강력매도) / ▼▼ (매도) / ▼ (비중축소)

❌ **매도 논리** (2 개 이상, 기술적 지표 기반):
   · 예: "RSI 78 로 과매수 구간, MACD 히스토그램 -0.08 로 전환되며 데드크로스"
   · 예: "주가 BB 상단 (100%) 에서 거절, 5 일 모멘텀 -4.5% 로 하락전환"

💸 **매도 전략**:
   · 즉시 매도: 50% 비중 축소
   · 추가 매도: 반등 시 +3% 근처에서 잔량 전량

🛑 **손절라인 (롱포지션)**: +5% (저항선)

📉 **하락 목표가**: -15% (MA60 지지)

⚠️ **리스크**: (1 줄)

---

## 3. 오늘의 종합 시장 판단 (6~8 줄)

📊 **시장 국면**: (상승장/하락장/박스권/변곡점)
📈 **섹터별 흐름**: (강세/약세 섹터 2 개씩)
💡 **단기 핵심 전략**: (1 가지, 구체적 숫자 포함)
   예: "RSI 30 이하 종목 분할매수, 10% 수익시 반씩 차익실현"
⚠️ **주의사항**: (1 줄)

─────────────────────────────────────────
⚠️ 본 분석은 참고용이며 투자 책임은 본인에게 있습니다.
모든 목표가·손절가는 기술적 지표 기반 추정치입니다."""

    try:
        resp = client.messages.create(
            model="claude-sonnet-4-6", max_tokens=8000,
            messages=[{"role": "user", "content": prompt}],
        )
        return resp.content[0].text
    except Exception as e:
        return f"[Claude API 오류: {e}]"


# ═══════════════════════════════════════════════════════════════
# 리포트 생성
# ═══════════════════════════════════════════════════════════════
def build_report(buy_top: list, sell_top: list,
                 total: int, claude_opinion: str) -> str:
    now = datetime.datetime.now().strftime("%Y년 %m월 %d일 %H:%M")
    L = []

    L.append("=" * 70)
    L.append(f"  📊 AI 주식 스크리닝 리포트  |  {now}")
    L.append(f"  스캔 {total}개 종목 → 매수 TOP10 / 매도 TOP10 선별")
    L.append("=" * 70)

    def fmt_block(stocks, header):
        L.append("\n" + "─" * 70)
        L.append(f"  {header}")
        L.append("─" * 70)
        for i, r in enumerate(stocks, 1):
            icon = "▲" if r["chg"] >= 0 else "▼"
            L.append(f"\n  {i:2d}위  {signal_label(r['score'])}  "
                     f"{r['name']} ({r['ticker']})  [{r['group']}]")
            L.append(f"       점수: {r['score']:+d}점  |  "
                     f"현재가: {r['price']:>12,.2f}  |  등락: {icon}{abs(r['chg']):.2f}%")
            L.append(f"       RSI: {r['rsi']:.1f}  |  MACD: {r['macd_hist']:+.4f}  |  "
                     f"5 일모멘텀: {r['mom5']:+.2f}%  |  BB: {r['bb_pct']:.0f}%")
            L.append(f"       MA5: {r['ma5']:,.2f}  MA20: {r['ma20']:,.2f}  "
                     f"MA60: {r['ma60']:,.2f}  |  거래량비: {r['vol_ratio']:.1f}x")

    fmt_block(buy_top,  "✅  매수 추천 TOP 10  (종합 점수 높은 순)")
    fmt_block(sell_top, "❌  매도 추천 TOP 10  (종합 점수 낮은 순)")

    L.append("\n" + "=" * 70)
    L.append("  🤖 Claude AI 심층 분석 의견")
    L.append("=" * 70)
    L.append(claude_opinion)

    L.append("\n" + "=" * 70)
    L.append("  ⚠️  기술적 분석 참고용 / 투자 손익 책임은 본인에게 있습니다.")
    L.append("=" * 70 + "\n")
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
            f"| 매수TOP10 / 매도TOP10"
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
# 카카오톡 나에게 보내기
# ═══════════════════════════════════════════════════════════════
def send_kakao(buy_top: list, sell_top: list):
    if not KAKAO_TOKEN:
        print("[카카오톡] KAKAO_TOKEN 미설정 — 건너뜀")
        return
    today = datetime.datetime.now().strftime("%m/%d")
    lines = [f"📊 [{today}] AI 주식 스크리닝\n"]
    lines.append("✅ 매수 추천 TOP 10")
    for i, r in enumerate(buy_top, 1):
        lines.append(f"  {i}. {r['name']}({r['ticker']}) {r['score']:+d}점 "
                     f"RSI:{r['rsi']:.0f} {r['chg']:+.1f}%")
    lines.append("\n❌ 매도 추천 TOP 10")
    for i, r in enumerate(sell_top, 1):
        lines.append(f"  {i}. {r['name']}({r['ticker']}) {r['score']:+d}점 "
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
    print(f"\n🚀 AI 주식 스크리닝 시작 — {start.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"   수신: {EMAIL_TO}\n")

    # ① 전종목 고속 스크리닝
    print("① 전종목 스크리닝...")
    results = run_screening()
    if len(results) < 10:
        print("❌ 유효 데이터 부족 — 종료")
        return
    buy_top  = results[:10]
    sell_top = results[-10:][::-1]
    print(f"   ✅ 유효 {len(results)}개 → 매수TOP10 / 매도TOP10 선별 완료")

    # ② 보조 데이터 수집
    print("② 거시경제 · 해외 · 뉴스 수집...")
    macro   = collect_macro()
    news    = collect_news()
    overseas = collect_overseas_snapshot()
    print(f"   거시 {len(macro)}개 · 뉴스 {len(news)}건 · 해외지표 {len(overseas)}개")

    # ③ Claude 심층 분석
    print("③ Claude 심층 분석 요청...")
    claude_opinion = ask_claude(buy_top, sell_top, macro, news, overseas)

    # ④ 리포트 저장
    report = build_report(buy_top, sell_top, len(results), claude_opinion)
    with open(REPORT_PATH, "w", encoding="utf-8") as f:
        f.write(report)
    print(f"④ 리포트 저장: {REPORT_PATH}")

    # ⑤ 알림 발송
    print("⑤ 알림 발송...")
    send_email(report)
    send_kakao(buy_top, sell_top)

    elapsed = int((datetime.datetime.now() - start).total_seconds())
    print(f"\n✅ 완료! 소요시간 {elapsed // 60}분 {elapsed % 60}초\n")


if __name__ == "__main__":
    main()
