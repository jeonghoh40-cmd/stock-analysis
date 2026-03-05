"""
Citrini 2028 글로벌 지능위기 — 부정적 종목 관리 모듈
────────────────────────────────────────────────────────────────
데이터 출처:
  - Citrini Research "2028 Global Intelligence Crisis" (2026-02-22 발표)
  - 보고서: Ark/Citrini_2028_Crisis.pdf (입수시)

목적:
  - AI 로 인한 대량실업 위기에 노출된 기업들 추적
  - 위기 피해주 (Losers) DB 저장 및 모니터링
  - 주기적 위험 경고 보고서 생성

시나리오 개요:
  - AI 가 화이트칼라 대량 실업 유발
  - 소비 붕괴 → 디플레이션 악순환
  - S&P 8000 → 3500 붕괴 (2028 년 6 월)
  - 실업률 최고 10.2%
"""

import os
import sys
import json
import datetime
from typing import Optional, Dict, List

import yfinance as yf
import pandas as pd

if sys.stdout.encoding != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

BASE_DIR = os.path.dirname(os.path.abspath(__file__))


# ═══════════════════════════════════════════════════════════════
# Citrini 2028 위기 시나리오 — 부정적 종목
# ═══════════════════════════════════════════════════════════════
# 데이터 출처: Citrini Research "2028 Global Intelligence Crisis"
# 발표일: 2026-02-22
# 저자: James van Geelen & Alap Shah
# ═══════════════════════════════════════════════════════════════

CITRINI_SCENARIO = {
    "report_date": "2026-02-22",
    "author": "Citrini Research (James van Geelen & Alap Shah)",
    "summary": "AI 가 화이트칼라 대량 실업 유발 → 소비 붕괴 → 디플레이션 악순환",
    "sp500_peak_target": 8000,
    "sp500_crash_target": 3500,
    "crash_timing": "2028 년 6 월",
    "unemployment_peak": 10.2,
}

