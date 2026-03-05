"""
국내 수급 분석기 — 외국인·기관 순매수 점수화
────────────────────────────────────────────────────────────────
데이터 소스 (우선순위):
  1순위: pykrx   — 가장 정확 (Python 3.14에서는 numpy 빌드 필요)
  2순위: 네이버 금융 API  — pykrx 미설치 시 자동 대체
  3순위: 점수 0 반환     — API 실패 시 안전한 fallback

점수 구조 (-30 ~ +30):
  외국인 순매수 비율 (시가총액 대비):
    >  0.3%  : +15  /  > 0.1% : +8  /  < -0.1% : -8  /  < -0.3% : -15
  기관 순매수 비율:
    >  0.3%  : +15  /  > 0.1% : +8  /  < -0.1% : -8  /  < -0.3% : -15

캐시: investor_flow_cache.json (12시간 유효)
"""

import os
import json
import datetime
import time

import requests

BASE_DIR   = os.path.dirname(os.path.abspath(__file__))
CACHE_FILE = os.path.join(BASE_DIR, "investor_flow_cache.json")
CACHE_TTL  = 12    # 시간 (hours)
FLOW_DAYS  = 5     # 최근 N 영업일 누적


# ═══════════════════════════════════════════════════════════════
# 캐시 I/O
# ═══════════════════════════════════════════════════════════════
def _load_cache() -> dict:
    try:
        if os.path.exists(CACHE_FILE):
            with open(CACHE_FILE, encoding="utf-8") as f:
                d = json.load(f)
            saved = datetime.datetime.fromisoformat(
                d.get("saved_at", "2000-01-01T00:00:00")
            )
            if (datetime.datetime.now() - saved).total_seconds() < CACHE_TTL * 3600:
                return d.get("flows", {})
    except Exception:
        pass
    return {}


def _save_cache(flows: dict):
    with open(CACHE_FILE, "w", encoding="utf-8") as f:
        json.dump({
            "saved_at": datetime.datetime.now().isoformat(timespec="seconds"),
            "flows":    flows,
        }, f, ensure_ascii=False, indent=2)


# ═══════════════════════════════════════════════════════════════
# 방법 1: pykrx (가장 정확)
# ═══════════════════════════════════════════════════════════════
def _collect_via_pykrx(codes: list) -> dict:
    from pykrx import stock as krx

    today   = datetime.date.today()
    from_d  = (today - datetime.timedelta(days=FLOW_DAYS + 10)).strftime("%Y%m%d")
    to_d    = today.strftime("%Y%m%d")
    flows   = {}

    for code in codes:
        try:
            df = krx.get_market_trading_value_by_date(from_d, to_d, code)
            if df is None or df.empty:
                continue
            df = df.tail(FLOW_DAYS)

            f_col = next((c for c in df.columns if "외국인" in c), None)
            i_col = next((c for c in df.columns
                          if "기관합계" in c or c.strip() == "기관"), None)

            foreign_net = int(df[f_col].sum()) if f_col else 0
            inst_net    = int(df[i_col].sum()) if i_col else 0

            cap_df = krx.get_market_cap_by_date(from_d, to_d, code)
            market_cap = (int(cap_df["시가총액"].iloc[-1])
                          if cap_df is not None and not cap_df.empty else 0)

            flows[code] = {"foreign_net": foreign_net,
                           "inst_net":    inst_net,
                           "market_cap":  market_cap}
            time.sleep(0.08)
        except Exception:
            continue

    return flows


# ═══════════════════════════════════════════════════════════════
# 방법 2: 네이버 금융 API (pykrx 대체)
# ═══════════════════════════════════════════════════════════════
def _collect_via_naver(codes: list) -> dict:
    """
    네이버 금융 일별 투자자별 매매현황 API.
    URL: https://finance.naver.com/item/frgn.naver?code={code}
    """
    import re

    headers = {
        "User-Agent": "Mozilla/5.0",
        "Referer":    "https://finance.naver.com/",
    }
    flows = {}

    for code in codes:
        try:
            # 네이버 금융 외국인/기관 일별 데이터 (최근 10거래일)
            url  = f"https://finance.naver.com/item/frgn.naver?code={code}&page=1"
            resp = requests.get(url, headers=headers, timeout=8)
            resp.encoding = "euc-kr"
            html = resp.text

            # 외국인 순매수 (최근 5행)
            frgn_pattern = re.compile(
                r'<td[^>]*class="[^"]*num[^"]*"[^>]*>([+-]?\d[\d,]*)</td>', re.S)
            nums = [int(m.group(1).replace(",", ""))
                    for m in frgn_pattern.finditer(html)]

            if len(nums) >= 10:
                # 네이버 테이블 구조: [외국인순매수, 기관순매수, ...] × N행
                # 단순 합산 (5일치)
                foreign_net = sum(nums[0:10:2])   # 짝수 인덱스 = 외국인
                inst_net    = sum(nums[1:10:2])   # 홀수 인덱스 = 기관
            else:
                foreign_net = 0
                inst_net    = 0

            # 시가총액: yfinance에서 가져오기
            import yfinance as yf
            info       = yf.Ticker(f"{code}.KS").fast_info
            market_cap = getattr(info, "market_cap", 0) or 0

            flows[code] = {"foreign_net": foreign_net,
                           "inst_net":    inst_net,
                           "market_cap":  int(market_cap)}
            time.sleep(0.15)
        except Exception:
            continue

    return flows


