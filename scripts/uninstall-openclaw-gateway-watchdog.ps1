# 适用机器：掌机（Windows）
# 系统 / OS：Windows
# 用途：卸载掌机上的 OpenClaw Gateway Watchdog 计划任务
# 用法：
#   .\scripts\uninstall-openclaw-gateway-watchdog.ps1

[CmdletBinding()]
param()

$ErrorActionPreference = 'Stop'

$taskName = 'OpenClaw Gateway Watchdog'
$existing = Get-ScheduledTask -TaskName $taskName -ErrorAction SilentlyContinue

if (-not $existing) {
    Write-Host "Scheduled task not found: $taskName"
    exit 0
}

Unregister-ScheduledTask -TaskName $taskName -Confirm:$false
Write-Host "Removed scheduled task: $taskName"
