"""
주가 데이터 수집기 (분석 전 단계)
- 실제 데이터를 CSV/콘솔로 출력해 눈으로 확인 가능
- 종목 수가 많으면 시가총액 기준으로 자동 필터링
"""

import os
import sys
import datetime
import time

if sys.stdout.encoding != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

import yfinance as yf
import pandas as pd
from universe import WATCHLIST   # 단일 관리 → universe.py 참조

pd.set_option('display.max_columns', None)
pd.set_option('display.width', 200)
pd.set_option('display.float_format', '{:,.1f}'.format)

# WATCHLIST는 universe.py에서 자동 생성됩니다.
# 종목 추가/삭제는 universe.py의 UNIVERSE 딕셔너리를 수정하세요.
# 현재 포함: 국내 코스피 대형주 + 코스닥 방산·보안 (총 65개 내외)


def fetch_stock_data(ticker_code: str, name: str, period: str = "60d") -> dict | None:
    """
    단일 종목의 OHLCV + 기술적 지표를 수집한다.
    반환값에 계산 근거가 되는 원본 데이터도 포함.
    """
    ticker = ticker_code + ".KS"
    try:
        stock = yf.Ticker(ticker)
        hist = stock.history(period=period)
        if hist.empty or len(hist) < 5:
            return None

        close = hist["Close"]
        volume = hist["Volume"]
        high = hist["High"]
        low = hist["Low"]

        # 기술적 지표 계산
        ma5   = close.rolling(5).mean()
        ma20  = close.rolling(20).mean()
        ma60  = close.rolling(60).mean()

        # RSI (14일)
        delta = close.diff()
        gain = delta.clip(lower=0).rolling(14).mean()
        loss = (-delta.clip(upper=0)).rolling(14).mean()
        rsi = (100 - 100 / (1 + gain / loss))

        # MACD (12, 26, 9)
        ema12 = close.ewm(span=12).mean()
        ema26 = close.ewm(span=26).mean()
        macd_line = ema12 - ema26
        signal_line = macd_line.ewm(span=9).mean()

        # 볼린저 밴드 (20일)
        bb_mid = close.rolling(20).mean()
        bb_std = close.rolling(20).std()
        bb_upper = bb_mid + 2 * bb_std
        bb_lower = bb_mid - 2 * bb_std

        # 52주 고/저가
        hist_1y = stock.history(period="252d")
        high_52w = hist_1y["High"].max() if not hist_1y.empty else high.max()
        low_52w  = hist_1y["Low"].min()  if not hist_1y.empty else low.min()

        # 시가총액 (야후 파이낸스)
        info = stock.info
        market_cap = info.get("marketCap", 0)
        per = info.get("trailingPE", None)
        pbr = info.get("priceToBook", None)

        # 최근 5일 종가 (근거 확인용)
        recent_closes = close.tail(5).round(0).tolist()
        recent_dates  = [d.strftime("%m/%d") for d in close.tail(5).index]

        current = close.iloc[-1]
        prev    = close.iloc[-2]
        change_pct = (current - prev) / prev * 100

        avg_vol_20 = volume.rolling(20).mean().iloc[-1]
        vol_ratio  = volume.iloc[-1] / avg_vol_20 if avg_vol_20 > 0 else 0

        # 거래량 상위 N일 (이상 급등 감지)
        vol_rank = int(volume.rank(ascending=False).iloc[-1])

        return {
            "코드": ticker_code,
            "종목명": name,
            # ── 현재가 ──
            "현재가": round(current, 0),
            "전일대비(%)": round(change_pct, 2),
            # ── 이동평균 ──
            "MA5":  round(ma5.iloc[-1], 0),
            "MA20": round(ma20.iloc[-1], 0) if not pd.isna(ma20.iloc[-1]) else None,
            "MA60": round(ma60.iloc[-1], 0) if not pd.isna(ma60.iloc[-1]) else None,
            "MA5>MA20(골든크로스)": bool(ma5.iloc[-1] > ma20.iloc[-1]),
            # ── 모멘텀 ──
            "RSI14": round(rsi.iloc[-1], 1) if not pd.isna(rsi.iloc[-1]) else None,
            "MACD선": round(macd_line.iloc[-1], 0),
            "시그널선": round(signal_line.iloc[-1], 0),
            "MACD>시그널": bool(macd_line.iloc[-1] > signal_line.iloc[-1]),
            # ── 볼린저밴드 ──
            "BB상단": round(bb_upper.iloc[-1], 0),
            "BB중단": round(bb_mid.iloc[-1], 0),
            "BB하단": round(bb_lower.iloc[-1], 0),
            "BB위치(%)": round((current - bb_lower.iloc[-1]) /
                               (bb_upper.iloc[-1] - bb_lower.iloc[-1]) * 100, 1)
                         if (bb_upper.iloc[-1] - bb_lower.iloc[-1]) > 0 else 50,
            # ── 거래량 ──
            "거래량": int(volume.iloc[-1]),
            "20일평균거래량": int(avg_vol_20),
            "거래량비율(vs20일)": round(vol_ratio, 2),
            "최근60일_거래량순위": vol_rank,
            # ── 52주 ──
            "52주최고": round(high_52w, 0),
            "52주최저": round(low_52w, 0),
            "52주고점대비(%)": round((current - high_52w) / high_52w * 100, 1),
            # ── 밸류에이션 ──
            "시가총액(억)": round(market_cap / 1e8, 0) if market_cap else None,
            "PER": round(per, 1) if per else None,
            "PBR": round(pbr, 2) if pbr else None,
            # ── 근거 데이터 (최근 5일 종가) ──
            "최근5일종가": dict(zip(recent_dates, [int(c) for c in recent_closes])),
        }
    except Exception as e:
        print(f"  [오류] {name}({ticker_code}): {e}")
        return None