# ═══════════════════════════════════════════════════════════════
# 방법 3: FinanceDataReader (numpy-free alternative)
# ═══════════════════════════════════════════════════════════════
def _collect_via_fdr(codes: list) -> dict:
    """FinanceDataReader로 수급 데이터 수집"""
    import FinanceDataReader as fdr

    today  = datetime.date.today()
    from_d = today - datetime.timedelta(days=20)
    flows  = {}

    for code in codes:
        try:
            df = fdr.DataReader(code, from_d.strftime("%Y-%m-%d"))
            if df is None or df.empty:
                continue

            # FDR에 투자자별 데이터가 없으면 거래량 기반 대리변수 사용
            # (방향: 가격 상승 + 거래량 급증 = 외국인 매수 추정)
            import yfinance as yf
            info       = yf.Ticker(f"{code}.KS").fast_info
            market_cap = getattr(info, "market_cap", 0) or 0

            close_5d = df["Close"].tail(FLOW_DAYS)
            mom_5d   = (float(close_5d.iloc[-1]) / float(close_5d.iloc[0]) - 1) * 100

            # 모멘텀 기반 proxy (실제 수급 데이터 아님 — 점수만 반영)
            proxy_net = int(market_cap * mom_5d / 100 / 10)   # 시총의 1/10 비례

            flows[code] = {"foreign_net": proxy_net,
                           "inst_net":    0,
                           "market_cap":  int(market_cap),
                           "proxy":       True}   # proxy 플래그
            time.sleep(0.1)
        except Exception:
            continue

    return flows


# ═══════════════════════════════════════════════════════════════
# 통합 수집 함수
# ═══════════════════════════════════════════════════════════════
def collect_all_flows(ticker_codes: list) -> dict:
    """
    국내 종목 리스트의 외국인·기관 순매수 데이터 수집.
    pykrx → 네이버금융 → FinanceDataReader 순으로 자동 대체.

    Args:
        ticker_codes: ['005930', '000660', ...] — suffix 없는 코드

    Returns:
        { '005930': {'foreign_net': int, 'inst_net': int, 'market_cap': int} }
    """
    cached = _load_cache()
    if cached:
        print(f"  [수급] 캐시 적중 ({len(cached)}개 · {CACHE_TTL}시간 유효)")
        return cached

    flows: dict = {}

    # ① pykrx 시도
    try:
        import pykrx  # noqa: F401
        print(f"  [수급] pykrx 방식으로 {len(ticker_codes)}개 수집 중...")
        flows = _collect_via_pykrx(ticker_codes)
        print(f"  [수급] ✅ pykrx: {len(flows)}개 완료")
    except ImportError:
        pass
    except Exception as e:
        print(f"  [수급] pykrx 실패: {e}")

    # ② FinanceDataReader 시도
    if not flows:
        try:
            import FinanceDataReader  # noqa: F401
            print(f"  [수급] FinanceDataReader 방식으로 {len(ticker_codes)}개 수집 중...")
            flows = _collect_via_fdr(ticker_codes)
            print(f"  [수급] ✅ FDR: {len(flows)}개 완료 (proxy 데이터)")
        except ImportError:
            pass
        except Exception as e:
            print(f"  [수급] FDR 실패: {e}")

    # ③ 네이버금융 시도
    if not flows:
        print(f"  [수급] 네이버금융 방식으로 {len(ticker_codes)}개 수집 중...")
        try:
            flows = _collect_via_naver(ticker_codes)
            print(f"  [수급] ✅ 네이버: {len(flows)}개 완료")
        except Exception as e:
            print(f"  [수급] 네이버금융 실패: {e}")

    if flows:
        _save_cache(flows)
    else:
        print("  [수급] ⚠️ 모든 방법 실패 — 수급 점수 미적용")

    return flows


# ═══════════════════════════════════════════════════════════════
# 수급 점수 계산
# ═══════════════════════════════════════════════════════════════
def calc_flow_score(foreign_net: int, inst_net: int, market_cap: int) -> int:
    """
    외국인·기관 순매수 비율 → 수급 점수 (-30 ~ +30)
    비율 = 순매수금액 / 시가총액 × 100 (%)
    """
    if market_cap <= 0:
        return 0

    f_ratio = foreign_net / market_cap * 100
    i_ratio = inst_net    / market_cap * 100
    score   = 0

    # 외국인 (±15)
    if   f_ratio >  0.3: score += 15
    elif f_ratio >  0.1: score += 8
    elif f_ratio < -0.3: score -= 15
    elif f_ratio < -0.1: score -= 8

    # 기관 (±15)
    if   i_ratio >  0.3: score += 15
    elif i_ratio >  0.1: score += 8
    elif i_ratio < -0.3: score -= 15
    elif i_ratio < -0.1: score -= 8

    return max(-30, min(30, score))


# ═══════════════════════════════════════════════════════════════
# CLI 테스트
# ═══════════════════════════════════════════════════════════════
if __name__ == "__main__":
    import sys
    if sys.stdout.encoding != "utf-8":
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    test_codes = ["005930", "000660", "035420", "012450", "079550"]

    print("=" * 65)
    print("  국내 종목 수급 분석 (외국인·기관 5일 순매수)")
    print("=" * 65)

    flows = collect_all_flows(test_codes)
    if flows:
        print(f"\n  {'코드':8s}  {'외국인순매수':>16s}  {'기관순매수':>14s}  {'수급점수':>6s}")
        print("  " + "-" * 50)
        for code, d in flows.items():
            sc   = calc_flow_score(d["foreign_net"], d["inst_net"], d["market_cap"])
            sign = "+" if sc >= 0 else ""
            proxy = " (proxy)" if d.get("proxy") else ""
            print(f"  {code:8s}  {d['foreign_net']:>16,.0f}  "
                  f"{d['inst_net']:>14,.0f}  {sign}{sc:>4d}점{proxy}")
    else:
        print("  수집 실패")
