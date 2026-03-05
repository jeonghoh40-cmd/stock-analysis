"""
종목 어제/오늘 비교 분석 + 상세 투자 대처 방안
사용: python compare_stock.py [티커] [종목명]
예시: python compare_stock.py 028260.KS 삼성물산
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

TICKER = sys.argv[1] if len(sys.argv) > 1 else "028260.KS"
NAME   = sys.argv[2] if len(sys.argv) > 2 else "삼성물산"

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

def _atr(high, low, close, n=14):
    tr = pd.concat([
        high - low,
        (high - close.shift()).abs(),
        (low  - close.shift()).abs(),
    ], axis=1).max(axis=1)
    return float(tr.rolling(n).mean().iloc[-1])

def calc(close, high, low, volume, offset=0):
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
    atr               = _atr(high, low, close)

    vol_avg   = float(volume.rolling(20).mean().iloc[-1])
    vol_today = float(volume.iloc[-1])
    vol_ratio = vol_today / (vol_avg + 1e-9)

    mom5  = float((close.iloc[-1]/close.iloc[-6]-1)*100)  if len(close) > 5  else 0
    mom20 = float((close.iloc[-1]/close.iloc[-21]-1)*100) if len(close) > 20 else 0
    mom60 = float((close.iloc[-1]/close.iloc[-61]-1)*100) if len(close) > 60 else 0

    high52 = float(high.rolling(252).max().iloc[-1])
    low52  = float(low.rolling(252).min().iloc[-1])

    # 최근 20일 고/저 (지지·저항)
    r_high20 = float(high.tail(20).max())
    r_low20  = float(low.tail(20).min())
    r_high60 = float(high.tail(60).max())
    r_low60  = float(low.tail(60).min())

    # 최근 10일 일봉 히스토리
    history = []
    for i in range(min(10, len(close))):
        idx = -(i+1)
        d_date  = close.index[idx].strftime("%m/%d(%a)")
        d_close = float(close.iloc[idx])
        d_high  = float(high.iloc[idx])
        d_low   = float(low.iloc[idx])
        d_vol   = int(volume.iloc[idx])
        d_chg   = (float(close.iloc[idx])-float(close.iloc[idx-1]))/float(close.iloc[idx-1])*100 if idx > -len(close) else 0
        history.append(f"  {d_date}: 종가 {d_close:>8,.0f}  고 {d_high:>8,.0f}  저 {d_low:>8,.0f}  ({d_chg:+.2f}%)  거래량 {d_vol/10000:.1f}만")
    history.reverse()

    return {
        "price": price, "prev": prev, "chg": chg,
        "ma5": round(ma5,0), "ma20": round(ma20,0),
        "ma60": round(ma60,0), "ma120": round(ma120,0),
        "rsi": round(rsi,1),
        "macd": round(macd_v,2), "sig": round(sig,2), "hist": round(hist,2),
        "bb_up": bb_up, "bb_dn": bb_dn, "bb_pct": bb_pct,
        "stoch_k": stoch_k, "stoch_d": stoch_d,
        "atr": round(atr,0),
        "vol_ratio": round(vol_ratio,2),
        "vol_avg": round(vol_avg/10000,1),
        "vol_today": round(vol_today/10000,1),
        "mom5": round(mom5,2), "mom20": round(mom20,2), "mom60": round(mom60,2),
        "high52": round(high52,0), "low52": round(low52,0),
        "dist_high52": round((price-high52)/high52*100,1),
        "dist_low52":  round((price-low52)/low52*100,1),
        "r_high20": round(r_high20,0), "r_low20": round(r_low20,0),
        "r_high60": round(r_high60,0), "r_low60": round(r_low60,0),
        "history": "\n".join(history),
    }

def main():
    print(f"\n📊 {NAME} ({TICKER}) 어제/오늘 비교 분석")
    print(f"   실행 시각: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")

    df = yf.download(TICKER, period="1y", interval="1d",
                     progress=False, auto_adjust=True)
    if df is None or df.empty or len(df) < 65:
        print("❌ 데이터 부족"); return

    close  = df["Close"].squeeze()
    high   = df["High"].squeeze()
    low    = df["Low"].squeeze()
    volume = df["Volume"].squeeze()

    td = calc(close, high, low, volume, offset=0)
    yd = calc(close, high, low, volume, offset=1)

    today_date = df.index[-1].strftime("%Y-%m-%d")
    yest_date  = df.index[-2].strftime("%Y-%m-%d")

    def chg_str(t, y, fmt=".1f"):
        d = t - y
        return f"{'+'if d>=0 else ''}{d:{fmt}}"

    SEP = "=" * 68
    sep = "-" * 68

    print(SEP)
    print(f"  {NAME} ({TICKER})  |  어제 vs 오늘 비교")
    print(SEP)
    print(f"{'지표':<22} {'어제 '+yest_date:>18}  {'오늘 '+today_date:>18}  {'변화':>8}")
    print(sep)
    print(f"{'현재가':<22} {yd['price']:>17,.0f}  {td['price']:>17,.0f}  {chg_str(td['price'],yd['price'],'.0f'):>8}")
    print(f"{'등락률':<22} {yd['chg']:>+17.2f}%  {td['chg']:>+17.2f}%")
    print(sep)
    print(f"{'MA5':<22} {yd['ma5']:>17,.0f}  {td['ma5']:>17,.0f}  {chg_str(td['ma5'],yd['ma5'],'.0f'):>8}")
    print(f"{'MA20':<22} {yd['ma20']:>17,.0f}  {td['ma20']:>17,.0f}  {chg_str(td['ma20'],yd['ma20'],'.0f'):>8}")
    print(f"{'MA60':<22} {yd['ma60']:>17,.0f}  {td['ma60']:>17,.0f}  {chg_str(td['ma60'],yd['ma60'],'.0f'):>8}")
    print(f"{'MA120':<22} {yd['ma120']:>17,.0f}  {td['ma120']:>17,.0f}  {chg_str(td['ma120'],yd['ma120'],'.0f'):>8}")
    ma_align = lambda d: "정배열↑" if d['ma5']>d['ma20']>d['ma60'] else ("역배열↓" if d['ma5']<d['ma20']<d['ma60'] else "혼조")
    print(f"{'MA배열':<22} {ma_align(yd):>18}  {ma_align(td):>18}")
    print(sep)
    print(f"{'RSI(14)':<22} {yd['rsi']:>18.1f}  {td['rsi']:>18.1f}  {chg_str(td['rsi'],yd['rsi']):>8}")
    print(f"{'MACD':<22} {yd['macd']:>+18.2f}  {td['macd']:>+18.2f}  {chg_str(td['macd'],yd['macd'],'.2f'):>8}")
    print(f"{'MACD Signal':<22} {yd['sig']:>+18.2f}  {td['sig']:>+18.2f}  {chg_str(td['sig'],yd['sig'],'.2f'):>8}")
    print(f"{'MACD Hist  ★':<22} {yd['hist']:>+18.2f}  {td['hist']:>+18.2f}  {chg_str(td['hist'],yd['hist'],'.2f'):>8}")
    print(f"{'BB 위치(%)  ★':<22} {yd['bb_pct']:>18.1f}  {td['bb_pct']:>18.1f}  {chg_str(td['bb_pct'],yd['bb_pct']):>8}")
    print(f"{'BB 상단':<22} {yd['bb_up']:>17,.0f}  {td['bb_up']:>17,.0f}")
    print(f"{'BB 하단':<22} {yd['bb_dn']:>17,.0f}  {td['bb_dn']:>17,.0f}")
    print(f"{'Stoch K  ★':<22} {yd['stoch_k']:>18.1f}  {td['stoch_k']:>18.1f}  {chg_str(td['stoch_k'],yd['stoch_k']):>8}")
    print(f"{'Stoch D':<22} {yd['stoch_d']:>18.1f}  {td['stoch_d']:>18.1f}  {chg_str(td['stoch_d'],yd['stoch_d']):>8}")
    print(f"{'ATR(14)':<22} {yd['atr']:>17,.0f}  {td['atr']:>17,.0f}")
    print(sep)
    print(f"{'5일 모멘텀':<22} {yd['mom5']:>+17.2f}%  {td['mom5']:>+17.2f}%")
    print(f"{'20일 모멘텀':<22} {yd['mom20']:>+17.2f}%  {td['mom20']:>+17.2f}%")
    print(f"{'60일 모멘텀':<22} {yd['mom60']:>+17.2f}%  {td['mom60']:>+17.2f}%")
    print(sep)
    print(f"{'거래량(오늘,만주) ★':<22} {yd['vol_today']:>17.1f}  {td['vol_today']:>17.1f}  {chg_str(td['vol_today'],yd['vol_today'],'.1f'):>8}")
    print(f"{'거래량(20일평균)':<22} {yd['vol_avg']:>17.1f}  {td['vol_avg']:>17.1f}")
    print(f"{'거래량 비율  ★':<22} {yd['vol_ratio']:>17.2f}x  {td['vol_ratio']:>17.2f}x  {chg_str(td['vol_ratio'],yd['vol_ratio'],'.2f'):>8}")
    print(sep)
    print(f"{'52주 고점':<22} {yd['high52']:>17,.0f}  {td['high52']:>17,.0f}")
    print(f"{'52주 저점':<22} {yd['low52']:>17,.0f}  {td['low52']:>17,.0f}")
    print(f"{'52주 고 대비':<22} {yd['dist_high52']:>+17.1f}%  {td['dist_high52']:>+17.1f}%")
    print(f"{'52주 저 대비':<22} {yd['dist_low52']:>+17.1f}%  {td['dist_low52']:>+17.1f}%")
    print(f"{'20일 고점(저항)':<22} {yd['r_high20']:>17,.0f}  {td['r_high20']:>17,.0f}")
    print(f"{'20일 저점(지지)':<22} {yd['r_low20']:>17,.0f}  {td['r_low20']:>17,.0f}")
    print(f"{'60일 고점(저항)':<22} {yd['r_high60']:>17,.0f}  {td['r_high60']:>17,.0f}")
    print(SEP)

    print(f"\n【 최근 10일 일봉 】")
    print(td['history'])

    # ── Claude 분석 ────────────────────────────────────────────────
    client = anthropic.Anthropic(api_key=_get("ANTHROPIC_API_KEY"))
    now_str = datetime.datetime.now().strftime("%Y년 %m월 %d일 %H:%M")

    prompt = f"""당신은 한국 주식 전문 애널리스트입니다.
