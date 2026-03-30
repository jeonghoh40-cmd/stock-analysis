"""
스크리닝 유니버스 & 관심 종목 공통 정의 (Single Source of Truth)
─────────────────────────────────────────────────────────────────
[정적]  UNIVERSE            — 국내·미국·중국ETF 고정 종목
[동적]  get_sp500_top20()   — S&P500 시총 상위 20 실시간 조회 (6h 캐시)
[동적]  get_recent_ipos()   — 신규상장 종목 자동 편입 (JSON 파일 기반)
[감시]  update_sell_pool()  — 유동성 급감 → SELL_POOL 자동 이동
[통합]  get_full_universe() — 정적 + 동적 유니버스 병합 반환

종목 추가·삭제는 이 파일(정적) 또는 universe_ipo_watchlist.json(IPO)만 수정.
"""

import json
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

import yfinance as yf

logger = logging.getLogger(__name__)

# ═══════════════════════════════════════════════════════════════════
# 0. 상수
# ═══════════════════════════════════════════════════════════════════

_KR_INDEX_CACHE_TTL_SEC  = 24 * 3600  # KOSPI/KOSDAQ 지수 구성종목 24시간 캐시
_SP500_CACHE_TTL_SEC     =  6 * 3600  # S&P500 시총 상위 6시간 캐시

KOSPI200_INDEX_CODE  = "KOSPI"   # FinanceDataReader — 시총 상위 200개 사용
KOSDAQ150_INDEX_CODE = "KOSDAQ"  # FinanceDataReader — 시총 상위 150개 사용

_kospi200_cache:  Optional[tuple] = None  # (cached_at, {name: ticker})
_kosdaq150_cache: Optional[tuple] = None

# ═══════════════════════════════════════════════════════════════════
# 1. 정적 유니버스 (Anchor — pykrx fallback 및 보조 종목)
# ═══════════════════════════════════════════════════════════════════

