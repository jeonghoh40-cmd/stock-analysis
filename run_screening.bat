@echo off
REM ──────────────────────────────────────────────────────────────
REM  AI 주식 스크리닝 자동 실행 배치파일
REM  Windows Task Scheduler → 매일 06:30 실행
REM ──────────────────────────────────────────────────────────────

chcp 65001 > nul

set "SCRIPT_DIR=%~dp0"
set "LOG_FILE=%SCRIPT_DIR%logs\screening_%date:~0,4%%date:~5,2%%date:~8,2%.log"

REM logs 폴더 생성 (없으면)
if not exist "%SCRIPT_DIR%logs" mkdir "%SCRIPT_DIR%logs"

echo [%date% %time%] 스크리닝 시작 >> "%LOG_FILE%"

py "%SCRIPT_DIR%stock_advisor.py" >> "%LOG_FILE%" 2>&1

echo [%date% %time%] 스크리닝 완료 >> "%LOG_FILE%"
