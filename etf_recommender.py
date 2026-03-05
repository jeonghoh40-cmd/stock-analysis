"""
한미 유망 ETF 분석 및 추천 모듈
────────────────────────────────────────────────────────────────
목적:
  - 한국 (KOSPI/KOSDAQ) 과 미국 (NYSE/NASDAQ) 의 유망 ETF 분석
  - 섹터별/테마별 ETF 추천
  - 구성 종목 및 비용비율 (TER) 정보 제공

분석 기준:
  - 최근 3 개월/6 개월/1 년 성과
  - 운용자산 (AUM)
  - 거래량
  - 보수 (TER)
"""

import os
import sys
import json
import datetime
from typing import Dict, List

import yfinance as yf
import pandas as pd

if sys.stdout.encoding != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

BASE_DIR = os.path.dirname(os.path.abspath(__file__))


# ═══════════════════════════════════════════════════════════════
# 추천 ETF 풀 (한국 + 미국)
# ═══════════════════════════════════════════════════════════════

# 한국 ETF (KOSPI/KOSDAQ)
KOREA_ETF_POOL = {
    # ── 반도체/AI ─────────────────────────────────────────────
    "TIGER 반도체 TOP10": {
        "ticker": "305720.KS",
        "category": "반도체/AI",
        "description": "국내 반도체 대표 기업 10 개 집중 투자",
        "reason": "AI 반도체 슈퍼사이클, HBM 수요 폭증",
        "risk": "중급",
    },
    "ACE 반도체": {
        "ticker": "294360.KS",
        "category": "반도체/AI",
        "description": "국내 반도체 기업 포괄적 투자",
        "reason": "삼성전자·SK 하이닉스 중심 포트폴리오",
        "risk": "중급",
    },
    "TIGER Fn반도체": {
        "ticker": "377180.KS",
        "category": "반도체/AI",
        "description": "반도체 설계·장비·소재 기업",
        "reason": "반도체 밸류체인 전반 투자",
        "risk": "중급",
    },
    
    # ── 2 차전지/에너지 ────────────────────────────────────────
    "TIGER 2 차전지 TOP10": {
        "ticker": "410190.KS",
        "category": "2 차전지/에너지",
        "description": "2 차전지 밸류체인 대표 기업",
        "reason": "ESS 수요 증가, 전기차 성장 지속",
        "risk": "중상급",
    },
    "KODEX 2 차전지산업": {
        "ticker": "233740.KS",
        "category": "2 차전지/에너지",
        "description": "2 차전지 소재·부품·완제품",
        "reason": "LG 에너지솔루션·에코프로 중심",
        "risk": "중상급",
    },
    "ACE 전기차배터리": {
        "ticker": "395650.KS",
        "category": "2 차전지/에너지",
        "description": "전기차 배터리 기업 집중 투자",
        "reason": "전기차渗透率 지속 증가",
        "risk": "중상급",
    },
    
    # ── 바이오/헬스케어 ────────────────────────────────────────
    "TIGER 바이오": {
        "ticker": "133690.KS",
        "category": "바이오/헬스케어",
        "description": "국내 바이오·제약 기업",
        "reason": "AI 신약개발, 바이오 CMO 성장",
        "risk": "상급",
    },
    "KODEX 바이오": {
        "ticker": "114800.KS",
        "category": "바이오/헬스케어",
        "description": "국내 바이오 대표 기업",
        "reason": "삼성바이오로직스·셀트리온 중심",
        "risk": "상급",
    },
    "ACE 글로벌바이오": {
        "ticker": "308470.KS",
        "category": "바이오/헬스케어",
        "description": "국내외 바이오 기업 혼합",
        "reason": "글로벌 바이오 기업 동시 투자",
        "risk": "상급",
    },
    
    # ── 방산/우주 ─────────────────────────────────────────────
    "TIGER 방산": {
        "ticker": "281050.KS",
        "category": "방산/우주",
        "description": "국내 방산 기업 집중 투자",
        "reason": "지정학적 리스크, 방산 수출 호조",
        "risk": "중급",
    },
    "KODEX 방산": {
        "ticker": "281060.KS",
        "category": "방산/우주",
        "description": "방산·항공·우주 기업",
        "reason": "한화에어로스페이스·LIG 넥스원",
        "risk": "중급",
    },
    
    # ── 배당/가치 ─────────────────────────────────────────────
    "TIGER 배당성장": {
        "ticker": "192090.KS",
        "category": "배당/가치",
        "description": "배당 성장 기업 포트폴리오",
        "reason": "안정적 현금흐름, 주주환원 강화",
        "risk": "하급",
    },
    "KODEX 배당플러스": {
        "ticker": "114770.KS",
        "category": "배당/가치",
        "description": "고배당 + 성장성 결합",
        "reason": "배당수익률 3-4% 목표",
        "risk": "하중급",
    },
    "ACE KOSPI50": {
        "ticker": "000780.KS",
        "category": "배당/가치",
        "description": "KOSPI50 대형주",
        "reason": "국내 우량 대형주 집중",
        "risk": "중급",
    },
    
    # ── 섹터형 ────────────────────────────────────────────────
    "TIGER 금융": {
        "ticker": "133800.KS",
        "category": "섹터형",
        "description": "국내 금융지주·은행",
        "reason": "고금리 기조, PBR 저평가",
        "risk": "중급",
    },
    "KODEX 자동차": {
        "ticker": "133680.KS",
        "category": "섹터형",
        "description": "국내 자동차 완성차·부품",
        "reason": "현대차·기아 실적 호조",
        "risk": "중급",
    },
    "TIGER 화장품": {
        "ticker": "410750.KS",
        "category": "섹터형",
        "description": "국내 화장품 기업",
        "reason": "K-뷰티 글로벌 성장",
        "risk": "중상급",
    },
}

