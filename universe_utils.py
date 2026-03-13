"""
유니버스 캐시 관리 유틸리티
────────────────────────────────────────────────────────────────
사용법:
  from universe_utils import clear_all_caches, refresh_universe

  clear_all_caches()          # 모든 캐시 초기화
  refresh_universe()          # 분석 루틴 시작 전 자동 refresh
  update_ipo_watchlist()      # KRX/미국 신규상장 자동 편입

CLI:
  python universe_utils.py                  # refresh 상태 출력
  python universe_utils.py ipo [--days 60]  # IPO 워치리스트 업데이트
"""

import json
import logging
import sys
from datetime import datetime, timedelta
from pathlib import Path

logger = logging.getLogger(__name__)

_IPO_PATH = Path(__file__).parent / "universe_ipo_watchlist.json"


# ═══════════════════════════════════════════════════════════════
# IPO 자동 편입
# ═══════════════════════════════════════════════════════════════

def fetch_kr_new_listings(days: int = 60) -> list:
    """
    FinanceDataReader로 최근 N일 내 KRX 신규상장 종목 조회.
    ListingDate 컬럼이 없는 경우 빈 리스트 반환.
    """
    try:
        import FinanceDataReader as fdr
        import pandas as pd
        cutoff = datetime.now() - timedelta(days=days)
        new_ipos = []
        for market, suffix in [("KOSPI", ".KS"), ("KOSDAQ", ".KQ")]:
            df = fdr.StockListing(market)
            date_col = next(
                (c for c in df.columns if "listing" in c.lower() or "상장" in c.lower()),
                None,
            )
            if date_col is None:
                continue
            df[date_col] = pd.to_datetime(df[date_col], errors="coerce")
            recent = df[df[date_col] >= cutoff].dropna(subset=[date_col])
            for _, row in recent.iterrows():
                code = str(row.get("Code", "")).zfill(6)
                name = str(row.get("Name", code))
                listed = row[date_col].strftime("%Y-%m-%d")
                if code:
                    new_ipos.append({
                        "name": name,
                        "ticker": f"{code}{suffix}",
                        "listed_date": listed,
                        "market": market,
                        "note": "자동수집",
                    })
        return new_ipos
    except ImportError:
        logger.warning("[IPO] FinanceDataReader 미설치 — KRX 신규상장 생략")
        return []
    except Exception as e:
        logger.warning(f"[IPO] KRX 신규상장 조회 실패: {e}")
        return []


