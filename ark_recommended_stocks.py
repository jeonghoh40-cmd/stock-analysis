"""
ARK Invest Big Ideas 2026 — 추천 종목 관리 모듈
────────────────────────────────────────────────────────────────
데이터 출처:
  - ARK Invest "Big Ideas 2026" (2026-01-21 발표)
  - PDF: Ark/ARKInvest BigIdeas2026.pdf (111 페이지)
  - 13 대 Big Ideas 테마별 핵심 종목

목적:
  - ARK 가 선정한 유망 기업들을 DB 에 저장
  - 주기적 관찰 보고서 생성
  - 기존 스크리닝 추천 종목과 별도 카테고리 관리
"""

import os
import sys
import json
import datetime
from typing import Optional

import yfinance as yf
import pandas as pd

if sys.stdout.encoding != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

BASE_DIR = os.path.dirname(os.path.abspath(__file__))


# ═══════════════════════════════════════════════════════════════
# ARK Big Ideas 2026 — 13 대 테마별 핵심 추천 종목
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


# ═══════════════════════════════════════════════════════════════
# 통합 종목 목록 (중복 제거)
# ═══════════════════════════════════════════════════════════════

def get_unique_ark_tickers() -> dict:
    """
    모든 테마에서 중복 없는 티커 목록을 반환한다.
    반환: {티커: {name, markets: [], themes: [], reasons: []}}
    """
    ticker_map = {}
    for theme_key, theme in ARK_RECOMMENDED.items():
        for ticker, info in theme["tickers"].items():
            if ticker not in ticker_map:
                ticker_map[ticker] = {
                    "name": info["name"],
                    "market": info["market"],
                    "themes": [],
                    "reasons": [],
                }
            ticker_map[ticker]["themes"].append(theme_key)
            ticker_map[ticker]["reasons"].append(info["reason"])
    return ticker_map


# ═══════════════════════════════════════════════════════════════
# 현재가 및 모멘텀 데이터 수집
# ═══════════════════════════════════════════════════════════════

def fetch_ticker_data(ticker: str, max_retries: int = 2) -> dict:
    """
    단일 티커의 현재가 및 모멘텀 데이터를 수집한다.
    yfinance 데이터 신뢰성 향상을 위해:
      - 1d 기간으로 최근 데이터만 조회 (가장 정확한 종가)
      - 실패 시 재시도 (최대 2 회)
      - fast_info 로 현재가 교차 검증
    """
    for attempt in range(max_retries + 1):
        try:
            t = yf.Ticker(ticker)
            
            # 1. 최근 2 일 데이터로 정확한 종가 확인 (가장 신뢰성 높음)
            h = t.history(period="2d", interval="1d")
            if h is None or h.empty or "Close" not in h.columns:
                raise ValueError("유효한 가격 데이터 없음")
            
            close = h["Close"].dropna()
            if len(close) == 0:
                raise ValueError("종가 데이터 없음")
            
            current = float(close.iloc[-1])
            
            # 2. fast_info 로 현재가 교차 검증 (선택적)
            try:
                fast_price = t.fast_info.get("lastPrice", current)
                # 5% 이상 차이 나면 경고 (데이터 신뢰성 문제)
                if abs(fast_price - current) / current > 0.05:
                    print(f"  ⚠️ {ticker} 가격 차이: history={current:.2f}, fast={fast_price:.2f}")
            except Exception:
                pass  # fast_info 실패 시 history 데이터 사용
            
            # 3. 과거 데이터 재조회 (모멘텀 계산용)
            if attempt == 0:
                try:
                    h_long = t.history(period="65d", interval="1d")
                    if h_long is not None and not h_long.empty and "Close" in h_long.columns:
                        h = h_long
                        close = h["Close"].dropna()
                except Exception:
                    pass  # 실패 시 짧은 데이터로 계속
            
            # 데이터 충분성 체크
            if len(close) < 2:
                raise ValueError("데이터 부족 (2 일 미만)")
            
            prev = float(close.iloc[-2])
            
            # 모멘텀 계산
            ret_1d = (current - prev) / prev * 100 if prev > 0 else 0
            ret_5d = (close.iloc[-1] / close.iloc[-6] - 1) * 100 if len(close) > 5 else 0
            ret_20d = (close.iloc[-1] / close.iloc[-21] - 1) * 100 if len(close) > 20 else 0
            
            # 기술적 지표
            ma5 = float(close.rolling(5).mean().iloc[-1])
            ma20 = float(close.rolling(20).mean().iloc[-1]) if len(close) >= 20 else current
            ma60 = float(close.rolling(60).mean().iloc[-1]) if len(close) >= 60 else current
            
            # RSI
            delta = close.diff()
            gain = delta.clip(lower=0).rolling(14).mean()
            loss = (-delta.clip(upper=0)).rolling(14).mean()
            rsi = 100 - 100 / (1 + gain.iloc[-1] / (loss.iloc[-1] + 1e-9))
            
            # 정보 (1 회만 시도)
            market_cap = pe = pb = None
            if attempt == 0:
                try:
                    info = t.info
                    market_cap = info.get("marketCap", 0)
                    pe = info.get("trailingPE")
                    pb = info.get("priceToBook")
                except Exception:
                    pass
            
            return {
                "ticker": ticker,
                "price": round(float(current), 2),
                "change_1d": round(float(ret_1d), 2),
                "change_5d": round(float(ret_5d), 2),
                "change_20d": round(float(ret_20d), 2),
                "ma5": round(ma5, 2),
                "ma20": round(ma20, 2),
                "ma60": round(ma60, 2),
                "rsi": round(float(rsi), 1),
                "market_cap": market_cap,
                "pe": round(float(pe), 1) if pe else None,
                "pb": round(float(pb), 2) if pb else None,
                "collected_at": datetime.datetime.now().isoformat(),
            }
            
        except Exception as e:
            if attempt < max_retries:
                print(f"  [재시도] {ticker}: {e} ({attempt + 1}/{max_retries})")
                import time
                time.sleep(1)  # 1 초 대기 후 재시도
            else:
                print(f"  [오류] {ticker}: {e} (최대 재시도 초과)")
                return {}
    
    return {}


