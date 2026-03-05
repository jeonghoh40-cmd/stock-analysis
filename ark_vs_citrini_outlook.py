"""
ARK vs Citrini — 최근 2 주 주가 분석 및 추가 전망
────────────────────────────────────────────────────────────────
목적:
  - ARK 추천 종목 (긍정적) 과 Citrini 부정적 종목 (부정적) 비교
  - 최근 2 주 (14 일) 주가 흐름 분석
  - 향후 전망 및 투자 전략 제언

분석 기간: 최근 14 영업일
"""

import os
import sys
import json
import datetime
from typing import Dict, List

import yfinance as yf
import pandas as pd
import numpy as np

if sys.stdout.encoding != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

BASE_DIR = os.path.dirname(os.path.abspath(__file__))


# ═══════════════════════════════════════════════════════════════
# 데이터 로드
# ═══════════════════════════════════════════════════════════════

def load_ark_losers() -> tuple:
    """
    DB 에서 ARK 추천 종목과 Citrini 부정적 종목을 로드한다.
    """
    sys.path.insert(0, BASE_DIR)
    from db_manager import get_latest_ark_recommended, get_latest_citrini_risky

    # ARK 추천 종목
    ark_rows = get_latest_ark_recommended(limit=100)
    
    # Citrini 부정적 종목
    citrini_rows = get_latest_citrini_risky(limit=100)

    return ark_rows, citrini_rows


def fetch_historical_prices(tickers: List[str], period: str = "1mo") -> Dict:
    """
    여러 티커의 과거 주가 데이터를 수집한다.
    """
    price_data = {}

    for ticker in tickers:
        try:
            t = yf.Ticker(ticker)
            h = t.history(period=period)
            if not h.empty:
                price_data[ticker] = h
        except Exception as e:
            pass

    return price_data


# ═══════════════════════════════════════════════════════════════
# 기술적 분석
# ═══════════════════════════════════════════════════════════════

def calculate_momentum_indicators(df: pd.DataFrame) -> dict:
    """
    모멘텀 지표들을 계산한다.
    """
    if len(df) < 14:
        return {}

    close = df["Close"]

    # 14 일 수익률
    ret_14d = (close.iloc[-1] / close.iloc[0] - 1) * 100

    # 5 일, 10 일 수익률
    ret_5d = (close.iloc[-1] / close.iloc[-5] - 1) * 100 if len(close) >= 5 else None
    ret_10d = (close.iloc[-1] / close.iloc[-10] - 1) * 100 if len(close) >= 10 else None

    # 이동평균
    ma5 = close.rolling(5).mean()
    ma10 = close.rolling(10).mean()
    ma20 = close.rolling(20).mean()

    # 현재가 vs 이동평균
    price_vs_ma5 = (close.iloc[-1] / ma5.iloc[-1] - 1) * 100
    price_vs_ma10 = (close.iloc[-1] / ma10.iloc[-1] - 1) * 100
    price_vs_ma20 = (close.iloc[-1] / ma20.iloc[-1] - 1) * 100 if len(close) >= 20 else None

    # RSI (14 일)
    delta = close.diff()
    gain = delta.clip(lower=0).rolling(14).mean()
    loss = (-delta.clip(upper=0)).rolling(14).mean()
    rsi = 100 - 100 / (1 + gain.iloc[-1] / (loss.iloc[-1] + 1e-9))

    # 거래량 추세
    volume = df["Volume"]
    avg_vol_5 = volume.rolling(5).mean()
    avg_vol_10 = volume.rolling(10).mean()
    vol_trend = (avg_vol_5.iloc[-1] / avg_vol_10.iloc[-1] - 1) * 100

    # 변동성
    daily_ret = close.pct_change()
    volatility_14d = daily_ret.std() * np.sqrt(252) * 100

    return {
        "ret_14d": round(ret_14d, 2),
        "ret_5d": round(ret_5d, 2) if ret_5d else None,
        "ret_10d": round(ret_10d, 2) if ret_10d else None,
        "price_vs_ma5": round(price_vs_ma5, 2),
        "price_vs_ma10": round(price_vs_ma10, 2),
        "price_vs_ma20": round(price_vs_ma20, 2) if price_vs_ma20 else None,
        "rsi": round(rsi, 1),
        "vol_trend": round(vol_trend, 2),
        "volatility_14d": round(volatility_14d, 1),
    }


# ═══════════════════════════════════════════════════════════════
# 포트폴리오 분석
# ═══════════════════════════════════════════════════════════════

