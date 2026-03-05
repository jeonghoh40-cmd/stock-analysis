"""
ARK Big Ideas 2026 × Citrini 2028 위기 — 통합 관찰 모듈
────────────────────────────────────────────────────────────────
데이터 출처:
  ① ARK Invest "Big Ideas 2026" (2026-01-21 발표)
     - 13대 Big Ideas: The Great Acceleration 등 5개 플랫폼 수렴
     - GDP 7.3% 달성 목표 (2030년)
  ② Citrini Research "2028 Global Intelligence Crisis" (2026-02-22 발표)
     - 시나리오 보고서 (예측이 아닌 시나리오)
     - S&P 8000 → 3500 붕괴 / 실업률 10.2% 경고
     - 승자: 컴퓨트 소유자(NVDA·TSM·AMZN)
     - 패자: 화이트칼라 대체 노출 업종

목적:
  - 13개 ARK 테마별 주간/월간 수익률 추적
  - Citrini 위기 지표 실시간 모니터링
  - 두 시나리오 간 현재 시장 위치 진단
  - stock_advisor_v4.py에 관찰보고서 섹션 첨부
"""

import os
import sys
import json
import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed

import yfinance as yf
import pandas as pd

if sys.stdout.encoding != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

BASE_DIR   = os.path.dirname(os.path.abspath(__file__))
CACHE_FILE = os.path.join(BASE_DIR, "ark_convergence_cache.json")
CACHE_TTL  = 6   # hours