# 위기 피해주 — 화이트칼라 대체 노출 업종 (모니터링·축소 대상)
CITRINI_LOSERS = {
    # ── 인도 IT 아웃소싱 (AI 로 계약 취소) ────────────────────────
    "WIT": {
        "name": "Wipro",
        "market": "US",
        "sector": "IT 아웃소싱",
        "reason": "Wipro ADR — IT 아웃소싱 AI 대체",
        "risk_level": "HIGH",
        "exposure": "인도 IT 서비스, BPO 계약",
    },
    "INFY": {
        "name": "Infosys",
        "market": "US",
        "sector": "IT 아웃소싱",
        "reason": "Infosys ADR — 계약 취소 가속",
        "risk_level": "HIGH",
        "exposure": "인도 IT 서비스, 시스템 통합",
    },
    "ACN": {
        "name": "Accenture",
        "market": "US",
        "sector": "IT 아웃소싱",
        "reason": "Accenture — 컨설팅·IT 서비스 AI 잠식",
        "risk_level": "HIGH",
        "exposure": "경영컨설팅, IT 아웃소싱",
    },
    "CTSH": {
        "name": "Cognizant",
        "market": "US",
        "sector": "IT 아웃소싱",
        "reason": "Cognizant — BPO AI 대체",
        "risk_level": "HIGH",
        "exposure": "비즈니스 프로세스 아웃소싱",
    },
    "TCS.NS": {
        "name": "Tata Consultancy Services",
        "market": "India",
        "sector": "IT 아웃소싱",
        "reason": "인도 최대 IT 서비스 — AI 자동화 직격",
        "risk_level": "HIGH",
        "exposure": "IT 서비스, 컨설팅",
    },
    "HCLTECH.NS": {
        "name": "HCL Technologies",
        "market": "India",
        "sector": "IT 아웃소싱",
        "reason": "인도 IT 서비스 — AI 대체 위험",
        "risk_level": "HIGH",
        "exposure": "IT 서비스, 엔지니어링",
    },

    # ── 전통 SaaS (AI 네이티브 앱으로 교체 위험) ─────────────────
    "CRM": {
        "name": "Salesforce",
        "market": "US",
        "sector": "전통 SaaS",
        "reason": "Salesforce — AI 네이티브 CRM 으로 전환 위험",
        "risk_level": "MEDIUM",
        "exposure": "CRM 소프트웨어",
    },
    "ORCL": {
        "name": "Oracle",
        "market": "US",
        "sector": "전통 SaaS",
        "reason": "Oracle ERP — 레거시 기업 소프트웨어",
        "risk_level": "MEDIUM",
        "exposure": "ERP, 데이터베이스",
    },
    "SAP": {
        "name": "SAP",
        "market": "US",
        "sector": "전통 SaaS",
        "reason": "SAP ERP — 레거시 시스템 대체 위험",
        "risk_level": "MEDIUM",
        "exposure": "ERP, 기업 소프트웨어",
    },
    "ADBE": {
        "name": "Adobe",
        "market": "US",
        "sector": "전통 SaaS",
        "reason": "Adobe — 생성형 AI 에 의한 크리에이티브 자동화",
        "risk_level": "MEDIUM",
        "exposure": "크리에이티브 소프트웨어",
    },
    "NOW": {
        "name": "ServiceNow",
        "market": "US",
        "sector": "전통 SaaS",
        "reason": "ServiceNow — AI 워크플로우 자동화",
        "risk_level": "MEDIUM",
        "exposure": "워크플로우 관리",
    },
    "WDAY": {
        "name": "Workday",
        "market": "US",
        "sector": "전통 SaaS",
        "reason": "Workday — HR AI 자동화",
        "risk_level": "MEDIUM",
        "exposure": "HR 소프트웨어",
    },

    # ── 배달·결제 (소비 감소 취약) ─────────────────────────────
    "DASH": {
        "name": "DoorDash",
        "market": "US",
        "sector": "배달·결제",
        "reason": "DoorDash — 실업·소비 감소 직격",
        "risk_level": "HIGH",
        "exposure": "음식 배달, 소비자 지출",
    },
    "AXP": {
        "name": "American Express",
        "market": "US",
        "sector": "배달·결제",
        "reason": "American Express — 화이트칼라 소비 감소",
        "risk_level": "MEDIUM",
        "exposure": "신용카드, 프리미엄 소비자",
    },
    "PYPL": {
        "name": "PayPal",
        "market": "US",
        "sector": "배달·결제",
        "reason": "PayPal — 소비 감소·경쟁 심화",
        "risk_level": "MEDIUM",
        "exposure": "디지털 결제",
    },
    "SQ": {
        "name": "Block (Square)",
        "market": "US",
        "sector": "배달·결제",
        "reason": "Block — 중소기업 결제 감소",
        "risk_level": "MEDIUM",
        "exposure": "결제 처리, 소상공인",
    },
    "UBER": {
        "name": "Uber",
        "market": "US",
        "sector": "배달·결제",
        "reason": "Uber — 소비 위축·자율주행 위협",
        "risk_level": "MEDIUM",
        "exposure": "라이드셰어링, 배달",
    },

    # ── 고가 부동산 (AI 허브 고소득 직종 실업) ──────────────────
    "Z": {
        "name": "Zillow",
        "market": "US",
        "sector": "부동산",
        "reason": "Zillow — SF·오스틴 주택 붕괴 시나리오",
        "risk_level": "HIGH",
        "exposure": "주택 중개, 기술 허브",
    },
    "RDFN": {
        "name": "Redfin",
        "market": "US",
        "sector": "부동산",
        "reason": "Redfin — 고가 주택시장 위축",
        "risk_level": "HIGH",
        "exposure": "주택 중개",
    },
    "OPEN": {
        "name": "Opendoor",
        "market": "US",
        "sector": "부동산",
        "reason": "Opendoor — iBuying 모델 위험",
        "risk_level": "HIGH",
        "exposure": "주택 매매",
    },

    # ── 화이트칼라 고용 의존 업종 ──────────────────────────────
    "IBM": {
        "name": "IBM",
        "market": "US",
        "sector": "IT 서비스",
        "reason": "IBM — 레거시 IT 서비스 AI 대체",
        "risk_level": "MEDIUM",
        "exposure": "IT 컨설팅, 클라우드",
    },
    "HPQ": {
        "name": "HP Inc",
        "market": "US",
        "sector": "하드웨어",
        "reason": "HP — PC 수요 감소 (재택근무 종료)",
        "risk_level": "LOW",
        "exposure": "PC, 프린터",
    },
    "DELL": {
        "name": "Dell Technologies",
        "market": "US",
        "sector": "하드웨어",
        "reason": "Dell — 엔터프라이즈 PC 수요 감소",
        "risk_level": "LOW",
        "exposure": "PC, 서버",
    },

    # ── 한국 시장 — 화이트칼라 대체 위험 ───────────────────────
    "035420.KS": {
        "name": "NAVER",
        "market": "KOSPI",
        "sector": "플랫폼",
        "reason": "NAVER — AI 검색·광고 수익 감소",
        "risk_level": "MEDIUM",
        "exposure": "검색, 광고, 클라우드",
    },
    "035720.KS": {
        "name": "카카오",
        "market": "KOSPI",
        "sector": "플랫폼",
        "reason": "카카오 — AI 비서 대체·모빌리티 위협",
        "risk_level": "MEDIUM",
        "exposure": "메신저, 모빌리티, 금융",
    },
    "035900.KS": {
        "name": "JYP Ent",
        "market": "KOSPI",
        "sector": "엔터테인먼트",
        "reason": "엔터 — AI 생성 콘텐츠 위협",
        "risk_level": "LOW",
        "exposure": "음악, 연예기획",
    },
}

