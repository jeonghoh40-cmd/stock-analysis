"""IR 추출 + 투자검토보고서 생성 래퍼 스크립트.

display_setting 프론트엔드에서 호출되며,
vc_investment_analyzer의 기능을 순차적으로 실행한다.

사용법:
  python scripts/run_analysis.py --company "Pixxel" \
    --ir-dir "V:\\DEPT\\...\\Pixxel" \
    --output-dir "C:\\Users\\geunho\\vc_investment_analyzer\\reports\\ic_reports" \
    [--no-web] [--no-api]
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path

def find_analyzer_root() -> Path:
    """vc_investment_analyzer 또는 vc-investment-analyzer 디렉토리를 찾는다."""
    if os.environ.get("ANALYZER_ROOT"):
        return Path(os.environ["ANALYZER_ROOT"])

    base = Path(__file__).resolve().parent.parent.parent
    for name in ["vc_investment_analyzer", "vc-investment-analyzer"]:
        candidate = base / name
        if candidate.is_dir():
            return candidate

    # fallback
    return base / "vc_investment_analyzer"

ANALYZER_ROOT = find_analyzer_root()

DEFAULT_CODES = {
    "sector": [],
    "stage": "UNKNOWN",
    "founder_grade": "FOUNDER_UNKNOWN",
    "market_grade": "UNKNOWN",
    "market_position": "POS_STARTUP",
    "global_expansion": "UNKNOWN",
    "era": "ERA_AI",
    "urgency_grade": "UNKNOWN",
    "tech_listing": "UNKNOWN",
    "vc_liquidity": "LIQUIDITY_NORMAL",
}


def run_step(label: str, args: list[str], cwd: Path) -> int:
    print(f"\n{'='*60}")
    print(f"  [{label}]")
    print(f"  명령: {' '.join(args)}")
    print(f"{'='*60}\n", flush=True)

    proc = subprocess.Popen(
        args,
        cwd=str(cwd),
        stdout=sys.stdout,
        stderr=sys.stderr,
        encoding="utf-8",
        errors="replace",
    )
    proc.wait()
    return proc.returncode


def ensure_codes_json(company: str, analysis_dir: Path) -> Path:
    """codes.json이 없으면 기본 분류 코드를 생성한다."""
    codes_path = analysis_dir / "codes.json"

    if codes_path.exists():
        print(f"  codes.json 이미 존재: {codes_path}")
        return codes_path

    # IR 텍스트가 있으면 읽어서 Claude API로 분류 시도
    ir_path = analysis_dir / "ir_text.md"
    codes = dict(DEFAULT_CODES)

    if ir_path.exists():
        try:
            import anthropic

            ir_text = ir_path.read_text(encoding="utf-8")[:25000]
            client = anthropic.Anthropic()
            response = client.messages.create(
                model="claude-sonnet-4-20250514",
                max_tokens=1024,
                temperature=0,
                system="IR 자료를 분석하여 투자 분류 코드를 JSON으로 반환하세요. 반드시 유효한 JSON만 반환.",
                messages=[{
                    "role": "user",
                    "content": f"""아래 IR 자료를 읽고 분류 코드를 JSON으로 반환하세요. 근거가 불충분하면 보수적으로(낮은 등급) 판정하세요.

