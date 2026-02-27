@echo off
set PYTHONPATH=%~dp0

echo Starting stock analysis scripts v2 (Detailed ★★★ Format)...

echo [1/5] Running investor_scorer.py (Pelosi, ARK, Korean investors scoring)...
"C:\Program Files\PostgreSQL\17\pgAdmin 4\python\python.exe" "%~dp0investor_scorer.py"

echo [2/5] Running investor_tracker.py (famous investors data)...
"C:\Program Files\PostgreSQL\17\pgAdmin 4\python\python.exe" "%~dp0investor_tracker.py"

echo [3/5] Running dart_collector.py...
"C:\Program Files\PostgreSQL\17\pgAdmin 4\python\python.exe" "%~dp0dart_collector.py"

echo [4/5] Running data_collector.py...
"C:\Program Files\PostgreSQL\17\pgAdmin 4\python\python.exe" "%~dp0data_collector.py"

echo [5/5] Running stock_advisor_v2.py (Detailed: Buy TOP10 / Sell TOP10 with ★★★ ratings)...
"C:\Program Files\PostgreSQL\17\pgAdmin 4\python\python.exe" -c "import sys; sys.path.insert(0, r'%~dp0'); import stock_advisor_v2; stock_advisor_v2.main()"

echo [Optional] Running geopolitical_collector.py...
"C:\Program Files\PostgreSQL\17\pgAdmin 4\python\python.exe" "%~dp0geopolitical_collector.py"

echo.
echo ========================================
echo All scripts completed.
echo ========================================
pause
