@echo off
REM ──────────────────────────────────────────────────────────────
REM  Task Scheduler 등록 스크립트 (관리자 권한으로 실행 필요)
REM  사용법: 이 파일을 우클릭 → "관리자 권한으로 실행"
REM ──────────────────────────────────────────────────────────────

chcp 65001 > nul

set "SCRIPT_DIR=%~dp0"
set "BAT_FILE=%SCRIPT_DIR%run_screening.bat"
set "TASK_NAME=AI주식스크리닝"

echo [1/2] 기존 작업 삭제 (없으면 무시)...
schtasks /delete /tn "%TASK_NAME%" /f 2>nul

echo [2/2] 매일 06:30 실행 작업 등록...
schtasks /create ^
  /tn "%TASK_NAME%" ^
  /tr "%BAT_FILE%" ^
  /sc DAILY ^
  /st 06:30 ^
  /ru "%USERNAME%" ^
  /f ^
  /rl HIGHEST

if %ERRORLEVEL% EQU 0 (
    echo.
    echo ✅ 작업 등록 성공!
    echo    작업명 : %TASK_NAME%
    echo    실행파일: %BAT_FILE%
    echo    일정   : 매일 06:30
    echo.
    echo 확인 방법: 작업 스케줄러 열기 → "작업 스케줄러 라이브러리" 확인
    echo           또는: schtasks /query /tn "%TASK_NAME%"
) else (
    echo.
    echo ❌ 등록 실패. 관리자 권한으로 다시 실행해 주세요.
)
pause