def update_ipo_watchlist(days: int = 60, dry_run: bool = False) -> int:
    """
    KRX 신규상장을 universe_ipo_watchlist.json에 자동 편입.

    Parameters
    ----------
    days : int
        최근 N일 이내 상장 종목만 수집.
    dry_run : bool
        True면 파일을 수정하지 않고 추가될 항목만 출력.

    Returns
    -------
    int
        새로 추가된 종목 수.
    """
    # 기존 watchlist 로드
    existing: list = []
    if _IPO_PATH.exists():
        try:
            existing = json.loads(_IPO_PATH.read_text(encoding="utf-8"))
        except Exception:
            existing = []
    existing_tickers = {item["ticker"] for item in existing}

    # KRX 신규상장 수집
    new_kr = fetch_kr_new_listings(days=days)

    added = []
    for item in new_kr:
        if item["ticker"] not in existing_tickers:
            added.append(item)
            existing_tickers.add(item["ticker"])

    if not added:
        print(f"  [IPO] 새로 추가할 종목 없음 (최근 {days}일 기준)")
        return 0

    print(f"  [IPO] 신규 편입 {len(added)}개:")
    for it in added:
        print(f"    + {it['name']} ({it['ticker']}) 상장일:{it['listed_date']}")

    if not dry_run:
        merged = existing + added
        _IPO_PATH.write_text(
            json.dumps(merged, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        print(f"  [IPO] {_IPO_PATH} 저장 완료 (총 {len(merged)}개)")

    return len(added)


def clear_all_caches():
    """
    모든 동적 캐시를 초기화합니다.
    - KOSPI200 / KOSDAQ150 구성종목 캐시 (24 시간)
    - S&P500 시총 상위 20 캐시 (6 시간)
    
    사용법:
      - 종목 풀이 update 되지 않을 때 수동 refresh
      - 매일 분석 루틴 시작 전 호출
    """
    import universe
    
    # 내부 캐시 변수 초기화
    universe._kospi200_cache = None
    universe._kosdaq150_cache = None
    universe._sp500_cache = None
    
    logger.info("[캐시초기화] 모든 동적 종목 풀 캐시 초기화 완료")
    print("  ✓ 유니버스 캐시 초기화 완료 (KOSPI200, KOSDAQ150, S&P500)")


def clear_sp500_cache():
    """S&P500 시총 상위 20 캐시만 초기화합니다."""
    import universe
    universe._sp500_cache = None
    logger.info("[캐시초기화] S&P500 캐시 초기화 완료")
    print("  ✓ S&P500 캐시 초기화 완료")


def clear_kr_index_cache():
    """KOSPI200 / KOSDAQ150 구성종목 캐시만 초기화합니다."""
    import universe
    universe._kospi200_cache = None
    universe._kosdaq150_cache = None
    logger.info("[캐시초기화] 국내 지수 구성종목 캐시 초기화 완료")
    print("  ✓ 국내 지수 (KOSPI200/KOSDAQ150) 캐시 초기화 완료")


def refresh_universe():
    """
    분석 루틴 시작 전 유니버스를 refresh 합니다.
    1. 모든 캐시 초기화
    2. 최신 종목 풀 재조회
    3. 현재 상태 출력
    """
    import universe
    
    print("\n🔄 유니버스 종목 풀 refresh 시작...")
    
    # 1. 캐시 초기화
    clear_all_caches()
    
    # 2. 최신 종목 풀 조회
    kospi = universe.get_kospi200()
    kosdaq = universe.get_kosdaq150()
    sp500 = universe.get_sp500_top20()
    
    # 3. 상태 출력
    print(f"\n  📊 현재 종목 풀:")
    print(f"     - KOSPI200:  {len(kospi)}개")
    print(f"     - KOSDAQ150: {len(kosdaq)}개")
    print(f"     - S&P500 Top20: {len(sp500)}개")
    print(f"     - 전체 합계: {len(kospi) + len(kosdaq) + len(sp500)}개")
    
    # 4. SELL_POOL 확인
    if universe.SELL_POOL:
        print(f"\n  ⚠️  유동성 급감 종목 (SELL_POOL): {len(universe.SELL_POOL)}개")
        for ticker, date in list(universe.SELL_POOL.items())[:5]:
            print(f"     - {ticker} ({date})")
    
    print("\n  ✓ 유니버스 refresh 완료\n")
    
    return {
        "kospi_count": len(kospi),
        "kosdaq_count": len(kosdaq),
        "sp500_count": len(sp500),
        "sell_pool_count": len(universe.SELL_POOL),
        "refreshed_at": datetime.now().isoformat(),
    }


if __name__ == "__main__":
    import argparse

    if sys.stdout.encoding != "utf-8":
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    parser = argparse.ArgumentParser(description="유니버스 캐시 관리 & IPO 업데이트")
    sub = parser.add_subparsers(dest="cmd")

    ipo_p = sub.add_parser("ipo", help="IPO 워치리스트 자동 업데이트")
    ipo_p.add_argument("--days", type=int, default=60, help="최근 N일 신규상장 수집 (기본 60)")
    ipo_p.add_argument("--dry-run", action="store_true", help="파일 저장 없이 미리보기만")

    args = parser.parse_args()

    print("\n" + "=" * 60)
    print("  유니버스 캐시 관리 유틸리티")
    print("=" * 60)

    if args.cmd == "ipo":
        print(f"\n[IPO] 최근 {args.days}일 신규상장 수집 중...")
        added = update_ipo_watchlist(days=args.days, dry_run=args.dry_run)
        print(f"\n완료: {added}개 추가{'(dry-run)' if args.dry_run else ''}")
    else:
        result = refresh_universe()
        print("\n" + "─" * 60)
        print("  주요 명령어:")
        print("─" * 60)
        print("  python universe_utils.py                  # 유니버스 상태 확인")
        print("  python universe_utils.py ipo              # IPO 자동 업데이트 (60일)")
        print("  python universe_utils.py ipo --days 30    # 최근 30일만")
        print("  python universe_utils.py ipo --dry-run    # 저장 없이 미리보기")
