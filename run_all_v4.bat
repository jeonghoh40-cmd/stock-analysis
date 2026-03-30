@echo off
chcp 65001 > nul
set "PYTHONPATH=%~dp0"
set "SCRIPT_DIR=%~dp0"
set "LOG_FILE=%SCRIPT_DIR%logs\analysis_%date:~0,4%%date:~5,2%%date:~8,2%.log"

REM logs 폴더 생성 (없으면)
if not exist "%SCRIPT_DIR%logs" mkdir "%SCRIPT_DIR%logs"

echo [%date% %time%] 전체분석 시작 >> "%LOG_FILE%"
echo Starting stock analysis v4 (ATR + Stochastic + ADX + OBV + Fundamental + Fear^&Greed)
echo ===========================================================================

echo [1/3] investor_scorer.py - Pelosi / ARK / Korean investor scoring...
echo [%date% %time%] [1/3] investor_scorer 시작 >> "%LOG_FILE%"
"C:\Program Files\PostgreSQL\17\pgAdmin 4\python\python.exe" "%~dp0investor_scorer.py" >> "%LOG_FILE%" 2>&1

echo [2/3] Refreshing live investor data cache...
echo [%date% %time%] [2/3] live investor cache 갱신 시작 >> "%LOG_FILE%"
"C:\Program Files\PostgreSQL\17\pgAdmin 4\python\python.exe" -c "import sys; sys.path.insert(0, r'%~dp0'); from investor_scorer import refresh_live_data; refresh_live_data()" >> "%LOG_FILE%" 2>&1

echo [3/3] stock_advisor_v4.py - Full analysis (Technical + Fundamental + Macro)...
echo [%date% %time%] [3/3] stock_advisor_v4 시작 >> "%LOG_FILE%"
"C:\Program Files\PostgreSQL\17\pgAdmin 4\python\python.exe" -c "import sys; sys.path.insert(0, r'%~dp0'); import stock_advisor_v4; stock_advisor_v4.main()" >> "%LOG_FILE%" 2>&1

echo [%date% %time%] 전체분석 완료 >> "%LOG_FILE%"
echo.
echo ========================================
echo v4 Analysis Complete. Report: report_v4.txt
echo Log: %LOG_FILE%
echo ========================================

REM 대시보드 자동 실행 (이미 켜져 있으면 스킵, 아니면 새로 시작)
echo.
echo [대시보드] 포트 8501 확인 중...
netstat -ano | findstr ":8501" | findstr "LISTENING" > nul 2>&1
if %errorlevel% == 0 (
    echo [대시보드] 이미 실행 중 -- http://localhost:8501
) else (
    echo [대시보드] 새로 시작합니다...
    start "" "C:\Program Files\PostgreSQL\17\pgAdmin 4\python\python.exe" -m streamlit run "%SCRIPT_DIR%dashboard.py" --server.headless false --browser.gatherUsageStats false
    echo [대시보드] http://localhost:8501 에서 확인하세요
)
echo.
pause
