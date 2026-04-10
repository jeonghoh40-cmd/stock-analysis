@echo off
chcp 65001 >nul
echo ============================================
echo   VC 투자 분석 시스템 - 서버 설치
echo ============================================
echo.

REM 1. vc_investment_analyzer 복사
echo [1/4] vc_investment_analyzer 복사 중...
if exist vc_investment_analyzer rmdir /s /q vc_investment_analyzer
xcopy /E /I /Q "%~dp0..\vc_investment_analyzer" vc_investment_analyzer
if exist vc_investment_analyzer\.git rmdir /s /q vc_investment_analyzer\.git
if exist vc_investment_analyzer\.venv rmdir /s /q vc_investment_analyzer\.venv
echo       완료
echo.

REM 2. .env 파일 확인
if not exist .env (
    echo [2/4] .env 파일 생성...
    echo ANTHROPIC_API_KEY=여기에_API키_입력 > .env
    echo       .env 파일이 생성되었습니다.
    echo       메모장으로 열어서 ANTHROPIC_API_KEY를 실제 키로 변경하세요.
    notepad .env
    pause
) else (
    echo [2/4] .env 파일 확인 완료
)
echo.

REM 3. Docker 빌드
echo [3/4] Docker 이미지 빌드 중... (수 분 소요)
docker compose build
if %errorlevel% neq 0 (
    echo       빌드 실패. Docker Desktop이 실행 중인지 확인하세요.
    pause
    exit /b 1
)
echo       빌드 완료
echo.

REM 4. 실행
echo [4/4] 서버 시작...
docker compose up -d
echo.
echo ============================================
echo   설치 완료!
echo   사내 접속: http://localhost:3000/run
echo ============================================
echo.

REM 임시 폴더 정리
rmdir /s /q vc_investment_analyzer 2>nul

pause
