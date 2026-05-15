# 适用机器：通用（宿主机 Windows）
# 系统 / OS：Windows
# 用途：为宿主机温度桥脚本创建计划任务，定时生成 host-thermal-bridge.json。

[CmdletBinding()]
param(
    [string]$TaskName = 'OpenClaw Host Thermal Bridge',
    [string]$ScriptPath,
    [string]$OutputPath = "$env:USERPROFILE\Documents\OpenClawBridge\host-thermal-bridge.json",
    [int]$EveryMinutes = 2
)

$ErrorActionPreference = 'Stop'

if (-not $ScriptPath) {
    $ScriptPath = Join-Path $PSScriptRoot 'host-thermal-bridge-windows.ps1'
}

$ScriptPath = [System.IO.Path]::GetFullPath($ScriptPath)
$OutputPath = [System.IO.Path]::GetFullPath($OutputPath)

if (-not (Test-Path -LiteralPath $ScriptPath)) {
    throw "未找到温度桥脚本：$ScriptPath"
}

if ($EveryMinutes -lt 1) {
    throw 'EveryMinutes 不能小于 1'
}

$outputDir = Split-Path -Parent $OutputPath
if ($outputDir) {
    New-Item -ItemType Directory -Force -Path $outputDir | Out-Null
}

$taskCommand = 'powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -File "{0}" -OutputPath "{1}"' -f $ScriptPath, $OutputPath

$createArgs = @(
    '/Create',
    '/TN', $TaskName,
    '/SC', 'MINUTE',
    '/MO', "$EveryMinutes",
    '/TR', $taskCommand,
    '/F'
)

$createOutput = & schtasks.exe @createArgs 2>&1
$createExit = $LASTEXITCODE
if ($createExit -ne 0) {
    $createMessage = (($createOutput | ForEach-Object { $_.ToString().Trim() }) | Where-Object { $_ }) -join "`n"
    if (-not $createMessage) {
        $createMessage = 'schtasks /Create 返回失败，但没有额外输出。'
    }
    throw "计划任务创建失败（exit=$createExit）：`n$createMessage"
}

$runOutput = & schtasks.exe /Run /TN $TaskName 2>&1
$runExit = $LASTEXITCODE
if ($runExit -ne 0) {
    $runMessage = (($runOutput | ForEach-Object { $_.ToString().Trim() }) | Where-Object { $_ }) -join "`n"
    Write-Warning "计划任务已创建，但首次触发失败；请手工检查任务：$TaskName`n$runMessage"
}

Write-Host "Installed scheduled task: $TaskName"
Write-Host "ScriptPath: $ScriptPath"
Write-Host "OutputPath: $OutputPath"
Write-Host "IntervalMinutes: $EveryMinutes"
Write-Host "建议把 OutputPath 所在目录作为 VMware 共享文件夹暴露给 Linux 客体。"
Write-Host "若共享名为 OpenClawBridge，则 Linux 客体通常可直接从 /mnt/hgfs/OpenClawBridge/host-thermal-bridge.json 读取。"