# 미국 ETF (NYSE/NASDAQ)
US_ETF_POOL = {
    # ── 반도체/AI ─────────────────────────────────────────────
    "VanEck Semiconductor": {
        "ticker": "SMH",
        "category": "반도체/AI",
        "description": "글로벌 반도체 기업 집중 투자",
        "reason": "NVDA·TSM 중심, AI 반도체 슈퍼사이클",
        "risk": "중급",
    },
    "iShares Semiconductor": {
        "ticker": "SOXX",
        "category": "반도체/AI",
        "description": "미국 반도체 설계·제조·장비",
        "reason": "반도체 밸류체인 전반 투자",
        "risk": "중급",
    },
    "Global X AI & Tech": {
        "ticker": "AIQ",
        "category": "반도체/AI",
        "description": "AI 관련 하드웨어·소프트웨어",
        "reason": "AI 산업 성장 수혜",
        "risk": "중상급",
    },
    "ARK Innovation": {
        "ticker": "ARKK",
        "category": "반도체/AI",
        "description": "파괴적 혁신 기업 집중",
        "reason": "고성장 테크 기업 포트폴리오",
        "risk": "상급",
    },
    
    # ── 2 차전지/클린에너지 ────────────────────────────────────
    "Global X Lithium": {
        "ticker": "LIT",
        "category": "2 차전지/에너지",
        "description": "리튬 채굴·2 차전지 기업",
        "reason": "전기차·ESS 수요 증가",
        "risk": "중상급",
    },
    "iShares Clean Energy": {
        "ticker": "ICLN",
        "category": "2 차전지/에너지",
        "description": "재생에너지 발전·장비",
        "reason": "탄소중립 정책 수혜",
        "risk": "중상급",
    },
    "First Trust NASDAQ Clean Edge": {
        "ticker": "QCLN",
        "category": "2 차전지/에너지",
        "description": "청정에너지·전기차",
        "reason": "미국 청정에너지 정책 지원",
        "risk": "중상급",
    },
    
    # ── 바이오/헬스케어 ────────────────────────────────────────
    "iShares Biotechnology": {
        "ticker": "IBB",
        "category": "바이오/헬스케어",
        "description": "미국 바이오·제약 대형주",
        "reason": "신약개발 모멘텀, M&A 활성",
        "risk": "상급",
    },
    "SPDR S&P Biotech": {
        "ticker": "XBI",
        "category": "바이오/헬스케어",
        "description": "미국 바이오 중소형주 중심",
        "reason": "고성장 바이오 기업 투자",
        "risk": "상급",
    },
    "iShares Healthcare": {
        "ticker": "IXJ",
        "category": "바이오/헬스케어",
        "description": "글로벌 헬스케어 기업",
        "reason": "안정적 방어 + 성장",
        "risk": "중급",
    },
    
    # ── 방산/우주 ─────────────────────────────────────────────
    "iShares US Aerospace & Defense": {
        "ticker": "ITA",
        "category": "방산/우주",
        "description": "미국 방산·항공우주",
        "reason": "지정학적 리스크, 방산비 증가",
        "risk": "중급",
    },
    "SPDR S&P Aerospace & Defense": {
        "ticker": "XAR",
        "category": "방산/우주",
        "description": "미국 방산 기업 다양화",
        "reason": "록히드마틴·RTX 중심",
        "risk": "중급",
    },
    
    # ── 빅테크/나스닥 ─────────────────────────────────────────
    "Invesco QQQ": {
        "ticker": "QQQ",
        "category": "빅테크/나스닥",
        "description": "나스닥 100 대형주",
        "reason": "애플·MS·NVDA 중심 성장",
        "risk": "중급",
    },
    "SPDR S&P 500": {
        "ticker": "SPY",
        "category": "빅테크/나스닥",
        "description": "S&P 500 대형주",
        "reason": "미국 시장 대표, 안정적",
        "risk": "하중급",
    },
    "iShares Russell 1000 Growth": {
        "ticker": "IWF",
        "category": "빅테크/나스닥",
        "description": "대형 성장주 중심",
        "reason": "성장성 높은 대형주",
        "risk": "중급",
    },
    "Vanguard Information Tech": {
        "ticker": "VGT",
        "description": "미국 정보기술 섹터",
        "category": "빅테크/나스닥",
        "reason": "애플·MS·NVDA 집중",
        "risk": "중급",
    },
    
    # ── 배당/가치 ─────────────────────────────────────────────
    "Vanguard High Dividend Yield": {
        "ticker": "VYM",
        "category": "배당/가치",
        "description": "고배당 미국 대형주",
        "reason": "배당수익률 3%+, 안정적",
        "risk": "하중급",
    },
    "Schwab US Dividend Equity": {
        "ticker": "SCHD",
        "category": "배당/가치",
        "description": "배당 성장 기업",
        "reason": "10 년 연속 배당성장 기업",
        "risk": "하중급",
    },
    "iShares Select Dividend": {
        "ticker": "DVY",
        "category": "배당/가치",
        "description": "고배당 수익률 기업",
        "reason": "배당수익률 4% 목표",
        "risk": "하중급",
    },
    
    # ── 섹터형 ────────────────────────────────────────────────
    "Financial Select Sector SPDR": {
        "ticker": "XLF",
        "category": "섹터형",
        "description": "미국 금융 섹터",
        "reason": "JP 모건·뱅크오브아메리카",
        "risk": "중급",
    },
    "Energy Select Sector SPDR": {
        "ticker": "XLE",
        "category": "섹터형",
        "description": "미국 에너지 (석유·가스)",
        "reason": "엑손모빌·쉐브론",
        "risk": "중급",
    },
    "Consumer Discretionary SPDR": {
        "ticker": "XLY",
        "category": "섹터형",
        "description": "미국 선택적 소비재",
        "reason": "아마존·테슬라 중심",
        "risk": "중급",
    },
}