분석 일자: {now_str}
종목: {NAME} ({TICKER})

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
【 어제({yest_date}) 기술적 지표 】
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
현재가: {yd['price']:,.0f}원  ({yd['chg']:+.2f}%)
MA5: {yd['ma5']:,.0f}  MA20: {yd['ma20']:,.0f}  MA60: {yd['ma60']:,.0f}  MA120: {yd['ma120']:,.0f}  → {ma_align(yd)}
RSI: {yd['rsi']}  |  MACD Hist: {yd['hist']:+.2f}  |  BB: {yd['bb_pct']}%
Stoch K/D: {yd['stoch_k']} / {yd['stoch_d']}
거래량: {yd['vol_today']:.1f}만주 (평균 대비 {yd['vol_ratio']:.2f}x)
모멘텀: 5일 {yd['mom5']:+.2f}%  20일 {yd['mom20']:+.2f}%  60일 {yd['mom60']:+.2f}%

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
【 오늘({today_date}) 기술적 지표 】
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
현재가: {td['price']:,.0f}원  ({td['chg']:+.2f}%)
MA5: {td['ma5']:,.0f}  MA20: {td['ma20']:,.0f}  MA60: {td['ma60']:,.0f}  MA120: {td['ma120']:,.0f}  → {ma_align(td)}
RSI: {td['rsi']}  |  MACD Hist: {td['hist']:+.2f}  |  BB: {td['bb_pct']}%
BB 상단: {td['bb_up']:,.0f}원  BB 하단: {td['bb_dn']:,.0f}원
Stoch K/D: {td['stoch_k']} / {td['stoch_d']}
거래량: {td['vol_today']:.1f}만주 (평균 대비 {td['vol_ratio']:.2f}x)
모멘텀: 5일 {td['mom5']:+.2f}%  20일 {td['mom20']:+.2f}%  60일 {td['mom60']:+.2f}%
52주 고 대비: {td['dist_high52']:+.1f}%  /  52주 저 대비: {td['dist_low52']:+.1f}%
20일 고점(저항): {td['r_high20']:,.0f}원  |  20일 저점(지지): {td['r_low20']:,.0f}원
60일 고점(저항): {td['r_high60']:,.0f}원
ATR(14): {td['atr']:,.0f}원 (하루 평균 변동폭)

