# AI 주식 스크리닝 — Task Scheduler 자동 등록 (PowerShell)
# 실행: PowerShell을 관리자 권한으로 열고 아래 실행
#   powershell -ExecutionPolicy Bypass -File "C:\Users\geunho\stock analysis\register_task.ps1"

$TaskName   = "AI주식스크리닝"
$ScriptDir  = "C:\Users\geunho\stock analysis"
$BatFile    = "$ScriptDir\run_daily.bat"
$LogDir     = "$ScriptDir\logs"

# 로그 폴더 생성
if (-not (Test-Path $LogDir)) { New-Item -ItemType Directory -Path $LogDir | Out-Null }

# 기존 작업 삭제
Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false -ErrorAction SilentlyContinue

# 실행 액션 (cmd.exe 경유)
$Action = New-ScheduledTaskAction `
    -Execute "cmd.exe" `
    -Argument "/c `"$BatFile`"" `
    -WorkingDirectory $ScriptDir

# 매일 06:00 트리거
$Trigger = New-ScheduledTaskTrigger -Daily -At "06:00"

# 설정: 최대 2시간, 로그인 여부 무관 실행
$Settings = New-ScheduledTaskSettingsSet `
    -ExecutionTimeLimit (New-TimeSpan -Hours 2) `
    -StartWhenAvailable `
    -WakeToRun `
    -MultipleInstances IgnoreNew

# 최고 권한으로 등록
$Principal = New-ScheduledTaskPrincipal `
    -UserId $env:USERNAME `
    -LogonType Interactive `
    -RunLevel Highest

try {
    Register-ScheduledTask `
        -TaskName $TaskName `
        -Action $Action `
        -Trigger $Trigger `
        -Settings $Settings `
        -Principal $Principal `
        -Force | Out-Null

    Write-Host ""
    Write-Host "✅ 등록 성공!" -ForegroundColor Green
    Write-Host "   작업명  : $TaskName"
    Write-Host "   실행파일: $BatFile"
    Write-Host "   일정    : 매일 06:00"
    Write-Host ""

    # 등록 확인
    $task = Get-ScheduledTask -TaskName $TaskName
    Write-Host "📋 등록된 작업 상태: $($task.State)" -ForegroundColor Cyan

} catch {
    Write-Host ""
    Write-Host "❌ 등록 실패: $_" -ForegroundColor Red
    Write-Host "   → PowerShell을 관리자 권한으로 실행해 주세요." -ForegroundColor Yellow
}

Write-Host ""
Write-Host "지금 바로 테스트 실행하려면 Enter를 누르세요 (건너뛰려면 Ctrl+C)..."
Read-Host
Start-ScheduledTask -TaskName $TaskName
Write-Host "▶ 실행 시작됨. 로그 확인: $LogDir" -ForegroundColor Green