# ═══════════════════════════════════════════════════════════════
# ARK Big Ideas 2026 — 13대 테마 × 핵심 종목
# ═══════════════════════════════════════════════════════════════
ARK_THEMES = {
    # 1. 대가속 (The Great Acceleration) — 5개 플랫폼 수렴의 상징 테마
    "1_대가속": {
        "name": "The Great Acceleration (5플랫폼 수렴)",
        "desc": "AI·로보틱스·에너지·블록체인·멀티오믹스 5개 플랫폼이 서로를 가속",
        "scenario": "bull",
        "tickers": {
            "NVDA": "AI 칩 대장주", "TSLA": "4개 테마 교차",
            "MSFT": "AI 생산성 통합", "META": "AI Consumer OS",
            "AMZN": "클라우드+물류 자동화", "GOOGL": "AI+자율주행(Waymo)",
        },
        "kr_tickers": {
            "005930.KS": "삼성전자(반도체)", "000660.KS": "SK하이닉스(HBM)",
        },
        "etf": "ARKK",
    },

    # 2. AI 인프라 — 데이터센터·칩·전력이 새로운 철도
    "2_AI인프라": {
        "name": "AI Infrastructure",
        "desc": "AI 수요가 데이터센터·반도체·전력 인프라 대규모 투자 촉발",
        "scenario": "bull",
        "tickers": {
            "NVDA": "GPU·CUDA 독점", "AMD": "2위 AI칩",
            "AVGO": "커스텀 AI칩(ASIC)", "TSM": "파운드리 95%+ 가동",
            "AMAT": "반도체 장비", "LRCX": "식각장비",
            "SMCI": "AI 서버", "VRT": "데이터센터 전력",
            "CEG": "원자력 전력", "NEE": "재생에너지+ESS",
        },
        "kr_tickers": {
            "000660.KS": "SK하이닉스 HBM", "042700.KS": "한미반도체",
            "064290.KQ": "이오테크닉스",
        },
        "etf": "SOXX",
    },

    # 3. AI Consumer OS — AI가 검색·쇼핑·의사결정을 대체
    "3_AI소비자OS": {
        "name": "AI Consumer Operating System",
        "desc": "AI가 앱·검색·커머스를 통합하는 새로운 소비자 인터페이스로 부상",
        "scenario": "bull",
        "tickers": {
            "AAPL": "기기 위의 AI(Apple Intelligence)", "META": "AI 피드+광고",
            "GOOGL": "검색 AI 전환", "AMZN": "Alexa+커머스",
            "MSFT": "Copilot 생산성", "SNAP": "AR+AI",
        },
        "kr_tickers": {
            "035420.KS": "NAVER AI", "035720.KS": "카카오AI",
        },
        "etf": "WCLD",
    },

    # 4. AI 생산성 — 기업 소프트웨어의 AI 대전환
    "4_AI생산성": {
        "name": "AI Productivity",
        "desc": "AI가 기업 내 지식노동 생산성을 비선형적으로 향상",
        "scenario": "bull",
        "tickers": {
            "MSFT": "Azure OpenAI·Copilot", "NOW": "ServiceNow AI",
            "CRM": "Salesforce Einstein AI", "WDAY": "HR AI",
            "PLTR": "국방·기업 AI 플랫폼", "AI": "C3.ai",
            "PATH": "RPA+AI 자동화", "SNOW": "데이터 AI",
        },
        "kr_tickers": {},
        "etf": "IGV",
    },

    # 5. 비트코인 — 디지털 금·제도권 편입
    "5_비트코인": {
        "name": "Bitcoin",
        "desc": "ETF 승인 이후 기관 자금 유입 가속, 디지털 금 포지셔닝",
        "scenario": "bull",
        "tickers": {
            "COIN": "코인베이스 거래소", "MSTR": "비트코인 국채 전략",
            "HOOD": "리테일 크립토 게이트웨이", "ARKB": "ARK 비트코인 ETF",
            "BTC-USD": "비트코인 현물",
        },
        "kr_tickers": {},
        "etf": "ARKB",
    },

    # 6. 토큰화 자산 — 실물자산의 블록체인 온체인화
    "6_토큰화자산": {
        "name": "Tokenized Assets",
        "desc": "주식·채권·부동산 등 실물자산이 블록체인으로 토큰화",
        "scenario": "bull",
        "tickers": {
            "COIN": "규제 준수 온램프", "CRCL": "Circle(USD코인)",
            "HOOD": "리테일 접근점", "BLK": "iShares 토큰화 펀드",
            "GS": "골드만삭스 디지털자산",
        },
        "kr_tickers": {},
        "etf": "BKCH",
    },

    # 7. DeFi 탈중앙화 금융
    "7_DeFi": {
        "name": "Decentralized Finance Applications",
        "desc": "스마트컨트랙트 기반 대출·파생상품·결제 인프라",
        "scenario": "bull",
        "tickers": {
            "COIN": "DEX·스테이킹 수익", "HOOD": "크립토 거래",
            "ETH-USD": "이더리움(DeFi 기반)", "SOL-USD": "솔라나",
        },
        "kr_tickers": {},
        "etf": "BKCH",
    },

    # 8. 멀티오믹스 — AI가 신약개발·정밀의료 가속
    "8_멀티오믹스": {
        "name": "Multiomics (AI × Biology)",
        "desc": "AI와 유전체·단백질체 분석이 결합해 신약 개발 기간·비용을 급감",
        "scenario": "bull",
        "tickers": {
            "ILMN": "유전체 시퀀싱 1위", "CRSP": "CRISPR 유전자 편집",
            "TXG": "단일세포 분석", "TEM": "Tempus AI 정밀의료",
            "RXRX": "Recursion(AI 신약 플랫폼)", "IONS": "RNA 치료제",
            "EXAS": "암 조기진단",
        },
        "kr_tickers": {
            "207940.KS": "삼성바이오로직스", "068270.KS": "셀트리온",
            "196170.KQ": "알테오젠(AI 바이오)",
        },
        "etf": "ARKG",
    },

    # 9. 재사용 로켓 — 우주 접근 비용 지수적 감소
    "9_재사용로켓": {
        "name": "Reusable Rockets",
        "desc": "SpaceX·RocketLab이 발사 비용을 kg당 수백만원 → 수만원으로 붕괴",
        "scenario": "bull",
        "tickers": {
            "RKLB": "Rocket Lab", "ASTS": "AST SpaceMobile(위성통신)",
            "GOOGL": "Waymo+위성 투자", "AMZN": "Project Kuiper",
            "LUNR": "달 착륙 서비스",
        },
        "kr_tickers": {},
        "etf": "ARKX",
    },

    # 10. 로보틱스 — 범용 물리 AI의 임계점
    "10_로보틱스": {
        "name": "Robotics (Physical AI)",
        "desc": "AI 모델이 로봇에 이식되며 공장·물류·가정까지 자동화 파고 확산",
        "scenario": "bull",
        "tickers": {
            "TSLA": "Optimus 휴머노이드", "PATH": "UiPath RPA+AI",
            "ABB": "산업용 로봇 세계 2위", "ISRG": "수술 로봇",
            "NVDA": "Isaac 로봇 AI 플랫폼",
        },
        "kr_tickers": {
            "457660.KS": "두산로보틱스", "277810.KQ": "레인보우로보틱스",
            "090360.KQ": "로보스타",
        },
        "etf": "ARKQ",
    },

    # 11. 분산 에너지 — 전력이 AI의 병목
    "11_분산에너지": {
        "name": "Distributed Energy",
        "desc": "AI 데이터센터 전력 수요 폭증 → 재생에너지+ESS+소형원전이 솔루션",
        "scenario": "bull",
        "tickers": {
            "TSLA": "Megapack ESS", "ENPH": "마이크로인버터",
            "NEE": "재생에너지 1위", "CEG": "원자력+신재생",
            "VST": "데이터센터 전력 공급", "GEV": "GE 버노바 전력 인프라",
            "SMR": "소형모듈원전(NuScale)",
        },
        "kr_tickers": {
            "373220.KS": "LG에너지솔루션", "247540.KQ": "에코프로비엠",
            "006400.KS": "삼성SDI",
        },
        "etf": "ICLN",
    },

    # 12. 자율주행 — 로보택시 경제학의 현실화
    "12_자율주행": {
        "name": "Autonomous Vehicles",
        "desc": "완전 자율주행이 상용화되면 이동 비용이 현재의 10분의 1로 감소",
        "scenario": "bull",
        "tickers": {
            "TSLA": "FSD·로보택시", "GOOGL": "Waymo(상용 로보택시)",
            "UBER": "자율주행 파트너십", "MOBILEYE": "MBLY",
            "NVDA": "DriveOSPlatform",
        },
        "kr_tickers": {
            "005380.KS": "현대차(자율주행)", "000270.KS": "기아(AV 투자)",
        },
        "etf": "DRIV",
    },

    # 13. 자율 물류 — 라스트마일 자동화
    "13_자율물류": {
        "name": "Autonomous Logistics",
        "desc": "AI 드론·자율트럭·로봇 창고가 물류 단가를 지수적으로 낮춤",
        "scenario": "bull",
        "tickers": {
            "AMZN": "물류 자동화 1위", "TSLA": "Semi 자율트럭",
            "UPS": "드론배송 투자", "GOOGL": "Wing 드론",
            "NVDA": "물류 AI 플랫폼",
        },
        "kr_tickers": {
            "086280.KS": "현대글로비스(자동화)",
        },
        "etf": "ARKQ",
    },
}