def collect_all_ark_data() -> list:
    """
    모든 ARK 추천 종목의 데이터를 수집한다.
    """
    tickers = get_unique_ark_tickers()
    results = []

    print(f"\n📊 ARK 추천 종목 데이터 수집 시작 ({len(tickers)}개 종목)...")

    for ticker, info in tickers.items():
        print(f"  수집 중: {info['name']}({ticker})...", end=" ")
        data = fetch_ticker_data(ticker)
        if data:
            data["name"] = info["name"]
            data["market"] = info["market"]
            data["themes"] = info["themes"]
            data["reasons"] = info["reasons"]
            results.append(data)
            print(f"완료 (현재가: {data['price']:,.0f}, 20 일: {data['change_20d']:+.1f}%)")
        else:
            print("실패")

    return results


# ═══════════════════════════════════════════════════════════════
# 관찰 보고서 생성
# ═══════════════════════════════════════════════════════════════

def build_ark_observation_report(data: list) -> str:
    """
    ARK 추천 종목 관찰 보고서를 생성한다.
    """
    lines = []
    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")

    lines.append("\n" + "═" * 90)
    lines.append("  🎯 ARK Invest Big Ideas 2026 — 추천 종목 관찰보고서")
    lines.append(f"  기준: {now}")
    lines.append("═" * 90)

    # 시장별 분류
    by_market = {"KOSPI": [], "KOSDAQ": [], "US": []}
    for d in data:
        m = d.get("market", "US")
        if m in by_market:
            by_market[m].append(d)

    for market in ["KOSPI", "KOSDAQ", "US"]:
        items = by_market[market]
        if not items:
            continue

        lines.append(f"\n【{market} 시장 — {len(items)}개 종목】")
        lines.append(f"  {'종목명':<20} {'티커':<15} {'현재가':>12} {'1 일':>8} {'5 일':>8} {'20 일':>8} {'RSI':>6} {'테마':<30}")
        lines.append("  " + "-" * 115)

        # 20 일 수익률 기준 정렬
        sorted_items = sorted(items, key=lambda x: x.get("change_20d", 0), reverse=True)

        for item in sorted_items:
            name = item.get("name", "")[:18]
            ticker = item.get("ticker", "")
            price = f"{item.get('price', 0):,.0f}"
            c1 = f"{item.get('change_1d', 0):>+7.1f}%"
            c5 = f"{item.get('change_5d', 0):>+7.1f}%"
            c20 = f"{item.get('change_20d', 0):>+7.1f}%"
            rsi = f"{item.get('rsi', 0):>5.1f}"
            themes = ", ".join(item.get("themes", [])[:2])
            themes = themes.replace("1_", "").replace("2_", "").replace("3_", "").replace("4_", "")
            themes = themes.replace("5_", "").replace("6_", "").replace("7_", "").replace("8_", "")
            themes = themes.replace("9_", "").replace("10_", "").replace("11_", "").replace("12_", "").replace("13_", "")
            themes = themes[:28]

            # 모멘텀 아이콘
            if item.get("change_20d", 0) >= 10:
                icon = "🚀"
            elif item.get("change_20d", 0) >= 3:
                icon = "📈"
            elif item.get("change_20d", 0) >= -3:
                icon = "➡️"
            elif item.get("change_20d", 0) >= -10:
                icon = "📉"
            else:
                icon = "💥"

            lines.append(f"  {icon} {name:<18} {ticker:<15} {price:>12} {c1:>8} {c5:>8} {c20:>8} {rsi:>6} {themes:<28}")

    # 핵심 테마별 요약
    lines.append("\n\n" + "─" * 90)
    lines.append("【핵심 테마별 성과】")

    theme_perf = {}
    for d in data:
        for theme in d.get("themes", []):
            if theme not in theme_perf:
                theme_perf[theme] = {"count": 0, "rets": []}
            theme_perf[theme]["count"] += 1
            if d.get("change_20d") is not None:
                theme_perf[theme]["rets"].append(d["change_20d"])

    lines.append(f"  {'테마':<30} {'종목수':>8} {'평균 20 일':>12} {'모멘텀':<16}")
    lines.append("  " + "-" * 70)

    for theme_key, perf in sorted(theme_perf.items(), key=lambda x: sum(x[1]["rets"])/len(x[1]["rets"]) if x[1]["rets"] else 0, reverse=True):
        theme_name = theme_key.replace("_", " ")
        avg_ret = sum(perf["rets"]) / len(perf["rets"]) if perf["rets"] else 0
        if avg_ret >= 10:
            mom = "🚀 강한상승"
        elif avg_ret >= 3:
            mom = "📈 상승"
        elif avg_ret >= -3:
            mom = "➡️ 횡보"
        elif avg_ret >= -10:
            mom = "📉 하락"
        else:
            mom = "💥 급락"

        lines.append(f"  {theme_name:<28} {perf['count']:>8} {avg_ret:>+11.1f}% {mom:<16}")

    # 종합 의견
    lines.append("\n\n" + "─" * 90)
    lines.append("【종합 의견】")

    all_rets = [d.get("change_20d", 0) for d in data if d.get("change_20d") is not None]
    if all_rets:
        avg_all = sum(all_rets) / len(all_rets)
        pos = sum(1 for r in all_rets if r > 0)
        neg = sum(1 for r in all_rets if r < 0)

        lines.append(f"  • 전체 평균 20 일 수익률: {avg_all:+.1f}%")
        lines.append(f"  • 양수 종목: {pos}개 / 음수 종목: {neg}개")

        if avg_all >= 10:
            verdict = "🟢 ARK 테마 강력 상승장 — 핵심 보유 종목 대폭등"
        elif avg_all >= 3:
            verdict = "🟢 ARK 테마 상승장 — 대가속 테마 주도"
        elif avg_all >= -3:
            verdict = "🟡 보합세 — 테마별 차별화 진행"
        elif avg_all >= -10:
            verdict = "🟠 조정 국면 — 일부 테마 약세"
        else:
            verdict = "🔴 ARK 테마 약세장 — 리스크 관리 필요"

        lines.append(f"\n  ▶ 종합 판단: {verdict}")

    lines.append("\n" + "═" * 90)
    lines.append("  ⚠️ ARK 추천 종목은 장기 성장 테마 기반이나 변동성이 큽니다.")
    lines.append("     분할 매수·손절 관리 필수 · 투자 참고용")
    lines.append("  📚 출처: ark-invest.com/big-ideas-2026")
    lines.append("═" * 90 + "\n")

    return "\n".join(lines)


