# ═══════════════════════════════════════════════════════════════
# ARK Big Ideas 2026 — 13 대 테마별 핵심 추천 종목 (PDF 기반 업데이트)
# ═══════════════════════════════════════════════════════════════
# 데이터 출처: ARK Invest "Big Ideas 2026" (2026 년 1 월 발표)
# PDF 파일: Ark/ARKInvest BigIdeas2026.pdf (111 페이지)
# 분석일: 2026-03-05
# ═══════════════════════════════════════════════════════════════

ARK_RECOMMENDED = {
    # ── 1. 대가속 (The Great Acceleration) — 5 개 플랫폼 수렴 ─────────
    "1_대가속": {
        "theme_name": "The Great Acceleration",
        "description": "AI·로보틱스·에너지·블록체인·멀티오믹스 5 개 플랫폼이 서로를 가속",
        "priority": "CORE",
        "tickers": {
            "NVDA": {"name": "NVIDIA", "market": "US", "reason": "AI 칩 독점 (GPU 85%), 5 개 테마 교차점"},
            "TSLA": {"name": "Tesla", "market": "US", "reason": "EV+AI+ 로보틱스 + 에너지 통합"},
            "MSFT": {"name": "Microsoft", "market": "US", "reason": "Azure OpenAI·Copilot 생산성"},
            "META": {"name": "Meta", "market": "US", "reason": "AI Consumer OS·광고 플랫폼"},
            "AMZN": {"name": "Amazon", "market": "US", "reason": "클라우드 + 물류 자동화"},
            "GOOGL": {"name": "Alphabet", "market": "US", "reason": "검색 AI+ 자율주행 (Waymo)"},
            "005930.KS": {"name": "삼성전자", "market": "KOSPI", "reason": "반도체·HBM·파운드리"},
            "000660.KS": {"name": "SK 하이닉스", "market": "KOSPI", "reason": "HBM 독점적 지위"},
        },
    },

    # ── 2. AI 인프라 — 데이터센터·반도체·전력 ───────────────────────
    "2_AI 인프라": {
        "theme_name": "AI Infrastructure",
        "description": "AI 수요가 데이터센터·반도체·전력 인프라 대규모 투자 촉발",
        "priority": "CORE",
        "tickers": {
            "NVDA": {"name": "NVIDIA", "market": "US", "reason": "GPU·CUDA 독점 (점유율 85%)"},
            "AMD": {"name": "AMD", "market": "US", "reason": "2 위 AI 칩 (MI300X)"},
            "AVGO": {"name": "Broadcom", "market": "US", "reason": "커스텀 AI 칩 (ASIC)"},
            "TSM": {"name": "TSMC", "market": "US", "reason": "파운드리 95%+ 가동"},
            "AMAT": {"name": "Applied Materials", "market": "US", "reason": "반도체 장비"},
            "LRCX": {"name": "Lam Research", "market": "US", "reason": "식각장비"},
            "KLAC": {"name": "KLA", "market": "US", "reason": "공정 제어 장비"},
            "SMCI": {"name": "Super Micro", "market": "US", "reason": "AI 서버"},
            "VRT": {"name": "Vertiv", "market": "US", "reason": "데이터센터 전력"},
            "CEG": {"name": "Constellation Energy", "market": "US", "reason": "원자력 전력"},
            "NEE": {"name": "NextEra Energy", "market": "US", "reason": "재생에너지+ESS"},
            "000660.KS": {"name": "SK 하이닉스", "market": "KOSPI", "reason": "HBM 필수 부품"},
            "042700.KS": {"name": "한미반도체", "market": "KOSDAQ", "reason": "HBM 장비"},
        },
    },

    # ── 3. AI Consumer OS ────────────────────────────────────────
    "3_AI_Consumer_OS": {
        "theme_name": "The AI Consumer Operating System",
        "description": "AI 가 앱·검색·커머스를 통합하는 새로운 소비자 인터페이스",
        "priority": "HIGH",
        "tickers": {
            "AAPL": {"name": "Apple", "market": "US", "reason": "기기 위의 AI(Apple Intelligence)"},
            "META": {"name": "Meta", "market": "US", "reason": "AI 피드 + 광고 (Meta AI)"},
            "GOOGL": {"name": "Alphabet", "market": "US", "reason": "검색 AI 전환 (Gemini)"},
            "AMZN": {"name": "Amazon", "market": "US", "reason": "Alexa+ 커머스"},
            "MSFT": {"name": "Microsoft", "market": "US", "reason": "Copilot 생산성"},
            "035420.KS": {"name": "NAVER", "market": "KOSPI", "reason": "AI 검색·하이퍼클로바"},
            "035720.KS": {"name": "카카오", "market": "KOSPI", "reason": "AI 비서·커머스"},
        },
    },

    # ── 4. AI 생산성 — 기업 소프트웨어 ───────────────────────────
    "4_AI_생산성": {
        "theme_name": "AI Productivity",
        "description": "AI 가 기업 내 지식노동 생산성을 비선형적으로 향상",
        "priority": "HIGH",
        "tickers": {
            "MSFT": {"name": "Microsoft", "market": "US", "reason": "Azure OpenAI·Copilot"},
            "NOW": {"name": "ServiceNow", "market": "US", "reason": "ServiceNow AI"},
            "CRM": {"name": "Salesforce", "market": "US", "reason": "Salesforce Einstein AI"},
            "WDAY": {"name": "Workday", "market": "US", "reason": "HR AI"},
            "PLTR": {"name": "Palantir", "market": "US", "reason": "국방·기업 AI 플랫폼"},
            "AI": {"name": "C3.ai", "market": "US", "reason": "AI 신약·에너지"},
            "PATH": {"name": "UiPath", "market": "US", "reason": "RPA+AI 자동화"},
            "SNOW": {"name": "Snowflake", "market": "US", "reason": "데이터 AI"},
            "DDOG": {"name": "Datadog", "market": "US", "reason": "AI 모니터링"},
            "MDB": {"name": "MongoDB", "market": "US", "reason": "AI 데이터베이스"},
        },
    },

    # ── 5. 비트코인 — 디지털 금 ──────────────────────────────────
    "5_비트코인": {
        "theme_name": "Bitcoin",
        "description": "ETF 승인 이후 기관 자금 유입 가속, 디지털 금 포지셔닝 (ETF 보유량 12%)",
        "priority": "CORE",
        "tickers": {
            "COIN": {"name": "Coinbase", "market": "US", "reason": "코인베이스 거래소"},
            "MSTR": {"name": "MicroStrategy", "market": "US", "reason": "비트코인 국채 전략"},
            "HOOD": {"name": "Robinhood", "market": "US", "reason": "리테일 크립토 게이트웨이"},
            "ARKB": {"name": "ARK Bitcoin ETF", "market": "US", "reason": "ARK 비트코인 ETF"},
            "BLK": {"name": "BlackRock", "market": "US", "reason": "iShares 비트코인 ETF"},
        },
    },

    # ── 6. 토큰화 자산 ───────────────────────────────────────────
    "6_토큰화자산": {
        "theme_name": "Tokenized Assets",
        "description": "주식·채권·부동산 등 실물자산이 블록체인으로 토큰화",
        "priority": "HIGH",
        "tickers": {
            "COIN": {"name": "Coinbase", "market": "US", "reason": "규제 준수 온램프"},
            "HOOD": {"name": "Robinhood", "market": "US", "reason": "리테일 접근점"},
            "BLK": {"name": "BlackRock", "market": "US", "reason": "iShares 토큰화 펀드"},
            "GS": {"name": "Goldman Sachs", "market": "US", "reason": "골드만삭스 디지털자산"},
            "MA": {"name": "Mastercard", "market": "US", "reason": "토큰화 결제"},
        },
    },

    # ── 7. DeFi 탈중앙화 금융 ───────────────────────────────────
    "7_DeFi": {
        "theme_name": "Decentralized Finance Applications",
        "description": "스마트컨트랙트 기반 대출·파생상품·결제 인프라",
        "priority": "MEDIUM",
        "tickers": {
            "COIN": {"name": "Coinbase", "market": "US", "reason": "DEX·스테이킹 수익"},
            "HOOD": {"name": "Robinhood", "market": "US", "reason": "크립토 거래"},
        },
    },

    # ── 8. 멀티오믹스 — AI × Biology ─────────────────────────────
    "8_멀티오믹스": {
        "theme_name": "Multiomics",
        "description": "AI 와 유전체·단백질체 분석이 결합해 신약 개발 기간·비용 급감",
        "priority": "HIGH",
        "tickers": {
            "ILMN": {"name": "Illumina", "market": "US", "reason": "유전체 시퀀싱 1 위"},
            "CRSP": {"name": "CRISPR Therapeutics", "market": "US", "reason": "CRISPR 유전자 편집"},
            "TXG": {"name": "10x Genomics", "market": "US", "reason": "단일세포 분석"},
            "TEM": {"name": "Tempus AI", "market": "US", "reason": "Tempus AI 정밀의료"},
            "RXRX": {"name": "Recursion", "market": "US", "reason": "AI 신약 플랫폼"},
            "IONS": {"name": "Ionis Pharma", "market": "US", "reason": "RNA 치료제"},
            "EXAS": {"name": "Exact Sciences", "market": "US", "reason": "암 조기진단"},
            "VEEV": {"name": "Veeva", "market": "US", "reason": "라이프사이언스 클라우드"},
            "207940.KS": {"name": "삼성바이오로직스", "market": "KOSPI", "reason": "바이오 CMO"},
            "068270.KS": {"name": "셀트리온", "market": "KOSPI", "reason": "바이오시밀러"},
            "196170.KQ": {"name": "알테오젠", "market": "KOSDAQ", "reason": "AI 바이오"},
        },
    },

    # ── 9. 재사용 로켓 — 우주 접근 비용 감소 ─────────────────────
    "9_재사용로켓": {
        "theme_name": "Reusable Rockets",
        "description": "SpaceX·RocketLab 이 발사 비용을 kg 당 수백만원 → 수만원으로 감소 (AI 칩 수요 60 배 증가)",
        "priority": "HIGH",
        "tickers": {
            "RKLB": {"name": "Rocket Lab", "market": "US", "reason": "로켓 랩 재사용 로켓"},
            "ASTS": {"name": "AST SpaceMobile", "market": "US", "reason": "위성통신"},
            "LUNR": {"name": "Intuitive Machines", "market": "US", "reason": "달 착륙 서비스"},
            "GOOGL": {"name": "Alphabet", "market": "US", "reason": "Waymo+ 위성 투자"},
            "AMZN": {"name": "Amazon", "market": "US", "reason": "Project Kuiper"},
        },
    },

    # ── 10. 로보틱스 — 범용 물리 AI ─────────────────────────────
    "10_로보틱스": {
        "theme_name": "Robotics",
        "description": "AI 모델이 로봇에 이식되며 공장·물류·가정까지 자동화 (2025 년 모멘텀 inflection)",
        "priority": "CORE",
        "tickers": {
            "TSLA": {"name": "Tesla", "market": "US", "reason": "Optimus 휴머노이드"},
            "ISRG": {"name": "Intuitive Surgical", "market": "US", "reason": "수술 로봇"},
            "ABB": {"name": "ABB", "market": "US", "reason": "산업용 로봇 세계 2 위"},
            "PATH": {"name": "UiPath", "market": "US", "reason": "RPA+AI"},
            "NVDA": {"name": "NVIDIA", "market": "US", "reason": "Isaac 로봇 AI 플랫폼"},
            "457660.KS": {"name": "두산로보틱스", "market": "KOSPI", "reason": "협동로봇"},
            "277810.KQ": {"name": "레인보우로보틱스", "market": "KOSDAQ", "reason": "로봇关节"},
            "090360.KQ": {"name": "로보스타", "market": "KOSDAQ", "reason": "로봇 제어기"},
        },
    },

    # ── 11. 분산 에너지 — 전력이 AI 의 병목 ─────────────────────
    "11_분산에너지": {
        "theme_name": "Distributed Energy",
        "description": "AI 데이터센터 전력 수요 폭증 → 재생에너지+ESS+ 소형원전이 솔루션",
        "priority": "CORE",
        "tickers": {
            "TSLA": {"name": "Tesla", "market": "US", "reason": "Megapack ESS"},
            "ENPH": {"name": "Enphase Energy", "market": "US", "reason": "마이크로인버터"},
            "NEE": {"name": "NextEra Energy", "market": "US", "reason": "재생에너지 1 위"},
            "CEG": {"name": "Constellation Energy", "market": "US", "reason": "원자력 + 신재생"},
            "VST": {"name": "Vistra", "market": "US", "reason": "데이터센터 전력 공급"},
            "GEV": {"name": "GE Vernova", "market": "US", "reason": "전력 인프라"},
            "SMR": {"name": "NuScale Power", "market": "US", "reason": "소형모듈원전"},
            "AES": {"name": "AES Corp", "market": "US", "reason": "전력 유틸리티"},
            "373220.KS": {"name": "LG 에너지솔루션", "market": "KOSPI", "reason": "배터리 ESS"},
            "247540.KQ": {"name": "에코프로비엠", "market": "KOSDAQ", "reason": "양극재"},
            "006400.KS": {"name": "삼성 SDI", "market": "KOSPI", "reason": "배터리"},
        },
    },

    # ── 12. 자율주행 — 로보택시 경제학 ──────────────────────────
    "12_자율주행": {
        "theme_name": "Autonomous Vehicles",
        "description": "완전 자율주행이 상용화되면 이동 비용이 현재의 10 분의 1 로 감소",
        "priority": "HIGH",
        "tickers": {
            "TSLA": {"name": "Tesla", "market": "US", "reason": "FSD·로보택시"},
            "GOOGL": {"name": "Alphabet", "market": "US", "reason": "Waymo(상용 로보택시)"},
            "UBER": {"name": "Uber", "market": "US", "reason": "자율주행 파트너십"},
            "MBLY": {"name": "Mobileye", "market": "US", "reason": "자율주행 칩"},
            "NVDA": {"name": "NVIDIA", "market": "US", "reason": "DriveOS Platform"},
            "005380.KS": {"name": "현대차", "market": "KOSPI", "reason": "자율주행 투자"},
            "000270.KS": {"name": "기아", "market": "KOSPI", "reason": "AV 투자"},
        },
    },

    # ── 13. 자율 물류 — 라스트마일 자동화 ───────────────────────
    "13_자율물류": {
        "theme_name": "Autonomous Logistics",
        "description": "AI 드론·자율트럭·로봇 창고가 물류 단가를 지수적으로 낮춤",
        "priority": "HIGH",
        "tickers": {
            "AMZN": {"name": "Amazon", "market": "US", "reason": "물류 자동화 1 위"},
            "TSLA": {"name": "Tesla", "market": "US", "reason": "Semi 자율트럭"},
            "UPS": {"name": "UPS", "market": "US", "reason": "드론배송 투자"},
            "GOOGL": {"name": "Alphabet", "market": "US", "reason": "Wing 드론"},
            "NVDA": {"name": "NVIDIA", "market": "US", "reason": "물류 AI 플랫폼"},
            "086280.KS": {"name": "현대글로비스", "market": "KOSPI", "reason": "물류 자동화"},
        },
    },
}
