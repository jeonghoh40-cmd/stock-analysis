#!/bin/bash
# ─────────────────────────────────────────────────────────────
# AI 주식 스크리닝 — 매일 06:30 자동 실행 cron 등록 스크립트
# 실행 방법: bash setup_schedule.sh
# ─────────────────────────────────────────────────────────────

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PYTHON_SCRIPT="$SCRIPT_DIR/stock_advisor.py"
LOG_FILE="$SCRIPT_DIR/analysis.log"

echo "📦 필요한 패키지 설치 중..."
pip3 install -r "$SCRIPT_DIR/requirements.txt" --quiet --break-system-packages 2>/dev/null || \
pip install -r "$SCRIPT_DIR/requirements.txt" --quiet --break-system-packages 2>/dev/null

echo "✅ 패키지 설치 완료"

# Python 경로 자동 감지
PYTHON_PATH=$(which python3 || which python)
echo "🐍 Python 경로: $PYTHON_PATH"

# .env 존재 확인
if [ ! -f "$SCRIPT_DIR/.env" ]; then
    echo ""
    echo "⚠️  .env 파일이 없습니다!"
    echo "   copy .env.example .env  (Windows)"
    echo "   cp .env.example .env    (Mac/Linux)"
    echo "   그 후 .env 파일에 API 키를 입력하세요."
    exit 1
fi

# cron 작업 설정 (매일 오전 6시 30분 → 7시 전 완료)
CRON_JOB="30 6 * * * $PYTHON_PATH \"$PYTHON_SCRIPT\" >> \"$LOG_FILE\" 2>&1"

# 기존 동일 작업 제거 후 새로 추가
(crontab -l 2>/dev/null | grep -v "stock_advisor.py"; echo "$CRON_JOB") | crontab -

echo ""
echo "✅ cron 스케줄 등록 완료!"
echo "   ⏰ 매일 오전 6시 30분 자동 실행 → 7시 전 완료"
echo "   📄 스크립트: $PYTHON_SCRIPT"
echo "   📝 로그 파일: $LOG_FILE"
echo ""
echo "현재 등록된 cron 작업:"
crontab -l | grep stock_advisor
echo ""
echo "─────────────────────────────────────"
echo "📌 지금 바로 테스트 실행하려면:"
echo "   python3 \"$PYTHON_SCRIPT\""
echo "─────────────────────────────────────"
