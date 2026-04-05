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
import os
import subprocess
import sys
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
    rc = run_step("Step 1/2: IR 텍스트 추출", extract_args, ANALYZER_ROOT)
    if rc != 0:
        print(f"\n[ERROR] IR 추출 실패 (exit code: {rc})")
        sys.exit(rc)

    # Step 2: 투심위 보고서 생성
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

    rc = run_step("Step 2/2: 투심위 보고서 생성", report_args, ANALYZER_ROOT)
    if rc != 0:
        print(f"\n[ERROR] 보고서 생성 실패 (exit code: {rc})")
        sys.exit(rc)

    print(f"\n{'='*60}")
    print(f"  완료! 보고서 저장 위치: {output_dir}")
    print(f"{'='*60}")


if __name__ == "__main__":
    main()
