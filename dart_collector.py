"""
DART(전자공시) 데이터 수집기
금융감독원 OpenDART API를 활용해 재무제표 + 공시 정보를 수집한다.

API 신청: https://opendart.fss.or.kr → 개발자센터 → 인증키 신청
"""

import os
import sys
import io
import zipfile
import datetime
import time
import xml.etree.ElementTree as ET

if sys.stdout.encoding != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

import requests
import pandas as pd
from dotenv import dotenv_values

# .env 로드
_env_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), '.env')
_cfg = dotenv_values(_env_path)

DART_API_KEY = os.environ.get("DART_API_KEY") or _cfg.get("DART_API_KEY", "")
BASE_URL = "https://opendart.fss.or.kr/api"

# ──────────────────────────────────────────────
# 종목코드 → DART 고유번호(corp_code) 매핑
# ──────────────────────────────────────────────

def build_corp_code_map(api_key: str) -> dict:
    """
    DART에서 전체 기업 고유번호 ZIP을 다운받아
    {종목코드: corp_code} 딕셔너리를 반환한다.
    """
    print("  DART 기업 코드 목록 다운로드 중...")
    url = f"{BASE_URL}/corpCode.xml?crtfc_key={api_key}"
    resp = requests.get(url, timeout=30)
    resp.raise_for_status()

    # ZIP 안의 XML 파싱
    with zipfile.ZipFile(io.BytesIO(resp.content)) as zf:
        xml_data = zf.read("CORPCODE.xml")

    root = ET.fromstring(xml_data)
    mapping = {}
    for item in root.findall("list"):
        stock_code = item.findtext("stock_code", "").strip()
        corp_code  = item.findtext("corp_code", "").strip()
        if stock_code:  # 상장 종목만
            mapping[stock_code] = corp_code

    print(f"  ✓ {len(mapping):,}개 상장 종목 코드 매핑 완료")
    return mapping


# ──────────────────────────────────────────────
# 최근 공시 목록 조회
# ──────────────────────────────────────────────

def get_recent_disclosures(corp_code: str, api_key: str, days: int = 90) -> list:
    """
    특정 기업의 최근 N일간 공시 목록을 가져온다.
    주가에 영향을 주는 공시 유형 필터링 포함.
    """
    end_dt   = datetime.date.today()
    start_dt = end_dt - datetime.timedelta(days=days)

    url = f"{BASE_URL}/list.json"
    params = {
        "crtfc_key": api_key,
        "corp_code": corp_code,
        "bgn_de": start_dt.strftime("%Y%m%d"),
        "end_de": end_dt.strftime("%Y%m%d"),
        "page_count": 40,
    }
    try:
        resp = requests.get(url, params=params, timeout=15)
        data = resp.json()
        if data.get("status") != "000":
            return []

        items = data.get("list", [])
        # 주가 영향 공시만 필터 (전체 반환 후 분석에서 필터)
        important_keywords = [
            "유상증자", "무상증자", "자기주식", "전환사채", "신주인수권",
            "합병", "분할", "주요사항", "영업정지", "불성실공시",
            "대규모내부거래", "최대주주", "임원", "배당",
        ]
        result = []
        for item in items:
            title = item.get("report_nm", "")
            result.append({
                "접수일": item.get("rcept_dt", ""),
                "공시유형": item.get("pblntf_ty", ""),
                "제목": title,
                "중요도": "★" if any(kw in title for kw in important_keywords) else "",
                "공시링크": f"https://dart.fss.or.kr/dsaf001/main.do?rcpNo={item.get('rcept_no','')}",
            })
        return result
    except Exception as e:
        return [{"오류": str(e)}]


# ──────────────────────────────────────────────
# 재무제표 조회
# ──────────────────────────────────────────────

