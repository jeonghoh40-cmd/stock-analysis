@echo off
REM ──────────────────────────────────────────────────────────────
REM  AI 주식 스크리닝 v4 — 자동 실행 배치 (Task Scheduler 전용)
REM  실행 흐름:
REM    ① investor_scorer.py  — Pelosi/ARK/국내투자자 라이브 캐시 갱신
REM    ② stock_advisor_v4.py — 기술+펀더멘털+Fear&Greed 종합 분석
REM  로그: logs\daily_YYYYMMDD.log
REM ──────────────────────────────────────────────────────────────

chcp 65001 > nul
set PYTHONPATH=%~dp0
set "SCRIPT_DIR=%~dp0"
set "PYTHON=C:\Python314\python.exe"

REM ── 날짜 포맷 (YYYYMMDD) ──────────────────────────────────────
for /f "tokens=1-3 delims=-" %%a in ('powershell -NoProfile -Command "Get-Date -Format yyyy-MM-dd"') do (
    set DATESTAMP=%%a%%b%%c
)

REM ── 로그 폴더 생성 ────────────────────────────────────────────
if not exist "%SCRIPT_DIR%logs" mkdir "%SCRIPT_DIR%logs"
set "LOG=%SCRIPT_DIR%logs\daily_%DATESTAMP%.log"

echo. >> "%LOG%"
echo ======================================== >> "%LOG%"
echo [%DATE% %TIME%] AI 주식 스크리닝 v4 시작 >> "%LOG%"
echo ======================================== >> "%LOG%"

REM ── ① 투자자 라이브 데이터 캐시 갱신 ────────────────────────
echo [%TIME%] Step 1: 투자자 데이터 캐시 갱신... >> "%LOG%"
"%PYTHON%" "%SCRIPT_DIR%investor_scorer.py" >> "%LOG%" 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo [%TIME%] WARNING: investor_scorer.py 오류 (계속 진행) >> "%LOG%"
)

REM ── ① ARK 라이브 데이터 강제 갱신 ──────────────────────────
echo [%TIME%] Step 1b: ARK/Pelosi 라이브 캐시 갱신... >> "%LOG%"
"%PYTHON%" -c "from investor_scorer import refresh_live_data; refresh_live_data()" >> "%LOG%" 2>&1

REM ── ② 주식 분석 v4 실행 ──────────────────────────────────────
echo [%TIME%] Step 2: stock_advisor_v4 분석 시작... >> "%LOG%"
"%PYTHON%" -c "import stock_advisor_v4; stock_advisor_v4.main()" >> "%LOG%" 2>&1

if %ERRORLEVEL% EQU 0 (
    echo [%TIME%] 완료 — report_v4.txt 생성됨 >> "%LOG%"
) else (
    echo [%TIME%] ERROR: stock_advisor_v4 실행 오류 (코드: %ERRORLEVEL%) >> "%LOG%"
)

echo ======================================== >> "%LOG%"
echo [%DATE% %TIME%] 전체 완료 >> "%LOG%"
echo ======================================== >> "%LOG%"
