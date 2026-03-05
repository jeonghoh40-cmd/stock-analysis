@echo off
chcp 65001 >nul

REM Python 3.14 경로 설정
set PYTHON=C:\Python314\python.exe
set PYLIB=C:\Users\geunho\AppData\Local\Programs\Python\Python314\Lib
set SITEPKG=C:\Users\geunho\stock analysis\Lib\site-packages
set SCRIPTDIR=C:\Users\geunho\stock analysis

set PYTHONHOME=C:\Users\geunho\AppData\Local\Programs\Python\Python314
set PYTHONPATH=%SITEPKG%;%SCRIPTDIR%;%PYLIB%

echo Python 경로: %PYTHON%
echo.
echo [주식 분석 시작] stock_advisor_v2.py
%PYTHON% "%SCRIPTDIR%\stock_advisor_v2.py"
echo.
echo 완료.
pause