def get_financial_statements(corp_code: str, api_key: str, year: int = None) -> dict:
    """
    최근 연간 재무제표를 가져온다.
    매출액, 영업이익, 당기순이익, 부채비율 등 핵심 지표 추출.
    """
    # 연도 후보: 올해-1 → 올해-2 순으로 시도 (사업보고서는 3월에 공시)
    current_year = datetime.date.today().year
    year_candidates = [current_year - 1, current_year - 2] if year is None else [year]

    url = f"{BASE_URL}/fnlttSinglAcnt.json"
    data = None
    used_year = None
    used_fs = "CFS"

    try:
        for try_year in year_candidates:
            for fs_div in ["CFS", "OFS"]:
                params = {
                    "crtfc_key": api_key,
                    "corp_code": corp_code,
                    "bsns_year": str(try_year),
                    "reprt_code": "11011",
                    "fs_div": fs_div,
                }
                resp = requests.get(url, params=params, timeout=15)
                d = resp.json()
                if d.get("status") == "000" and d.get("list"):
                    data = d
                    used_year = try_year
                    used_fs = fs_div
                    break
            if data:
                break

        if not data:
            return {"오류": f"재무제표 없음 ({year_candidates}년 모두 없음)"}

        items = data.get("list", [])

        # DART는 account_id 없이 한글 account_nm으로 반환
        # 계정명 → 저장 레이블 매핑 (부분 일치 허용)
        target_accounts_nm = {
            "매출액":           "매출액",
            "수익(매출액)":      "매출액",
            "영업수익":          "매출액",
            "영업이익":          "영업이익",
            "영업이익(손실)":    "영업이익",
            "당기순이익":        "당기순이익",
            "당기순이익(손실)":  "당기순이익",
            "자산총계":          "자산총계",
            "부채총계":          "부채총계",
            "자본총계":          "자본총계",
        }

        financials = {"기준연도": used_year, "재무제표유형": used_fs}
        seen = set()  # 연결/별도 중복 방지 (첫 번째 값만 사용)

        def parse_amount(s: str) -> int:
            """콤마, 공백 제거 후 정수 변환 (음수 포함)"""
            s = s.replace(",", "").replace(" ", "").strip()
            try:
                return int(s)
            except ValueError:
                return 0

        for item in items:
            account_nm = item.get("account_nm", "").strip()
            thstrm_amt = item.get("thstrm_amount", "0")

            if account_nm in target_accounts_nm and account_nm not in seen:
                label = target_accounts_nm[account_nm]
                if label not in financials:   # 첫 번째 값(연결)만 저장
                    val = parse_amount(thstrm_amt)
                    financials[label] = val
                    financials[label + "_억"] = round(val / 1e8, 0)
                    seen.add(account_nm)

        # 부채비율 / 영업이익률 계산
        if "자본총계" in financials and "부채총계" in financials:
            cap = financials["자본총계"]
            dbt = financials["부채총계"]
            if cap > 0:
                financials["부채비율(%)"] = round(dbt / cap * 100, 1)

        if "매출액" in financials and "영업이익" in financials:
            rev = financials["매출액"]
            opr = financials["영업이익"]
            if rev > 0:
                financials["영업이익률(%)"] = round(opr / rev * 100, 1)

        return financials

    except Exception as e:
        return {"오류": str(e)}


# ──────────────────────────────────────────────
# 분기 실적 (최근 4분기)
# ──────────────────────────────────────────────

def get_quarterly_results(corp_code: str, api_key: str) -> list:
    """
    최근 4분기 실적을 가져온다 (분기보고서 기준).
    실적 추세 파악에 활용.
    """
    report_codes = {
        "11013": "1분기보고서",
        "11012": "반기보고서",
        "11014": "3분기보고서",
        "11011": "사업보고서(연간)",
    }
    results = []
    year = datetime.date.today().year

    for reprt_code, reprt_name in report_codes.items():
        for y in [year, year - 1]:
            url = f"{BASE_URL}/fnlttSinglAcnt.json"
            params = {
                "crtfc_key": api_key,
                "corp_code": corp_code,
                "bsns_year": str(y),
                "reprt_code": reprt_code,
                "fs_div": "CFS",
            }
            try:
                resp = requests.get(url, params=params, timeout=10)
                data = resp.json()
                if data.get("status") != "000":
                    continue

                items = data.get("list", [])
                rev = opr = 0
                rev_found = opr_found = False
                for item in items:
                    nm  = item.get("account_nm", "").strip()
                    raw = item.get("thstrm_amount", "0").replace(",", "").replace(" ", "").strip()
                    try: val = int(raw)
                    except: val = 0
                    if not rev_found and nm in ("매출액", "수익(매출액)", "영업수익"):
                        rev = val; rev_found = True
                    if not opr_found and nm in ("영업이익", "영업이익(손실)"):
                        opr = val; opr_found = True

                if rev > 0:
                    results.append({
                        "연도": y,
                        "보고서": reprt_name,
                        "매출액(억)": round(rev / 1e8, 0),
                        "영업이익(억)": round(opr / 1e8, 0),
                        "영업이익률(%)": round(opr / rev * 100, 1) if rev > 0 else 0,
                    })
                    if len(results) >= 4:
                        return results
            except:
                continue
            time.sleep(0.2)
    return results


# ──────────────────────────────────────────────
# 메인: 종목 리스트 전체 DART 데이터 수집
# ──────────────────────────────────────────────