UNIVERSE: dict = {

    # ─── 국내 코스피 대형주 ────────────────────────────────────────
    "🇰🇷 국내": {
        "삼성전자":           "005930.KS",  "SK하이닉스":        "000660.KS",
        "LG에너지솔루션":     "373220.KS",  "삼성바이오로직스":  "207940.KS",
        "현대차":             "005380.KS",  "기아":              "000270.KS",
        "NAVER":              "035420.KS",  "카카오":            "035720.KS",
        "셀트리온":           "068270.KS",  "POSCO홀딩스":       "005490.KS",
        "삼성SDI":            "006400.KS",  "LG화학":            "051910.KS",
        "한화에어로스페이스": "012450.KS",  "크래프톤":          "259960.KS",
        "SK이노베이션":       "096770.KS",  "현대모비스":        "012330.KS",
        "KB금융":             "105560.KS",  "신한지주":          "055550.KS",
        "하나금융지주":       "086790.KS",  "삼성물산":          "028260.KS",
        "LG전자":             "066570.KS",  "SK텔레콤":          "017670.KS",
        "KT":                 "030200.KS",  "두산에너빌리티":    "034020.KS",
        "카카오뱅크":         "323410.KS",  "카카오페이":        "377300.KS",
        "HMM":                "011200.KS",  "고려아연":          "010130.KS",
        "LG이노텍":           "011070.KS",  "삼성전기":          "009150.KS",
        "에코프로비엠":       "247540.KQ",  "에코프로":          "086520.KQ",
        "포스코퓨처엠":       "003670.KS",  "엔씨소프트":        "036570.KS",
        "넷마블":             "251270.KS",  "펄어비스":          "263750.KQ",
        "현대건설":           "000720.KS",  "한국전력":          "015760.KS",
        "삼성생명":           "032830.KS",  "삼성화재":          "000810.KS",
        "아모레퍼시픽":       "090430.KS",  "LG생활건강":        "051900.KS",
        "CJ제일제당":         "097950.KS",  "오리온":            "271560.KS",
        "대한항공":           "003490.KS",  "현대글로비스":      "086280.KS",
        "GS":                 "078930.KS",  "SK":                "034730.KS",
        "한국조선해양":       "009540.KS",  "한미반도체":        "042700.KS",
        "LIG넥스원":          "079550.KS",  "한국항공우주":      "047810.KS",
    },

    # ─── 코스닥 방산·보안 ──────────────────────────────────────────
    "🛡️ 코스닥 방산·보안": {
        "아이쓰리시스템":       "214430.KQ",
        "켄코아에어로스페이스": "274090.KQ",
        "빅텍":                 "065150.KQ",
        "스페코":               "013810.KQ",
        "퍼스텍":               "010820.KQ",
        "안랩":                 "053800.KQ",
        "이글루코퍼레이션":     "067920.KQ",
        "지니언스":             "263860.KQ",
        "라온시큐어":           "042510.KQ",
        "드림시큐리티":         "203650.KQ",
        "쎄트렉아이":           "099440.KQ",
    },

    # ─── 미국 대형주 (고정 베이스 60개) ──────────────────────────
    # S&P500 시총 상위 20은 get_sp500_top20()이 실시간으로 추가 편입
    "🇺🇸 미국": {
        "Apple":              "AAPL",   "NVIDIA":           "NVDA",
        "Microsoft":          "MSFT",   "Alphabet":         "GOOGL",
        "Amazon":             "AMZN",   "Meta":             "META",
        "Tesla":              "TSLA",   "Broadcom":         "AVGO",
        "AMD":                "AMD",    "TSMC ADR":         "TSM",
        "Netflix":            "NFLX",   "Salesforce":       "CRM",
        "Oracle":             "ORCL",   "Adobe":            "ADBE",
        "Qualcomm":           "QCOM",   "Intel":            "INTC",
        "Texas Instruments":  "TXN",    "Micron":           "MU",
        "Applied Materials":  "AMAT",   "Lam Research":     "LRCX",
        "KLA Corp":           "KLAC",   "Palo Alto":        "PANW",
        "CrowdStrike":        "CRWD",   "Snowflake":        "SNOW",
        "Palantir":           "PLTR",   "Datadog":          "DDOG",
        "ServiceNow":         "NOW",    "Workday":          "WDAY",
        "Uber":               "UBER",   "Airbnb":           "ABNB",
        "Booking":            "BKNG",   "Shopify":          "SHOP",
        "PayPal":             "PYPL",   "Coinbase":         "COIN",
        "Visa":               "V",      "Mastercard":       "MA",
        "JPMorgan":           "JPM",    "Goldman Sachs":    "GS",
        "Morgan Stanley":     "MS",     "Berkshire B":      "BRK-B",
        "Johnson&Johnson":    "JNJ",    "Pfizer":           "PFE",
        "Eli Lilly":          "LLY",    "UnitedHealth":     "UNH",
        "Novo Nordisk":       "NVO",    "Moderna":          "MRNA",
        "Exxon Mobil":        "XOM",    "Chevron":          "CVX",
        "NextEra Energy":     "NEE",    "Rivian":           "RIVN",
        "Boeing":             "BA",     "Lockheed Martin":  "LMT",
        "Caterpillar":        "CAT",    "Deere":            "DE",
        "Walmart":            "WMT",    "Costco":           "COST",
        "Nike":               "NKE",    "Starbucks":        "SBUX",
        "Walt Disney":        "DIS",    "McDonald's":       "MCD",
    },

    # ─── 중국ETF (KRX 상장 — 한국 증권사 판매 상품만) ──────────────
    # 개별 중국 ADR(BABA·JD 등) 및 홍콩 직상장 종목은 포함하지 않음
    "🇨🇳 중국ETF": {
        # 기존 6개
        "TIGER 차이나CSI300":       "192090.KS",  # 중국 A주 대형 300 벤치마크
        "KODEX 차이나H주":          "099140.KS",  # 홍콩 H주 블루칩
        "TIGER 차이나전기차":       "305540.KS",  # BYD·CATL 등 EV 밸류체인
        "KODEX 차이나항셍테크":     "371160.KS",  # 텐센트·알리바바 등 홍콩 테크
        "KINDEX 중국본토CSI300":    "168580.KS",  # CSI300 본토 합성
        "KODEX 차이나CSI300합성":   "310080.KS",  # CSI300 SWAP 합성
        # 추가 6개 (확장 풀)
        "TIGER 차이나CSI500":       "192720.KS",  # 중국 중소형 성장주 500
        # "TIGER 차이나항셍H주" (152280.KS), "ACE 중국본토CSI300" (420330.KS) — 상폐/yfinance 미지원으로 제거
        "KODEX 차이나과창판STAR50합성": "391600.KS", # 상하이 과학혁신판 STAR50
        "TIGER 차이나소비테마":     "290130.KS",  # 중국 내수 소비 섹터
        # "KBSTAR 중국본토대형주CSI100" (304850.KS) — yfinance 미지원으로 제거
    },

    # ─── 국내 섹터·테마 ETF (KRX 상장) ──────────────────────────────
    "🇰🇷 국내 ETF": {
        "KODEX 반도체":           "091160.KS",
        "KODEX 2차전지산업":      "305720.KS",
        "TIGER 원자력테마":       "381180.KS",
        "KODEX 헬스케어":         "266410.KS",
        "KODEX 에너지화학":       "117460.KS",
        "TIGER AI반도체핵심공정": "396520.KS",
        "TIGER K방산&우주":       "463250.KS",
        "TIGER 조선TOP10":        "466920.KS",
        "KODEX 은행":             "091170.KS",
        "TIGER 미디어컨텐츠":     "227550.KS",
    },

    # ─── 코스닥 테마주 (반도체장비·2차전지·바이오·우주방산) ──────────
    "🇰🇷 코스닥 테마": {
        # 반도체 장비·소재
        "리노공업":     "058470.KQ",  "이오테크닉스": "039030.KQ",
        "원익IPS":      "240810.KQ",  "피에스케이":   "319660.KQ",
        "하나마이크론": "067310.KQ",  "나노신소재":   "121600.KQ",
        # 2차전지 소재
        "엘앤에프":     "066970.KS",  "천보":         "278280.KQ",
        "솔브레인":     "357780.KQ",  "동화기업":     "025900.KQ",
        # 바이오·헬스케어
        "HLB":          "028300.KQ",  "알테오젠":     "196170.KQ",
        "파마리서치":   "214450.KQ",  "에이비엘바이오": "298380.KQ",
        "리가켐바이오": "141080.KQ",
        # 우주·방산
        "이노스페이스": "462350.KQ",  "비에이치아이": "083650.KQ",
        "퍼스텍":       "010820.KQ",
    },

    # ─── 코스피 테마주 (에너지·방산·전력기기·조선) ───────────────────
    "🇰🇷 코스피 테마": {
        # 에너지·정유
        "S-Oil":          "010950.KS",  "GS":             "078930.KS",
        # 방산·조선
        "HD현대중공업":   "329180.KS",  "현대로템":       "064350.KS",
        "풍산":           "103140.KS",  "한화시스템":     "272210.KS",
        # 전력기기·원전
        "HD현대일렉트릭": "267260.KS",  "LS일렉트릭":     "010120.KS",
        "효성중공업":     "298040.KS",  "두산밥캣":       "241560.KS",
        # 헬스케어
        "유한양행":       "000100.KS",  "종근당":         "185750.KS",
    },
}