# 위기 수혜주 (참고용)
CITRINI_WINNERS = {
    "NVDA": {"reason": "AI 칩 독점 → 실업 증가해도 컴퓨트 수요 지속"},
    "TSM": {"reason": "파운드리 95%+ 가동율 유지"},
    "AMZN": {"reason": "AWS 가 모든 AI 앱의 세금 수취자"},
    "MSFT": {"reason": "Azure OpenAI — 기업 AI 전환 인프라"},
    "GOOGL": {"reason": "클라우드 + 검색 AI — 광고 단가 상승"},
    "CEG": {"reason": "원자력 전력 — AI 데이터센터 전력 공급"},
    "VST": {"reason": "데이터센터 전력 독점 공급"},
    "000660.KS": {"reason": "SK 하이닉스 HBM — AI 칩 필수 부품"},
    "005930.KS": {"reason": "삼성전자 — 대만·한국이 컴퓨트 경제 수혜"},
}

# 위기 선행 지표
CITRINI_CRISIS_INDICATORS = {
    "IGV": "소프트웨어 ETF (SaaS 멀티플 압축 선행지표)",
    "XHB": "주택건설 ETF (주택시장 버블 지표)",
    "^VIX": "공포지수 (50+ = 위기 급박)",
    "^TNX": "미 10 년채 수익률 (급락 = 디플레이션 신호)",
    "DXY": "달러인덱스 (급등 = 위험회피 자금 이동)",
    "XRT": "소매 ETF (소비 붕괴 조기 지표)",
    "XLY": "소비재 ETF (선택적 소비 지표)",
    "KRE": "지역은행 ETF (부동산 대출 위험)",
}


# ═══════════════════════════════════════════════════════════════
# 유틸리티 함수
# ═══════════════════════════════════════════════════════════════

def get_unique_losers() -> Dict:
    """
    모든 부정적 종목의 중복 없는 목록을 반환한다.
    """
    return CITRINI_LOSERS.copy()


def get_losers_by_risk_level(risk_level: str = "HIGH") -> Dict:
    """
    위험등급별 부정적 종목을 반환한다.
    """
    return {k: v for k, v in CITRINI_LOSERS.items() 
            if v.get("risk_level") == risk_level}


def get_losers_by_sector(sector: str) -> Dict:
    """
    섹터별 부정적 종목을 반환한다.
    """
    return {k: v for k, v in CITRINI_LOSERS.items() 
            if v.get("sector") == sector}


# ═══════════════════════════════════════════════════════════════
# 데이터 수집
# ═══════════════════════════════════════════════════════════════