【 최근 10일 일봉 】
{td['history']}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
【 오늘 시장 맥락 】
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
KOSPI: 2,681 (+0.67%)
USD/KRW: 1,435원
미 10년채: 4.27%
삼성물산은 삼성전자 지분 4.1% 보유 (삼성전자 오늘 +0.0% 보합)
건설/지주 섹터: 부동산 경기 회복 불확실성 지속

다음 순서대로 분석해 주세요:

═══════════════════════════════════════════════════
1. 어제 → 오늘, 실제로 달라진 것 vs 거의 동일한 것 구분
═══════════════════════════════════════════════════
수치 기반으로 표로 정리. 유의미한 변화(★)와 노이즈 수준 변화를 명확히 구분.

═══════════════════════════════════════════════════
2. 오늘 하락(-2.64%)의 의미 해석
═══════════════════════════════════════════════════
- 단순 숨고르기인가, 추세 전환 신호인가?
- 거래량 맥락에서의 해석
- 볼린저밴드 상단 저항과의 관계
- 스토캐스틱 K/D 배열 변화가 주는 신호

═══════════════════════════════════════════════════
3. 지지선 / 저항선 지도 (구체적 가격 제시)
═══════════════════════════════════════════════════
저항선 2~3개, 지지선 3~4개를 가격과 근거 함께 제시.