# ═══════════════════════════════════════════════════════════════════
# 2. KOSPI 200 / KOSDAQ 150 동적 편입 (FinanceDataReader)
# ═══════════════════════════════════════════════════════════════════

_FDR_TOP_N = {"KOSPI": 200, "KOSDAQ": 150}

def _fetch_kr_index(index_code: str, suffix: str) -> dict:
    """
    FinanceDataReader로 시장 전체 목록을 조회한 뒤 시총 상위 N개를 반환.
    KOSPI → 상위 200개(KOSPI200 근사), KOSDAQ → 상위 150개(KOSDAQ150 근사).
    미설치 또는 API 오류 시 빈 딕셔너리 반환.
    """
    try:
        import FinanceDataReader as fdr
        top_n = _FDR_TOP_N.get(index_code, 200)
        df = fdr.StockListing(index_code)
        df = df.dropna(subset=["Marcap"])
        df = df.sort_values("Marcap", ascending=False).head(top_n)
        result: dict = {}
        for _, row in df.iterrows():
            code = str(row.get("Code", "")).zfill(6)
            name = str(row.get("Name", code))
            if code:
                result[name] = f"{code}{suffix}"
        return result
    except ImportError:
        logger.warning("[FinanceDataReader] 미설치 — pip install finance-datareader")
        return {}
    except Exception as e:
        logger.warning(f"[FinanceDataReader] index={index_code} 조회 실패: {e}")
        return {}