def analyze_portfolio_performance(ark_data: list, citrini_data: list, 
                                   price_data: dict) -> dict:
    """
    두 포트폴리오의 성과를 비교 분석한다.
    """
    # ARK 분석
    ark_analysis = []
    for item in ark_data:
        ticker = item.get("ticker")
        if ticker in price_data:
            indicators = calculate_momentum_indicators(price_data[ticker])
            if indicators:
                ark_analysis.append({
                    **item,
                    **indicators,
                })

    # Citrini 분석
    citrini_analysis = []
    for item in citrini_data:
        ticker = item.get("ticker")
        if ticker in price_data:
            indicators = calculate_momentum_indicators(price_data[ticker])
            if indicators:
                citrini_analysis.append({
                    **item,
                    **indicators,
                })

    # 종합 통계
    ark_rets = [a["ret_14d"] for a in ark_analysis if a.get("ret_14d") is not None]
    citrini_rets = [c["ret_14d"] for c in citrini_analysis if c.get("ret_14d") is not None]

    return {
        "ark": {
            "count": len(ark_analysis),
            "avg_ret_14d": round(sum(ark_rets) / len(ark_rets), 2) if ark_rets else 0,
            "positive_count": sum(1 for r in ark_rets if r > 0),
            "negative_count": sum(1 for r in ark_rets if r < 0),
            "best_performer": max(ark_rets) if ark_rets else 0,
            "worst_performer": min(ark_rets) if ark_rets else 0,
            "avg_rsi": round(sum(a.get("rsi", 50) for a in ark_analysis) / len(ark_analysis), 1) if ark_analysis else 50,
        },
        "citrini": {
            "count": len(citrini_analysis),
            "avg_ret_14d": round(sum(citrini_rets) / len(citrini_rets), 2) if citrini_rets else 0,
            "positive_count": sum(1 for r in citrini_rets if r > 0),
            "negative_count": sum(1 for r in citrini_rets if r < 0),
            "best_performer": max(citrini_rets) if citrini_rets else 0,
            "worst_performer": min(citrini_rets) if citrini_rets else 0,
            "avg_rsi": round(sum(c.get("rsi", 50) for c in citrini_analysis) / len(citrini_analysis), 1) if citrini_analysis else 50,
        },
        "spread": round(
            (sum(ark_rets) / len(ark_rets) if ark_rets else 0) - 
            (sum(citrini_rets) / len(citrini_rets) if citrini_rets else 0), 2
        ),
    }


# ═══════════════════════════════════════════════════════════════
# 섹터별 분석
# ═══════════════════════════════════════════════════════════════

def analyze_by_sector(citrini_data: list, price_data: dict) -> dict:
    """
    Citrini 부정적 종목을 섹터별로 분석한다.
    """
    by_sector = {}

    for item in citrini_data:
        ticker = item.get("ticker")
        sector = item.get("sector", "Unknown")
        
        if ticker in price_data:
            indicators = calculate_momentum_indicators(price_data[ticker])
            if indicators:
                if sector not in by_sector:
                    by_sector[sector] = []
                by_sector[sector].append({
                    **item,
                    **indicators,
                })

    # 섹터별 통계
    sector_stats = {}
    for sector, items in by_sector.items():
        rets = [i["ret_14d"] for i in items if i.get("ret_14d") is not None]
        sector_stats[sector] = {
            "count": len(items),
            "avg_ret_14d": round(sum(rets) / len(rets), 2) if rets else 0,
            "positive_ratio": round(sum(1 for r in rets if r > 0) / len(rets) * 100, 1) if rets else 0,
            "avg_rsi": round(sum(i.get("rsi", 50) for i in items) / len(items), 1) if items else 50,
        }

    return sector_stats


# ═══════════════════════════════════════════════════════════════
# ARK 테마별 분석
# ═══════════════════════════════════════════════════════════════

