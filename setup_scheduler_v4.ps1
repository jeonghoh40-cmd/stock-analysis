# ─────────────────────────────────────────────────────────────
# AI 주식 스크리닝 v4 — Windows 작업 스케줄러 자동 등록
# 실행: PowerShell 에서 우클릭 → "관리자 권한으로 실행"
# ─────────────────────────────────────────────────────────────

$ScriptDir  = Split-Path -Parent $MyInvocation.MyCommand.Path
$BatchFile  = "$ScriptDir\run_daily.bat"
$TaskName   = "AI_Stock_Screener"
$RunTime    = "06:30AM"

Write-Host ""
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "  AI 주식 스크리닝 v4 — 작업 스케줄러 등록" -ForegroundColor Cyan
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host ""

# 관리자 권한 확인
$isAdmin = ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole(
    [Security.Principal.WindowsBuiltInRole]::Administrator)
if (-not $isAdmin) {
    Write-Host "❌ 관리자 권한이 필요합니다." -ForegroundColor Red
    Write-Host "   이 파일을 우클릭 → 'PowerShell로 실행' → 관리자 권한 선택" -ForegroundColor Yellow
    pause; exit 1
}

# 배치 파일 존재 확인
if (-not (Test-Path $BatchFile)) {
    Write-Host "❌ 실행 파일 없음: $BatchFile" -ForegroundColor Red
    pause; exit 1
}

Write-Host "실행 파일 : $BatchFile" -ForegroundColor Gray
Write-Host "실행 시간 : 월~금 $RunTime" -ForegroundColor Gray
Write-Host ""

# 기존 작업 삭제
$existing = Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
if ($existing) {
    Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false
    Write-Host "  ✓ 기존 작업 삭제: $TaskName" -ForegroundColor Yellow
}

# 트리거: 월~금 오전 6:30
$trigger = New-ScheduledTaskTrigger `
    -Weekly `
    -DaysOfWeek Monday, Tuesday, Wednesday, Thursday, Friday `
    -At $RunTime

# 동작: cmd.exe 통해 배치 파일 실행
$action = New-ScheduledTaskAction `
    -Execute "cmd.exe" `
    -Argument "/c `"$BatchFile`"" `
    -WorkingDirectory $ScriptDir

# 설정
$settings = New-ScheduledTaskSettingsSet `
    -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries `
    -StartWhenAvailable `
    -WakeToRun `
    -ExecutionTimeLimit (New-TimeSpan -Hours 2) `
    -MultipleInstances IgnoreNew

$currentUser = [System.Security.Principal.WindowsIdentity]::GetCurrent().Name

try {
    Register-ScheduledTask `
        -TaskName    $TaskName `
        -Description "매일 오전 6:30 AI 주식 스크리닝 v4 자동 실행 (월~금)" `
        -User        $currentUser `
        -Trigger     $trigger `
        -Action      $action `
        -Settings    $settings `
        -RunLevel    Highest `
        -ErrorAction Stop | Out-Null

    Write-Host ""
    Write-Host "============================================================" -ForegroundColor Green
    Write-Host "  ✅ 작업 스케줄러 등록 완료!" -ForegroundColor Green
    Write-Host "============================================================" -ForegroundColor Green
    Write-Host ""
    Write-Host "  작업 이름  : $TaskName" -ForegroundColor White
    Write-Host "  실행 시간  : 월~금 오전 6:30" -ForegroundColor White
    Write-Host "  실행 파일  : $BatchFile" -ForegroundColor White
    Write-Host "  로그 위치  : $ScriptDir\logs\daily_YYYYMMDD.log" -ForegroundColor White
    Write-Host ""

    # 등록 확인
    $task = Get-ScheduledTask -TaskName $TaskName
    Write-Host "  현재 상태  : $($task.State)" -ForegroundColor Cyan
    $taskInfo = Get-ScheduledTaskInfo -TaskName $TaskName
    Write-Host "  다음 실행  : $($taskInfo.NextRunTime)" -ForegroundColor Cyan
    Write-Host ""
    Write-Host "  확인 방법: schtasks /query /tn `"$TaskName`" /fo LIST /v" -ForegroundColor Gray

} catch {
    Write-Host ""
    Write-Host "❌ 등록 실패: $($_.Exception.Message)" -ForegroundColor Red
    pause; exit 1
}

Write-Host ""
pause