판정 기준:
- sector: 복수 선택. ["SW","DEEPTECH","BIO","HEALTHCARE","COMMERCE","FOOD","PLATFORM","LOGISTICS","O2O","CONTENT","AI","FINTECH","ENERGY","MANUFACTURING","GLOBAL","ENTERTAINMENT","SECURITY","MOBILITY","AGRITECH","PROPTECH","EDTECH","GAMING","HARDWARE"]
- stage: IR에 명시된 투자 라운드 기준. "Seed/Pre-A"(시드~Pre-A), "Series-A", "Series-B", "Series-C+", "Pre-IPO"(상장 직전), "Growth". 명시되지 않으면 임직원수/매출 규모로 추정.
- founder_grade: "FOUNDER_A"(교수/박사+10년 이상 도메인 전문가, 연쇄창업 성공, 글로벌 기업 임원 출신), "FOUNDER_B"(관련 분야 경력 보유, 일반적 수준), "FOUNDER_C"(경력 부족/신입). IR에서 경력이 명확히 드러나지 않으면 FOUNDER_B로 판정.
- market_grade: "MARKET_S"(TAM 1조원+ 글로벌 메가 트렌드), "MARKET_A"(수천억 이상 구조적 성장), "MARKET_B"(수백억 규모 또는 니치), "MARKET_C"(소규모)
- market_position: "POS_1ST"(매출/점유율 1위 또는 유일한 기업), "POS_CREATING"(기존에 없던 새로운 카테고리를 창출하는 기업. 반드시 IR에서 '최초', '신시장', '새로운 카테고리' 등이 명확해야 함), "POS_CONTENDER"(시장에 경쟁자가 있고 상위권에 위치), "POS_FOLLOWER"(후발주자), "POS_STARTUP"(아직 시장 포지션이 불명확한 초기 스타트업). 근거가 불충분하면 POS_STARTUP으로 판정.
- global_expansion: "GLOBAL_BORN"(해외 매출 50% 이상), "GLOBAL_READY"(해외 진출 준비 완료, 구체적 계획), "GLOBAL_ACTIVE"(해외 사업 진행 중), "GLOBAL_DOMESTIC"(국내 중심, 해외 계획 불명확)
- era: "ERA_AI" (현재 고정)
- urgency_grade: "STABLE"(런웨이 18개월+), "CAUTION"(런웨이 12개월+), "WARNING"(런웨이 부족). 재무 정보 없으면 "CAUTION".
- tech_listing: "TECH_LISTED"(기술특례 상장 완료), "TECH_ELIGIBLE"(기술특례 상장 가능성 있음), "TECH_NOT_ELIGIBLE"(해당 없음)
- vc_liquidity: "LIQUIDITY_TIGHT"(VC 시장 위축기), "LIQUIDITY_NORMAL"(일반적)

IR 자료:
{ir_text}