# ═══════════════════════════════════════════════════════════════
# Citrini 2028 위기 시나리오 모니터링 지표
# ═══════════════════════════════════════════════════════════════

# 시나리오: S&P 8000까지 상승(AI 낙관) → 2028년 3500 붕괴(실업 디플레이션)
CITRINI_SCENARIO = {
    "report_date": "2026-02-22",
    "author": "Citrini Research (James van Geelen & Alap Shah)",
    "summary": "AI가 화이트칼라 대량 실업 유발 → 소비 붕괴 → 디플레이션 악순환",
    "sp500_peak_target": 8000,
    "sp500_crash_target": 3500,
    "crash_timing": "2028년 6월",
    "unemployment_peak": 10.2,
}

# 위기 수혜주 — 컴퓨트·인프라 소유자 (매수 유지)
CITRINI_WINNERS = {
    "NVDA":  {"reason": "AI 칩 독점 → 실업 증가해도 컴퓨트 수요 지속"},
    "TSM":   {"reason": "파운드리 95%+ 가동율 유지"},
    "AMZN":  {"reason": "AWS가 모든 AI 앱의 세금 수취자"},
    "MSFT":  {"reason": "Azure OpenAI — 기업 AI 전환 인프라"},
    "GOOGL": {"reason": "클라우드+검색 AI — 광고 단가 상승"},
    "CEG":   {"reason": "원자력 전력 — AI 데이터센터 전력 공급"},
    "VST":   {"reason": "데이터센터 전력 독점 공급"},
    "000660.KS": {"reason": "SK하이닉스 HBM — AI칩 필수 부품"},
    "005930.KS": {"reason": "삼성전자 — 대만·한국이 컴퓨트 경제 수혜"},
}

