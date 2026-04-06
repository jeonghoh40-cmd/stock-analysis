"""IR 추출 + 투심위 보고서 생성 래퍼 스크립트.

display_setting 프론트엔드에서 호출되며,
vc_investment_analyzer의 기능을 순차적으로 실행한다.

사용법:
  python scripts/run_analysis.py --company "CSO" \
    --ir-dir "V:\\DEPT\\...\\CSO" \
    --output-dir "C:\\Users\\geunho\\reports" \
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

ANALYZER_ROOT = Path(
    os.environ.get("ANALYZER_ROOT", Path(__file__).resolve().parent.parent.parent / "vc_investment_analyzer")
)


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


def ensure_analysis_json(company: str, analysis_dir: Path, ir_dir: Path) -> None:
    """analysis.json이 없으면 최소한의 기본 데이터를 생성한다.

    batch_ic_report.py가 analysis.json 존재를 필수로 요구하므로,
    IR 텍스트만 있는 신규 기업의 경우 기본 구조를 만들어준다.
    """
    aj_path = analysis_dir / "analysis.json"
    if aj_path.exists():
        print(f"  analysis.json 이미 존재: {aj_path}")
        return

    # IR 폴더에서 파일 목록 수집
    ir_files = []
    if ir_dir.is_dir():
        ir_files = [f.name for f in ir_dir.iterdir() if f.is_file() and not f.name.startswith("~")]

    analysis = {
        "company": {
            "name": company,
            "total_name": company,
        },
        "classification": {
            "sector": [],
            "investment_era": "2024~(AI시대)",
            "investment_stage": "UNKNOWN",
            "founder_grade": "FOUNDER_UNKNOWN",
            "market_grade": "UNKNOWN",
            "market_position": "UNKNOWN",
            "global_expansion": "UNKNOWN",
            "vc_liquidity": "UNKNOWN",
            "tech_listing": "UNKNOWN",
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
        "_note": "IR 텍스트 기반 자동 생성. Claude API가 IR 내용을 분석하여 보고서를 작성합니다.",
    }

    with open(aj_path, "w", encoding="utf-8") as f:
        json.dump(analysis, f, ensure_ascii=False, indent=2)

    print(f"  analysis.json 자동 생성: {aj_path}")


def main():
    parser = argparse.ArgumentParser(description="IR 추출 + 투심위 보고서 생성")
    parser.add_argument("--company", required=True, help="기업명")
    parser.add_argument("--ir-dir", required=True, help="IR 자료 디렉토리 경로")
    parser.add_argument("--output-dir", required=True, help="리포트 저장 경로")
    parser.add_argument("--no-web", action="store_true", help="웹 조사 건너뛰기")
    parser.add_argument("--no-api", action="store_true", help="Claude API 미사용")
    args = parser.parse_args()

    ir_dir = Path(args.ir_dir)
    output_dir = Path(args.output_dir)
    company = args.company

    if not ir_dir.is_dir():
        print(f"[ERROR] IR 디렉토리가 존재하지 않습니다: {ir_dir}")
        sys.exit(1)

    output_dir.mkdir(parents=True, exist_ok=True)

    # 분석 결과 저장 디렉토리
    analysis_out = ANALYZER_ROOT / "data" / "analysis" / company
    analysis_out.mkdir(parents=True, exist_ok=True)

    # Step 1: IR 텍스트 추출
    extract_args = [
        sys.executable,
        "-m", "src.parser.ir_extractor",
        "--folder", str(ir_dir),
        "--company", company,
        "--output", str(analysis_out),
    ]
    rc = run_step("Step 1/3: IR 텍스트 추출", extract_args, ANALYZER_ROOT)
    if rc != 0:
        print(f"\n[ERROR] IR 추출 실패 (exit code: {rc})")
        sys.exit(rc)

    # Step 2: analysis.json 확인/생성
    print(f"\n{'='*60}")
    print(f"  [Step 2/3: 분석 데이터 확인]")
    print(f"{'='*60}\n", flush=True)
    ensure_analysis_json(company, analysis_out, ir_dir)

    # Step 3: 투심위 보고서 생성
    report_args = [
        sys.executable,
        "-m", "scripts.batch_ic_report",
        "--company", company,
        "--output-dir", str(output_dir),
    ]
    if args.no_web:
        report_args.append("--no-web")
    if args.no_api:
        report_args.append("--no-api")

    rc = run_step("Step 3/3: 투심위 보고서 생성", report_args, ANALYZER_ROOT)
    if rc != 0:
        print(f"\n[ERROR] 보고서 생성 실패 (exit code: {rc})")
        sys.exit(rc)

    print(f"\n{'='*60}")
    print(f"  완료! 보고서 저장 위치: {output_dir}")
    print(f"{'='*60}")


if __name__ == "__main__":
    main()