def get_kospi200() -> dict:
    """
    KOSPI 200 구성종목 반환 ({종목명: XXXXXX.KS}, 24시간 캐시).
    pykrx 미설치 시 UNIVERSE['🇰🇷 국내'] fallback.
    """
    global _kospi200_cache
    now = datetime.now()
    if _kospi200_cache and (now - _kospi200_cache[0]).total_seconds() < _KR_INDEX_CACHE_TTL_SEC:
        return _kospi200_cache[1]

    data = _fetch_kr_index(KOSPI200_INDEX_CODE, ".KS")
    if not data:
        logger.warning("[KOSPI200] fallback → 정적 UNIVERSE['🇰🇷 국내'] 사용")
        data = UNIVERSE.get("🇰🇷 국내", {})

    _kospi200_cache = (now, data)
    logger.info(f"[KOSPI200] {len(data)}개 갱신 완료")
    return data


def get_kosdaq150() -> dict:
    """
    KOSDAQ 150 구성종목 반환 ({종목명: XXXXXX.KQ}, 24시간 캐시).
    pykrx 미설치 시 UNIVERSE['🛡️ 코스닥 방산·보안'] fallback.
    """
    global _kosdaq150_cache
    now = datetime.now()
    if _kosdaq150_cache and (now - _kosdaq150_cache[0]).total_seconds() < _KR_INDEX_CACHE_TTL_SEC:
        return _kosdaq150_cache[1]

    data = _fetch_kr_index(KOSDAQ150_INDEX_CODE, ".KQ")
    if not data:
        logger.warning("[KOSDAQ150] fallback → 정적 UNIVERSE['🛡️ 코스닥 방산·보안'] 사용")
        data = UNIVERSE.get("🛡️ 코스닥 방산·보안", {})

    _kosdaq150_cache = (now, data)
    logger.info(f"[KOSDAQ150] {len(data)}개 갱신 완료")
    return data


# ═══════════════════════════════════════════════════════════════════
# 3. S&P500 시총 상위 20 동적 편입
# ═══════════════════════════════════════════════════════════════════

# 후보 풀: S&P500 시총 상위 50 범위 종목 (주기적으로 검토)
_SP500_CANDIDATES: dict = {
    # ── 빅테크 / AI ──────────────────────────────────────────────
    "Apple":            "AAPL",  "NVIDIA":          "NVDA",
    "Microsoft":        "MSFT",  "Alphabet":        "GOOGL",
    "Amazon":           "AMZN",  "Meta":            "META",
    "Tesla":            "TSLA",  "Broadcom":        "AVGO",
    "AMD":              "AMD",   "TSMC ADR":        "TSM",
    "Oracle":           "ORCL",  "Salesforce":      "CRM",
    "Adobe":            "ADBE",  "ServiceNow":      "NOW",
    "Palantir":         "PLTR",  "CrowdStrike":     "CRWD",
    "Palo Alto":        "PANW",  "Snowflake":       "SNOW",
    # ── 금융 ─────────────────────────────────────────────────────
    "Berkshire B":      "BRK-B", "JPMorgan":        "JPM",
    "Visa":             "V",     "Mastercard":      "MA",
    "Bank of America":  "BAC",   "Goldman Sachs":   "GS",
    "Morgan Stanley":   "MS",    "Wells Fargo":     "WFC",
    "American Express": "AXP",   "BlackRock":       "BLK",
    # ── 헬스케어 ─────────────────────────────────────────────────
    "Eli Lilly":        "LLY",   "UnitedHealth":    "UNH",
    "Johnson&Johnson":  "JNJ",   "Abbott Labs":     "ABT",
    "Novo Nordisk":     "NVO",   "Pfizer":          "PFE",
    "Merck":            "MRK",   "AbbVie":          "ABBV",
    # ── 소비재 / 필수소비재 ───────────────────────────────────────
    "Walmart":          "WMT",   "Costco":          "COST",
    "Procter&Gamble":   "PG",    "Pepsico":         "PEP",
    "Coca-Cola":        "KO",    "Home Depot":      "HD",
    "McDonald's":       "MCD",   "Nike":            "NKE",
    # ── 에너지 ───────────────────────────────────────────────────
    "Exxon Mobil":      "XOM",   "Chevron":         "CVX",
    "ConocoPhillips":   "COP",   "NextEra Energy":  "NEE",
    # ── 통신 / 미디어 ────────────────────────────────────────────
    "Netflix":          "NFLX",  "Walt Disney":     "DIS",
    "Comcast":          "CMCSA", "AT&T":            "T",
    # ── 산업재 ───────────────────────────────────────────────────
    "Caterpillar":      "CAT",   "Boeing":          "BA",
    "Lockheed Martin":  "LMT",   "Deere":           "DE",
    "Honeywell":        "HON",   "RTX":             "RTX",
}

