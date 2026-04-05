#!/bin/bash
# Docker 빌드 스크립트
# vc_investment_analyzer를 빌드 컨텍스트에 복사 후 이미지 생성

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
ANALYZER_SRC="${SCRIPT_DIR}/../vc_investment_analyzer"

echo "=== vc_investment_analyzer 복사 ==="
rm -rf "${SCRIPT_DIR}/vc_investment_analyzer"
cp -r "${ANALYZER_SRC}" "${SCRIPT_DIR}/vc_investment_analyzer"

# 불필요한 파일 제거
rm -rf "${SCRIPT_DIR}/vc_investment_analyzer/.git"
rm -rf "${SCRIPT_DIR}/vc_investment_analyzer/__pycache__"
rm -rf "${SCRIPT_DIR}/vc_investment_analyzer/.venv"

echo "=== Docker 이미지 빌드 ==="
docker compose build

echo "=== 임시 복사본 정리 ==="
rm -rf "${SCRIPT_DIR}/vc_investment_analyzer"

echo ""
echo "=== 빌드 완료 ==="
echo "실행: docker compose up -d"
echo "접속: http://<서버IP>:3000/run"