# 위기 피해주 — 화이트칼라 대체 노출 업종 (모니터링·축소 대상)
CITRINI_LOSERS = {
    # 인도 IT 아웃소싱 (AI로 계약 취소)
    "WIT":   {"reason": "Wipro ADR — IT 아웃소싱 AI 대체"},
    "INFY":  {"reason": "Infosys ADR — 계약 취소 가속"},
    "ACN":   {"reason": "Accenture — 컨설팅·IT서비스 AI 잠식"},
    "CTSH":  {"reason": "Cognizant — BPO AI 대체"},
    # 전통 SaaS (AI 네이티브 앱으로 교체 위험)
    "CRM":   {"reason": "Salesforce — AI 네이티브 CRM으로 전환 위험"},
    "ORCL":  {"reason": "Oracle ERP — 레거시 기업 소프트웨어"},
    # 배달·결제 (소비 감소 취약)
    "DASH":  {"reason": "DoorDash — 실업·소비 감소 직격"},
    "AXP":   {"reason": "American Express — 화이트칼라 소비 감소"},
    # 고가 부동산 (AI 허브 고소득 직종 실업)
    "Z":     {"reason": "Zillow — SF·오스틴 주택 붕괴 시나리오"},
}

# 위기 선행 지표 ETF (이 지표들이 악화되면 위기 국면 진입 신호)
CITRINI_CRISIS_INDICATORS = {
    "IGV":   "소프트웨어 ETF (SaaS 멀티플 압축 선행지표)",
    "XHB":   "주택건설 ETF (주택시장 버블 지표)",
    "^VIX":  "공포지수 (50+ = 위기 급박)",
    "^TNX":  "미10년채 수익률 (급락 = 디플레이션 신호)",
    "DXY":   "달러인덱스 (급등 = 위험회피 자금 이동)",
    "XRT":   "소매 ETF (소비 붕괴 조기 지표)",
}


# ═══════════════════════════════════════════════════════════════
# 캐시 I/O
# ═══════════════════════════════════════════════════════════════

def _load_cache() -> dict:
    try:
        if os.path.exists(CACHE_FILE):
            with open(CACHE_FILE, encoding="utf-8") as f:
                d = json.load(f)
            saved = datetime.datetime.fromisoformat(d.get("saved_at", "2000-01-01T00:00:00"))
            if (datetime.datetime.now() - saved).total_seconds() < CACHE_TTL * 3600:
                return d
    except Exception:
        pass
    return {}

