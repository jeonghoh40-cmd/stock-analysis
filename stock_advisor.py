"""
AI 주식 스크리닝 어드바이저 (동적 TOP10 선별판)

실행 흐름:
  ① 국내50 + 미국60 + 중국40 = 약 150개 전종목 병렬 스크리닝
  ② 기술적 점수 계산 → 매수 TOP10 / 매도 TOP10 자동 선별
  ③ 거시경제 + 뉴스 + 해외섹터 + DART 재무 데이터 수집
  ④ Claude가 선별된 20개 종목 심층 분석 → 투자 의견
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
import glob
from dotenv import dotenv_values
from universe import UNIVERSE

if sys.stdout.encoding != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

# ── .env 로드 ─────────────────────────────────────────────────
_env_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")
_cfg = dotenv_values(_env_path)

def _get(key: str, default: str = "") -> str:
    return os.environ.get(key) or _cfg.get(key) or default

BASE_DIR     = os.path.dirname(os.path.abspath(__file__))
REPORT_PATH  = os.path.join(BASE_DIR, "report.txt")          # 최신본 (이메일용)
REPORTS_DIR  = os.path.join(BASE_DIR, "reports")             # 히스토리 디렉토리
os.makedirs(REPORTS_DIR, exist_ok=True)

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

def _atr(df: pd.DataFrame, n: int = 14) -> float:
    """
    Average True Range (14일) — 변동성 기반 손절가·목표가 산출 기준
      True Range = max(High-Low, |High-PrevClose|, |Low-PrevClose|)
      손절가    = 진입가 - 2 × ATR   (2ATR 룰)
      목표가    = 진입가 + 3 × ATR   (Risk:Reward ≈ 1 : 1.5)
    """
    try:
        high  = df["High"].squeeze()
        low   = df["Low"].squeeze()
        close = df["Close"].squeeze()
        prev  = close.shift(1)
        tr = pd.concat([
            high - low,
            (high - prev).abs(),
            (low  - prev).abs(),
        ], axis=1).max(axis=1)
        return float(tr.rolling(n).mean().iloc[-1])
    except Exception:
        return 0.0

def score_stock(rsi, macd_hist, price, ma5, ma20, ma60, mom5,
                bb_pct: float = 50.0, vol_ratio: float = 1.0,
                chg: float = 0.0) -> int:
    """기술적 종합 점수 –100 ~ +100

    지표별 배점:
      RSI(14)        : ±40
      MACD hist      : ±20
      이동평균 정배열 : ±15
      MA5 vs MA20    : ±10
      5일 모멘텀     : ±10
      볼린저밴드 위치 : ±15  ← 신규
      거래량 방향성  : ±10  ← 신규
    """
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
    # 이동평균 정배열 (±15)
    if price > ma20 > ma60:   s += 15
    elif price > ma20:        s += 7
    elif price < ma20 < ma60: s -= 15
    elif price < ma20:        s -= 7
    # MA5 vs MA20 (±10)
    s += 10 if ma5 > ma20 else -10
    # 5일 모멘텀 (±10)
    if   mom5 >  5: s += 10
    elif mom5 >  2: s += 5
    elif mom5 < -5: s -= 10
    elif mom5 < -2: s -= 5
    # ── 볼린저밴드 위치 (±15) ─────────────────────────
    # bb_pct=0 : 하단(과매도) → 매수 신호
    # bb_pct=100: 상단(과매수) → 매도 신호
    if   bb_pct < 10: s += 15
    elif bb_pct < 20: s += 8
    elif bb_pct > 90: s -= 15
    elif bb_pct > 80: s -= 8
    # ── 거래량 방향성 (±10) ──────────────────────────
    # 거래량 급증 + 가격 상승 = 강한 매수 신호
    # 거래량 급증 + 가격 하락 = 강한 매도 신호
    if   vol_ratio > 2.0 and chg > 0: s += 10
    elif vol_ratio > 2.0 and chg < 0: s -= 10
    elif vol_ratio > 1.5 and chg > 0: s += 5
    elif vol_ratio > 1.5 and chg < 0: s -= 5
    return max(-100, min(100, s))


def score_with_investor_weight(ticker: str, base_score: int) -> tuple:
    """
    유명 투자자 포트폴리오 가중치를 적용한 점수 보정.

    반환: (조정된_점수, 투자자_보너스, 노트_리스트)

    점수 기준:
      Pelosi 의회 매수 공시  : +15
      ARK 비중 ≥1%          : +15  / 0.5% : +10  / 보유 : +5
      Pelosi + ARK 동시 보유 : +5 추가
      국내 유명투자자 픽      : 최대 +15 (박세익·존리·이채원·김민국·강방천)
    """
    try:
        from investor_scorer import get_investor_score
        inv = get_investor_score(ticker)   # .KS/.KQ 처리는 investor_scorer 내부에서

        bonus = 0
        if inv['is_pelosi_pick']:
            bonus += inv['pelosi_score']
        if inv['is_ark_pick']:
            bonus += inv['ark_score']
        if inv['is_pelosi_pick'] and inv['is_ark_pick']:
            bonus += 5
        # 국내 유명 투자자 픽 (최대 +15)
        kr_bonus = min(15, inv.get('korean_investor_score', 0))
        bonus += kr_bonus

        new_score = max(-100, min(100, base_score + bonus))
        return new_score, bonus, inv.get('investor_notes', [])
    except Exception:
        return base_score, 0, []


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

        vol = df["Volume"].squeeze() if "Volume" in df.columns else pd.Series([0]*len(df))
        vol_avg = float(vol.rolling(20).mean().iloc[-1])
        vol_cur = float(vol.iloc[-1])
        vol_ratio = round(vol_cur / (vol_avg + 1e-9), 2)

        # BB + 거래량 방향성을 포함한 기술적 종합 점수
        base_score = score_stock(
            rsi, macd_hist, price, ma5, ma20, ma60, mom5,
            bb_pct=bb_pct, vol_ratio=vol_ratio, chg=chg
        )

        # 유명 투자자 포트폴리오 가중치 적용 (Pelosi·ARK·국내 5인)
        score, inv_bonus, inv_notes = score_with_investor_weight(ticker, base_score)

        # ATR 기반 손절가·목표가 (2ATR 손절 / 3ATR 목표 → R:R ≈ 1:1.5)
        atr          = _atr(df)
        stop_loss    = round(price - 2 * atr, 2) if atr else None
        target_price = round(price + 3 * atr, 2) if atr else None

        return {
            "group": group, "name": name, "ticker": ticker,
            "price": round(price, 2), "chg": chg,
            "rsi": round(rsi, 1), "macd_hist": round(macd_hist, 4),
            "ma5": round(ma5, 2), "ma20": round(ma20, 2), "ma60": round(ma60, 2),
            "bb_up": bb_up, "bb_dn": bb_dn, "bb_pct": bb_pct,
            "mom5": round(mom5, 2), "vol_ratio": vol_ratio,
            "score": score,
            "inv_bonus": inv_bonus,           # 투자자 보너스 점수
            "inv_notes": inv_notes,           # 투자자 태그 리스트
            "atr":          round(atr, 2) if atr else None,
            "stop_loss":    stop_loss,
            "target_price": target_price,
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
        "USD/KRW": "KRW=X",  "WTI유가": "CL=F",
        "금(Gold)": "GC=F",  "VIX": "^VIX",
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
                    "등락(%)": round((cur-prev)/prev*100, 2),
                }
        except Exception:
            pass
    return macro


def collect_news() -> list:
    """
    6개 경제 뉴스 RSS를 모두 수집한다.
    - break 제거: 첫 성공 소스에서 멈추지 않고 전체 수집
    - 중복 제거: 동일 제목 헤드라인 필터링
    - 최대 20건 반환
    """
    rss_sources = [
        "https://www.yonhapnewstv.co.kr/category/news/economy/feed/",  # 연합뉴스TV
        "https://rss.donga.com/economy.xml",                            # 동아경제
        "https://www.mk.co.kr/rss/30000001/",                          # 매일경제
        "https://rss.mt.co.kr/mt_news.xml",                            # 머니투데이
        "https://rss.hankyung.com/economy.xml",                        # 한국경제
        "https://www.sedaily.com/RSS/Economy",                         # 서울경제
    ]
    headlines: list = []
    seen:      set  = set()

    for rss in rss_sources:
        try:
            feed = feedparser.parse(rss)
            for entry in feed.entries[:5]:   # 소스당 최대 5건
                title = entry.get("title", "").strip()
                if title and title not in seen:
                    seen.add(title)
                    headlines.append(title)
        except Exception:
            continue

    return headlines[:20]   # 최대 20건


def collect_overseas_snapshot() -> dict:
    snap = {}
    for tk, label in [
        ("NVDA","엔비디아"), ("TSM","TSMC"), ("ASML","ASML"),
        ("SOXX","반도체ETF"), ("TSLA","테슬라"), ("LIT","리튬ETF"),
        ("META","메타"), ("GOOGL","알파벳"), ("MSFT","MS"),
        ("LMT","록히드마틴"), ("^TNX","미10년채"), ("DX=F","달러인덱스"),
    ]:
        try:
            h = yf.Ticker(tk).history(period="10d")
            if not h.empty:
                cur  = float(h["Close"].iloc[-1])
                prev = float(h["Close"].iloc[-2]) if len(h) > 1 else cur
                snap[label] = {
                    "현재": round(cur, 2),
                    "전일(%)": round((cur-prev)/prev*100, 2),
                }
        except Exception:
            pass
    return snap


# ═══════════════════════════════════════════════════════════════
# DART 재무 점수 가산 (국내주 전용)
# ═══════════════════════════════════════════════════════════════
def apply_dart_bonus(results: list) -> list:
    """
    스크리닝 결과 중 국내주(.KS/.KQ)에 DART 재무 점수를 가산한다.
    대상: 전체 결과의 상위 40개 + 하위 40개 (매수/매도 후보 범위)

    점수 기준:
      영업이익률 > 15%  : +10
      영업이익률 > 10%  : +5
      영업이익률 < 0%   : -15  (적자)
      부채비율   < 50%  : +10
      부채비율   < 100% : +5
      부채비율   > 200% : -10
      유상증자·영업정지 공시 : -15
    """
    try:
        from dart_collector import collect_dart_data
    except ImportError:
        print("  [DART] dart_collector 모듈 없음 — 건너뜀")
        return results

    dart_key = _get("DART_API_KEY")
    if not dart_key:
        print("  [DART] DART_API_KEY 미설정 — 건너뜀")
        return results

    # 매수·매도 후보 범위(상위·하위 40개)에서 국내주만 추출
    candidate_range = results[:40] + results[-40:]
    seen_tickers: set = set()
    domestic = []
    for r in candidate_range:
        t = r["ticker"]
        if t.endswith((".KS", ".KQ")) and t not in seen_tickers:
            seen_tickers.add(t)
            domestic.append(r)

    if not domestic:
        return results

    codes = [r["ticker"].replace(".KS", "").replace(".KQ", "") for r in domestic]
    print(f"  [DART] 국내 {len(codes)}개 종목 재무 데이터 조회 중...")

    try:
        dart_data = collect_dart_data(codes, dart_key)
    except Exception as e:
        print(f"  [DART] 수집 오류: {e} — 건너뜀")
        return results

    # 종목별 보너스 점수 계산
    bonus_map: dict = {}
    neg_keywords = ["유상증자", "영업정지", "불성실공시", "횡령", "배임"]

    for r in domestic:
        code = r["ticker"].replace(".KS", "").replace(".KQ", "")
        fin  = dart_data.get(code, {}).get("재무제표", {})
        important = dart_data.get(code, {}).get("중요공시", [])

        bonus = 0
        opr_margin = fin.get("영업이익률(%)")
        debt_ratio = fin.get("부채비율(%)")

        if opr_margin is not None:
            if   opr_margin > 15: bonus += 10
            elif opr_margin > 10: bonus += 5
            elif opr_margin <  0: bonus -= 15   # 적자

        if debt_ratio is not None:
            if   debt_ratio <  50: bonus += 10
            elif debt_ratio < 100: bonus += 5
            elif debt_ratio > 200: bonus -= 10

        for d in important:
            if any(kw in d.get("제목", "") for kw in neg_keywords):
                bonus -= 15
                break  # 종목당 최대 1회만 페널티

        bonus_map[r["ticker"]] = bonus

    # 점수 반영 후 재정렬
    adjusted = []
    for r in results:
        if r["ticker"] in bonus_map:
            b = bonus_map[r["ticker"]]
            adjusted.append({
                **r,
                "score":      max(-100, min(100, r["score"] + b)),
                "dart_bonus": b,
            })
        else:
            adjusted.append({**r, "dart_bonus": 0})

    adjusted.sort(key=lambda x: x["score"], reverse=True)

    applied = sum(1 for r in adjusted if r.get("dart_bonus", 0) != 0)
    print(f"  [DART] ✅ {applied}개 국내 종목 재무 점수 가산 완료")
    return adjusted


# ═══════════════════════════════════════════════════════════════
# 수급 점수 가산 (국내주 전용 — pykrx 외국인·기관 5일 순매수)
# ═══════════════════════════════════════════════════════════════
def apply_investor_flow(results: list) -> list:
    """
    스크리닝 결과 중 국내주(.KS/.KQ)에 수급 점수를 가산한다.
    외국인 + 기관 5일 누적 순매수 비율 → -30 ~ +30점.
    pykrx 미설치 또는 API 실패 시 원본 그대로 반환.
    """
    try:
        from investor_flow import collect_all_flows, calc_flow_score
    except ImportError:
        print("  [수급] investor_flow 모듈 없음 — 건너뜀")
        return results

    # 매수·매도 후보 범위 내 국내주만 추출
    candidate_range = results[:40] + results[-40:]
    seen: set = set()
    domestic = []
    for r in candidate_range:
        t = r["ticker"]
        if t.endswith((".KS", ".KQ")) and t not in seen:
            seen.add(t)
            domestic.append(r)

    if not domestic:
        return results

    codes = [r["ticker"].replace(".KS", "").replace(".KQ", "") for r in domestic]
    print(f"  [수급] 국내 {len(codes)}개 종목 외국인·기관 순매수 조회 중...")

    try:
        flow_data = collect_all_flows(codes)
    except Exception as e:
        print(f"  [수급] 수집 오류: {e} — 건너뜀")
        return results

    # 종목별 수급 점수 매핑
    flow_map: dict = {}
    for r in domestic:
        code = r["ticker"].replace(".KS", "").replace(".KQ", "")
        d    = flow_data.get(code)
        if d:
            flow_map[r["ticker"]] = calc_flow_score(
                d["foreign_net"], d["inst_net"], d["market_cap"]
            )

    # 점수 반영 후 재정렬
    adjusted = []
    for r in results:
        fs = flow_map.get(r["ticker"], 0)
        adjusted.append({
            **r,
            "score":      max(-100, min(100, r["score"] + fs)),
            "flow_score": fs,
        })

    adjusted.sort(key=lambda x: x["score"], reverse=True)

    applied = sum(1 for r in adjusted if r.get("flow_score", 0) != 0)
    print(f"  [수급] ✅ {applied}개 국내 종목 수급 점수 가산 완료")
    return adjusted


# ═══════════════════════════════════════════════════════════════
# Claude 심층 분석 (TOP20 대상)
# ═══════════════════════════════════════════════════════════════
def ask_claude(buy_top: list, sell_top: list,
               macro: dict, news: list, overseas: dict) -> str:
    try:
        import anthropic
        client = anthropic.Anthropic(api_key=_get("ANTHROPIC_API_KEY"))
    except Exception as e:
        return f"[Claude 분석 생략 — ANTHROPIC_API_KEY 없음: {e}]"

    macro_txt = "\n".join(
        f"  {k}: {v['현재']} ({v['등락(%)']:+.2f}%)"
        for k, v in macro.items()
    )
    news_txt = "\n".join(f"  - {h}" for h in news[:8]) if news else "  (뉴스 없음)"
    ov_txt   = "\n".join(
        f"  {k}: {v['현재']} ({v['전일(%)']:+.2f}%)"
        for k, v in overseas.items()
    )

    def stock_block(stocks, label):
        lines = [f"\n[{label}]"]
        for r in stocks:
            lines.append(
                f"  {r['name']}({r['ticker']}) | 점수:{r['score']:+d} | "
                f"가격:{r['price']:,.2f} ({r['chg']:+.1f}%) | "
                f"RSI:{r['rsi']:.0f} | MACD hist:{r['macd_hist']:+.4f} | "
                f"MA5:{r['ma5']:,.2f} MA20:{r['ma20']:,.2f} MA60:{r['ma60']:,.2f} | "
                f"BB위치:{r['bb_pct']:.0f}% | 모멘텀:{r['mom5']:+.1f}% | "
                f"거래량비:{r['vol_ratio']:.1f}x"
            )
        return "\n".join(lines)

    prompt = f"""당신은 한국·미국·중국 주식시장 전문 애널리스트입니다.
