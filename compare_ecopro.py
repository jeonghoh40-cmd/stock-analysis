"""
에코프로 어제/오늘 기술적 지표 비교 분석
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

def calc_for_day(close, high, low, volume, offset=0):
    """offset=0: 오늘, offset=1: 어제"""
    if offset > 0:
        close  = close.iloc[:-offset]
        high   = high.iloc[:-offset]
        low    = low.iloc[:-offset]
        volume = volume.iloc[:-offset]

    price  = float(close.iloc[-1])
    prev   = float(close.iloc[-2])
    chg    = (price - prev) / prev * 100

    ma5   = float(close.rolling(5).mean().iloc[-1])
    ma20  = float(close.rolling(20).mean().iloc[-1])
    ma60  = float(close.rolling(60).mean().iloc[-1])
    ma120 = float(close.rolling(120).mean().iloc[-1])

    rsi               = _rsi(close)
    macd_v, sig, hist = _macd(close)
    bb_up, bb_dn, bb_pct = _bb(close)
    stoch_k, stoch_d  = _stoch(high, low, close)

    vol_avg   = float(volume.rolling(20).mean().iloc[-1])
    vol_today = float(volume.iloc[-1])
    vol_ratio = vol_today / (vol_avg + 1e-9)

    mom5  = float((close.iloc[-1]/close.iloc[-6]-1)*100) if len(close)>5 else 0
    mom20 = float((close.iloc[-1]/close.iloc[-21]-1)*100) if len(close)>20 else 0
    mom60 = float((close.iloc[-1]/close.iloc[-61]-1)*100) if len(close)>60 else 0

    high52 = float(high.rolling(252).max().iloc[-1])
    dist_from_high = (price - high52)/high52*100

    return {
        "price": price, "chg": chg,
        "ma5": round(ma5,0), "ma20": round(ma20,0),
        "ma60": round(ma60,0), "ma120": round(ma120,0),
        "rsi": round(rsi,1),
        "macd": round(macd_v,2), "sig": round(sig,2), "hist": round(hist,2),
        "bb_up": bb_up, "bb_dn": bb_dn, "bb_pct": bb_pct,
        "stoch_k": stoch_k, "stoch_d": stoch_d,
        "vol_ratio": round(vol_ratio,2), "vol_avg": round(vol_avg/10000,1),
        "vol_today": round(vol_today/10000,1),
        "mom5": round(mom5,2), "mom20": round(mom20,2), "mom60": round(mom60,2),
        "dist_from_high": round(dist_from_high,1),
    }

def main():
    print("에코프로 (086520.KQ) 어제/오늘 비교 분석\n")

    df = yf.download("086520.KQ", period="1y", interval="1d",
                     progress=False, auto_adjust=True)
    close  = df["Close"].squeeze()
    high   = df["High"].squeeze()
    low    = df["Low"].squeeze()
    volume = df["Volume"].squeeze()

    today_date = df.index[-1].strftime("%Y-%m-%d")
    yest_date  = df.index[-2].strftime("%Y-%m-%d")

    today = calc_for_day(close, high, low, volume, offset=0)
    yest  = calc_for_day(close, high, low, volume, offset=1)

    # ── 출력 ─────────────────────────────────────────────────────
    def diff(t, y, fmt=".1f"):
        d = t - y
        sign = "+" if d >= 0 else ""
        return f"{sign}{d:{fmt}}"

    print("=" * 65)
    print(f"  에코프로 (086520.KQ)  |  어제 vs 오늘 비교")
    print("=" * 65)
    print(f"{'지표':<20} {'어제':>15}  {'오늘':>15}  {'변화':>10}")
    print("-" * 65)
    print(f"{'날짜':<20} {yest_date:>15}  {today_date:>15}")
    print(f"{'현재가':<20} {yest['price']:>14,.0f}  {today['price']:>14,.0f}  {diff(today['price'],yest['price'],'.0f'):>10}")
    print(f"{'등락률':<20} {yest['chg']:>+14.2f}%  {today['chg']:>+14.2f}%")
    print(f"{'MA5':<20} {yest['ma5']:>14,.0f}  {today['ma5']:>14,.0f}  {diff(today['ma5'],yest['ma5'],'.0f'):>10}")
    print(f"{'MA20':<20} {yest['ma20']:>14,.0f}  {today['ma20']:>14,.0f}  {diff(today['ma20'],yest['ma20'],'.0f'):>10}")
    print(f"{'MA60':<20} {yest['ma60']:>14,.0f}  {today['ma60']:>14,.0f}  {diff(today['ma60'],yest['ma60'],'.0f'):>10}")
    print(f"{'MA120':<20} {yest['ma120']:>14,.0f}  {today['ma120']:>14,.0f}  {diff(today['ma120'],yest['ma120'],'.0f'):>10}")
    print("-" * 65)
    print(f"{'RSI(14)':<20} {yest['rsi']:>15.1f}  {today['rsi']:>15.1f}  {diff(today['rsi'],yest['rsi']):>10}")
    print(f"{'MACD':<20} {yest['macd']:>+15.2f}  {today['macd']:>+15.2f}  {diff(today['macd'],yest['macd'],'.2f'):>10}")
    print(f"{'MACD Signal':<20} {yest['sig']:>+15.2f}  {today['sig']:>+15.2f}  {diff(today['sig'],yest['sig'],'.2f'):>10}")
    print(f"{'MACD Hist':<20} {yest['hist']:>+15.2f}  {today['hist']:>+15.2f}  ★{diff(today['hist'],yest['hist'],'.2f'):>9}")
    print(f"{'BB 위치(%)':<20} {yest['bb_pct']:>15.1f}  {today['bb_pct']:>15.1f}  {diff(today['bb_pct'],yest['bb_pct']):>10}")
    print(f"{'BB 상단':<20} {yest['bb_up']:>14,.0f}  {today['bb_up']:>14,.0f}")
    print(f"{'BB 하단':<20} {yest['bb_dn']:>14,.0f}  {today['bb_dn']:>14,.0f}")
    print(f"{'Stoch K':<20} {yest['stoch_k']:>15.1f}  {today['stoch_k']:>15.1f}  {diff(today['stoch_k'],yest['stoch_k']):>10}")
    print(f"{'Stoch D':<20} {yest['stoch_d']:>15.1f}  {today['stoch_d']:>15.1f}  {diff(today['stoch_d'],yest['stoch_d']):>10}")
    print("-" * 65)
    print(f"{'5일 모멘텀':<20} {yest['mom5']:>+15.2f}%  {today['mom5']:>+15.2f}%")
    print(f"{'20일 모멘텀':<20} {yest['mom20']:>+15.2f}%  {today['mom20']:>+15.2f}%")
    print(f"{'60일 모멘텀':<20} {yest['mom60']:>+15.2f}%  {today['mom60']:>+15.2f}%")
    print("-" * 65)
    print(f"{'거래량(오늘,만주)':<20} {yest['vol_today']:>15.1f}  {today['vol_today']:>15.1f}  ★{diff(today['vol_today'],yest['vol_today'],'.1f'):>9}")
    print(f"{'거래량(20일평균)':<20} {yest['vol_avg']:>15.1f}  {today['vol_avg']:>15.1f}")
    print(f"{'거래량 비율':<20} {yest['vol_ratio']:>15.2f}x  {today['vol_ratio']:>15.2f}x  ★{diff(today['vol_ratio'],yest['vol_ratio'],'.2f'):>9}")
    print(f"{'52주고 대비':<20} {yest['dist_from_high']:>+14.1f}%  {today['dist_from_high']:>+14.1f}%")
    print("=" * 65)

    # ── Claude 비교 해설 ──────────────────────────────────────────
    client = anthropic.Anthropic(api_key=_get("ANTHROPIC_API_KEY"))

    prompt = f"""투자자가 에코프로(086520.KQ) 관련해서 어제와 오늘의 분석이 달라진 이유를 묻고 있습니다.

