# 适用机器：掌机（Windows）
# 系统 / OS：Windows
# 用途：修复原生 `OpenClaw Gateway` 计划任务在电池模式下禁止启动 / 自动停止的问题
# 行为：
#   1. 导出 `OpenClaw Gateway` 任务 XML
#   2. 将电池相关限制改为 false
#   3. 重新导入同名计划任务
# 注意：
#   - 某些系统环境下可能需要“以管理员身份运行”
#   - 当前脚本只修改 `OpenClaw Gateway`，不会动 watchdog 任务

[CmdletBinding()]
param()

$ErrorActionPreference = 'Stop'

$taskName = 'OpenClaw Gateway'
$tempXml = Join-Path $env:TEMP 'openclaw-gateway-battery-policy-fix.xml'

function Write-Step {
    param([string]$Message)
    Write-Host "==> $Message" -ForegroundColor Cyan
}

function Set-TaskNodeValue {
    param(
        [xml]$Xml,
        [System.Xml.XmlNamespaceManager]$Ns,
        [string]$XPath,
        [string]$Value
    )

    $node = $Xml.SelectSingleNode($XPath, $Ns)
    if ($null -eq $node) {
        throw "Task XML node not found: $XPath"
    }

    $node.InnerText = $Value
}

Write-Step "Exporting scheduled task XML: $taskName"
[xml]$xml = schtasks /Query /TN $taskName /XML

$ns = New-Object System.Xml.XmlNamespaceManager($xml.NameTable)
$ns.AddNamespace('t', 'http://schemas.microsoft.com/windows/2004/02/mit/task')

Set-TaskNodeValue -Xml $xml -Ns $ns -XPath '//t:DisallowStartIfOnBatteries' -Value 'false'
Set-TaskNodeValue -Xml $xml -Ns $ns -XPath '//t:StopIfGoingOnBatteries' -Value 'false'

Write-Step 'Saving patched XML to temp file'
$xml.Save($tempXml)

try {
    Write-Step 'Re-registering scheduled task with battery-safe settings'
    $createOutput = schtasks /Create /TN $taskName /XML $tempXml /F 2>&1 | Out-String
    if ($LASTEXITCODE -ne 0) {
        throw ($createOutput.Trim())
    }
}
catch {
    $message = ($_ | Out-String).Trim()
    Write-Host ''
    Write-Host 'OpenClaw Gateway battery policy repair did not complete.' -ForegroundColor Red
    if ($message) {
        Write-Host "  - Details: $message" -ForegroundColor Red
    }
    Write-Host '  - Tip: on this Windows handheld, please retry this script in an elevated PowerShell window.' -ForegroundColor Yellow
    exit 2
}
finally {
    Remove-Item $tempXml -ErrorAction SilentlyContinue
}

Write-Step 'Verifying patched task XML'
[xml]$verifyXml = schtasks /Query /TN $taskName /XML
$verifyNs = New-Object System.Xml.XmlNamespaceManager($verifyXml.NameTable)
$verifyNs.AddNamespace('t', 'http://schemas.microsoft.com/windows/2004/02/mit/task')

$disallow = $verifyXml.SelectSingleNode('//t:DisallowStartIfOnBatteries', $verifyNs)
$stop = $verifyXml.SelectSingleNode('//t:StopIfGoingOnBatteries', $verifyNs)

if ($disallow.InnerText -ne 'false' -or $stop.InnerText -ne 'false') {
    Write-Host ''
    Write-Host 'OpenClaw Gateway battery policy verification failed.' -ForegroundColor Red
    Write-Host "  - DisallowStartIfOnBatteries = $($disallow.InnerText)" -ForegroundColor Red
    Write-Host "  - StopIfGoingOnBatteries = $($stop.InnerText)" -ForegroundColor Red
    exit 3
}

Write-Host ''
Write-Host 'OpenClaw Gateway battery policy has been repaired for this Windows handheld.' -ForegroundColor Green
Write-Host "  - DisallowStartIfOnBatteries = $($disallow.InnerText)"
Write-Host "  - StopIfGoingOnBatteries = $($stop.InnerText)"