_sp500_cache: Optional[tuple] = None  # (cached_at: datetime, data: dict)


def get_sp500_top20() -> dict:
    """
    _SP500_CANDIDATES 중 실시간 시가총액 상위 20개 반환.
    6시간 인메모리 캐시 적용 — 매 실행 시 API 과호출 방지.
    """
    global _sp500_cache
    now = datetime.now()

    if _sp500_cache:
        cached_at, cached_data = _sp500_cache
        if (now - cached_at).total_seconds() < _SP500_CACHE_TTL_SEC:
            return cached_data

    caps: dict = {}
    for name, ticker in _SP500_CANDIDATES.items():
        try:
            cap = yf.Ticker(ticker).fast_info.market_cap or 0
            if cap:
                caps[name] = (ticker, cap)
        except Exception as e:
            logger.debug(f"[SP500] {ticker} 시총 조회 실패: {e}")

    top20 = {
        name: ticker
        for name, (ticker, _) in sorted(
            caps.items(), key=lambda x: x[1][1], reverse=True
        )[:20]
    }
    _sp500_cache = (now, top20)
    logger.info(f"[SP500 Top20] {len(top20)}개 갱신 완료")
    return top20


# ═══════════════════════════════════════════════════════════════════
# 4. 신규상장(IPO) 자동 편입
# ═══════════════════════════════════════════════════════════════════

_IPO_WATCHLIST_PATH = Path(__file__).parent / "universe_ipo_watchlist.json"

# universe_ipo_watchlist.json 형식 (예시):
# [
#   {"name": "CoreWeave", "ticker": "CRWV", "listed_date": "2025-03-28", "market": "NASDAQ"},
#   {"name": "Cerebras",  "ticker": "CBRS", "listed_date": "2025-09-10", "market": "NASDAQ"}
# ]


def get_recent_kr_ipos_auto(days: int = 180) -> dict:
    """
    FinanceDataReader KRX-DESC 에서 ListingDate 기준 최근 N일 내 상장 종목 반환.
    SPAC, ETN, KONEX, 리츠 등 제외 — 일반 주식만 포함.
    반환: {종목명: 티커(XXXXXX.KS or .KQ)}
    """
    try:
        import FinanceDataReader as fdr
        import pandas as pd
        import re

        df = fdr.StockListing("KRX-DESC")
        df["ListingDate"] = pd.to_datetime(df["ListingDate"], errors="coerce")
        cutoff = datetime.now() - timedelta(days=days)
        recent = df[df["ListingDate"] >= cutoff].copy()

        # KOSPI / KOSDAQ 만 (KONEX 제외)
        recent = recent[recent["Market"].isin(["KOSPI", "KOSDAQ"])]
        # SPAC / ETN 코드 패턴 제외 (0으로 시작하는 코드)
        recent = recent[~recent["Code"].astype(str).str.startswith("0")]
        # 이름 기반 SPAC 필터
        recent = recent[~recent["Name"].str.contains(
            r"스팩|SPAC|호$|호스팩|리츠|REIT", case=False, na=False, regex=True
        )]

        result: dict = {}
        for _, row in recent.iterrows():
            code = str(row["Code"]).zfill(6)
            name = str(row["Name"])
            suffix = ".KS" if row["Market"] == "KOSPI" else ".KQ"
            result[name] = f"{code}{suffix}"

        logger.info(f"[IPO-FDR] 최근 {days}일 KRX 신규상장 {len(result)}개 탐지")
        return result
    except ImportError:
        logger.warning("[IPO-FDR] FinanceDataReader 미설치 — 자동 IPO 탐지 생략")
        return {}
    except Exception as e:
        logger.warning(f"[IPO-FDR] KRX-DESC 조회 실패: {e}")
        return {}


