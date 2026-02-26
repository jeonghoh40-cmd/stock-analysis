# ─────────────────────────────────────────────────────────────
# AI 주식 스크리닝 — Windows 작업 스케줄러 자동 등록 스크립트
# 관리자 권한으로 실행 필요
# 실행 방법: 우클릭 → "PowerShell 로 실행"
# ─────────────────────────────────────────────────────────────

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$BatchFile = "$ScriptDir\run_all.bat"
$TaskName = "AI_Stock_Screener"
$TaskDescription = "매일 오전 6 시 30 분 주식 분석 자동 실행 (월~금)"

Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "  AI 주식 스크리닝 작업 스케줄러 등록" -ForegroundColor Cyan
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host ""

# 관리자 권한 확인
$isAdmin = ([Security.Principal.WindowsPrincipal] [Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
if (-not $isAdmin) {
    Write-Host "관리자 권한이 필요합니다!" -ForegroundColor Red
    Write-Host ""
    Write-Host "실행 방법:" -ForegroundColor Yellow
    Write-Host "  1. 이 파일을 우클릭합니다" -ForegroundColor Yellow
    Write-Host "  2. '다른 이름으로 실행'을 선택합니다" -ForegroundColor Yellow
    Write-Host "  3. '관리자 권한으로 실행'을 체크합니다" -ForegroundColor Yellow
    Write-Host "  4. '확인'을 클릭합니다" -ForegroundColor Yellow
    Write-Host ""
    pause
    exit 1
}

Write-Host "관리자 권한 확인 완료" -ForegroundColor Green
Write-Host ""

# 기존 작업 삭제
Write-Host "기존 작업 삭제 중..." -ForegroundColor Cyan
try {
    $existingTask = Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
    if ($existingTask) {
        Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false
        Write-Host "기존 작업 삭제 완료: $TaskName" -ForegroundColor Green
    } else {
        Write-Host "기존 작업이 없습니다" -ForegroundColor Gray
    }
} catch {
    Write-Host "기존 작업 삭제 중 오류 (무시)" -ForegroundColor Yellow
}
Write-Host ""

# 작업 생성
Write-Host "새 작업 생성 중..." -ForegroundColor Cyan

# 트리거: 월~금 오전 6:30
$trigger = New-ScheduledTaskTrigger -Weekly -DaysOfWeek Monday, Tuesday, Wednesday, Thursday, Friday -At 6:30AM

# 동작: 배치 파일 실행
$action = New-ScheduledTaskAction -Execute "cmd.exe" -Argument "/c `"$BatchFile`"" -WorkingDirectory $ScriptDir

# 설정
$settings = New-ScheduledTaskSettingsSet `
    -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries `
    -StartWhenAvailable `
    -WakeToRun `
    -ExecutionTimeLimit (New-TimeSpan -Hours 2)

# 현재 사용자 확인
$currentUser = [System.Security.Principal.WindowsIdentity]::GetCurrent().Name
Write-Host "실행 사용자: $currentUser" -ForegroundColor Gray

# 작업 등록
try {
    Register-ScheduledTask `
        -TaskName $TaskName `
        -Description $TaskDescription `
        -User $currentUser `
        -Trigger $trigger `
        -Action $action `
        -Settings $settings `
        -RunLevel Highest `
        -ErrorAction Stop
    
    Write-Host "작업 등록 완료!" -ForegroundColor Green
} catch {
    Write-Host "작업 등록 실패!" -ForegroundColor Red
    Write-Host "오류: $($_.Exception.Message)" -ForegroundColor Red
    pause
    exit 1
}

Write-Host ""
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "  작업 스케줄러 등록 완료!" -ForegroundColor Green
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "작업 정보:" -ForegroundColor Cyan
Write-Host "  작업 이름: $TaskName" -ForegroundColor White
Write-Host "  실행 시간: 월~금 오전 6:30" -ForegroundColor White
Write-Host "  실행 파일: $BatchFile" -ForegroundColor White
Write-Host ""

# 작업 상태 확인
$task = Get-ScheduledTask -TaskName $TaskName
Write-Host "작업 상태: $($task.State)" -ForegroundColor White
Write-Host ""

Write-Host "완료!" -ForegroundColor Green
Write-Host ""
pause
