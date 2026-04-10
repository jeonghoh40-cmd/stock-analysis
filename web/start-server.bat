@echo off
chcp 65001 >nul
echo ============================================
echo   VC 투자 분석 시스템 - 직접 실행
echo ============================================
echo.

REM Node.js 확인
where node >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Node.js가 설치되어 있지 않습니다.
    echo   https://nodejs.org 에서 LTS 버전을 설치하세요.
    pause
    exit /b 1
)

REM Python 확인
where python >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Python이 설치되어 있지 않습니다.
    echo   https://python.org 에서 설치하세요.
    pause
    exit /b 1
)

REM .env 파일 확인
if not exist .env (
    echo ANTHROPIC_API_KEY=여기에_API키_입력 > .env
    echo [!] .env 파일이 생성되었습니다. API 키를 입력하세요.
    notepad .env
    pause
)

REM 의존성 설치 (최초 1회)
if not exist node_modules (
    echo [1/3] npm 패키지 설치 중...
    call npm install
)

REM Python 의존성 설치
echo [2/3] Python 의존성 확인 중...
pip install -q pydantic anthropic python-docx python-pptx openpyxl numpy rich fastapi uvicorn 2>nul

REM 빌드
echo [3/3] Next.js 빌드 중...
call npx next build

echo.
echo ============================================
echo   서버 시작 (0.0.0.0:3000)
echo   사내: http://localhost:3000/run
echo   이 창을 닫으면 서버가 종료됩니다.
echo ============================================
echo.

set HOSTNAME=0.0.0.0
set PORT=3000
call npx next start -H 0.0.0.0 -p 3000