【어제 분석 내용 (투자자가 받은 메시지)】
- 현재가: 184,200원
- RSI: 58.6 → "과매수(70) 미만으로 추가 상승 공간 존재"
- MA5(173,980) > MA20(164,440) > MA60(120,555) 정배열
- MA60 대비 +52.8% 프리미엄
- BB 96.0% → "강한 추세 지속을 의미" (긍정적 해석)
- 결론: 강한 매수 / 추가 상승 공간 존재

【오늘 분석 내용 (방금 실행)】
- 현재가: {today['price']:,.0f}원
- RSI: {today['rsi']} → "중립권이나 스토캐스틱 과매수 임계권"
- MA5({today['ma5']:,.0f}) > MA20({today['ma20']:,.0f}) > MA60({today['ma60']:,.0f}) 정배열 유지
- MA60 대비 +{(today['price']-today['ma60'])/today['ma60']*100:.1f}%
- BB 위치: {today['bb_pct']}% → "극단적 상단 밀착, 단기 조정 압력" (부정적 해석)
- MACD Hist: {today['hist']:+.2f} (축소 중)
- Stochastic K={today['stoch_k']} / D={today['stoch_d']} (과매수, 데드크로스 임박)
- 거래량: 20일 평균의 {today['vol_ratio']:.2f}배 (부진)
- 결론: 비중 축소 (부분 차익 실현)