def collect_all(
    watchlist: dict = None,
    top_n: int = None,
    sort_by: str = "시가총액(억)"
) -> pd.DataFrame:
    """
    watchlist 종목을 모두 수집한 뒤,
    top_n이 지정되면 sort_by 기준 상위 N개만 반환한다.
    """
    watchlist = watchlist or WATCHLIST
    results = []

    print(f"\n총 {len(watchlist)}개 종목 수집 시작...\n")
    for code, name in watchlist.items():
        print(f"  수집 중: {name}({code})...", end=" ", flush=True)
        data = fetch_stock_data(code, name)
        if data:
            results.append(data)
            print(f"완료 (현재가: {data['현재가']:,.0f}원, RSI: {data['RSI14']})")
        else:
            print("실패")
        time.sleep(0.3)   # API 요청 간격

    if not results:
        print("수집된 데이터가 없습니다.")
        return pd.DataFrame()

    df = pd.DataFrame(results)

    # top_n 필터링
    if top_n and sort_by in df.columns:
        df = df.sort_values(sort_by, ascending=False).head(top_n).reset_index(drop=True)
        print(f"\n→ {sort_by} 기준 상위 {top_n}개 종목으로 필터링됨")

    return df


def print_summary_table(df: pd.DataFrame):
    """핵심 지표만 골라 콘솔에 보기 좋게 출력한다."""
    if df.empty:
        return

    cols = [
        "종목명", "현재가", "전일대비(%)",
        "RSI14", "MA5>MA20(골든크로스)", "MACD>시그널",
        "BB위치(%)", "거래량비율(vs20일)",
        "52주고점대비(%)", "PER", "시가총액(억)"
    ]
    display_df = df[[c for c in cols if c in df.columns]].copy()

    # RSI 신호 추가
    def rsi_signal(r):
        if r is None: return "-"
        if r >= 70: return f"{r} [과매수]"
        if r <= 30: return f"{r} [과매도]"
        return str(r)

    display_df["RSI14"] = display_df["RSI14"].apply(rsi_signal)

    print("\n" + "=" * 100)
    print("[ 주가 데이터 요약표 ]")
    print("=" * 100)
    print(display_df.to_string(index=True))
    print("=" * 100)


def print_recent_prices(df: pd.DataFrame):
    """최근 5일 종가 (분석 근거 확인용)"""
    if df.empty:
        return
    print("\n[ 최근 5일 종가 - 분석 근거 확인용 ]")
    print("-" * 80)
    for _, row in df.iterrows():
        prices = row.get("최근5일종가", {})
        price_str = "  ".join([f"{d}:{p:,}" for d, p in prices.items()])
        print(f"  {row['종목명']:12s} | {price_str}")
    print("-" * 80)


def save_to_csv(df: pd.DataFrame, filename: str = None):
    """전체 데이터를 CSV로 저장 (스프레드시트에서 확인 가능)"""
    if df.empty:
        return
    # 최근5일종가 컬럼은 dict라 CSV 저장 전 문자열 변환
    df_save = df.copy()
    if "최근5일종가" in df_save.columns:
        df_save["최근5일종가"] = df_save["최근5일종가"].apply(str)

    if not filename:
        filename = f"stock_data_{datetime.datetime.now().strftime('%Y%m%d_%H%M')}.csv"

    df_save.to_csv(filename, index=False, encoding="utf-8-sig")
    print(f"\n💾 전체 데이터 저장 완료: {filename}")
    print("   (Excel에서 열어 상세 데이터를 확인할 수 있습니다)")