# ═══════════════════════════════════════════════════════════════
# ETF 데이터 수집
# ═══════════════════════════════════════════════════════════════

def fetch_etf_data(ticker: str) -> dict:
    """
    단일 ETF 의 데이터를 수집한다.
    """
    try:
        etf = yf.Ticker(ticker)
        info = etf.info
        
        # 가격 데이터
        h = etf.history(period="1y")
        if h.empty:
            return {}
        
        close = h["Close"]
        current = close.iloc[-1]
        
        # 수익률 계산
        ret_1m = (close.iloc[-1] / close.iloc[-21] - 1) * 100 if len(close) >= 21 else None
        ret_3m = (close.iloc[-1] / close.iloc[-63] - 1) * 100 if len(close) >= 63 else None
        ret_6m = (close.iloc[-1] / close.iloc[-126] - 1) * 100 if len(close) >= 126 else None
        ret_1y = (close.iloc[-1] / close.iloc[0] - 1) * 100
        
        # 거래량
        avg_vol_3m = h["Volume"].rolling(63).mean().iloc[-1]
        current_vol = h["Volume"].iloc[-1]
        
        # 기본 정보
        return {
            "ticker": ticker,
            "name": info.get("shortName", info.get("longName", "")),
            "price": round(float(current), 2),
            "ret_1m": round(float(ret_1m), 2) if ret_1m else None,
            "ret_3m": round(float(ret_3m), 2) if ret_3m else None,
            "ret_6m": round(float(ret_6m), 2) if ret_6m else None,
            "ret_1y": round(float(ret_1y), 2),
            "aum": info.get("totalAssets", 0),
            "ter": info.get("annualReportExpenseRatio", None),
            "dividend_yield": info.get("dividendYield", 0),
            "avg_volume": int(avg_vol_3m) if avg_vol_3m else 0,
            "current_volume": int(current_vol),
            "52w_high": round(float(h["High"].max()), 2),
            "52w_low": round(float(h["Low"].min()), 2),
        }
    except Exception as e:
        return {}