def fetch_ticker_data(ticker: str) -> dict:
    """
    단일 티커의 현재가 및 모멘텀 데이터를 수집한다.
    """
    try:
        t = yf.Ticker(ticker)
        h = t.history(period="60d")
        if h.empty:
            return {}

        close = h["Close"]
        current = close.iloc[-1]
        prev = close.iloc[-2] if len(close) > 1 else current

        # 모멘텀
        ret_1d = (current - prev) / prev * 100 if prev > 0 else 0
        ret_5d = (close.iloc[-1] / close.iloc[-6] - 1) * 100 if len(close) > 5 else 0
        ret_20d = (close.iloc[-1] / close.iloc[-21] - 1) * 100 if len(close) > 20 else 0

        # 기술적 지표
        ma5 = close.rolling(5).mean().iloc[-1]
        ma20 = close.rolling(20).mean().iloc[-1] if len(close) >= 20 else current
        ma60 = close.rolling(60).mean().iloc[-1] if len(close) >= 60 else current

        # RSI
        delta = close.diff()
        gain = delta.clip(lower=0).rolling(14).mean()
        loss = (-delta.clip(upper=0)).rolling(14).mean()
        rsi = 100 - 100 / (1 + gain.iloc[-1] / (loss.iloc[-1] + 1e-9))

        # 정보
        info = t.info
        market_cap = info.get("marketCap", 0)
        pe = info.get("trailingPE")
        pb = info.get("priceToBook")

        return {
            "ticker": ticker,
            "price": round(float(current), 2),
            "change_1d": round(float(ret_1d), 2),
            "change_5d": round(float(ret_5d), 2),
            "change_20d": round(float(ret_20d), 2),
            "ma5": round(float(ma5), 2),
            "ma20": round(float(ma20), 2),
            "ma60": round(float(ma60), 2),
            "rsi": round(float(rsi), 1),
            "market_cap": market_cap,
            "pe": round(float(pe), 1) if pe else None,
            "pb": round(float(pb), 2) if pb else None,
            "collected_at": datetime.datetime.now().isoformat(),
        }
    except Exception as e:
        print(f"  [오류] {ticker}: {e}")
        return {}


def collect_all_losers_data() -> list:
    """
    모든 부정적 종목의 데이터를 수집한다.
    """
    losers = get_unique_losers()
    results = []

    print(f"\n⚠️ Citrini 2028 부정적 종목 데이터 수집 시작 ({len(losers)}개 종목)...")

    for ticker, info in losers.items():
        print(f"  수집 중: {info['name']}({ticker})...", end=" ")
        data = fetch_ticker_data(ticker)
        if data:
            data["name"] = info["name"]
            data["market"] = info["market"]
            data["sector"] = info["sector"]
            data["reason"] = info["reason"]
            data["risk_level"] = info["risk_level"]
            data["exposure"] = info.get("exposure", "")
            results.append(data)
            print(f"완료 (현재가: {data['price']:,.0f}, 20 일: {data['change_20d']:+.1f}%)")
        else:
            print("실패")

    return results


# ═══════════════════════════════════════════════════════════════
# 위험 분석
# ═══════════════════════════════════════════════════════════════

def analyze_risk_portfolio(data: list) -> dict:
    """
    부정적 종목 포트폴리오 위험도를 분석한다.
    """
    if not data:
        return {}

    # 위험등급별 분류
    by_risk = {"HIGH": [], "MEDIUM": [], "LOW": []}
    for d in data:
        risk = d.get("risk_level", "MEDIUM")
        if risk in by_risk:
            by_risk[risk].append(d)

    # 섹터별 분류
    by_sector = {}
    for d in data:
        sector = d.get("sector", "Unknown")
        if sector not in by_sector:
            by_sector[sector] = []
        by_sector[sector].append(d)

    # 성과 분석
    all_rets = [d.get("change_20d", 0) for d in data if d.get("change_20d") is not None]
    
    analysis = {
        "total_count": len(data),
        "by_risk_level": {k: len(v) for k, v in by_risk.items()},
        "by_sector": {k: len(v) for k, v in by_sector.items()},
        "avg_20d_return": round(sum(all_rets) / len(all_rets), 2) if all_rets else 0,
        "worst_performers": sorted(data, key=lambda x: x.get("change_20d", 0))[:5],
        "best_performers": sorted(data, key=lambda x: x.get("change_20d", 0), reverse=True)[:5],
    }

    return analysis


# ═══════════════════════════════════════════════════════════════
# 보고서 생성
# ═══════════════════════════════════════════════════════════════

