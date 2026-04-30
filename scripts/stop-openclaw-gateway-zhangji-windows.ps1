# 适用机器：掌机（Windows）
# 系统 / OS：Windows
# 用途：一键关闭掌机上的 OpenClaw gateway 自动拉起与当前运行实例
# 行为：
#   1. 禁用 `OpenClaw Gateway Watchdog`
#   2. 禁用 `OpenClaw Gateway`
#   3. 停止当前 gateway 任务 / 进程
# 注意：执行后，OpenClaw 不会再自动拉起，直到重新启用

[CmdletBinding()]
param()

$ErrorActionPreference = 'Stop'

$taskNames = @('OpenClaw Gateway Watchdog', 'OpenClaw Gateway')

function Write-Step {
    param([string]$Message)
    Write-Host "==> $Message" -ForegroundColor Cyan
}

foreach ($taskName in $taskNames) {
    $task = Get-ScheduledTask -TaskName $taskName -ErrorAction SilentlyContinue
    if ($null -eq $task) {
        Write-Host "[skip] Scheduled task not found: $taskName"
        continue
    }

    Write-Step "Disabling scheduled task: $taskName"
    Disable-ScheduledTask -TaskName $taskName | Out-Null

    try {
        Stop-ScheduledTask -TaskName $taskName -ErrorAction SilentlyContinue | Out-Null
    }
    catch {
    }
}

Write-Step 'Stopping OpenClaw gateway via CLI'
$openclaw = Get-Command openclaw.cmd -ErrorAction SilentlyContinue
if ($openclaw) {
    try {
        & $openclaw.Source gateway stop
    }
    catch {
        Write-Host "[warn] openclaw gateway stop failed: $($_.Exception.Message)"
    }
}
else {
    Write-Host '[warn] openclaw.cmd not found in PATH; skipping CLI stop'
}

Write-Step 'Stopping leftover gateway process if still running'
$gatewayProcesses = Get-CimInstance Win32_Process -Filter "Name = 'node.exe'" |
    Where-Object {
        $_.CommandLine -and
        $_.CommandLine -match 'openclaw' -and
        $_.CommandLine -match '\bgateway\b'
    }

foreach ($proc in $gatewayProcesses) {
    try {
        Stop-Process -Id $proc.ProcessId -Force -ErrorAction Stop
        Write-Host "[ok] Stopped gateway process PID=$($proc.ProcessId)"
    }
    catch {
        Write-Host "[warn] Failed to stop PID=$($proc.ProcessId): $($_.Exception.Message)"
    }
}

Write-Host ''
Write-Host 'OpenClaw gateway has been shut down for 掌机（Windows）.' -ForegroundColor Green
Write-Host 'Disabled tasks:' -ForegroundColor Green
Write-Host '  - OpenClaw Gateway Watchdog'
Write-Host '  - OpenClaw Gateway'
Write-Host 'Use the paired start script to enable them again.'