def analyze_by_ark_theme(ark_data: list, price_data: dict) -> dict:
    """
    ARK 추천 종목을 테마별로 분석한다.
    """
    by_theme = {}

    for item in ark_data:
        ticker = item.get("ticker")
        # themes 리스트에서 첫 번째 테마만 사용
        themes = item.get("themes", [])
        theme_key = themes[0] if themes else "Unknown"
        
        if ticker in price_data:
            indicators = calculate_momentum_indicators(price_data[ticker])
            if indicators:
                if theme_key not in by_theme:
                    by_theme[theme_key] = []
                by_theme[theme_key].append({
                    **item,
                    **indicators,
                    "theme_key": theme_key,
                })

    # 테마별 통계
    theme_stats = {}
    for theme, items in by_theme.items():
        rets = [i["ret_14d"] for i in items if i.get("ret_14d") is not None]
        theme_stats[theme] = {
            "count": len(items),
            "avg_ret_14d": round(sum(rets) / len(rets), 2) if rets else 0,
            "positive_ratio": round(sum(1 for r in rets if r > 0) / len(rets) * 100, 1) if rets else 0,
            "avg_rsi": round(sum(i.get("rsi", 50) for i in items) / len(items), 1) if items else 50,
        }

    return theme_stats


# ═══════════════════════════════════════════════════════════════
# 전망 및 시나리오
# ═══════════════════════════════════════════════════════════════