# ──────────────────────────────────────────────
# DART 통합: 재무/공시 데이터를 주가 DataFrame에 병합
# ──────────────────────────────────────────────

def merge_dart_into_df(df: pd.DataFrame, dart_data: dict) -> pd.DataFrame:
    """
    DART 재무 데이터를 주가 DataFrame에 컬럼으로 추가한다.
    """
    if df.empty or not dart_data:
        return df

    dart_rows = []
    for code, data in dart_data.items():
        fin = data.get("재무제표", {})
        imp_disclosures = data.get("중요공시", [])
        row = {"코드": code}
        # 재무 지표
        row["매출액(억)_DART"]      = fin.get("매출액_억")
        row["영업이익(억)_DART"]    = fin.get("영업이익_억")
        row["당기순이익(억)_DART"]  = fin.get("당기순이익_억")
        row["부채비율(%)_DART"]     = fin.get("부채비율(%)")
        row["영업이익률(%)_DART"]   = fin.get("영업이익률(%)")
        row["재무기준연도"]          = fin.get("기준연도")
        # 중요 공시 요약 (★ 표시 공시 제목)
        row["중요공시(최근90일)"] = " | ".join(
            [d["제목"] for d in imp_disclosures[:3]]
        ) if imp_disclosures else "없음"
        dart_rows.append(row)

    if not dart_rows:
        return df

    dart_df = pd.DataFrame(dart_rows)
    merged = df.merge(dart_df, on="코드", how="left")
    return merged


def print_integrated_table(df: pd.DataFrame):
    """주가 + DART 재무 통합 요약표 출력"""
    if df.empty:
        return

    dart_cols = [c for c in [
        "매출액(억)_DART", "영업이익(억)_DART",
        "영업이익률(%)_DART", "부채비율(%)_DART",
        "중요공시(최근90일)"
    ] if c in df.columns]

    if not dart_cols:
        print("  DART 데이터 없음 (주가 데이터만 표시)")
        return

    base_cols = ["종목명", "현재가", "전일대비(%)", "RSI14",
                 "52주고점대비(%)", "PER"]
    cols = [c for c in base_cols + dart_cols if c in df.columns]

    print("\n" + "=" * 120)
    print("[ 주가 + DART 재무 통합 요약표 ]")
    print("=" * 120)
    print(df[cols].to_string(index=True))
    print("=" * 120)


# ──────────────────────────────────────────────
# 실행
# ──────────────────────────────────────────────
if __name__ == "__main__":
    import argparse
    from dart_collector import collect_dart_data, print_dart_summary, save_dart_to_csv

    parser = argparse.ArgumentParser(description="주가 + DART 통합 데이터 수집기")
    parser.add_argument("--top",    type=int,  default=None,
                        help="시가총액 기준 상위 N개만 (예: --top 10)")
    parser.add_argument("--stocks", type=str,  default=None,
                        help="특정 종목만 (예: --stocks 005930,000660)")
    parser.add_argument("--no-dart", action="store_true",
                        help="DART 수집 건너뜀 (주가 데이터만)")
    args = parser.parse_args()

    print("=" * 60)
    print("  주가 + DART 통합 데이터 수집기")
    print(f"  실행 시각: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print("=" * 60)

    # 종목 목록 결정
    if args.stocks:
        codes = [s.strip() for s in args.stocks.split(",")]
        target = {c: WATCHLIST.get(c, c) for c in codes}
    else:
        target = WATCHLIST

    # ── 1단계: 주가 데이터 수집 ──
    df = collect_all(watchlist=target, top_n=args.top)

    if df.empty:
        print("수집된 데이터가 없습니다.")
    else:
        print_summary_table(df)
        print_recent_prices(df)

        # ── 2단계: DART 재무/공시 수집 ──
        if not args.no_dart:
            from dotenv import dotenv_values
            _cfg = dotenv_values(
                os.path.join(os.path.dirname(os.path.abspath(__file__)), '.env')
            )
            dart_key = os.environ.get("DART_API_KEY") or _cfg.get("DART_API_KEY", "")

            if dart_key and dart_key != "your_dart_api_key_here":
                dart_data = collect_dart_data(list(target.keys()), dart_key)
                if dart_data:
                    print_dart_summary(dart_data, target)
                    df = merge_dart_into_df(df, dart_data)
                    print_integrated_table(df)
                    save_dart_to_csv(dart_data, target)
            else:
                print("\n[DART 건너뜀] .env에 DART_API_KEY를 입력하면 재무/공시 데이터도 수집됩니다.")

        # ── 3단계: CSV 저장 (주가 + DART 통합) ──
        save_to_csv(df)
        print(f"\n총 {len(df)}개 종목 수집 완료.")
        print("다음 단계: py stock_advisor.py  → Claude 종합 분석")
