# 适用机器：掌机（Windows）
# 系统 / OS：Windows
# 用途：重新启用并启动掌机上的 OpenClaw gateway
# 行为：
#   1. 启用 `OpenClaw Gateway`
#   2. 启用 `OpenClaw Gateway Watchdog`
#   3. 启动 `OpenClaw Gateway`

[CmdletBinding()]
param()

$ErrorActionPreference = 'Stop'

function Enable-TaskIfExists {
    param([string]$TaskName)
    $task = Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
    if ($null -eq $task) {
        Write-Host "[skip] Scheduled task not found: $TaskName"
        return $false
    }

    Enable-ScheduledTask -TaskName $TaskName | Out-Null
    Write-Host "[ok] Enabled: $TaskName"
    return $true
}

$gatewayEnabled = Enable-TaskIfExists 'OpenClaw Gateway'
$watchdogEnabled = Enable-TaskIfExists 'OpenClaw Gateway Watchdog'

if ($gatewayEnabled) {
    try {
        Start-ScheduledTask -TaskName 'OpenClaw Gateway'
        Write-Host '[ok] Started: OpenClaw Gateway'
    }
    catch {
        Write-Host "[warn] Failed to start OpenClaw Gateway: $($_.Exception.Message)"
    }
}

if ($watchdogEnabled) {
    try {
        Start-ScheduledTask -TaskName 'OpenClaw Gateway Watchdog'
        Write-Host '[ok] Triggered: OpenClaw Gateway Watchdog'
    }
    catch {
        Write-Host "[warn] Failed to trigger watchdog: $($_.Exception.Message)"
    }
}

Write-Host ''
Write-Host 'OpenClaw gateway has been re-enabled for 掌机（Windows）.' -ForegroundColor Green