def _save_cache(data: dict):
    data["saved_at"] = datetime.datetime.now().isoformat(timespec="seconds")
    with open(CACHE_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


# ═══════════════════════════════════════════════════════════════
# 수익률 계산 유틸
# ═══════════════════════════════════════════════════════════════

def _fetch_returns(ticker: str, periods: list = [1, 5, 20]) -> dict:
    """1일·5일·20일 수익률 계산"""
    try:
        h = yf.Ticker(ticker).history(period="2mo")
        if h.empty or len(h) < 2:
            return {}
        close = h["Close"]
        result = {"price": round(float(close.iloc[-1]), 2)}
        for p in periods:
            if len(close) > p:
                ret = (close.iloc[-1] / close.iloc[-p-1] - 1) * 100
                result[f"ret_{p}d"] = round(float(ret), 2)
        return result
    except Exception:
        return {}


def _fetch_theme_returns(theme_key: str, theme: dict) -> dict:
    """테마 전체 종목 수익률 수집 → 테마 평균 모멘텀 계산"""
    all_tickers = {**theme["tickers"], **theme.get("kr_tickers", {})}
    stock_data = {}
    returns_20d = []

    for tk in all_tickers:
        r = _fetch_returns(tk)
        if r:
            stock_data[tk] = r
            if "ret_20d" in r:
                returns_20d.append(r["ret_20d"])

    avg_20d = round(sum(returns_20d) / len(returns_20d), 2) if returns_20d else None
    etf_r   = _fetch_returns(theme.get("etf", "")) if theme.get("etf") else {}

    return {
        "theme_key":   theme_key,
        "name":        theme["name"],
        "desc":        theme["desc"],
        "scenario":    theme["scenario"],
        "stocks":      stock_data,
        "avg_20d_ret": avg_20d,
        "etf_ticker":  theme.get("etf"),
        "etf_returns": etf_r,
        "momentum":    _classify_momentum(avg_20d),
    }


def _classify_momentum(ret: float) -> str:
    if ret is None:     return "⚪ 데이터없음"
    if ret >=  10:      return "🚀 강한상승"
    if ret >=   3:      return "📈 상승"
    if ret >=  -3:      return "➡️ 횡보"
    if ret >=  -10:     return "📉 하락"
    return "💥 급락"


# ═══════════════════════════════════════════════════════════════
# Citrini 위기 지표 수집
# ═══════════════════════════════════════════════════════════════

def fetch_citrini_indicators() -> dict:
    """위기 선행 지표 + 수혜주·피해주 현황"""
    result = {
        "scenario": CITRINI_SCENARIO,
        "crisis_indicators": {},
        "winners": {},
        "losers": {},
        "crisis_signal": "",
    }

    # 위기 선행 지표
    for tk, label in CITRINI_CRISIS_INDICATORS.items():
        r = _fetch_returns(tk, [1, 5, 20])
        if r:
            result["crisis_indicators"][tk] = {**r, "label": label}

    # 수혜주
    for tk, info in CITRINI_WINNERS.items():
        r = _fetch_returns(tk, [1, 5, 20])
        if r:
            result["winners"][tk] = {**r, **info}

    # 피해주
    for tk, info in CITRINI_LOSERS.items():
        r = _fetch_returns(tk, [1, 5, 20])
        if r:
            result["losers"][tk] = {**r, **info}

    # 위기 국면 진단
    result["crisis_signal"] = _diagnose_crisis_phase(result)
    return result


def _diagnose_crisis_phase(indicators: dict) -> str:
    """
    현재 시장이 Citrini 시나리오의 어느 단계에 있는지 진단
    Phase A: AI 낙관 랠리 (S&P → 8000)
    Phase B: 균열 시작 (SaaS 멀티플 압축, IT서비스 계약 취소)
    Phase C: 위기 본격화 (실업급증, 소비붕괴)
    """
    ci = indicators.get("crisis_indicators", {})
    w  = indicators.get("winners", {})
    l  = indicators.get("losers", {})

    # IGV(SaaS ETF) 20일 수익률
    igv_20d = ci.get("IGV", {}).get("ret_20d", 0) or 0
    # VIX 수준
    vix = ci.get("^VIX", {}).get("price", 18)
    # 피해주 평균 성과
    loser_rets = [v.get("ret_20d", 0) for v in l.values() if v.get("ret_20d") is not None]
    avg_loser  = sum(loser_rets) / len(loser_rets) if loser_rets else 0
    # 수혜주 평균 성과
    winner_rets = [v.get("ret_20d", 0) for v in w.values() if v.get("ret_20d") is not None]
    avg_winner  = sum(winner_rets) / len(winner_rets) if winner_rets else 0

    if vix and vix > 35:
        return "🔴 Phase C: 위기 본격화 신호 (VIX 35+ / 즉각 방어 필요)"
    elif igv_20d < -15 and avg_loser < -10:
        return "🟠 Phase B: 균열 시작 (SaaS 급락·IT서비스 이탈 / 포지션 축소 검토)"
    elif avg_winner > avg_loser + 10:
        return "🟡 Phase A+: AI 낙관 랠리 지속 (수혜주 강세 / 피해주 분리 심화)"
    elif igv_20d > 5 and avg_winner > 0:
        return "🟢 Phase A: AI 낙관 랠리 (모든 섹터 상승 / 위기 신호 없음)"
    else:
        return "⚪ 전환기: 방향성 불명확 (관찰 지속)"


# ═══════════════════════════════════════════════════════════════
# 전체 수집 — 병렬 처리
# ═══════════════════════════════════════════════════════════════

def collect_ark_convergence() -> dict:
    """ARK 13대 테마 + Citrini 위기 지표 전체 수집"""
    cache = _load_cache()
    if cache:
        print("  ✓ ARK 수렴 데이터 캐시 사용")
        return cache

    print("  ARK Big Ideas 2026 × Citrini 2028 데이터 수집 중...")
    result = {
        "report_date": datetime.datetime.now().strftime("%Y-%m-%d %H:%M"),
        "ark_themes": {},
        "citrini": {},
    }

    # ARK 13개 테마 병렬 수집
    with ThreadPoolExecutor(max_workers=6) as ex:
        futs = {
            ex.submit(_fetch_theme_returns, k, v): k
            for k, v in ARK_THEMES.items()
        }
        for fut in as_completed(futs):
            key = futs[fut]
            try:
                result["ark_themes"][key] = fut.result()
                print(f"    ✓ {ARK_THEMES[key]['name'][:30]}...")
            except Exception as e:
                print(f"    ✗ {key}: {e}")

    # Citrini 위기 지표 수집
    print("  Citrini 위기 지표 수집 중...")
    result["citrini"] = fetch_citrini_indicators()

    _save_cache(result)
    return result


# ═══════════════════════════════════════════════════════════════
# 관찰보고서 텍스트 생성
# ═══════════════════════════════════════════════════════════════

def build_observation_report(data: dict) -> str:
    """stock_advisor_v4.py에 첨부될 관찰보고서 섹션"""
    lines = []
    now   = data.get("report_date", "")

    lines.append("\n" + "═" * 80)
    lines.append("  📡 ARK Big Ideas 2026 × Citrini 2028 — 테마 관찰보고서")
    lines.append(f"  기준: {now}")
    lines.append("═" * 80)

    # ── 1. ARK 대가속 테마 요약 ────────────────────────────────
    lines.append("\n【ARK Big Ideas 2026 — 13대 테마 모멘텀】")
    lines.append("  테마가 서로를 가속할 때: GDP 7.3% 목표 달성 가능")
    lines.append("  테마가 분리·약화될 때 : Citrini 위기 시나리오 현실화 위험")
    lines.append("")
    lines.append(f"  {'#':<3} {'테마명':<28} {'20일수익률':>10} {'모멘텀':<16} {'대표ETF':>8}")
    lines.append("  " + "-" * 74)

    themes = data.get("ark_themes", {})
    sorted_themes = sorted(
        themes.items(),
        key=lambda x: x[1].get("avg_20d_ret") or -999,
        reverse=True
    )
    for key, th in sorted_themes:
        num    = key.split("_")[0]
        name   = th["name"][:26]
        avg    = th.get("avg_20d_ret")
        avg_s  = f"{avg:+.1f}%" if avg is not None else "  N/A"
        mom    = th.get("momentum", "")
        etf    = th.get("etf_ticker", "")
        lines.append(f"  {num:<3} {name:<28} {avg_s:>10} {mom:<16} {etf:>8}")

    # ── 2. 테마별 핵심 종목 상세 ────────────────────────────────
    lines.append("\n\n【테마별 핵심 종목 성과 (20일 기준)】")
    priority_themes = ["1_대가속", "2_AI인프라", "10_로보틱스", "8_멀티오믹스", "11_분산에너지"]

    for key in priority_themes:
        th = themes.get(key)
        if not th:
            continue
        lines.append(f"\n  ▶ {th['name']}")
        lines.append(f"    {th['desc']}")
        lines.append(f"    모멘텀: {th.get('momentum','')}")
        lines.append("")

        stocks = th.get("stocks", {})
        all_names = {**ARK_THEMES[key]["tickers"], **ARK_THEMES[key].get("kr_tickers", {})}

        sorted_stocks = sorted(
            [(tk, stocks[tk]) for tk in stocks if "ret_20d" in stocks[tk]],
            key=lambda x: x[1]["ret_20d"],
            reverse=True
        )
        for tk, r in sorted_stocks[:6]:
            note = all_names.get(tk, "")
            ret1 = r.get("ret_1d", 0)
            ret5 = r.get("ret_5d", 0)
            ret20 = r.get("ret_20d", 0)
            lines.append(
                f"    {tk:<12} {note:<22} "
                f"1일:{ret1:+.1f}%  5일:{ret5:+.1f}%  20일:{ret20:+.1f}%"
            )

    # ── 3. Citrini 2028 위기 시나리오 모니터링 ─────────────────
    citrini = data.get("citrini", {})
    lines.append("\n\n" + "─" * 80)
    lines.append("【Citrini Research — 2028 Global Intelligence Crisis 모니터링】")
    sc = citrini.get("scenario", {})
    lines.append(f"  보고서: {sc.get('report_date','')} | 저자: {sc.get('author','')}")
    lines.append(f"  시나리오: {sc.get('summary','')}")
    lines.append(f"  경로: S&P {sc.get('sp500_peak_target','')} 상승 → {sc.get('crash_timing','')} {sc.get('sp500_crash_target','')} 붕괴")
    lines.append(f"  실업률 최고점 전망: {sc.get('unemployment_peak','')}%")
    lines.append("")
    lines.append(f"  ◆ 현재 국면 진단: {citrini.get('crisis_signal','')}")

    # 위기 선행 지표
    lines.append("\n  [위기 선행 지표]")
    lines.append(f"  {'티커':<8} {'현재가':>10} {'1일':>7} {'5일':>7} {'20일':>7}  설명")
    lines.append("  " + "-" * 72)
    for tk, v in citrini.get("crisis_indicators", {}).items():
        r1  = v.get("ret_1d", 0)
        r5  = v.get("ret_5d", 0)
        r20 = v.get("ret_20d", 0)
        prc = v.get("price", 0)
        lbl = v.get("label", "")[:30]
        lines.append(
            f"  {tk:<8} {prc:>10.2f} {r1:>+6.1f}% {r5:>+6.1f}% {r20:>+6.1f}%  {lbl}"
        )

    # 수혜주
    lines.append("\n  [Citrini 수혜주 — 컴퓨트 소유자 (매수 유지)]")
    for tk, v in citrini.get("winners", {}).items():
        r1  = v.get("ret_1d", 0)
        r20 = v.get("ret_20d", 0)
        rsn = v.get("reason", "")[:40]
        lines.append(f"    ✅ {tk:<10} 1일:{r1:>+5.1f}%  20일:{r20:>+6.1f}%  {rsn}")

    # 피해주
    lines.append("\n  [Citrini 피해주 — 화이트칼라 대체 노출 (모니터링·축소 검토)]")
    for tk, v in citrini.get("losers", {}).items():
        r1  = v.get("ret_1d", 0)
        r20 = v.get("ret_20d", 0)
        rsn = v.get("reason", "")[:40]
        lines.append(f"    ⚠️  {tk:<10} 1일:{r1:>+5.1f}%  20일:{r20:>+6.1f}%  {rsn}")

    # ── 4. 두 시나리오 종합 판단 ────────────────────────────────
    lines.append("\n\n" + "─" * 80)
    lines.append("【ARK vs Citrini — 시나리오 판단 매트릭스】")
    lines.append("")
    lines.append("  조건                                ARK 낙관     Citrini 위기")
    lines.append("  ─────────────────────────────────   ─────────    ────────────")
    lines.append("  AI인프라 테마 강세(+10%+ 20일)      🟢 확인       🟡 Phase A")
    lines.append("  SaaS(IGV) 급락(-15% 이상)           🔴 경보       🟠 Phase B")
    lines.append("  VIX > 35                            🔴 위험       🔴 Phase C")
    lines.append("  수혜주 vs 피해주 성과 격차 확대      🟢 정상       🟡 분리 시작")
    lines.append("")

    # 현재 시나리오 위치 자동 판단
    igv_data  = citrini.get("crisis_indicators", {}).get("IGV", {})
    igv_20d   = igv_data.get("ret_20d", 0) or 0
    vix_data  = citrini.get("crisis_indicators", {}).get("^VIX", {})
    vix_level = vix_data.get("price", 18) or 18

    ai_theme = themes.get("2_AI인프라", {})
    ai_20d   = ai_theme.get("avg_20d_ret", 0) or 0

    lines.append(f"  현재 AI인프라 테마 20일: {ai_20d:+.1f}%")
    lines.append(f"  현재 SaaS(IGV) 20일: {igv_20d:+.1f}%")
    lines.append(f"  현재 VIX: {vix_level:.1f}")
    lines.append("")

    if vix_level > 35:
        verdict = "🔴 Citrini Phase C 진입 — 즉각 포트폴리오 방어 검토"
    elif igv_20d < -15:
        verdict = "🟠 Citrini Phase B — SaaS 멀티플 압축 진행 / 피해주 축소 권고"
    elif ai_20d > 10 and igv_20d > -5:
        verdict = "🟢 ARK 대가속 시나리오 — AI인프라 강세 유지 / 수혜주 유지"
    elif ai_20d > 0:
        verdict = "🟡 Phase A 중반 — 방향성 관찰 중 / 수혜주 비중 유지"
    else:
        verdict = "⚪ 전환기 불확실 — 리스크 관리 강화 / 분할 접근 권고"

    lines.append(f"  ▶▶ 종합 판단: {verdict}")

    lines.append("\n" + "═" * 80)
    lines.append("  ⚠️ ARK/Citrini 보고서는 투자 참고용 시나리오입니다.")
    lines.append("     ARK: ark-invest.com/big-ideas-2026 | Citrini: citriniresearch.com")
    lines.append("═" * 80 + "\n")

    return "\n".join(lines)


# ═══════════════════════════════════════════════════════════════
# Claude 프롬프트용 압축 요약
# ═══════════════════════════════════════════════════════════════

def build_claude_context(data: dict) -> str:
    """Claude 분석 프롬프트에 삽입할 ARK/Citrini 핵심 컨텍스트"""
    themes  = data.get("ark_themes", {})
    citrini = data.get("citrini", {})

    # 상위 3개 / 하위 3개 테마
    sorted_th = sorted(
        [(k, v) for k, v in themes.items() if v.get("avg_20d_ret") is not None],
        key=lambda x: x[1]["avg_20d_ret"],
        reverse=True
    )
    top3    = sorted_th[:3]
    bottom3 = sorted_th[-3:]

    lines = ["■ ARK Big Ideas 2026 × Citrini 2028 컨텍스트"]
    lines.append(f"  위기국면: {citrini.get('crisis_signal','')}")
    lines.append("  [ARK 강세테마 TOP3]")
    for k, v in top3:
        avg = v.get("avg_20d_ret", 0)
        lines.append(f"    {v['name'][:25]}: {avg:+.1f}% ({v.get('momentum','')})")
    lines.append("  [ARK 약세테마 BOT3]")
    for k, v in bottom3:
        avg = v.get("avg_20d_ret", 0)
        lines.append(f"    {v['name'][:25]}: {avg:+.1f}% ({v.get('momentum','')})")

    # Citrini 수혜/피해 비교
    w_avg = 0
    l_avg = 0
    w_rets = [v.get("ret_20d", 0) for v in citrini.get("winners", {}).values() if v.get("ret_20d")]
    l_rets = [v.get("ret_20d", 0) for v in citrini.get("losers", {}).values() if v.get("ret_20d")]
    if w_rets: w_avg = sum(w_rets) / len(w_rets)
    if l_rets: l_avg = sum(l_rets) / len(l_rets)

    lines.append(f"  [Citrini] 수혜주 평균20일:{w_avg:+.1f}% vs 피해주:{l_avg:+.1f}%")
    lines.append("  → 격차가 클수록 시나리오 분리 심화")
    return "\n".join(lines)


# ═══════════════════════════════════════════════════════════════
# 독립 실행
# ═══════════════════════════════════════════════════════════════

if __name__ == "__main__":
    print("\n🔍 ARK Big Ideas 2026 × Citrini 2028 모니터링 시작...\n")
    data = collect_ark_convergence()

    report = build_observation_report(data)
    print(report)

    # 파일 저장
    out_path = os.path.join(BASE_DIR, "ark_convergence_report.txt")
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(report)
    print(f"\n💾 저장 완료: {out_path}")
