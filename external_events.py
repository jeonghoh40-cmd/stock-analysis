"""
외부 변수 관리 도구
──────────────────────────────────────────────────────────
정부 정책, 통화정책, 지정학 이슈 등 외부 변수를 등록하면
stock_advisor_v4.py 분석 시 Claude 프롬프트에 자동 반영됩니다.

사용법:
  python external_events.py add    # 대화형으로 이벤트 추가
  python external_events.py list   # 현재 이벤트 목록
  python external_events.py clear  # 만료된 이벤트 삭제

예시:
  python external_events.py add
  > 카테고리: 1 (정부정책)
  > 제목: 증시안정기금 100조원 조성 발표
  > 영향: 1 (강한 매수)
  > 섹터: 증권,금융,전체
"""

import json
import os
import sys
import datetime

EVENTS_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "external_events.json")

CATEGORY_OPTIONS = ["정부정책", "통화정책", "지정학", "경제지표", "기업이슈", "기타"]
IMPACT_OPTIONS   = ["강한 매수", "매수", "중립", "매도", "강한 매도"]


def load_events() -> list:
    if not os.path.exists(EVENTS_FILE):
        return []
    with open(EVENTS_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def save_events(events: list):
    with open(EVENTS_FILE, "w", encoding="utf-8") as f:
        json.dump(events, f, ensure_ascii=False, indent=2)


def get_active_events() -> list:
    """stock_advisor_v4.py에서 호출 — 오늘 이후 만료되지 않은 이벤트만 반환"""
    today = datetime.datetime.now().strftime("%Y-%m-%d")
    return [e for e in load_events() if e.get("expires", "9999-12-31") >= today]


def add_event():
    print("\n── 외부 변수 추가 ──────────────────────────")

    print("카테고리:")
    for i, c in enumerate(CATEGORY_OPTIONS, 1):
        print(f"  {i}. {c}")
    try:
        cat_idx = int(input("선택 (번호): ").strip()) - 1
        category = CATEGORY_OPTIONS[cat_idx] if 0 <= cat_idx < len(CATEGORY_OPTIONS) else "기타"
    except (ValueError, IndexError):
        category = "기타"

    title = input("제목 (예: 증시안정기금 100조원 조성 발표): ").strip()
    if not title:
        print("제목이 비어 있습니다. 취소합니다.")
        return

    description = input("상세 설명 (간략히, 엔터 생략 가능): ").strip()

    print("시장 영향:")
    for i, imp in enumerate(IMPACT_OPTIONS, 1):
        print(f"  {i}. {imp}")
    try:
        imp_idx = int(input("선택 (번호): ").strip()) - 1
        impact = IMPACT_OPTIONS[imp_idx] if 0 <= imp_idx < len(IMPACT_OPTIONS) else "중립"
    except (ValueError, IndexError):
        impact = "중립"

    sectors_input = input("영향 섹터 (쉼표 구분, 예: 금융,증권,전체): ").strip()
    sectors = [s.strip() for s in sectors_input.split(",") if s.strip()]

    try:
        duration_raw = input("유효기간 (일수, 기본 3): ").strip()
        duration_days = int(duration_raw) if duration_raw else 3
    except ValueError:
        duration_days = 3

    event = {
        "id":               datetime.datetime.now().strftime("%Y%m%d%H%M%S"),
        "date":             datetime.datetime.now().strftime("%Y-%m-%d"),
        "expires":          (datetime.datetime.now() + datetime.timedelta(days=duration_days)).strftime("%Y-%m-%d"),
        "category":         category,
        "title":            title,
        "description":      description,
        "impact":           impact,
        "affected_sectors": sectors,
    }

    events = load_events()
    events.append(event)
    save_events(events)

    sectors_str = ", ".join(sectors) if sectors else "미지정"
    print(f"\n[OK] 이벤트 추가됨: [{category}] {title}")
    print(f"     영향: {impact} | 섹터: {sectors_str} | 만료: {event['expires']}")


def list_events():
    events = load_events()
    if not events:
        print("등록된 이벤트가 없습니다.")
        return

    today = datetime.datetime.now().strftime("%Y-%m-%d")
    active  = [e for e in events if e.get("expires", "9999-12-31") >= today]
    expired = [e for e in events if e.get("expires", "9999-12-31") < today]

    if active:
        print(f"\n[ 활성 이벤트 ({len(active)}개) ]")
        for e in active:
            sectors_str = ", ".join(e.get("affected_sectors", [])) or "미지정"
            print(f"  [{e['category']}] {e['title']}")
            print(f"    영향: {e['impact']} | 섹터: {sectors_str} | 만료: {e['expires']}")
            if e.get("description"):
                print(f"    설명: {e['description']}")

    if expired:
        print(f"\n[ 만료 이벤트 ({len(expired)}개) — 'clear' 명령으로 삭제 가능 ]")
        for e in expired:
            print(f"  (만료) [{e['category']}] {e['title']} ({e['expires']})")


def clear_expired():
    events = load_events()
    today  = datetime.datetime.now().strftime("%Y-%m-%d")
    active = [e for e in events if e.get("expires", "9999-12-31") >= today]
    removed = len(events) - len(active)
    save_events(active)
    print(f"[OK] 만료 이벤트 {removed}개 삭제, 활성 이벤트 {len(active)}개 유지")


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "list"

    if cmd == "add":
        add_event()
    elif cmd == "list":
        list_events()
    elif cmd == "clear":
        clear_expired()
    else:
        print(__doc__)