def collect_dart_data(stock_codes: list, api_key: str = None) -> dict:
    """
    여러 종목의 DART 데이터를 한번에 수집한다.
    반환: {종목코드: {공시, 재무제표, 분기실적}}
    """
    key = api_key or DART_API_KEY
    if not key:
        print("❌ DART API 키가 없습니다. .env에 DART_API_KEY를 추가하세요.")
        return {}

    print("\n" + "=" * 60)
    print("  DART 공시/재무 데이터 수집 시작")
    print("=" * 60)

    # 1. 종목코드 → corp_code 매핑 구축
    corp_map = build_corp_code_map(key)

    results = {}
    for code in stock_codes:
        # ".KS" 제거
        clean_code = code.replace(".KS", "").replace(".KQ", "").strip()
        corp_code = corp_map.get(clean_code)

        if not corp_code:
            print(f"  [경고] {clean_code}: DART 기업코드 없음 (비상장 또는 코드 오류)")
            continue

        print(f"\n  [{clean_code}] 수집 중...")

        # 2. 최근 공시
        print(f"    → 최근 공시 조회...", end=" ")
        disclosures = get_recent_disclosures(corp_code, key, days=90)
        print(f"{len(disclosures)}건")
        time.sleep(0.3)

        # 3. 연간 재무제표
        print(f"    → 재무제표 조회...", end=" ")
        financials = get_financial_statements(corp_code, key)
        print("완료" if "오류" not in financials else f"실패({financials['오류']})")
        time.sleep(0.3)

        # 4. 분기 실적
        print(f"    → 분기 실적 조회...", end=" ")
        quarterly = get_quarterly_results(corp_code, key)
        print(f"{len(quarterly)}분기")
        time.sleep(0.3)

        results[clean_code] = {
            "corp_code":    corp_code,
            "최근공시":     disclosures[:10],       # 최근 10건
            "중요공시":     [d for d in disclosures if d.get("중요도") == "★"],
            "재무제표":     financials,
            "분기실적":     quarterly,
        }

    return results


def print_dart_summary(dart_data: dict, stock_names: dict = None):
    """DART 수집 결과를 보기 좋게 출력한다."""
    stock_names = stock_names or {}

    for code, data in dart_data.items():
        name = stock_names.get(code, code)
        print(f"\n{'='*60}")
        print(f"  {name} ({code})")
        print(f"{'='*60}")

        # 재무제표
        fin = data.get("재무제표", {})
        if "오류" not in fin:
            print(f"\n  [재무제표 - {fin.get('기준연도')}년 {fin.get('재무제표유형','')}]")
            for k in ["매출액_억", "영업이익_억", "당기순이익_억", "부채비율(%)", "영업이익률(%)"]:
                if k in fin:
                    print(f"    {k:20s}: {fin[k]:>12,.1f}")

        # 분기 실적 추세
        quarterly = data.get("분기실적", [])
        if quarterly:
            print(f"\n  [분기 실적 추세]")
            print(f"    {'연도':>6} {'보고서':16} {'매출(억)':>10} {'영업이익(억)':>12} {'이익률':>6}")
            print(f"    {'-'*55}")
            for q in quarterly:
                print(f"    {q['연도']:>6} {q['보고서']:16} "
                      f"{q['매출액(억)']:>10,.0f} {q['영업이익(억)']:>12,.0f} "
                      f"{q['영업이익률(%)']:>5.1f}%")

        # 중요 공시
        important = data.get("중요공시", [])
        if important:
            print(f"\n  [중요 공시 ★ - 최근 90일]")
            for d in important[:5]:
                print(f"    {d['접수일']}  {d['제목']}")
                print(f"             {d['공시링크']}")
        else:
            print(f"\n  [중요 공시] 최근 90일간 없음")

        # 일반 공시 건수
        total = len(data.get("최근공시", []))
        print(f"\n  전체 공시 {total}건 (최근 90일)")


def save_dart_to_csv(dart_data: dict, stock_names: dict = None):
    """재무제표 데이터를 CSV로 저장한다."""
    stock_names = stock_names or {}
    rows = []
    for code, data in dart_data.items():
        fin = data.get("재무제표", {})
        if "오류" in fin:
            continue
        row = {"코드": code, "종목명": stock_names.get(code, code)}
        row.update({k: v for k, v in fin.items()
                    if not k.endswith("_억") and k not in ["기준연도", "재무제표유형"]})
        rows.append(row)

    if rows:
        df = pd.DataFrame(rows)
        fname = f"dart_financial_{datetime.datetime.now().strftime('%Y%m%d_%H%M')}.csv"
        df.to_csv(fname, index=False, encoding="utf-8-sig")
        print(f"\n💾 재무제표 CSV 저장: {fname}")


# ──────────────────────────────────────────────
# 실행
# ──────────────────────────────────────────────
if __name__ == "__main__":
    # data_collector.py의 WATCHLIST 가져오기
    from data_collector import WATCHLIST

    if not DART_API_KEY:
        print("❌ DART_API_KEY가 .env에 없습니다.")
        print("   1. https://opendart.fss.or.kr 접속")
        print("   2. 개발자센터 → 인증키 신청/관리")
        print("   3. .env 파일에 DART_API_KEY=발급받은키 추가")
    else:
        # 수집 대상 (전체 또는 일부)
        target_codes = list(WATCHLIST.keys())

        # 필요시 일부만: target_codes = ["005930", "000660", "035420"]

        dart_data = collect_dart_data(target_codes, DART_API_KEY)

        if dart_data:
            print_dart_summary(dart_data, WATCHLIST)
            save_dart_to_csv(dart_data, WATCHLIST)
            print(f"\n총 {len(dart_data)}개 종목 DART 데이터 수집 완료")