═══════════════════════════════════════════════════
4. 보유자 시나리오별 대처 방안 (숫자 必)
═══════════════════════════════════════════════════

시나리오 A — 반등 성공 (확률 추정)
 · 반등 신호 조건
 · 목표가 1·2·3차

시나리오 B — 추가 하락 (확률 추정)
 · 1차 지지선 이탈 시 행동
 · 2차 지지선 이탈 시 행동
 · 손절 기준가와 이유

시나리오 C — 중장기 보유 (확률 추정)
 · 펀더멘털 회복 조건 (삼성물산 고유 요소)
 · 중장기 목표가 및 보유 기간

═══════════════════════════════════════════════════
5. 삼성물산 고유 투자 포인트 (기술적 분석 너머)
═══════════════════════════════════════════════════
- 삼성 그룹주 지주사로서의 특성
- 삼성전자 주가와의 연동 관계
- 건설/리조트/상사 사업부 현황
- 지배구조 이슈 (이재용 복귀 이후 변화)

═══════════════════════════════════════════════════
6. 결론 — 지금 이 순간 보유자 핵심 행동 1가지
═══════════════════════════════════════════════════
모호하지 않게, 구체적인 가격과 조건을 포함해서.

⚠️ 투자 참고용. 최종 판단은 투자자 본인."""

    print(f"\n\n{'='*68}")
    print(f"  🤖 Claude AI 상세 분석")
    print(f"{'='*68}\n")
    print("  분석 중...")

    resp = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=6000,
        messages=[{"role": "user", "content": prompt}],
    )
    result = resp.content[0].text
    print(result)

    # 저장
    out = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                       f"compare_{NAME}_{today_date}.txt")
    full = f"{NAME} ({TICKER}) 어제/오늘 비교 분석\n{now_str}\n\n" + result
    with open(out, "w", encoding="utf-8") as f:
        f.write(full)
    print(f"\n\n📄 리포트 저장: {out}")

if __name__ == "__main__":
    main()
