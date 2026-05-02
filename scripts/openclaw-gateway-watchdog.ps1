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
    [int]$TimeoutSeconds = 8
)

$restartGraceSeconds = 20
$directStartGraceSeconds = 25
$startingGraceSeconds = 20

$ErrorActionPreference = 'Stop'

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$repoRoot = Split-Path -Parent $scriptDir
$logDir = Join-Path $env:LOCALAPPDATA 'OpenClaw\watchdog'
$logFile = Join-Path $logDir 'gateway-watchdog.log'
$gatewayWrapper = Join-Path (Join-Path $env:USERPROFILE '.openclaw') 'gateway.cmd'

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
            Healthy      = $true
            Transitional = $false
            Method       = 'http'
            Detail       = "HTTP probe ok: $uri"
            Raw          = $null
        }
    }

    $statusText = Get-GatewayStatusText -CommandPath $CommandPath
    $looksHealthy = $statusText -match 'Connectivity probe:\s+ok' -or $statusText -match 'gateway status reports healthy'
    $looksStarting =
        $statusText -match 'Runtime:\s+running' -or
        $statusText -match 'Warm-up:' -or
        $statusText -match 'Verified gateway listener detected on port' -or
        $statusText -match 'Port\s+' + [regex]::Escape([string]$GatewayPort) + '\s+is already in use' -or
        $statusText -match 'Gateway already running locally'

    return [pscustomobject]@{
        Healthy      = $looksHealthy
        Transitional = (-not $looksHealthy) -and $looksStarting
        Method       = 'status'
        Detail       = if ($looksHealthy) {
            'gateway status reports healthy'
        }
        elseif ($looksStarting) {
            'gateway process/listener exists but is still starting or temporarily overloaded'
        }
        else {
            'HTTP probe failed and gateway status did not report healthy state'
        }
        Raw          = $statusText
    }
}

function Wait-GatewayRecovery {
    param(
        [string]$CommandPath,
        [int]$GatewayPort,
        [int]$TimeoutSec,
        [int]$MaxWaitSeconds,
        [string]$Reason
    )

    $deadline = (Get-Date).AddSeconds($MaxWaitSeconds)
    do {
        Start-Sleep -Seconds 5
        $check = Test-GatewayHealthy -CommandPath $CommandPath -GatewayPort $GatewayPort -TimeoutSec $TimeoutSec
        if ($check.Healthy) {
            return $check
        }
        if ($check.Transitional) {
            Write-Log "${Reason}: gateway still looks transitional, keep waiting" 'WARN'
        }
    } while ((Get-Date) -lt $deadline)

    return Test-GatewayHealthy -CommandPath $CommandPath -GatewayPort $GatewayPort -TimeoutSec $TimeoutSec
}

function Get-GatewayTaskBatteryPolicy {
    param([string]$TaskName = 'OpenClaw Gateway')

    try {
        [xml]$xml = schtasks /Query /TN $TaskName /XML 2>$null
        $ns = New-Object System.Xml.XmlNamespaceManager($xml.NameTable)
        $ns.AddNamespace('t', 'http://schemas.microsoft.com/windows/2004/02/mit/task')

        $disallow = $xml.SelectSingleNode('//t:DisallowStartIfOnBatteries', $ns)
        $stop = $xml.SelectSingleNode('//t:StopIfGoingOnBatteries', $ns)

        return [pscustomobject]@{
            Found                       = $true
            DisallowStartIfOnBatteries  = $disallow -and $disallow.InnerText -eq 'true'
            StopIfGoingOnBatteries      = $stop -and $stop.InnerText -eq 'true'
        }
    }
    catch {
        return [pscustomobject]@{
            Found                       = $false
            DisallowStartIfOnBatteries  = $false
            StopIfGoingOnBatteries      = $false
        }
    }
}

function Start-GatewayDirectly {
    param(
        [string]$WrapperPath,
        [string]$WorkingDirectory
    )

    if (-not (Test-Path $WrapperPath)) {
        throw "Gateway wrapper not found: $WrapperPath"
    }

    Start-Process -FilePath $WrapperPath -WorkingDirectory $WorkingDirectory -WindowStyle Hidden | Out-Null
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

if ($check.Transitional) {
    Write-Log "Gateway looks busy rather than dead; waiting ${startingGraceSeconds}s before trying restart" 'WARN'
    $warmupCheck = Wait-GatewayRecovery -CommandPath $openclawCmd -GatewayPort $Port -TimeoutSec $TimeoutSeconds -MaxWaitSeconds $startingGraceSeconds -Reason 'Warm-up grace'
    if ($warmupCheck.Healthy) {
        Write-Log "Gateway recovered during warm-up grace: $($warmupCheck.Detail)"
        exit 0
    }
}

Write-Log 'Running openclaw gateway restart' 'WARN'
Push-Location $repoRoot
try {
    & $openclawCmd gateway restart | Out-Null
}
finally {
    Pop-Location
}

$recheck = Wait-GatewayRecovery -CommandPath $openclawCmd -GatewayPort $Port -TimeoutSec $TimeoutSeconds -MaxWaitSeconds $restartGraceSeconds -Reason 'Post-restart grace'
if ($recheck.Healthy) {
    Write-Log "Gateway recovered after restart: $($recheck.Detail)"
    exit 0
}

Write-Log "Gateway still unhealthy after restart: $($recheck.Detail)" 'WARN'
if ($recheck.Raw) {
    Write-Log ("Post-restart diagnostics: " + ($recheck.Raw -replace "`r?`n", ' | ')) 'WARN'
}

$taskPolicy = Get-GatewayTaskBatteryPolicy
if ($taskPolicy.Found -and ($taskPolicy.DisallowStartIfOnBatteries -or $taskPolicy.StopIfGoingOnBatteries)) {
    Write-Log 'Detected battery-restricted OpenClaw Gateway scheduled task; trying direct wrapper start as fallback' 'WARN'
}
else {
    Write-Log 'Trying direct gateway wrapper start as fallback' 'WARN'
}

try {
    Start-GatewayDirectly -WrapperPath $gatewayWrapper -WorkingDirectory $repoRoot
}
catch {
    Write-Log "Direct wrapper start failed: $($_.Exception.Message)" 'ERROR'
    exit 2
}

$directRecheck = Wait-GatewayRecovery -CommandPath $openclawCmd -GatewayPort $Port -TimeoutSec $TimeoutSeconds -MaxWaitSeconds $directStartGraceSeconds -Reason 'Direct-start grace'
if ($directRecheck.Healthy) {
    Write-Log "Gateway recovered after direct wrapper start: $($directRecheck.Detail)"
    exit 0
}

Write-Log "Gateway still unhealthy after direct wrapper start: $($directRecheck.Detail)" 'ERROR'
if ($directRecheck.Raw) {
    Write-Log ("Direct-start diagnostics: " + ($directRecheck.Raw -replace "`r?`n", ' | ')) 'ERROR'
}

exit 2