def generate_outlook(analysis: dict, sector_stats: dict, theme_stats: dict) -> str:
    """
    분석 결과를 바탕으로 향후 전망을 생성한다.
    """
    lines = []

    ark = analysis["ark"]
    citrini = analysis["citrini"]
    spread = analysis["spread"]

    lines.append("\n" + "═" * 90)
    lines.append("  📈 ARK vs Citrini — 최근 2 주 분석 및 향후 전망")
    lines.append(f"  분석 기준: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M')}")
    lines.append("═" * 90)

    # 1. 종합 비교
    lines.append("\n【종합 비교 — 최근 14 일】")
    lines.append(f"  {'구분':<20} {'ARK 추천':>15} {'Citrini 부정':>15} {'격차':>10}")
    lines.append("  " + "-" * 55)
    lines.append(f"  {'평균 수익률':<20} {ark['avg_ret_14d']:>+14.1f}% {citrini['avg_ret_14d']:>+14.1f}% {spread:>+10.1f}p")
    lines.append(f"  {'양수 종목':<20} {ark['positive_count']:>8}개 ({ark['positive_count']/ark['count']*100:.0f}%) {citrini['positive_count']:>8}개 ({citrini['positive_count']/citrini['count']*100:.0f}%)")
    lines.append(f"  {'평균 RSI':<20} {ark['avg_rsi']:>14.1f} {citrini['avg_rsi']:>14.1f}")

    # 2. 시장 국면 진단
    lines.append("\n\n【시장 국면 진단】")

    if ark['avg_ret_14d'] > 10 and citrini['avg_ret_14d'] > 0:
        phase = "🟢 강세장 — 모든 종목 상승 (ARK 테마 주도)"
        action = "• ARK 핵심 종목 보유 유지\n• Citrini 부정적 종목도 상승하지만 장기적 위험 인식"
    elif ark['avg_ret_14d'] > 5 and citrini['avg_ret_14d'] < 0:
        phase = "🟡 차별화 장세 — ARK 수혜주 강세, Citrini 피해주 약세"
        action = "• ARK 테마 중심 투자\n• Citrini HIGH 위험 종목 회피\n• 섹터별 선별 접근"
    elif ark['avg_ret_14d'] > 0 and citrini['avg_ret_14d'] < -5:
        phase = "🟠 방어적 장세 — 성장주 약세, 가치주 상대적 강세"
        action = "• 현금 비중 확대\n• 고품질 성장주 선별 매수\n• Citrini 부정적 종목 추가 축소"
    elif ark['avg_ret_14d'] < 0 and citrini['avg_ret_14d'] < -10:
        phase = "🔴 약세장 — 모든 종목 하락 (Citrini 시나리오 가속)"
        action = "• 현금 비중 대폭 확대 (70%+)\n• 방어적 섹터 (유틸리티, 필수소비재) 이동\n• 모든 위험자산 축소"
    else:
        phase = "⚪ 보합세 — 방향성 불명확"
        action = "• 분할 매수/매도\n• 포트폴리오 리밸런싱\n• 변동성 축소 대기"

    lines.append(f"  ▶ 현재 국면: {phase}")
    lines.append(f"\n  [투자 행동]\n  {action}")

    # 3. ARK 테마별 전망
    lines.append("\n\n【ARK 테마별 전망】")
    sorted_themes = sorted(theme_stats.items(), key=lambda x: x[1]['avg_ret_14d'], reverse=True)[:5]

    for theme, stats in sorted_themes:
        theme_name = theme.replace("_", " ").replace("1_", "").replace("2_", "")
        theme_name = theme_name.replace("3_", "").replace("4_", "").replace("5_", "")
        theme_name = theme_name.replace("6_", "").replace("7_", "").replace("8_", "")
        theme_name = theme_name.replace("9_", "").replace("10_", "").replace("11_", "")
        theme_name = theme_name.replace("12_", "").replace("13_", "")

        if stats['avg_ret_14d'] >= 10:
            outlook = "🚀 강력 상승 — 모멘텀 지속"
            strategy = "보유 유지, 추종 매수는 조정 대기"
        elif stats['avg_ret_14d'] >= 3:
            outlook = "📈 상승 — 양호한 모멘텀"
            strategy = "분할 매수 유지"
        elif stats['avg_ret_14d'] >= -3:
            outlook = "➡️ 보합 — 방향성 불명확"
            strategy = "관찰, 추가 정보 대기"
        else:
            outlook = "📉 약세 — 모멘텀 약화"
            strategy = "비중 축소, 손절 라인 준수"

        lines.append(f"\n  ▶ {theme_name[:25]}")
        lines.append(f"     14 일 수익률: {stats['avg_ret_14d']:+.1f}% | 양수비율: {stats['positive_ratio']:.0f}% | RSI: {stats['avg_rsi']:.1f}")
        lines.append(f"     전망: {outlook}")
        lines.append(f"     전략: {strategy}")

    # 4. Citrini 섹터별 위험도
    lines.append("\n\n【Citrini 섹터별 위험도】")
    sorted_sectors = sorted(sector_stats.items(), key=lambda x: x[1]['avg_ret_14d'])

    for sector, stats in sorted_sectors[:5]:
        if stats['avg_ret_14d'] < -15:
            risk = "🔴 극위험 — 대폭락 진행 중"
            action = "즉시 축소"
        elif stats['avg_ret_14d'] < -5:
            risk = "🟠 고위험 — 약세 지속"
            action = "비중 축소"
        elif stats['avg_ret_14d'] < 0:
            risk = "🟡 주의 — 약보합"
            action = "모니터링"
        else:
            risk = "⚪ 상대적 강세"
            action = "관찰"

        lines.append(f"\n  ▶ {sector}")
        lines.append(f"     14 일 수익률: {stats['avg_ret_14d']:+.1f}% | 양수비율: {stats['positive_ratio']:.0f}% | RSI: {stats['avg_rsi']:.1f}")
        lines.append(f"     위험도: {risk}")
        lines.append(f"     행동: {action}")

    # 5. 시나리오별 대응
    lines.append("\n\n【시나리오별 대응 전략】")

    lines.append("\n  [시나리오 A: ARK 낙관론 현실화 (확률 40%)]")
    lines.append("    조건: AI 인프라 투자 지속, 생산성 향상 증거, 연착륙")
    lines.append("    신호: NVDA/MSFT/GOOGL 20 일 +15% 이상, IGV -5% 이내")
    lines.append("    대응:")
    lines.append("      • ARK CORE 테마 (AI 인프라, 로보틱스) 비중 확대 (50%+)")
    lines.append("      • Citrini 부정적 종목 중 AI 수혜주 (MSFT, GOOGL) 는 보유")
    lines.append("      • 레버리지 ETF 고려 (QQQ, TQQQ)")

    lines.append("\n  [시나리오 B: Citrini 위기론 현실화 (확률 30%)]")
    lines.append("    조건: AI 실업 가시화, 소비 위축, 디플레이션")
    lines.append("    신호: IGV -20% 이하, ^VIX 35+, XRT -15%")
    lines.append("    대응:")
    lines.append("      • 현금 비중 70%+ 확대")
    lines.append("      • ARK 종목 전량 매도")
    lines.append("      • 방어적 섹터 (유틸리티, 필수소비재, 금) 이동")
    lines.append("      • 공매도 고려 (SQQQ, SPXS)")

    lines.append("\n  [시나리오 C: 보합세 지속 (확률 30%)]")
    lines.append("    조건: 점진적 AI 도입, 연착륙 vs 연착륙")
    lines.append("    신호: S&P 500 ±5% 범위, VIX 15-25")
    lines.append("    대응:")
    lines.append("      • 60/40 포트폴리오 유지")
    lines.append("      • ARK 30%, Citrini 부정 10%, 현금 40%, 기타 20%")
    lines.append("      • 분할 매수/매도로 비용 평균화")

    # 6. 핵심 모니터링 지표
    lines.append("\n\n【핵심 모니터링 지표】")
    lines.append("\n  [주간 체크리스트]")
    lines.append("    1. NVDA 주가 (AI 심리 지표) — +10% 이상: 낙관, -10% 이하: 비관")
    lines.append("    2. IGV (소프트웨어 ETF) — -15% 이하: Citrini 신호")
    lines.append("    3. ^VIX (공포지수) — 35+: 위기 임박")
    lines.append("    4. XRT (소매 ETF) — -20% 이하: 소비 위축")
    lines.append("    5. DXY (달러인덱스) — 110+: 위험회피")

    lines.append("\n  [월간 리밸런싱]")
    lines.append("    • ARK 비중: 30-50% (국면별 조정)")
    lines.append("    • Citrini 부정: 0-10% (HIGH 위험은 0%)")
    lines.append("    • 현금: 20-70% (위기 심화시 확대)")
    lines.append("    • 방어적 자산: 10-30% (금, 채권, 유틸리티)")

    lines.append("\n" + "═" * 90)
    lines.append("  ⚠️ 이 보고서는 투자 참고용이며, 최종 결정은 본인의 책임입니다.")
    lines.append("  📚 출처: ARK Invest, Citrini Research, Yahoo Finance")
    lines.append("═" * 90 + "\n")

    return "\n".join(lines)