def collect_all_etf_data() -> tuple:
    """
    모든 ETF 데이터를 수집한다.
    """
    print("\n📊 한국 ETF 데이터 수집 중...")
    korea_data = []
    for name, info in KOREA_ETF_POOL.items():
        print(f"  수집: {name}...", end=" ")
        data = fetch_etf_data(info["ticker"])
        if data:
            data["category"] = info["category"]
            data["description"] = info["description"]
            data["reason"] = info["reason"]
            data["risk"] = info["risk"]
            data["etf_name"] = name
            korea_data.append(data)
            print(f"완료 ({data['price']:,.0f}원, 1 년: {data['ret_1y']:+.1f}%)")
        else:
            print("실패")
    
    print("\n📊 미국 ETF 데이터 수집 중...")
    us_data = []
    for name, info in US_ETF_POOL.items():
        print(f"  수집: {name}...", end=" ")
        data = fetch_etf_data(info["ticker"])
        if data:
            data["category"] = info["category"]
            data["description"] = info["description"]
            data["reason"] = info["reason"]
            data["risk"] = info["risk"]
            data["etf_name"] = name
            us_data.append(data)
            print(f"완료 (${data['price']:,.2f}, 1 년: {data['ret_1y']:+.1f}%)")
        else:
            print("실패")
    
    return korea_data, us_data


# ═══════════════════════════════════════════════════════════════
# ETF 분석 및 랭킹
# ═══════════════════════════════════════════════════════════════

def rank_etf_by_category(etf_data: list) -> dict:
    """
    카테고리별 ETF 순위를 매긴다.
    """
    by_category = {}
    
    for etf in etf_data:
        cat = etf.get("category", "Unknown")
        if cat not in by_category:
            by_category[cat] = []
        by_category[cat].append(etf)
    
    # 카테고리별 정렬 (1 년 수익률 기준)
    ranked = {}
    for cat, etfs in by_category.items():
        sorted_etfs = sorted(etfs, key=lambda x: x.get("ret_1y", 0), reverse=True)
        ranked[cat] = sorted_etfs
    
    return ranked


def get_top_etf_recommendations(korea_data: list, us_data: list, 
                                 top_n: int = 5) -> dict:
    """
    종합 추천 ETF 를 선별한다.
    """
    # 한국 TOP
    korea_ranked = rank_etf_by_category(korea_data)
    us_ranked = rank_etf_by_category(us_data)
    
    # 전체 통합 순위 (1 년 수익률)
    korea_sorted = sorted(korea_data, key=lambda x: x.get("ret_1y", 0), reverse=True)
    us_sorted = sorted(us_data, key=lambda x: x.get("ret_1y", 0), reverse=True)
    
    return {
        "korea_top": korea_sorted[:top_n],
        "us_top": us_sorted[:top_n],
        "korea_by_category": korea_ranked,
        "us_by_category": us_ranked,
    }


# ═══════════════════════════════════════════════════════════════
# ETF 구성 종목 정보
# ═══════════════════════════════════════════════════════════════

def get_etf_holdings(ticker: str) -> list:
    """
    ETF 의 상위 구성 종목을 가져온다.
    """
    try:
        etf = yf.Ticker(ticker)
        holdings = etf.holdings
        if holdings is not None:
            return holdings[:10]  # 상위 10 개
        return []
    except:
        return []


