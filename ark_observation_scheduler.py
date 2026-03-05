"""
ARK 추천 종목 — 주기적 관찰 보고서 스케줄러
────────────────────────────────────────────────────────────────
기능:
  - 매일/매주 ARK 추천 종목 자동 추적
  - 기존 스크리닝 추천 종목과 별도 카테고리 관리
  - 관찰 보고서 자동 생성 및 저장

실행 방법:
  python ark_observation_scheduler.py [--daily|--weekly|--once]
"""

import os
import sys
import datetime
import argparse
import time

if sys.stdout.encoding != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
REPORT_DIR = os.path.join(BASE_DIR, "ark_reports")

# ARK 모듈 import
from ark_recommended_stocks import (
    collect_all_ark_data,
    build_ark_observation_report,
    save_ark_report,
    save_ark_to_db,
)
from db_manager import (
    get_latest_ark_recommended,
    get_ark_history_dates,
    get_ark_performance_summary,
)


# ═══════════════════════════════════════════════════════════════
# 관찰 보고서 디렉토리 관리
# ═══════════════════════════════════════════════════════════════

def ensure_report_dir():
    """보고서 저장 디렉토리를 생성한다."""
    if not os.path.exists(REPORT_DIR):
        os.makedirs(REPORT_DIR)
        print(f"  📁 보고서 디렉토리 생성: {REPORT_DIR}")


# ═══════════════════════════════════════════════════════════════
# 일일 관찰 보고서
# ═══════════════════════════════════════════════════════════════

