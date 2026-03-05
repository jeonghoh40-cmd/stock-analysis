"""
스크리닝 유니버스 & 관심 종목 공통 정의 (Single Source of Truth)
─────────────────────────────────────────────────────────────────
모든 파일이 이 파일에서 종목 목록을 참조한다.
종목 추가·삭제·변경은 이 파일 하나만 수정하면 전체 시스템에 자동 반영된다.

사용처:
  stock_advisor.py  →  from universe import UNIVERSE
  data_collector.py →  from universe import WATCHLIST
  dart_collector.py →  (data_collector 경유)
"""

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
        # ── 방산 대형주 (코스피) ─────────────────────────────────
        "LIG넥스원":          "079550.KS",  # 유도무기·레이더 전문
        "한국항공우주":       "047810.KS",  # KAI, FA-50 수출
    },

    # ─── 코스닥 방산·보안 (이란-미국 긴장 테마) ──────────────────
    "🛡️ 코스닥 방산·보안": {
        # 방산 / 무기·부품
        "아이쓰리시스템":     "214430.KQ",  # 군용 적외선 열화상 센서
        "켄코아에어로스페이스":"274090.KQ", # 항공기 구조물·방산 부품
        "빅텍":               "065150.KQ",  # 군용 전자장비·전원공급장치
        "스페코":             "013810.KQ",  # 방산 구동장치 (K2전차·자주포)
        "퍼스텍":             "010820.KQ",  # 방산 정밀부품·방위산업 기계
        # "나노스":           "151910.KQ",  # 상장폐지 (2025 년)
        # 사이버보안
        "안랩":               "053800.KQ",  # 국내 1위 보안 솔루션
        "이글루코퍼레이션":   "067920.KQ",  # 통합보안관제(SIEM)
        "지니언스":           "263860.KQ",  # 네트워크 접근제어(NAC)
        "라온시큐어":         "042510.KQ",  # 인증·암호화 보안
        "드림시큐리티":       "203650.KQ",  # PKI·전자서명
        # 드론·위성
        "쎄트렉아이":         "099440.KQ",  # 군용 위성·광학 감시 시스템
        # "에이스테크":       "088920.KQ",  # 상장폐지 (2025 년)
    },

    # ─── 미국 대형주 ──────────────────────────────────────────────
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

    # ─── 중국 (상장폐지 4종목 제외 후) ───────────────────────────
    "🇨🇳 중국": {
        "알리바바":     "BABA",   "징둥닷컴":   "JD",    "바이두":      "BIDU",
        "핀둬둬":       "PDD",    "넷이즈":     "NTES",  "비리비리":    "BILI",
        "샤오펑":       "XPEV",   "니오":       "NIO",   "리오토":      "LI",
        "ZTO Express":  "ZTO",    "Trip.com":   "TCOM",  "Vipshop":     "VIPS",
        "Ke Holdings":  "BEKE",   "iQIYI":      "IQ",    "Weibo":       "WB",
        "360 Finance":  "QFIN",   "Lufax":      "LU",    "Full Truck":  "YMM",
        "Kanzhun":      "BZ",     "New Orient": "EDU",   "TAL Education":"TAL",
        "Daqo Energy":  "DQ",     "JinkoSolar": "JKS",   "ACM Research":"ACMR",
        "Himax Tech":   "HIMX",   "Agora":      "API",   "Kingsoft Cloud":"KC",
        "Tuya Smart":   "TUYA",   "Liqtech Intl":"LIQT", "UTStarcom":   "UTSI",
        "GreenPower":   "GP",     "Sohu.com":   "SOHU",  "Remark Hdgs": "MARK",
        "Ebang Intl":   "EBON",   "Nano-X":     "NNOX",  "ChinaNet":    "CNET",
    },
}

# ─── data_collector 전용: 심층 분석 대상 (DART + 기술지표) ──────
# 국내 코스피 + 코스닥 방산·보안 통합
# 형식: {종목코드: 종목명}  (yfinance suffix 제거)
WATCHLIST: dict = {
    ticker.replace(".KS", "").replace(".KQ", ""): name
    for name, ticker in {
        **UNIVERSE["🇰🇷 국내"],
        **UNIVERSE["🛡️ 코스닥 방산·보안"],
    }.items()
}
