# Install OpenClaw Gateway Watchdog scheduled task (Windows / PowerShell)
# Usage:
#   .\scripts\install-openclaw-gateway-watchdog.ps1

[CmdletBinding()]
param(
    [int]$IntervalMinutes = 3,
    [switch]$Force
)

$ErrorActionPreference = 'Stop'

$taskName = 'OpenClaw Gateway Watchdog'
$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$watchdogScript = Join-Path $scriptDir 'openclaw-gateway-watchdog.ps1'
$powershellExe = Join-Path $env:WINDIR 'System32\WindowsPowerShell\v1.0\powershell.exe'
$currentUser = [System.Security.Principal.WindowsIdentity]::GetCurrent().Name

if (-not (Test-Path $watchdogScript)) {
    throw "Watchdog script not found: $watchdogScript"
}

if ($IntervalMinutes -lt 1) {
    throw 'IntervalMinutes must be at least 1.'
}

$existing = Get-ScheduledTask -TaskName $taskName -ErrorAction SilentlyContinue
if ($existing -and -not $Force) {
    throw "Scheduled task '$taskName' already exists. Use -Force to replace it."
}

if ($existing) {
    Unregister-ScheduledTask -TaskName $taskName -Confirm:$false
}

$action = New-ScheduledTaskAction -Execute $powershellExe -Argument ('-NoProfile -ExecutionPolicy Bypass -File "{0}" -AutoFix -Quiet' -f $watchdogScript)
$triggerLogon = New-ScheduledTaskTrigger -AtLogOn -User $currentUser
$triggerRepeat = New-ScheduledTaskTrigger -Once -At (Get-Date).AddMinutes(1) -RepetitionInterval (New-TimeSpan -Minutes $IntervalMinutes) -RepetitionDuration (New-TimeSpan -Days 3650)
$settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -MultipleInstances IgnoreNew
$principal = New-ScheduledTaskPrincipal -UserId $currentUser -LogonType Interactive -RunLevel Limited

Register-ScheduledTask -TaskName $taskName -Action $action -Trigger @($triggerLogon, $triggerRepeat) -Settings $settings -Principal $principal | Out-Null
Start-ScheduledTask -TaskName $taskName

Write-Host "Installed scheduled task: $taskName"
Write-Host "  - check at logon"
Write-Host "  - repeat every $IntervalMinutes minutes"
Write-Host "  - script: $watchdogScript"
Write-Host "  - log: $env:LOCALAPPDATA\OpenClaw\watchdog\gateway-watchdog.log"
