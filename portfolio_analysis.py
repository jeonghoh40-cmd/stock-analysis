"""
보유 종목 맞춤 심층 분석 스크립트
- 매수 TOP10 미선정 보유 종목 집중 분석
- 실시간 기술적 지표 + Claude 투자 대처 방안 제시
"""

import os, sys, datetime
import yfinance as yf
import pandas as pd
import anthropic
from dotenv import dotenv_values

if sys.stdout.encoding != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

_env = dotenv_values(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env"))
def _get(k, d=""): return os.environ.get(k) or _env.get(k) or d

ANTHROPIC_API_KEY = _get("ANTHROPIC_API_KEY")

# ── 분석 대상 종목 ─────────────────────────────────────────────────────────
TARGET_STOCKS = {
    "에코프로":       "086520.KQ",
    "에코프로비엠":   "247540.KQ",
    "삼성물산":       "028260.KS",
}

# ── 기술적 지표 계산 함수 ──────────────────────────────────────────────────
def _rsi(close, n=14):
    d    = close.diff()
    gain = d.where(d > 0, 0.0).rolling(n).mean()
    loss = (-d.where(d < 0, 0.0)).rolling(n).mean()
    return float(100 - 100 / (1 + gain.iloc[-1] / (loss.iloc[-1] + 1e-9)))

def _macd(close):
    e12  = close.ewm(span=12, adjust=False).mean()
    e26  = close.ewm(span=26, adjust=False).mean()
    macd = e12 - e26
    sig  = macd.ewm(span=9, adjust=False).mean()
    hist = macd - sig
    return float(macd.iloc[-1]), float(sig.iloc[-1]), float(hist.iloc[-1])

def _bb(close):
    mid = close.rolling(20).mean()
    std = close.rolling(20).std()
    up  = (mid + 2*std).iloc[-1]
    dn  = (mid - 2*std).iloc[-1]
    cur = close.iloc[-1]
    pct = (cur - dn) / (up - dn) * 100 if (up - dn) > 0 else 50.0
    return round(up,0), round(dn,0), round(pct,1)

def _stoch(high, low, close, k=14, d=3):
    ll = low.rolling(k).min()
    hh = high.rolling(k).max()
    ks = (close - ll) / (hh - ll + 1e-9) * 100
    ds = ks.rolling(d).mean()
    return round(float(ks.iloc[-1]),1), round(float(ds.iloc[-1]),1)

def _obv(close, volume):
    direction = close.diff().apply(lambda x: 1 if x > 0 else (-1 if x < 0 else 0))
    return float((direction * volume).cumsum().iloc[-1])

def fetch_stock(name, ticker):
    print(f"  [{name}] {ticker} 데이터 수집 중...")
    df = yf.download(ticker, period="1y", interval="1d",
                     progress=False, auto_adjust=True)
    if df is None or df.empty or len(df) < 65:
        print(f"  [{name}] ❌ 데이터 부족")
        return None

    close  = df["Close"].squeeze()
    high   = df["High"].squeeze()
    low    = df["Low"].squeeze()
    volume = df["Volume"].squeeze()
    price  = float(close.iloc[-1])
    prev   = float(close.iloc[-2])
    chg    = round((price - prev) / prev * 100, 2)

    # 이동평균
    ma5   = float(close.rolling(5).mean().iloc[-1])
    ma20  = float(close.rolling(20).mean().iloc[-1])
    ma60  = float(close.rolling(60).mean().iloc[-1])
    ma120 = float(close.rolling(120).mean().iloc[-1])

    # 모멘텀
    mom5  = float((close.iloc[-1]/close.iloc[-6]-1)*100) if len(close)>5 else 0
    mom20 = float((close.iloc[-1]/close.iloc[-21]-1)*100) if len(close)>20 else 0
    mom60 = float((close.iloc[-1]/close.iloc[-61]-1)*100) if len(close)>60 else 0

    # 52주 고/저
    high52 = float(high.rolling(252).max().iloc[-1])
    low52  = float(low.rolling(252).min().iloc[-1])
    dist_from_high = round((price - high52)/high52*100, 1)
    dist_from_low  = round((price - low52)/low52*100, 1)

    rsi               = _rsi(close)
    macd_v, sig, hist = _macd(close)
    bb_up, bb_dn, bb_pct = _bb(close)
    stoch_k, stoch_d  = _stoch(high, low, close)

    vol_avg = float(volume.rolling(20).mean().iloc[-1])
    vol_cur = float(volume.iloc[-1])
    vol_ratio = round(vol_cur / (vol_avg + 1e-9), 2)

    # 지지/저항 레벨
    recent_high = float(high.tail(60).max())
    recent_low  = float(low.tail(60).min())

    # 히스토리 (최근 10일)
    hist_data = []
    for i in range(min(10, len(df))):
        idx = -(i+1)
        d_date = df.index[idx].strftime("%m/%d")
        d_close = float(close.iloc[idx])
        d_vol   = int(volume.iloc[idx])
        hist_data.append(f"  {d_date}: {d_close:>10,.0f}원  거래량:{d_vol/10000:.1f}만주")
    hist_data.reverse()

    return {
        "name": name, "ticker": ticker,
        "price": price, "prev": prev, "chg": chg,
        "rsi": round(rsi,1), "stoch_k": stoch_k, "stoch_d": stoch_d,
        "macd": round(macd_v,2), "macd_sig": round(sig,2), "macd_hist": round(hist,2),
        "ma5": round(ma5,0), "ma20": round(ma20,0),
        "ma60": round(ma60,0), "ma120": round(ma120,0),
        "bb_up": bb_up, "bb_dn": bb_dn, "bb_pct": bb_pct,
        "mom5": round(mom5,2), "mom20": round(mom20,2), "mom60": round(mom60,2),
        "vol_ratio": vol_ratio, "vol_avg": round(vol_avg/10000,1),
        "high52": round(high52,0), "low52": round(low52,0),
        "dist_from_high": dist_from_high, "dist_from_low": dist_from_low,
        "recent_high": round(recent_high,0), "recent_low": round(recent_low,0),
        "history": "\n".join(hist_data),
    }

def build_stock_block(s):
    """Claude 프롬프트용 종목 데이터 블록"""
    ma_align = "정배열(↑)" if s["ma5"] > s["ma20"] > s["ma60"] else (
               "역배열(↓)" if s["ma5"] < s["ma20"] < s["ma60"] else "혼조")
    return f"""
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
【 {s['name']} ({s['ticker']}) 】
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
● 현재가:   {s['price']:>10,.0f}원  ({s['chg']:+.2f}%)
● 52주 고:  {s['high52']:>10,.0f}원  (현재가 대비 {s['dist_from_high']:+.1f}%)
● 52주 저:  {s['low52']:>10,.0f}원  (현재가 대비 {s['dist_from_low']:+.1f}%)
● 60일 고:  {s['recent_high']:>10,.0f}원
● 60일 저:  {s['recent_low']:>10,.0f}원

[이동평균]
  MA5:  {s['ma5']:>10,.0f}  |  MA20: {s['ma20']:>10,.0f}
  MA60: {s['ma60']:>10,.0f}  |  MA120:{s['ma120']:>10,.0f}
  배열: {ma_align}  |  현재가 vs MA60: {(s['price']-s['ma60'])/s['ma60']*100:+.1f}%

[오실레이터]
  RSI(14):    {s['rsi']:.1f}
  Stochastic: K={s['stoch_k']:.1f}  D={s['stoch_d']:.1f}
  MACD:       {s['macd']:+.2f}  |  Signal: {s['macd_sig']:+.2f}  |  Hist: {s['macd_hist']:+.2f}

[볼린저밴드]
  상단: {s['bb_up']:>10,.0f}  |  하단: {s['bb_dn']:>10,.0f}  |  위치: {s['bb_pct']:.1f}%

[모멘텀]
  5일:  {s['mom5']:+.2f}%  |  20일: {s['mom20']:+.2f}%  |  60일: {s['mom60']:+.2f}%

[거래량]
  오늘 vs 20일평균: {s['vol_ratio']:.2f}x  (20일 평균 {s['vol_avg']:.1f}만주)

[최근 10일 주가]
{s['history']}
"""

def ask_claude_portfolio(stocks_data):
    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
    now_str = datetime.datetime.now().strftime("%Y년 %m월 %d일 %H:%M")

    blocks = "\n".join(build_stock_block(s) for s in stocks_data)

    prompt = f"""당신은 한국 주식시장 전문 애널리스트입니다.
분석 일자: {now_str}

아래는 투자자가 현재 보유 중이나, 오늘 AI 스크리닝 매수 TOP10에 포함되지 못한 종목들의 실시간 기술적 지표입니다.
투자자가 이 종목들을 현재 보유 중이라는 가정 하에 **향후 대처 방안**을 구체적으로 제시해 주세요.

{blocks}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
【 시장 맥락 (오늘 기준) 】
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
- KOSPI: 2,681 (+0.67%)
- KOSDAQ: 765 (+1.02%)
- USD/KRW: 1,435원 (+0.63%)
- WTI 유가: 69.43달러 (+0.55%)
- 미 10년채: 4.27% (-0.77%)
- VIX: 18.63 (+3.90%)
- 2차전지 섹터: 전반적 약세 지속 (CATL 저가 공세, EV 수요 둔화)
- 건설/지주 섹터: 부동산 경기 불확실성 지속
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

각 종목에 대해 아래 형식으로 상세하게 분석해 주세요:

═══════════════════════════════════════════════
【 종목명 (티커) 】 현재 상태 진단
═══════════════════════════════════════════════

## 1. 기술적 현황 진단 (3~4줄)
- 이동평균 배열 상태와 지지/저항 분석
- RSI·MACD·스토캐스틱 오실레이터 종합 해석
- 볼린저밴드 위치와 모멘텀 방향성

## 2. 매수 TOP10 미선정 이유 분석 (2~3줄)
- 현재 기술적 점수가 낮은 구체적인 이유
- 다른 상위 종목 대비 약점

## 3. 보유자 대처 방안 (가장 중요 - 구체적 숫자 必)

### 📌 시나리오 A: 현재가 기준 단기 반등 가능성
- 반등 신호 조건: (예: "RSI가 XX 이하로 하락 후 반등", "MACD 골든크로스 시")
- 목표 반등가: X원 (현재가 대비 +X%)
- 이 경우 전략: (보유 유지 / 추가 매수 / 비중 조절)

### 📌 시나리오 B: 추가 하락 시 대응
- 1차 지지선: X원 (MA60 / 52주 저가 / 심리적 지지 등)
- 2차 지지선: X원
- 손절 고려 가격: X원 (이 가격 하향 돌파 시 추세 훼손)
- 이 경우 전략: (분할 매수 / 비중 유지 / 손절 후 재진입 시점)

### 📌 시나리오 C: 중장기 보유 관점
- 종목의 펀더멘털 회복 조건
- 중장기 목표가: X원 (XX% 수익)
- 보유 기간 추정: X개월 / X분기

## 4. 리스크 요인 (2~3가지)
- 종목 고유 리스크
- 섹터 리스크
- 시장 리스크

## 5. 핵심 결론 (1줄 요약)
→ "보유 유지 / 분할 추가 / 비중 축소 / 손절 검토" 중 하나 + 이유

---

분석 시 반드시:
- 실제 현재가와 기술적 지표 수치를 인용할 것
- 목표가·손절가는 반드시 구체적인 원화 금액으로 제시
- 52주 고점 대비 현재 낙폭 심각성을 언급
- 각 종목 섹터의 현재 업황을 반영

⚠️ 본 분석은 기술적 지표 기반 참고용이며 투자 최종 책임은 투자자 본인에게 있습니다."""

    print("  Claude AI 분석 요청 중...")
    resp = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=10000,
        messages=[{"role": "user", "content": prompt}],
    )
    return resp.content[0].text