def generate_daily_report() -> tuple:
    """
    일일 ARK 관찰 보고서를 생성한다.
    반환: (data, report_text)
    """
    print("\n" + "═" * 70)
    print("  📊 ARK 일일 관찰 보고서 생성")
    print(f"  시각: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print("═" * 70)

    # 데이터 수집
    data = collect_all_ark_data()

    if not data:
        print("  ⚠️ 데이터 수집 실패")
        return None, None

    # 보고서 생성
    report = build_ark_observation_report(data)

    return data, report


# ═══════════════════════════════════════════════════════════════
# 주간 종합 보고서
# ═══════════════════════════════════════════════════════════════

def generate_weekly_report() -> str:
    """
    주간 ARK 종합 보고서를 생성한다.
    - 금일 데이터 + 과거 히스토리 비교
    - 주간 성과 요약
    """
    print("\n" + "═" * 70)
    print("  📈 ARK 주간 종합 보고서")
    print("═" * 70)

    lines = []
    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")

    lines.append("\n" + "═" * 90)
    lines.append("  📈 ARK Invest Big Ideas 2026 — 주간 종합 관찰보고서")
    lines.append(f"  기준: {now}")
    lines.append("═" * 90)

    # 1. 금일 데이터 수집
    print("\n  [1/3] 금일 데이터 수집 중...")
    today_data = collect_all_ark_data()

    # 2. DB 히스토리 조회
    print("  [2/3] 히스토리 데이터 조회 중...")
    history_dates = get_ark_history_dates()[:7]  # 최근 7 회
    perf_summary = get_ark_performance_summary(days_back=30)

    # 3. 주간 성과 요약
    lines.append("\n【주간 성과 요약】")
    if perf_summary:
        lines.append(f"  • 분석 대상 종목: {perf_summary.get('종목수', 0)}개")
        lines.append(f"  • 평균 20 일 수익률: {perf_summary.get('평균 20 일수익률', 0):+.2f}%")
        lines.append(f"  • 최고 수익률: {perf_summary.get('최고수익률', 0):+.2f}%")
        lines.append(f"  • 최저 수익률: {perf_summary.get('최저수익률', 0):+.2f}%")
        lines.append(f"  • 양수 비율: {perf_summary.get('양수비율', 0):.1f}%")

    # 4. 금일 상위/하위 종목
    lines.append("\n\n【금일 상위 성과 종목 TOP 10】")
    if today_data:
        sorted_data = sorted(today_data, key=lambda x: x.get("change_20d", 0), reverse=True)[:10]
        lines.append(f"  {'순위':>4} {'종목명':<20} {'티커':<12} {'20 일':>8} {'RSI':>6} {'테마':<30}")
        lines.append("  " + "-" * 85)
        for i, item in enumerate(sorted_data, 1):
            name = item.get("name", "")[:18]
            ticker = item.get("ticker", "")
            ret20 = f"{item.get('change_20d', 0):>+7.1f}%"
            rsi = f"{item.get('rsi', 0):>5.1f}"
            themes = ", ".join(item.get("themes", [])[:2])[:28]
            lines.append(f"  {i:>4} {name:<20} {ticker:<12} {ret20:>8} {rsi:>6} {themes:<28}")

    lines.append("\n\n【금일 하위 성과 종목 BOTTOM 5】")
    if today_data:
        sorted_data = sorted(today_data, key=lambda x: x.get("change_20d", 0))[:5]
        for i, item in enumerate(sorted_data, 1):
            name = item.get("name", "")[:18]
            ticker = item.get("ticker", "")
            ret20 = f"{item.get('change_20d', 0):>+7.1f}%"
            lines.append(f"  {i:>2}. {name:<18} {ticker:<12} {ret20:>8}")

    # 5. 테마별 주간 성과
    lines.append("\n\n【테마별 주간 성과】")
    theme_perf = {}
    for item in today_data:
        for theme in item.get("themes", []):
            if theme not in theme_perf:
                theme_perf[theme] = {"count": 0, "rets": []}
            theme_perf[theme]["count"] += 1
            if item.get("change_20d") is not None:
                theme_perf[theme]["rets"].append(item["change_20d"])

    lines.append(f"  {'테마':<30} {'종목수':>8} {'평균 20 일':>12} {'모멘텀':<16}")
    lines.append("  " + "-" * 70)

    for theme_key, perf in sorted(
        theme_perf.items(),
        key=lambda x: sum(x[1]["rets"])/len(x[1]["rets"]) if x[1]["rets"] else 0,
        reverse=True
    )[:10]:
        theme_name = theme_key.replace("_", " ").replace("1_", "").replace("2_", "")
        theme_name = theme_name.replace("3_", "").replace("4_", "").replace("5_", "")
        theme_name = theme_name.replace("6_", "").replace("7_", "").replace("8_", "")
        theme_name = theme_name.replace("9_", "").replace("10_", "").replace("11_", "")
        theme_name = theme_name.replace("12_", "").replace("13_", "")
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

    # 6. 종합 의견
    lines.append("\n\n" + "─" * 90)
    lines.append("【주간 종합 의견】")

    all_rets = [d.get("change_20d", 0) for d in today_data if d.get("change_20d") is not None]
    if all_rets:
        avg_all = sum(all_rets) / len(all_rets)
        pos = sum(1 for r in all_rets if r > 0)
        neg = sum(1 for r in all_rets if r < 0)

        lines.append(f"  • 전체 평균 20 일 수익률: {avg_all:+.1f}%")
        lines.append(f"  • 양수 종목: {pos}개 / 음수 종목: {neg}개")

        if avg_all >= 10:
            verdict = "🟢 강력 상승장 — ARK 테마 전반에 걸쳐 강한 모멘텀"
        elif avg_all >= 3:
            verdict = "🟢 상승장 — 대가속 테마 주도"
        elif avg_all >= -3:
            verdict = "🟡 보합세 — 테마별 차별화 심화"
        elif avg_all >= -10:
            verdict = "🟠 조정 국면 — 일부 테마 약세, 선별 접근 필요"
        else:
            verdict = "🔴 약세장 — 리스크 관리 강화 필요"

        lines.append(f"\n  ▶ 종합 판단: {verdict}")

        # 투자 권고
        lines.append("\n【투자 권고】")
        if avg_all >= 10:
            lines.append("  • 추종 모멘텀 유지, 그러나 과열 구간은 차익 실현 고려")
            lines.append("  • 신규 진입은 조정 대기")
        elif avg_all >= 3:
            lines.append("  • 핵심 테마 (AI 인프라, 로보틱스) 중심 보유")
            lines.append("  • 분할 매수 유지")
        elif avg_all >= -3:
            lines.append("  • 섹터별 선별 접근, 저가 매수 기회 탐색")
            lines.append("  • 현금 비중 확대")
        elif avg_all >= -10:
            lines.append("  • 방어적 포지셔닝, 손절 라인 준수")
            lines.append("  • 변동성 확대에 유의")
        else:
            lines.append("  • 현금 비중 대폭 확대, 관망")
            lines.append("  • 급등주 추종 금지")

    lines.append("\n" + "═" * 90)
    lines.append("  ⚠️ ARK 추천 종목은 장기 성장 테마 기반이나 변동성이 매우 큽니다.")
    lines.append("     분할 매수·손절 관리 필수 · 투자 참고용")
    lines.append("  📚 출처: ark-invest.com/big-ideas-2026")
    lines.append("═" * 90 + "\n")

    report = "\n".join(lines)
    print("  [3/3] 보고서 생성 완료")

    return report


# ═══════════════════════════════════════════════════════════════
# 스케줄러 실행
# ═══════════════════════════════════════════════════════════════

def run_once():
    """
    단일 실행 — 즉시 보고서 생성
    """
    ensure_report_dir()

    # 일일 보고서
    data, daily_report = generate_daily_report()

    if data and daily_report:
        # 파일명 생성
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M")
        filename = f"ark_daily_{timestamp}"

        # 저장
        save_ark_report(data, daily_report, os.path.join(REPORT_DIR, filename))
        save_ark_to_db(data)

        print(f"\n✅ 일일 보고서 저장 완료: {filename}")

    # 주간 보고서 (매주 금요일에만)
    if datetime.datetime.now().weekday() == 4:  # 금요일
        print("\n" + "─" * 70)
        weekly_report = generate_weekly_report()
        if weekly_report:
            timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M")
            filename = f"ark_weekly_{timestamp}"
            with open(os.path.join(REPORT_DIR, f"{filename}.txt"), "w", encoding="utf-8") as f:
                f.write(weekly_report)
            print(f"✅ 주간 보고서 저장 완료: {filename}")


def run_daily_scheduler():
    """
    매일 자동 실행 — 장 마감 후 (오후 6 시)
    """
    print("\n🕐 일일 스케줄러 시작 (매일 오후 6 시)")
    print("   종료: Ctrl+C")

    while True:
        now = datetime.datetime.now()
        target_time = now.replace(hour=18, minute=0, second=0, microsecond=0)

        # 오후 6 시 지났으면 내일
        if now >= target_time:
            target_time += datetime.timedelta(days=1)

        seconds_until = (target_time - now).total_seconds()
        print(f"\n  다음 실행까지: {seconds_until/3600:.1f}시간")
        print(f"  다음 실행: {target_time.strftime('%Y-%m-%d %H:%M')}")

        # 1 시간마다 체크
        check_interval = 3600
        for _ in range(int(seconds_until / check_interval) + 1):
            time.sleep(check_interval)
            if datetime.datetime.now() >= target_time:
                break

        # 실행
        run_once()


def run_weekly_scheduler():
    """
    매주 자동 실행 — 금요일 오후 6 시
    """
    print("\n🕐 주간 스케줄러 시작 (매주 금요일 오후 6 시)")
    print("   종료: Ctrl+C")

    while True:
        now = datetime.datetime.now()
        # 다음 금요일 계산
        days_until_friday = (4 - now.weekday()) % 7
        if days_until_friday == 0 and now.hour >= 18:
            days_until_friday = 7

        target_time = now + datetime.timedelta(days=days_until_friday)
        target_time = target_time.replace(hour=18, minute=0, second=0, microsecond=0)

        seconds_until = (target_time - now).total_seconds()
        print(f"\n  다음 실행까지: {seconds_until/86400:.1f}일")
        print(f"  다음 실행: {target_time.strftime('%Y-%m-%d %H:%M')}")

        # 1 시간마다 체크
        check_interval = 3600
        for _ in range(int(seconds_until / check_interval) + 1):
            time.sleep(check_interval)
            if datetime.datetime.now() >= target_time:
                break

        # 실행
        run_once()


# ═══════════════════════════════════════════════════════════════
# CLI
# ═══════════════════════════════════════════════════════════════

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="ARK 관찰 보고서 스케줄러")
    parser.add_argument(
        "--daily",
        action="store_true",
        help="매일 자동 실행 (장 마감 후)"
    )
    parser.add_argument(
        "--weekly",
        action="store_true",
        help="매주 자동 실행 (금요일 장 마감 후)"
    )
    parser.add_argument(
        "--once",
        action="store_true",
        help="단일 실행 (즉시)"
    )

    args = parser.parse_args()

    if args.daily:
        run_daily_scheduler()
    elif args.weekly:
        run_weekly_scheduler()
    elif args.once:
        run_once()
    else:
        # 기본: 단일 실행
        run_once()
