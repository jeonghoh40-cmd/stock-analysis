@echo off
set PYTHONPATH=%~dp0

echo Starting stock analysis v4 (ATR + Stochastic + ADX + OBV + Fundamental + Fear^&Greed)
echo ===========================================================================

echo [1/3] investor_scorer.py - Pelosi / ARK / Korean investor scoring...
"C:\Program Files\PostgreSQL\17\pgAdmin 4\python\python.exe" "%~dp0investor_scorer.py"

echo [2/3] Refreshing live investor data cache...
"C:\Program Files\PostgreSQL\17\pgAdmin 4\python\python.exe" -c "import sys; sys.path.insert(0, r'%~dp0'); from investor_scorer import refresh_live_data; refresh_live_data()"

echo [3/3] stock_advisor_v4.py - Full analysis (Technical + Fundamental + Macro)...
"C:\Program Files\PostgreSQL\17\pgAdmin 4\python\python.exe" -c "import sys; sys.path.insert(0, r'%~dp0'); import stock_advisor_v4; stock_advisor_v4.main()"

echo.
echo ========================================
echo v4 Analysis Complete. Report: report_v4.txt
echo ========================================
pause
