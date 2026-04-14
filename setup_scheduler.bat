@echo off
REM ──────────────────────────────────────────────────────────────
REM  Task Scheduler 등록 스크립트
REM  ★ 이 파일을 더블클릭하면 자동으로 관리자 권한 요청합니다 ★
REM ──────────────────────────────────────────────────────────────
chcp 65001 > nul

REM 관리자 권한 자동 요청
net session >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo 관리자 권한이 필요합니다. UAC 창이 열립니다...
    powershell -Command "Start-Process cmd -ArgumentList '/c cd /d ""%~dp0"" && ""%~f0""' -Verb RunAs"
    exit /b
)

echo.
echo [AI 주식 스크리닝] Task Scheduler 등록 중...
echo.

powershell -ExecutionPolicy Bypass -File "%~dp0register_task.ps1"

echo.
pause
