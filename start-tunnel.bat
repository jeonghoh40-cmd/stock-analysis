@echo off
chcp 65001 >nul
echo ============================================
echo   외부 접속 터널 시작 (ngrok)
echo ============================================
echo.

REM ngrok 설치 확인
where ngrok >nul 2>&1
if %errorlevel% neq 0 (
    echo ngrok이 설치되어 있지 않습니다.
    echo.
    echo 설치 방법:
    echo   1. https://ngrok.com 에서 무료 회원가입
    echo   2. https://ngrok.com/download 에서 다운로드
    echo   3. 압축 해제 후 이 폴더에 ngrok.exe 복사
    echo   4. ngrok config add-authtoken 여기에_토큰_입력
    echo   5. 이 파일 다시 실행
    echo.
    pause
    exit /b 1
)

echo 터널을 시작합니다...
echo 표시되는 Forwarding URL을 외부 사용자에게 공유하세요.
echo (예: https://xxxx-xxxx.ngrok-free.app)
echo.
echo 이 창을 닫으면 외부 접속이 끊깁니다.
echo ============================================
echo.
ngrok http 3000