def main():
    print(f"\n🔍 보유 종목 맞춤 심층 분석 시작")
    print(f"   분석 시각: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"   대상: {', '.join(TARGET_STOCKS.keys())}\n")

    # 데이터 수집
    stocks_data = []
    for name, ticker in TARGET_STOCKS.items():
        data = fetch_stock(name, ticker)
        if data:
            stocks_data.append(data)

    if not stocks_data:
        print("❌ 수집된 데이터 없음")
        return

    print(f"\n✅ {len(stocks_data)}개 종목 데이터 수집 완료\n")

    # Claude 분석
    print("🤖 Claude AI 심층 분석 시작...")
    analysis = ask_claude_portfolio(stocks_data)

    # 리포트 출력
    now_str = datetime.datetime.now().strftime("%Y년 %m월 %d일 %H:%M")
    separator = "=" * 70

    report = f"""
{separator}
  🔍 보유 종목 맞춤 심층 분석 리포트  |  {now_str}
  대상: {', '.join(s['name'] for s in stocks_data)}
{separator}

"""
    # 기술적 지표 요약표
    report += "【 기술적 지표 요약 】\n"
    report += f"{'종목':<12} {'현재가':>10} {'등락':>7} {'RSI':>6} {'MACD_H':>10} {'BB%':>6} {'MA배열':>10} {'52주낙폭':>10}\n"
    report += "-" * 80 + "\n"
    for s in stocks_data:
        ma_align = "정배열" if s["ma5"] > s["ma20"] > s["ma60"] else (
                   "역배열" if s["ma5"] < s["ma20"] < s["ma60"] else "혼조")
        report += (f"{s['name']:<10} {s['price']:>10,.0f} {s['chg']:>+6.2f}% "
                   f"{s['rsi']:>6.1f} {s['macd_hist']:>+10.2f} {s['bb_pct']:>5.1f}% "
                   f"{ma_align:>10} {s['dist_from_high']:>+8.1f}%\n")

    report += f"\n{separator}\n"
    report += "  🤖 Claude AI 투자 대처 방안\n"
    report += f"{separator}\n\n"
    report += analysis

    report += f"\n\n{separator}\n"
    report += "  ⚠️  기술적 분석 참고용 / 투자 손익 책임은 본인에게 있습니다.\n"
    report += f"{separator}\n"

    # 파일 저장
    out_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "portfolio_report.txt")
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(report)

    print(report)
    print(f"\n📄 리포트 저장: {out_path}")

if __name__ == "__main__":
    main()
