# ──────────────────────────────────────────────────────────────
# AI 주식 스크리닝 — Task Scheduler 등록 스크립트 (PowerShell)
# 사용법: PowerShell을 관리자 권한으로 열고 아래 명령 실행
#   Set-ExecutionPolicy RemoteSigned -Scope CurrentUser -Force
#   & "C:\Users\geunho\stock analysis\setup_scheduler.ps1"
# ──────────────────────────────────────────────────────────────

$TaskName  = "AI주식스크리닝"
$BatFile   = "C:\Users\geunho\stock analysis\run_screening.bat"
$StartTime = "06:30"

# 기존 작업 삭제 (없으면 무시)
Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false -ErrorAction SilentlyContinue

# Action 정의 (배치파일 실행)
$Action  = New-ScheduledTaskAction `
    -Execute "cmd.exe" `
    -Argument "/c `"$BatFile`"" `
    -WorkingDirectory "C:\Users\geunho\stock analysis"

# Trigger 정의 (매일 06:30)
$Trigger = New-ScheduledTaskTrigger `
    -Daily `
    -At $StartTime

# Settings
$Settings = New-ScheduledTaskSettingsSet `
    -ExecutionTimeLimit (New-TimeSpan -Hours 2) `
    -StartWhenAvailable `
    -RunOnlyIfNetworkAvailable

# Principal (현재 사용자, 최고 권한)
$Principal = New-ScheduledTaskPrincipal `
    -UserId ([System.Security.Principal.WindowsIdentity]::GetCurrent().Name) `
    -LogonType Interactive `
    -RunLevel Highest

# 등록
Register-ScheduledTask `
    -TaskName  $TaskName `
    -Action    $Action `
    -Trigger   $Trigger `
    -Settings  $Settings `
    -Principal $Principal `
    -Force

# 결과 확인
$Task = Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
if ($Task) {
    Write-Host ""
    Write-Host "✅ 작업 등록 성공!" -ForegroundColor Green
    Write-Host "   작업명 : $TaskName"
    Write-Host "   실행   : $BatFile"
    Write-Host "   일정   : 매일 $StartTime"
    Write-Host ""
    Write-Host "▶ 즉시 테스트 실행: Start-ScheduledTask -TaskName '$TaskName'" -ForegroundColor Cyan
} else {
    Write-Host "❌ 등록 실패. 관리자 PowerShell로 다시 실행하세요." -ForegroundColor Red
}