def build_citrini_warning_report(data: list) -> str:
    """
    Citrini 2028 위기 경고 보고서를 생성한다.
    """
    lines = []
    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")

    lines.append("\n" + "═" * 90)
    lines.append("  ⚠️ Citrini 2028 글로벌 지능위기 — 부정적 종목 경고보고서")
    lines.append(f"  기준: {now}")
    lines.append("═" * 90)

    # 시나리오 개요
    lines.append("\n【Citrini 2028 위기 시나리오 개요】")
    lines.append(f"  • 보고서: {CITRINI_SCENARIO['report_date']} | {CITRINI_SCENARIO['author']}")
    lines.append(f"  • 시나리오: {CITRINI_SCENARIO['summary']}")
    lines.append(f"  • S&P 500: {CITRINI_SCENARIO['sp500_peak_target']} → {CITRINI_SCENARIO['sp500_crash_target']} ({CITRINI_SCENARIO['crash_timing']})")
    lines.append(f"  • 실업률 최고: {CITRINI_SCENARIO['unemployment_peak']}%")

    # 위험등급별 종목수
    lines.append("\n【부정적 종목 현황】")
    lines.append(f"  • 총 종목수: {len(data)}개")
    
    risk_counts = {"HIGH": 0, "MEDIUM": 0, "LOW": 0}
    for d in data:
        risk = d.get("risk_level", "MEDIUM")
        if risk in risk_counts:
            risk_counts[risk] += 1

    lines.append(f"  • 위험등급별: HIGH {risk_counts['HIGH']}개 | MEDIUM {risk_counts['MEDIUM']}개 | LOW {risk_counts['LOW']}개")

    # 섹터별 분류
    sector_counts = {}
    for d in data:
        sector = d.get("sector", "Unknown")
        sector_counts[sector] = sector_counts.get(sector, 0) + 1

    lines.append("\n  【섹터별 분포】")
    for sector, count in sorted(sector_counts.items(), key=lambda x: x[1], reverse=True):
        lines.append(f"    • {sector}: {count}개")

    # 시장별 분류
    lines.append("\n【시장별 부정적 종목】")
    by_market = {"US": [], "KOSPI": [], "KOSDAQ": [], "India": [], "Other": []}
    for d in data:
        market = d.get("market", "Other")
        if market in by_market:
            by_market[market].append(d)
        else:
            by_market["Other"].append(d)

    for market, items in by_market.items():
        if items:
            lines.append(f"\n  [{market} — {len(items)}개 종목]")
            lines.append(f"  {'종목명':<25} {'티커':<12} {'위험':<8} {'20 일':>8} {'RSI':>6} {'이유':<40}")
            lines.append("  " + "-" * 100)

            sorted_items = sorted(items, key=lambda x: x.get("change_20d", 0))
            for item in sorted_items[:10]:  # 상위 10 개만
                name = item.get("name", "")[:23]
                ticker = item.get("ticker", "")
                risk = item.get("risk_level", "")
                ret20 = f"{item.get('change_20d', 0):>+7.1f}%"
                rsi = f"{item.get('rsi', 0):>5.1f}"
                reason = item.get("reason", "")[:38]

                # 위험등급 아이콘
                risk_icon = "🔴" if risk == "HIGH" else ("🟡" if risk == "MEDIUM" else "⚪")

                lines.append(f"  {risk_icon} {name:<23} {ticker:<12} {risk:<8} {ret20:>8} {rsi:>6} {reason:<38}")

    # 최악의 성과 종목
    lines.append("\n\n【최악의 성과 종목 (20 일 기준)】")
    worst = sorted(data, key=lambda x: x.get("change_20d", 0))[:10]
    lines.append(f"  {'순위':>4} {'종목명':<25} {'티커':<12} {'20 일':>8} {'RSI':>6} {'위험':<8} {'섹터':<20}")
    lines.append("  " + "-" * 85)
    for i, item in enumerate(worst, 1):
        name = item.get("name", "")[:23]
        ticker = item.get("ticker", "")
        ret20 = f"{item.get('change_20d', 0):>+7.1f}%"
        rsi = f"{item.get('rsi', 0):>5.1f}"
        risk = item.get("risk_level", "")
        sector = item.get("sector", "")[:18]
        lines.append(f"  {i:>4} {name:<25} {ticker:<12} {ret20:>8} {rsi:>6} {risk:<8} {sector:<20}")

    # 위험 분석
    lines.append("\n\n【종합 위험 분석】")
    analysis = analyze_risk_portfolio(data)
    if analysis:
        lines.append(f"  • 평균 20 일 수익률: {analysis.get('avg_20d_return', 0):+.1f}%")
        lines.append(f"  • HIGH 위험 종목: {analysis['by_risk_level'].get('HIGH', 0)}개")
        lines.append(f"  • MEDIUM 위험 종목: {analysis['by_risk_level'].get('MEDIUM', 0)}개")
        lines.append(f"  • LOW 위험 종목: {analysis['by_risk_level'].get('LOW', 0)}개")

    # 투자 권고
    lines.append("\n\n【투자 권고】")
    avg_ret = analysis.get('avg_20d_return', 0) if analysis else 0

    if avg_ret < -20:
        verdict = "🔴 심각 — 부정적 종목 대폭락, Citrini 시나리오 현실화 가속"
        action = "• 모든 부정적 종목 즉시 축소\n• 현금 비중 대폭 확대\n• AI 수혜주로 이동"
    elif avg_ret < -10:
        verdict = "🟠 위험 — 부정적 종목 약세, 위기 신호 감지"
        action = "• HIGH 위험 종목 매도\n• MEDIUM 위험 종목 모니터링\n• 방어적 포지셔닝"
    elif avg_ret < 0:
        verdict = "🟡 주의 — 부정적 종목 보합세, 관찰 필요"
        action = "• 포트폴리오 리밸런싱\n• 섹터별 위험도 재평가\n• 점진적 축소"
    else:
        verdict = "⚪ 관망 — 부정적 종목도 상승, 단기적 무풍지대"
        action = "• 장기적 위험 인식 유지\n• 분할 매도 고려\n• 헤지 전략 검토"

    lines.append(f"  ▶ 종합 판단: {verdict}")
    lines.append(f"\n  [권고사항]\n  {action}")

    # 위기 선행 지표
    lines.append("\n\n【위기 선행 지표 모니터링】")
    lines.append(f"  {'지표':<10} {'설명':<50}")
    lines.append("  " + "-" * 65)
    for ticker, label in CITRINI_CRISIS_INDICATORS.items():
        lines.append(f"  {ticker:<10} {label:<50}")

    lines.append("\n" + "═" * 90)
    lines.append("  ⚠️ Citrini 2028 보고서는 시나리오 기반 경고입니다.")
    lines.append("     실제 위기 발생 여부는 다르며, 투자 참고용으로만 활용하세요.")
    lines.append("  📚 출처: Citrini Research '2028 Global Intelligence Crisis'")
    lines.append("═" * 90 + "\n")

    return "\n".join(lines)