# ═══════════════════════════════════════════════════════════════
# JSON 저장
# ═══════════════════════════════════════════════════════════════

def save_ark_to_db(data: list):
    """
    ARK 추천 종목 데이터를 DB 에 저장한다.
    """
    import sys
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from db_manager import save_ark_recommended
    save_ark_recommended(data)


def save_ark_report(data: list, report_text: str, filename: str = None):
    """
    ARK 보고서를 JSON 과 TXT 로 저장한다.
    """
    if not filename:
        filename = f"ark_report_{datetime.datetime.now().strftime('%Y%m%d_%H%M')}"

    # JSON 데이터
    json_path = os.path.join(BASE_DIR, f"{filename}.json")
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump({
            "report_date": datetime.datetime.now().isoformat(),
            "tickers": data,
        }, f, ensure_ascii=False, indent=2, default=str)

    # TXT 보고서
    txt_path = os.path.join(BASE_DIR, f"{filename}.txt")
    with open(txt_path, "w", encoding="utf-8") as f:
        f.write(report_text)

    print(f"\n💾 저장 완료:")
    print(f"   - JSON: {json_path}")
    print(f"   - TXT:  {txt_path}")


# ═══════════════════════════════════════════════════════════════
# 실행
# ═══════════════════════════════════════════════════════════════

if __name__ == "__main__":
    print("\n🔍 ARK Invest Big Ideas 2026 — 추천 종목 분석 시작...\n")

    # 데이터 수집
    data = collect_all_ark_data()

    if not data:
        print("수집된 데이터가 없습니다.")
        sys.exit(1)

    # 보고서 생성
    report = build_ark_observation_report(data)
    print(report)

    # 저장 (파일 + DB)
    save_ark_report(data, report)
    save_ark_to_db(data)

    print(f"\n총 {len(data)}개 종목 ARK 분석 완료.")