# ═══════════════════════════════════════════════════════════════
# 보고서 생성
# ═══════════════════════════════════════════════════════════════

def build_etf_recommendation_report(korea_data: list, us_data: list) -> str:
    """
    ETF 추천 보고서를 생성한다.
    """
    lines = []
    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
    
    lines.append("\n" + "═" * 90)
    lines.append("  🇰🇷 한국 & 🇺🇸 미국 유망 ETF 추천 보고서")
    lines.append(f"  분석 기준: {now}")
    lines.append("═" * 90)
    
    # 한국 ETF 추천
    lines.append("\n" + "═" * 90)
    lines.append("  🇰🇷 한국 ETF 추천 (KOSPI/KOSDAQ)")
    lines.append("═" * 90)
    
    korea_ranked = rank_etf_by_category(korea_data)
    
    for category, etfs in sorted(korea_ranked.items()):
        lines.append(f"\n【{category}】")
        lines.append(f"  {'ETF 명':<20} {'티커':<12} {'현재가':>12} {'1M':>8} {'3M':>8} {'6M':>8} {'1Y':>8} {'이유':<30}")
        lines.append("  " + "-" * 115)
        
        for etf in sorted(etfs, key=lambda x: x.get("ret_1y", 0), reverse=True):
            name = etf.get("etf_name", "")[:18]
            ticker = etf.get("ticker", "")
            price = f"{etf.get('price', 0):>12,.0f}"
            r1m = f"{etf.get('ret_1m', 0):>+7.1f}%" if etf.get('ret_1m') else "N/A"
            r3m = f"{etf.get('ret_3m', 0):>+7.1f}%" if etf.get('ret_3m') else "N/A"
            r6m = f"{etf.get('ret_6m', 0):>+7.1f}%" if etf.get('ret_6m') else "N/A"
            r1y = f"{etf.get('ret_1y', 0):>+7.1f}%"
            reason = etf.get("reason", "")[:28]
            
            lines.append(f"  {name:<20} {ticker:<12} {price:>12} {r1m:>8} {r3m:>8} {r6m:>8} {r1y:>8} {reason:<28}")
    
    # 미국 ETF 추천
    lines.append("\n\n" + "═" * 90)
    lines.append("  🇺🇸 미국 ETF 추천 (NYSE/NASDAQ)")
    lines.append("═" * 90)
    
    us_ranked = rank_etf_by_category(us_data)
    
    for category, etfs in sorted(us_ranked.items()):
        lines.append(f"\n【{category}】")
        lines.append(f"  {'ETF 명':<25} {'티커':<10} {'현재가':>10} {'1M':>7} {'3M':>7} {'6M':>7} {'1Y':>7} {'이유':<30}")
        lines.append("  " + "-" * 105)
        
        for etf in sorted(etfs, key=lambda x: x.get("ret_1y", 0), reverse=True):
            name = etf.get("etf_name", "")[:23]
            ticker = etf.get("ticker", "")
            price = f"${etf.get('price', 0):>9.2f}"
            r1m = f"{etf.get('ret_1m', 0):>+6.1f}%" if etf.get('ret_1m') else "N/A"
            r3m = f"{etf.get('ret_3m', 0):>+6.1f}%" if etf.get('ret_3m') else "N/A"
            r6m = f"{etf.get('ret_6m', 0):>+6.1f}%" if etf.get('ret_6m') else "N/A"
            r1y = f"{etf.get('ret_1y', 0):>+6.1f}%"
            reason = etf.get("reason", "")[:28]
            
            lines.append(f"  {name:<25} {ticker:<10} {price:>10} {r1m:>7} {r3m:>7} {r6m:>7} {r1y:>7} {reason:<28}")
    
    # 종합 TOP 10
    lines.append("\n\n" + "═" * 90)
    lines.append("  🏆 종합 TOP 10 ETF (1 년 수익률 기준)")
    lines.append("═" * 90)
    
    all_etfs = korea_data + us_data
    all_sorted = sorted(all_etfs, key=lambda x: x.get("ret_1y", 0), reverse=True)[:10]
    
    lines.append(f"\n  {'순위':>4} {'국가':>4} {'ETF 명':<25} {'티커':<10} {'1Y':>8} {'3M':>8} {'AUM':>12} {'추천이유':<30}")
    lines.append("  " + "-" * 130)
    
    for i, etf in enumerate(all_sorted, 1):
        country = "🇰🇷" if ".KS" in etf.get("ticker", "") else "🇺🇸"
        name = etf.get("etf_name", "")[:23]
        ticker = etf.get("ticker", "")
        r1y = f"{etf.get('ret_1y', 0):>+7.1f}%"
        r3m = f"{etf.get('ret_3m', 0):>+7.1f}%" if etf.get('ret_3m') else "N/A"
        aum = f"{etf.get('aum', 0)/1e9:.1f}B" if etf.get('aum') else "N/A"
        reason = etf.get("reason", "")[:28]
        
        lines.append(f"  {i:>4} {country:>4} {name:<25} {ticker:<10} {r1y:>8} {r3m:>8} {aum:>12} {reason:<28}")
    
    # 투자 전략
    lines.append("\n\n" + "═" * 90)
    lines.append("  💡 ETF 투자 전략")
    lines.append("═" * 90)
    
    lines.append("""
  [초보자 추천 포트폴리오]
  • 한국 (40%): TIGER 반도체 TOP10(15%) + TIGER 배당성장 (15%) + KODEX 2 차전지 (10%)
  • 미국 (60%): QQQ(25%) + SCHD(20%) + SMH(15%)
  
  [공격적 포트폴리오]
  • 한국 (30%): TIGER Fn 반도체 (15%) + TIGER 2 차전지 TOP10(15%)
  • 미국 (70%): ARKK(20%) + SMH(20%) + AIQ(15%) + LIT(15%)
  
  [방어적 포트폴리오]
  • 한국 (50%): TIGER 배당성장 (25%) + KODEX 배당플러스 (25%)
  • 미국 (50%): SCHD(30%) + VYM(20%)
  
  [리밸런싱 가이드]
  • 분기별 1 회 리밸런싱
  • 개별 ETF ±20% 등락시 재조정
  • 현금 비중 10-20% 유지
""")
    
    # 주의사항
    lines.append("\n" + "─" * 90)
    lines.append("  ⚠️ 투자 유의사항")
    lines.append("─" * 90)
    lines.append("""
  • 과거 수익률은 미래 수익률을 보장하지 않습니다
  • 섹터 ETF 는 변동성이 크므로 분산 투자 필수
  • 미국 ETF 는 환율 리스크 고려 (원/달러 환율)
  • TER(보수) 를 반드시 확인하세요 (0.03-0.75% 일반적)
  • 거래량이 적은 ETF 는 매매 차질 가능
""")
    
    lines.append("\n" + "═" * 90)
    lines.append("  📚 데이터 출처: Yahoo Finance, 각 운용사")
    lines.append("  ⚠️ 이 보고서는 투자 참고용이며, 최종 결정은 본인의 책임입니다.")
    lines.append("═" * 90 + "\n")
    
    return "\n".join(lines)