# ═══════════════════════════════════════════════════════════════
# 저장 함수
# ═══════════════════════════════════════════════════════════════

def save_citrini_to_db(data: list):
    """
    Citrini 부정적 종목 데이터를 DB 에 저장한다.
    """
    import sys
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from db_manager import save_citrini_risky
    save_citrini_risky(data)


def save_citrini_report(data: list, report_text: str, filename: str = None):
    """
    Citrini 보고서를 JSON 과 TXT 로 저장한다.
    """
    if not filename:
        filename = f"citrini_report_{datetime.datetime.now().strftime('%Y%m%d_%H%M')}"

    # JSON 데이터
    json_path = os.path.join(BASE_DIR, f"{filename}.json")
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump({
            "report_date": datetime.datetime.now().isoformat(),
            "scenario": CITRINI_SCENARIO,
            "losers": data,
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
    print("\n⚠️ Citrini 2028 글로벌 지능위기 — 부정적 종목 분석 시작...\n")

    # 데이터 수집
    data = collect_all_losers_data()

    if not data:
        print("수집된 데이터가 없습니다.")
        sys.exit(1)

    # 보고서 생성
    report = build_citrini_warning_report(data)
    print(report)

    # 저장 (파일 + DB)
    save_citrini_report(data, report)
    save_citrini_to_db(data)

    print(f"\n총 {len(data)}개 부정적 종목 Citrini 분석 완료.")
