# 适用机器：掌机（Windows）
# 系统 / OS：Windows
# 用途：巡检并自愈掌机上的 OpenClaw gateway
# 行为：
#   1. 检查本地 `http://127.0.0.1:18789/` 是否可用
#   2. 若不可用，则补充执行 `openclaw gateway restart`
# 用法：
#   .\scripts\openclaw-gateway-watchdog.ps1           # 仅检查
#   .\scripts\openclaw-gateway-watchdog.ps1 -AutoFix  # 检查并自动修复

[CmdletBinding()]
param(
    [switch]$AutoFix,
    [switch]$Quiet,
    [int]$Port = 18789,
    [int]$TimeoutSeconds = 5
)

$ErrorActionPreference = 'Stop'

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$repoRoot = Split-Path -Parent $scriptDir
$logDir = Join-Path $env:LOCALAPPDATA 'OpenClaw\watchdog'
$logFile = Join-Path $logDir 'gateway-watchdog.log'

New-Item -ItemType Directory -Force -Path $logDir | Out-Null

function Write-Log {
    param(
        [string]$Message,
        [string]$Level = 'INFO'
    )

    $line = ('[{0}] [{1}] {2}' -f (Get-Date -Format 'yyyy-MM-dd HH:mm:ss'), $Level, $Message)
    Add-Content -Path $logFile -Value $line

    if (-not $Quiet) {
        Write-Host $line
    }
}

function Resolve-OpenClawCommand {
    $cmd = Get-Command openclaw.cmd -ErrorAction SilentlyContinue
    if ($cmd) { return $cmd.Source }

    $plain = Get-Command openclaw -ErrorAction SilentlyContinue
    if ($plain) { return $plain.Source }

    throw 'Could not find openclaw / openclaw.cmd in PATH.'
}

function Test-GatewayHttp {
    param(
        [string]$Uri,
        [int]$TimeoutSec
    )

    try {
        $response = Invoke-WebRequest -UseBasicParsing -Uri $Uri -TimeoutSec $TimeoutSec
        return $response.StatusCode -ge 200 -and $response.StatusCode -lt 500
    }
    catch {
        return $false
    }
}

function Get-GatewayStatusText {
    param([string]$CommandPath)

    try {
        $output = & $CommandPath gateway status 2>&1 | Out-String
        return $output.Trim()
    }
    catch {
        return ($_ | Out-String).Trim()
    }
}

function Test-GatewayHealthy {
    param(
        [string]$CommandPath,
        [int]$GatewayPort,
        [int]$TimeoutSec
    )

    $uri = "http://127.0.0.1:$GatewayPort/"
    if (Test-GatewayHttp -Uri $uri -TimeoutSec $TimeoutSec) {
        return [pscustomobject]@{
            Healthy = $true
            Method  = 'http'
            Detail  = "HTTP probe ok: $uri"
            Raw     = $null
        }
    }

    $statusText = Get-GatewayStatusText -CommandPath $CommandPath
    $looksHealthy = $statusText -match 'Connectivity probe:\s+ok' -or $statusText -match 'Runtime:\s+running'

    return [pscustomobject]@{
        Healthy = $looksHealthy
        Method  = 'status'
        Detail  = if ($looksHealthy) { 'gateway status reports healthy' } else { 'HTTP probe failed and gateway status did not report healthy state' }
        Raw     = $statusText
    }
}

$openclawCmd = Resolve-OpenClawCommand
Write-Log "Checking OpenClaw gateway (port=$Port, autoFix=$AutoFix)"

$check = Test-GatewayHealthy -CommandPath $openclawCmd -GatewayPort $Port -TimeoutSec $TimeoutSeconds
if ($check.Healthy) {
    Write-Log "Gateway healthy: $($check.Detail)"
    exit 0
}

Write-Log "Gateway unhealthy: $($check.Detail)" 'WARN'
if ($check.Raw) {
    Write-Log ("Diagnostics: " + ($check.Raw -replace "`r?`n", ' | ')) 'WARN'
}

if (-not $AutoFix) {
    exit 1
}

Write-Log 'Running openclaw gateway restart' 'WARN'
Push-Location $repoRoot
try {
    & $openclawCmd gateway restart | Out-Null
}
finally {
    Pop-Location
}

Start-Sleep -Seconds 5
$recheck = Test-GatewayHealthy -CommandPath $openclawCmd -GatewayPort $Port -TimeoutSec $TimeoutSeconds
if ($recheck.Healthy) {
    Write-Log "Gateway recovered after restart: $($recheck.Detail)"
    exit 0
}

Write-Log "Gateway still unhealthy after restart: $($recheck.Detail)" 'ERROR'
if ($recheck.Raw) {
    Write-Log ("Post-restart diagnostics: " + ($recheck.Raw -replace "`r?`n", ' | ')) 'ERROR'
}

exit 2
