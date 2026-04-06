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

ANALYZER_ROOT = Path(
    os.environ.get("ANALYZER_ROOT", Path(__file__).resolve().parent.parent.parent / "vc_investment_analyzer")
)

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

            ir_text = ir_path.read_text(encoding="utf-8")[:10000]
            client = anthropic.Anthropic()
            response = client.messages.create(
                model="claude-sonnet-4-20250514",
                max_tokens=1024,
                system="IR 자료를 분석하여 투자 분류 코드를 JSON으로 반환하세요. 반드시 유효한 JSON만 반환.",
                messages=[{
                    "role": "user",
                    "content": f"""아래 IR 자료를 읽고 분류 코드를 JSON으로 반환하세요.

가능한 값:
- sector: ["SW","DEEPTECH","BIO","HEALTHCARE","COMMERCE","FOOD","PLATFORM","LOGISTICS","O2O","CONTENT","AI","FINTECH","ENERGY","MANUFACTURING","GLOBAL","ENTERTAINMENT","SECURITY","MOBILITY","AGRITECH","PROPTECH","EDTECH","GAMING","HARDWARE"] (복수 선택)
- stage: "Seed/Pre-A", "Series-A", "Series-B", "Series-C+", "Pre-IPO", "Growth"
- founder_grade: "FOUNDER_A"(연쇄창업/업계경력10년+), "FOUNDER_B"(관련경력), "FOUNDER_C"(신입)
- market_grade: "MARKET_S"(글로벌 메가), "MARKET_A"(대규모 구조적 성장), "MARKET_B"(중간), "MARKET_C"(소규모)
- market_position: "POS_1ST", "POS_CONTENDER", "POS_CREATING", "POS_FOLLOWER", "POS_STARTUP"
- global_expansion: "GLOBAL_BORN"(해외매출50%+), "GLOBAL_READY"(해외진출준비), "GLOBAL_ACTIVE"(해외사업진행), "GLOBAL_DOMESTIC"(국내중심)
- era: "ERA_AI"
- urgency_grade: "STABLE", "CAUTION", "WARNING"
- tech_listing: "TECH_LISTED", "TECH_ELIGIBLE", "TECH_NOT_ELIGIBLE"
- vc_liquidity: "LIQUIDITY_TIGHT", "LIQUIDITY_NORMAL"

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


def main():
    parser = argparse.ArgumentParser(description="IR 추출 + 투자검토보고서 생성")
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
    rc = run_step("Step 1/4: IR 텍스트 추출", extract_args, ANALYZER_ROOT)
    if rc != 0:
        print(f"\n[ERROR] IR 추출 실패 (exit code: {rc})")
        sys.exit(rc)

    # Step 2: 분류 코드 생성
    print(f"\n{'='*60}")
    print(f"  [Step 2/4: 분류 코드 생성]")
    print(f"{'='*60}\n", flush=True)
    codes_path = ensure_codes_json(company, analysis_out)

    # Step 3: analysis.json 생성
    print(f"\n{'='*60}")
    print(f"  [Step 3/4: 분석 데이터 생성]")
    print(f"{'='*60}\n", flush=True)
    ensure_analysis_json(company, analysis_out, ir_dir)

    # Step 4: 투자검토보고서 생성 (gen_report.py)
    gen_report_path = ANALYZER_ROOT / "scripts" / "gen_report.py"
    report_args = [
        sys.executable,
        str(gen_report_path),
        "--company", company,
        "--codes", str(codes_path),
    ]
    rc = run_step("Step 4/4: 투자검토보고서 생성", report_args, ANALYZER_ROOT)
    if rc != 0:
        print(f"\n[ERROR] 보고서 생성 실패 (exit code: {rc})")
        sys.exit(rc)

    # 생성된 보고서를 output_dir로 복사
    reports_dir = ANALYZER_ROOT / "reports"
    import shutil
    copied = False
    for f in sorted(reports_dir.glob(f"{company}_투자검토보고서_*.docx"), reverse=True):
        dest = output_dir / f.name
        shutil.copy2(f, dest)
        print(f"\n  보고서 복사: {dest}")
        copied = True
        break

    if not copied:
        print(f"\n  [WARN] 생성된 보고서 파일을 찾지 못했습니다.")

    print(f"\n{'='*60}")
    print(f"  완료! 보고서 저장 위치: {output_dir}")
    print(f"{'='*60}")


if __name__ == "__main__":
    main()