JSON만 반환:""",
                }],
            )

            raw = response.content[0].text.strip()
            if raw.startswith("```"):
                lines = raw.split("\n")
                lines = [l for l in lines if not l.strip().startswith("```")]
                raw = "\n".join(lines)

            parsed = json.loads(raw)
            # 유효한 키만 병합
            for k in DEFAULT_CODES:
                if k in parsed:
                    codes[k] = parsed[k]

            print(f"  Claude API로 분류 코드 자동 생성 완료")
            print(f"  sector: {codes.get('sector')}")
            print(f"  stage: {codes.get('stage')}")

        except ImportError:
            print("  [WARN] anthropic 패키지 없음. 기본 코드 사용.")
        except Exception as e:
            print(f"  [WARN] 자동 분류 실패, 기본 코드 사용: {e}")

    with open(codes_path, "w", encoding="utf-8") as f:
        json.dump(codes, f, ensure_ascii=False, indent=2)

    print(f"  codes.json 저장: {codes_path}")
    return codes_path


def ensure_analysis_json(company: str, analysis_dir: Path, ir_dir: Path) -> None:
    """analysis.json이 없으면 최소한의 기본 데이터를 생성한다."""
    aj_path = analysis_dir / "analysis.json"
    if aj_path.exists():
        print(f"  analysis.json 이미 존재: {aj_path}")
        return

    ir_files = []
    if ir_dir.is_dir():
        ir_files = [f.name for f in ir_dir.iterdir() if f.is_file() and not f.name.startswith("~")]

    # codes.json이 있으면 읽어서 classification에 반영
    codes_path = analysis_dir / "codes.json"
    codes = dict(DEFAULT_CODES)
    if codes_path.exists():
        with open(codes_path, encoding="utf-8") as f:
            codes = json.load(f)

    analysis = {
        "company": {"name": company, "total_name": company},
        "classification": {
            "sector": codes.get("sector", []),
            "investment_era": codes.get("era", "ERA_AI"),
            "investment_stage": codes.get("stage", "UNKNOWN"),
            "founder_grade": codes.get("founder_grade", "FOUNDER_UNKNOWN"),
            "market_grade": codes.get("market_grade", "UNKNOWN"),
            "market_position": codes.get("market_position", "UNKNOWN"),
            "global_expansion": codes.get("global_expansion", "UNKNOWN"),
            "vc_liquidity": codes.get("vc_liquidity", "UNKNOWN"),
            "tech_listing": codes.get("tech_listing", "UNKNOWN"),
        },
        "investment": {
            "investment_date": datetime.now().strftime("%Y-%m-%d"),
            "total_invested_krw": 0,
        },
        "ir_source": {
            "folder": str(ir_dir),
            "files": ir_files,
            "extracted_at": datetime.now().isoformat(),
        },
        "_auto_generated": True,
    }

    with open(aj_path, "w", encoding="utf-8") as f:
        json.dump(analysis, f, ensure_ascii=False, indent=2)
    print(f"  analysis.json 자동 생성: {aj_path}")


def copy_latest_report(pattern: str, output_dir: Path, label: str) -> bool:
    """reports 디렉토리에서 최신 보고서를 output_dir로 복사한다."""
    import shutil
    import time

    reports_dir = ANALYZER_ROOT / "reports"
    ic_reports_dir = reports_dir / "ic_reports"

    # reports/ 와 reports/ic_reports/ 모두 검색
    candidates = list(reports_dir.glob(pattern)) + list(ic_reports_dir.glob(pattern))
    if not candidates:
        print(f"\n  [WARN] {label} 파일을 찾지 못했습니다.")
        return False

    for f in sorted(candidates, key=lambda x: x.stat().st_mtime, reverse=True):
        dest = output_dir / f.name
        for attempt in range(5):
            try:
                time.sleep(1)
                shutil.copy2(f, dest)
                print(f"\n  {label} 복사: {dest}")
                return True
            except PermissionError:
                print(f"  파일 복사 재시도 ({attempt + 1}/5)...")
        break

    return False


def main():
    parser = argparse.ArgumentParser(description="IR 추출 + 보고서 생성")
    parser.add_argument("--company", required=True, help="기업명")
    parser.add_argument("--ir-dir", required=True, help="IR 자료 디렉토리 경로")
    parser.add_argument("--output-dir", required=True, help="리포트 저장 경로")
    parser.add_argument("--report-type", default="both",
                        choices=["investment", "ic", "both"],
                        help="보고서 유형: investment(투자검토), ic(투심위), both(둘 다)")
    parser.add_argument("--no-web", action="store_true", help="웹 조사 건너뛰기")
    parser.add_argument("--no-api", action="store_true", help="Claude API 미사용")
    args = parser.parse_args()

    ir_dir = Path(args.ir_dir)
    output_dir = Path(args.output_dir)
    company = args.company
    report_type = args.report_type

    if not ir_dir.is_dir():
        print(f"[ERROR] IR 디렉토리가 존재하지 않습니다: {ir_dir}")
        sys.exit(1)

    output_dir.mkdir(parents=True, exist_ok=True)

    # 분석 결과 저장 디렉토리 (기존 데이터 정리 후 새로 생성)
    analysis_out = ANALYZER_ROOT / "data" / "analysis" / company
    if analysis_out.exists():
        import shutil
        for old_file in ["ir_text.md", "analysis.json", "codes.json"]:
            old_path = analysis_out / old_file
            if old_path.exists():
                old_path.unlink()
                print(f"  기존 파일 정리: {old_file}")
    analysis_out.mkdir(parents=True, exist_ok=True)

    # 단계 수 계산
    gen_investment = report_type in ("investment", "both")
    gen_ic = report_type in ("ic", "both")
    total_steps = 4 + (1 if gen_investment else 0) + (1 if gen_ic else 0)
    step = 0

    # Step 1: IR 텍스트 추출
    step += 1
    extract_args = [
        sys.executable,
        "-m", "src.parser.ir_extractor",
        "--folder", str(ir_dir),
        "--company", company,
        "--output", str(analysis_out),
    ]
    rc = run_step(f"Step {step}/{total_steps}: IR 텍스트 추출", extract_args, ANALYZER_ROOT)
    if rc != 0:
        print(f"\n[ERROR] IR 추출 실패 (exit code: {rc})")
        sys.exit(rc)

    # Step 2: 분류 코드 생성
    step += 1
    print(f"\n{'='*60}")
    print(f"  [Step {step}/{total_steps}: 분류 코드 생성]")
    print(f"{'='*60}\n", flush=True)
    codes_path = ensure_codes_json(company, analysis_out)

    # Step 3: 구조화 데이터 추출 (enriched_analysis.json)
    step += 1
    print(f"\n{'='*60}")
    print(f"  [Step {step}/{total_steps}: 구조화 데이터 추출]")
    print(f"{'='*60}\n", flush=True)
    enriched_path = None
    ir_text_file = analysis_out / "ir_text.md"
    if ir_text_file.exists():
        try:
            sys.path.insert(0, str(ANALYZER_ROOT))
            from src.extraction.structured_extractor import extract_and_save
            enriched_path = extract_and_save(company, ir_text_file, analysis_out)
        except Exception as e:
            print(f"  [WARN] 구조화 데이터 추출 실패: {e}")
    else:
        print(f"  [WARN] IR 텍스트 파일 없음, 건너뜀")

    # Step 4: analysis.json 생성
    step += 1
    print(f"\n{'='*60}")
    print(f"  [Step {step}/{total_steps}: 분석 데이터 생성]")
    print(f"{'='*60}\n", flush=True)
    ensure_analysis_json(company, analysis_out, ir_dir)

    # Step 4: 투자검토보고서 생성
    if gen_investment:
        step += 1
        gen_report_path = ANALYZER_ROOT / "scripts" / "gen_report.py"
        ir_text_path = analysis_out / "ir_text.md"
        report_args = [
            sys.executable,
            str(gen_report_path),
            "--company", company,
            "--codes", str(codes_path),
        ]
        if ir_text_path.exists():
            report_args.extend(["--ir-text", str(ir_text_path)])
        enriched_file = analysis_out / "enriched_analysis.json"
        if enriched_file.exists():
            report_args.extend(["--enriched-data", str(enriched_file)])
        rc = run_step(f"Step {step}/{total_steps}: 투자검토보고서 생성", report_args, ANALYZER_ROOT)
        if rc != 0:
            print(f"\n[ERROR] 투자검토보고서 생성 실패 (exit code: {rc})")
            sys.exit(rc)

    # Step 5: 투심위보고서 생성
    if gen_ic:
        step += 1
        ic_args = [
            sys.executable,
            "-m", "scripts.batch_ic_report",
            "--company", company,
        ]
        if args.no_web:
            ic_args.append("--no-web")
        if args.no_api:
            ic_args.append("--no-api")

        rc = run_step(f"Step {step}/{total_steps}: 투심위보고서 생성", ic_args, ANALYZER_ROOT)
        if rc != 0:
            print(f"\n[ERROR] 투심위보고서 생성 실패 (exit code: {rc})")
            sys.exit(rc)

    # 생성된 보고서를 output_dir로 복사
    copied_any = False
    if gen_investment:
        if copy_latest_report(f"{company}_투자검토보고서_*.docx", output_dir, "투자검토보고서"):
            copied_any = True
    if gen_ic:
        if copy_latest_report(f"{company}_투심위보고서_*.docx", output_dir, "투심위보고서"):
            copied_any = True

    if not copied_any:
        print(f"\n  [WARN] 생성된 보고서 파일을 찾지 못했습니다.")

    print(f"\n{'='*60}")
    print(f"  완료! 보고서 저장 위치: {output_dir}")
    print(f"{'='*60}")


if __name__ == "__main__":
    main()