# ═══════════════════════════════════════════════════════════════
# 실행
# ═══════════════════════════════════════════════════════════════

if __name__ == "__main__":
    print("\n📊 ARK vs Citrini — 최근 2 주 주가 분석 시작...\n")

    # 1. 데이터 로드
    print("  [1/5] DB 에서 종목 목록 로드 중...")
    ark_rows, citrini_rows = load_ark_losers()
    print(f"      ARK 추천 종목: {len(ark_rows)}개")
    print(f"      Citrini 부정적 종목: {len(citrini_rows)}개")

    # 2. 티커 목록 추출
    ark_tickers = list(set(r.get("ticker") for r in ark_rows if r.get("ticker")))
    citrini_tickers = list(set(r.get("ticker") for r in citrini_rows if r.get("ticker")))
    all_tickers = list(set(ark_tickers + citrini_tickers))

    print(f"      중복 제거 티커: {len(all_tickers)}개")

    # 3. 주가 데이터 수집
    print("\n  [2/5] 최근 1 개월 주가 데이터 수집 중...")
    price_data = fetch_historical_prices(all_tickers, period="1mo")
    print(f"      수집 완료: {len(price_data)}개 티커")

    # 4. 포트폴리오 분석
    print("\n  [3/5] 포트폴리오 분석 중...")
    analysis = analyze_portfolio_performance(ark_rows, citrini_rows, price_data)
    print(f"      ARK 평균 14 일: {analysis['ark']['avg_ret_14d']:+.1f}%")
    print(f"      Citrini 평균 14 일: {analysis['citrini']['avg_ret_14d']:+.1f}%")
    print(f"      격차: {analysis['spread']:+.1f}p")

    # 5. 섹터/테마별 분석
    print("\n  [4/5] 섹터/테마별 분석 중...")
    sector_stats = analyze_by_sector(citrini_rows, price_data)
    theme_stats = analyze_by_ark_theme(ark_rows, price_data)
    print(f"      ARK 테마: {len(theme_stats)}개")
    print(f"      Citrini 섹터: {len(sector_stats)}개")

    # 6. 전망 생성
    print("\n  [5/5] 향후 전망 생성 중...")
    outlook = generate_outlook(analysis, sector_stats, theme_stats)
    print(outlook)

    # 7. 저장
    report_path = os.path.join(BASE_DIR, f"ark_vs_citrini_outlook_{datetime.datetime.now().strftime('%Y%m%d_%H%M')}.txt")
    with open(report_path, "w", encoding="utf-8") as f:
        f.write(outlook)

    print(f"\n💾 보고서 저장 완료: {report_path}")

    # JSON 데이터 저장
    json_path = os.path.join(BASE_DIR, f"ark_vs_citrini_analysis_{datetime.datetime.now().strftime('%Y%m%d_%H%M')}.json")
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump({
            "analysis_date": datetime.datetime.now().isoformat(),
            "portfolio_analysis": analysis,
            "sector_stats": sector_stats,
            "theme_stats": theme_stats,
        }, f, ensure_ascii=False, indent=2, default=str)

    print(f"💾 분석 데이터 저장 완료: {json_path}")