def get_recent_ipos(days: int = 180) -> dict:
    """
    universe_ipo_watchlist.json에서 최근 N일 내 상장된 종목 반환.
    파일이 없으면 빈 딕셔너리 반환 (오류 없이 fallback).
    """
    if not _IPO_WATCHLIST_PATH.exists():
        logger.debug("[IPO] universe_ipo_watchlist.json 없음 — 신규상장 편입 생략")
        return {}

    try:
        records = json.loads(_IPO_WATCHLIST_PATH.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as e:
        logger.warning(f"[IPO] watchlist 로드 실패: {e}")
        return {}

    cutoff = datetime.now() - timedelta(days=days)
    result: dict = {}
    for item in records:
        try:
            if datetime.strptime(item["listed_date"], "%Y-%m-%d") >= cutoff:
                result[item["name"]] = item["ticker"]
        except (KeyError, ValueError):
            continue

    logger.info(f"[IPO] 최근 {days}일 신규상장 {len(result)}개 편입")
    return result


# ═══════════════════════════════════════════════════════════════════
# 5. 유동성 급감 감지 → SELL_POOL 자동 편입
# ═══════════════════════════════════════════════════════════════════

# 상장폐지·데이터 없음 확인 종목 — 동적 풀에서 영구 제외
DELIST_BLACKLIST: set = {
    "068670.KS",   # 상장폐지 확인
    "426260.KQ",   # 상장폐지 확인
    "457400.KS",   # 구 TIGER K방산 코드 — 463250으로 변경됨
}

SELL_POOL: dict = {}  # {ticker: detected_date}  — 유동성 급감 종목

_LIQUIDITY_THRESHOLD = 0.3  # 20일 평균 대비 30% 이하 → 급감 판정
_LIQUIDITY_LOOKBACK  = 3    # 최근 N일 평균으로 비교


def check_liquidity_drop(ticker: str) -> bool:
    """
    최근 3일 평균 거래량이 20일 평균의 30% 이하이면 True.
    데이터 부족·API 오류 시 False 반환 (안전 방향).
    """
    try:
        df = yf.Ticker(ticker).history(period="25d", timeout=10)
        vol = df["Volume"].dropna()
        if len(vol) < _LIQUIDITY_LOOKBACK + 5:
            return False
        avg_20d = float(vol.iloc[:-_LIQUIDITY_LOOKBACK].mean())
        recent  = float(vol.iloc[-_LIQUIDITY_LOOKBACK:].mean())
        return avg_20d > 0 and recent < avg_20d * _LIQUIDITY_THRESHOLD
    except Exception as e:
        logger.debug(f"[유동성] {ticker} 조회 실패: {e}")
        return False


def update_sell_pool(tickers: list) -> dict:
    """
    tickers 목록을 순회해 유동성 급감 종목을 SELL_POOL에 추가.
    이미 SELL_POOL에 있는 종목은 재검사하지 않음.
    반환값: 갱신된 SELL_POOL 전체.
    """
    today = datetime.now().strftime("%Y-%m-%d")
    for ticker in tickers:
        if ticker in SELL_POOL:
            continue
        if check_liquidity_drop(ticker):
            SELL_POOL[ticker] = today
            logger.warning(f"[유동성 급감] {ticker} → SELL_POOL 편입 ({today})")
    return SELL_POOL


# ═══════════════════════════════════════════════════════════════════
# 6. 통합 유니버스 조회
# ═══════════════════════════════════════════════════════════════════

def get_full_universe(
    include_kr_index: bool = True,
    include_sp500_top20: bool = True,
    include_ipos: bool = True,
    ipo_days: int = 180,
) -> dict:
    """
    아래 소스를 병합해 {name: ticker} 반환.
      - 정적 UNIVERSE (중국ETF·미국 anchor)
      - KOSPI 200 + KOSDAQ 150 (pykrx 동적 조회)
      - S&P500 시총 상위 20 (동적)
      - 신규상장 IPO (JSON 파일)
    중복 티커는 먼저 추가된 이름 우선 유지.
    SELL_POOL 티커는 결과에서 제외.
    """
    merged: dict = {}  # {name: ticker}

    # 미국·중국ETF anchor + 국내 ETF/테마 (정적)
    for key in ("🇺🇸 미국", "🇨🇳 중국ETF", "🇰🇷 국내 ETF", "🇰🇷 코스피 테마", "🇰🇷 코스닥 테마"):
        merged.update(UNIVERSE.get(key, {}))

    # KOSPI 200 / KOSDAQ 150 (동적 우선, fallback 정적)
    if include_kr_index:
        existing = set(merged.values())
        for name, ticker in get_kospi200().items():
            if ticker not in existing:
                merged[name] = ticker
        existing = set(merged.values())
        for name, ticker in get_kosdaq150().items():
            if ticker not in existing:
                merged[name] = ticker

    # S&P500 시총 상위 20 (동적)
    if include_sp500_top20:
        existing = set(merged.values())
        for name, ticker in get_sp500_top20().items():
            if ticker not in existing:
                merged[f"[SP500] {name}"] = ticker

    # 신규상장 IPO
    if include_ipos:
        existing = set(merged.values())
        for name, ticker in get_recent_ipos(days=ipo_days).items():
            if ticker not in existing:
                merged[f"[IPO] {name}"] = ticker

    exclude = set(SELL_POOL.keys()) | DELIST_BLACKLIST
    return {name: ticker for name, ticker in merged.items() if ticker not in exclude}


def get_kr_pools() -> tuple[dict, dict]:
    """
    stock_advisor_v4.py용 — KOSPI / KOSDAQ 풀을 분리해서 반환.
    반환: (kospi_pool, kosdaq_pool)  각각 {name: ticker}
    정적 테마·ETF 종목을 동적 풀에 병합.
    """
    kospi  = get_kospi200()
    kosdaq = get_kosdaq150()

    # 정적 테마/ETF 보강
    for name, ticker in {**UNIVERSE.get("🇰🇷 국내 ETF", {}), **UNIVERSE.get("🇰🇷 코스피 테마", {})}.items():
        if ticker not in kospi.values():
            kospi[name] = ticker
    for name, ticker in UNIVERSE.get("🇰🇷 코스닥 테마", {}).items():
        if ticker not in kosdaq.values():
            kosdaq[name] = ticker

    exclude = set(SELL_POOL.keys()) | DELIST_BLACKLIST
    kospi  = {n: t for n, t in kospi.items()  if t not in exclude}
    kosdaq = {n: t for n, t in kosdaq.items() if t not in exclude}
    return kospi, kosdaq


# ═══════════════════════════════════════════════════════════════════
# 7. WATCHLIST — DART 심층 분석 대상 (국내 전용)
# ═══════════════════════════════════════════════════════════════════

def get_watchlist() -> dict:
    """
    DART 심층 분석 대상 종목 코드 반환 ({종목코드: 종목명}).
    KOSPI200 + KOSDAQ150 동적 조회 우선, 실패 시 정적 fallback.
    """
    combined = {**get_kospi200(), **get_kosdaq150()}
    if not combined:
        combined = {**UNIVERSE.get("🇰🇷 국내", {}), **UNIVERSE.get("🛡️ 코스닥 방산·보안", {})}
    return {
        ticker.replace(".KS", "").replace(".KQ", ""): name
        for name, ticker in combined.items()
    }


# 정적 fallback — pykrx 미설치 환경에서 dart_collector.py 등 직접 참조 시 사용
WATCHLIST: dict = {
    ticker.replace(".KS", "").replace(".KQ", ""): name
    for name, ticker in {
        **UNIVERSE["🇰🇷 국내"],
        **UNIVERSE["🛡️ 코스닥 방산·보안"],
    }.items()
}
