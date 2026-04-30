# Uninstall OpenClaw Gateway Watchdog scheduled task (Windows / PowerShell)
# Usage:
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