오늘 {datetime.datetime.now().strftime('%Y년 %m월 %d일')} 기준 데이터를 바탕으로
기술적 스크리닝으로 선별된 20개 종목에 대해 투자 의견을 작성하세요.

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
【작성 지침】

1. 매수 추천 TOP 10 종목별 (각 4~5줄):
   [순위. 종목명] 투자의견: ★★★ / ★★ / ★
   · 핵심 매수 근거 (기술적+거시 연계)
   · 목표가 / 손절가
   · 주의 리스크

2. 매도 추천 TOP 10 종목별 (각 3~4줄):
   [순위. 종목명] 매도/비중축소 의견
   · 핵심 매도 근거
   · 손실 제한 전략

3. 오늘의 종합 시장 판단 (5줄 이내):
   · 시장 국면 + 섹터별 흐름
   · 단기 핵심 전략 1가지

⚠️ 본 분석은 참고용이며 투자 책임은 본인에게 있습니다."""

    try:
        resp = client.messages.create(
            model="claude-sonnet-4-6", max_tokens=6000,
            messages=[{"role": "user", "content": prompt}],
        )
        return resp.content[0].text
    except Exception as e:
        return f"[Claude API 오류: {e}]"


# ═══════════════════════════════════════════════════════════════
# 리포트 히스토리 관리
# ═══════════════════════════════════════════════════════════════
def save_report_history(report_text: str) -> str:
    """
    reports/ 디렉토리에 날짜별 리포트를 보관한다.
    - 파일명: reports/report_YYYYMMDD_HHMMSS.txt
    - 최근 30개만 유지, 오래된 파일 자동 삭제
    - report.txt(최신본)도 동시에 갱신 (이메일 발송용)
    반환: 저장된 히스토리 파일 경로
    """
    ts        = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    hist_path = os.path.join(REPORTS_DIR, f"report_{ts}.txt")

    # 날짜별 히스토리 저장
    with open(hist_path, "w", encoding="utf-8") as f:
        f.write(report_text)

    # 최신본 갱신 (report.txt)
    with open(REPORT_PATH, "w", encoding="utf-8") as f:
        f.write(report_text)

    # 오래된 파일 정리 (최근 30개만 유지)
    all_reports = sorted(glob.glob(os.path.join(REPORTS_DIR, "report_*.txt")))
    for old in all_reports[:-30]:
        try:
            os.remove(old)
        except OSError:
            pass

    return hist_path


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
            dart_tag = f" [DART:{r['dart_bonus']:+d}]" if r.get("dart_bonus") else ""
            inv_tag  = f" [투자자:{r['inv_bonus']:+d}]"  if r.get("inv_bonus") else ""
            flow_tag = f" [수급:{r.get('flow_score', 0):+d}]" if r.get("flow_score") else ""
            L.append(f"\n  {i:2d}위  {signal_label(r['score'])}  "
                     f"{r['name']} ({r['ticker']})  [{r['group']}]{dart_tag}{inv_tag}{flow_tag}")
            L.append(f"       점수: {r['score']:+d}점  |  "
                     f"현재가: {r['price']:>12,.2f}  |  등락: {icon}{abs(r['chg']):.2f}%")
            L.append(f"       RSI: {r['rsi']:.1f}  |  MACD: {r['macd_hist']:+.4f}  |  "
                     f"5일모멘텀: {r['mom5']:+.2f}%  |  BB: {r['bb_pct']:.0f}%")
            L.append(f"       MA5: {r['ma5']:,.2f}  MA20: {r['ma20']:,.2f}  "
                     f"MA60: {r['ma60']:,.2f}  |  거래량비: {r['vol_ratio']:.1f}x")
            # 투자자 노트 (Pelosi·ARK·국내 투자자 명)
            if r.get("inv_notes"):
                L.append(f"       👤 {' / '.join(r['inv_notes'][:3])}")
            # ATR 기반 손절가·목표가 (매수 종목만 표시)
            if r.get("stop_loss") and r.get("target_price") and r.get("atr"):
                L.append(f"       ATR14: {r['atr']:,.2f}  |  "
                         f"손절가: {r['stop_loss']:,.2f}  |  "
                         f"목표가: {r['target_price']:,.2f}")

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
    # 한글 플레이스홀더 감지 (실제 토큰은 ASCII 문자만 포함)
    try:
        KAKAO_TOKEN.encode("ascii")
    except UnicodeEncodeError:
        print("[카카오톡] ⚠️ KAKAO_TOKEN이 플레이스홀더입니다. "
              ".env에 실제 액세스 토큰을 입력하세요.")
        print("  발급 방법: https://developers.kakao.com → "
              "내 애플리케이션 → 카카오 로그인 → 액세스 토큰")
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
        from urllib.parse import urlencode
        body = urlencode({
            "template_object": json.dumps(
                {"object_type": "text", "text": text,
                 "link": {"web_url": "", "mobile_web_url": ""}},
                ensure_ascii=False,
            )
        }).encode("utf-8")
        resp = requests.post(
            "https://kapi.kakao.com/v2/api/talk/memo/default/send",
            headers={
                "Authorization": f"Bearer {KAKAO_TOKEN}",
                "Content-Type": "application/x-www-form-urlencoded; charset=utf-8",
            },
            data=body,
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
    print(f"   ✅ 유효 {len(results)}개 스크리닝 완료")

    # ① - b: 국내주 DART 재무 점수 가산 → 재정렬
    print("  DART 재무 점수 보정 중...")
    results = apply_dart_bonus(results)

    # ① - c: 국내주 수급 점수 가산 (외국인·기관 5일 순매수)
    print("  수급 점수 보정 중...")
    results = apply_investor_flow(results)

    buy_top  = results[:10]
    sell_top = results[-10:][::-1]
    print(f"   ✅ 매수TOP10 / 매도TOP10 선별 완료 (DART·수급 보정 적용)")

    # ② 보조 데이터 수집
    print("② 거시경제 · 해외 · 뉴스 수집...")
    macro   = collect_macro()
    news    = collect_news()
    overseas = collect_overseas_snapshot()
    print(f"   거시 {len(macro)}개 · 뉴스 {len(news)}건 · 해외지표 {len(overseas)}개")

    # ③ Claude 심층 분석
    print("③ Claude 심층 분석 요청...")
    claude_opinion = ask_claude(buy_top, sell_top, macro, news, overseas)

    # ④ 리포트 저장 (최신본 + 히스토리)
    report    = build_report(buy_top, sell_top, len(results), claude_opinion)
    hist_path = save_report_history(report)
    print(f"④ 리포트 저장: {REPORT_PATH}")
    print(f"   히스토리  : {hist_path}")

    # ⑤ 알림 발송
    print("⑤ 알림 발송...")
    send_email(report)
    send_kakao(buy_top, sell_top)

    # ⑥ DB 저장 + 30일 백테스팅 성과 출력
    print("⑥ DB 저장 + 백테스팅...")
    try:
        from db_manager import save_screening, get_performance_summary
        save_screening(buy_top, sell_top, macro)
        perf = get_performance_summary(30)
        if perf:
            print(f"   [30일 백테스팅] "
                  f"종목수:{perf['종목수']}  "
                  f"승률:{perf['승률(%)']:.1f}%  "
                  f"평균수익률:{perf['평균수익률']:+.2f}%  "
                  f"최대수익률:{perf['최대수익률']:+.2f}%  "
                  f"최대손실률:{perf['최대손실률']:+.2f}%")
        else:
            print("   [백테스팅] 데이터 누적 중 (오늘이 첫 실행이면 내일부터 표시)")
    except Exception as e:
        print(f"   [DB] ⚠️ {e}")

    elapsed = int((datetime.datetime.now() - start).total_seconds())
    print(f"\n✅ 완료! 소요시간 {elapsed // 60}분 {elapsed % 60}초\n")


if __name__ == "__main__":
    main()