# ═══════════════════════════════════════════════════════════════
# 실행
# ═══════════════════════════════════════════════════════════════

if __name__ == "__main__":
    print("\n🇰🇷🇺🇸 한미 유망 ETF 분석 시작...\n")
    
    # 데이터 수집
    korea_data, us_data = collect_all_etf_data()
    
    if not korea_data and not us_data:
        print("수집된 데이터가 없습니다.")
        sys.exit(1)
    
    print(f"\n✅ 한국 ETF: {len(korea_data)}개 수집 완료")
    print(f"✅ 미국 ETF: {len(us_data)}개 수집 완료")
    
    # 보고서 생성
    report = build_etf_recommendation_report(korea_data, us_data)
    print(report)
    
    # 저장
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M")
    
    report_path = os.path.join(BASE_DIR, f"etf_recommendation_{timestamp}.txt")
    with open(report_path, "w", encoding="utf-8") as f:
        f.write(report)
    
    json_path = os.path.join(BASE_DIR, f"etf_analysis_{timestamp}.json")
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump({
            "analysis_date": datetime.datetime.now().isoformat(),
            "korea_etfs": korea_data,
            "us_etfs": us_data,
        }, f, ensure_ascii=False, indent=2, default=str)
    
    print(f"\n💾 보고서 저장 완료:")
    print(f"   - TXT: {report_path}")
    print(f"   - JSON: {json_path}")