【실제 계산된 지표 변화】
- 가격: {yest['price']:,.0f}원 → {today['price']:,.0f}원 ({diff(today['price'],yest['price'],'.0f')}원)
- RSI: {yest['rsi']} → {today['rsi']} ({diff(today['rsi'],yest['rsi'])}p)
- MACD Hist: {yest['hist']:+.2f} → {today['hist']:+.2f} ({diff(today['hist'],yest['hist'],'.2f')})
- BB%: {yest['bb_pct']}% → {today['bb_pct']}% ({diff(today['bb_pct'],yest['bb_pct'])}p)
- Stoch K: {yest['stoch_k']} → {today['stoch_k']} ({diff(today['stoch_k'],yest['stoch_k'])}p)
- 거래량 비율: {yest['vol_ratio']:.2f}x → {today['vol_ratio']:.2f}x ({diff(today['vol_ratio'],yest['vol_ratio'],'.2f')})

다음 세 가지를 솔직하고 명확하게 답변해 주세요:

## 1. 실제로 달라진 지표가 있는가? (있다면 무엇이 얼마나 달라졌는가)
수치 기반으로 구체적으로 설명. "어제 대비 유의미한 변화"와 "거의 동일한 수치"를 구분.

## 2. BB 96% vs 95.9%를 어제는 "강한 추세", 오늘은 "조정 압력"으로 해석한 이유
같은 BB 수치에 대한 해석이 달라진 것이 정당한지, 아니면 분석 프레임의 불일치인지 솔직하게 평가.

## 3. 현재 가장 정확한 에코프로 상태 판단
어제 분석과 오늘 분석 중 어느 쪽이 더 실상에 가까운지, 혹은 둘 다 부분적으로 맞는지.
그리고 지금 이 순간 보유자에게 가장 적절한 행동 방침 1가지.

솔직하고 균형 잡힌 시각으로, AI 분석의 한계도 인정하면서 답변해 주세요."""

    resp = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=4000,
        messages=[{"role": "user", "content": prompt}],
    )
    print("\n" + "=" * 65)
    print("  🤖 Claude AI — 어제/오늘 분석 변화 해설")
    print("=" * 65)
    print(resp.content[0].text)
    print("=" * 65)

if __name__ == "__main__":
    main()
