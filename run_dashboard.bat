@echo off
REM ──────────────────────────────────────────────────────────────
REM  Streamlit 대시보드 실행
REM  더블클릭 → 브라우저 자동 열림 (http://localhost:8501)
REM ──────────────────────────────────────────────────────────────
chcp 65001 > nul
cd /d "%~dp0"

echo 대시보드 시작 중... (브라우저가 자동으로 열립니다)
echo 종료하려면 이 창을 닫으세요.
echo.

"C:\Program Files\PostgreSQL\17\pgAdmin 4\python\python.exe" -m streamlit run dashboard.py --server.headless false --browser.gatherUsageStats false
pause
