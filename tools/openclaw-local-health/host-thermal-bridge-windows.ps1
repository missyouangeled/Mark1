# 适用机器：通用（宿主机 Windows）
# 系统 / OS：Windows
# 用途：在 Windows 宿主机上读取 CPU/热区温度并写出 OpenClaw 本地健康监督可读取的桥接 JSON。

[CmdletBinding()]
param(
    [string]$OutputPath = "$env:TEMP\openclaw-host-thermal-bridge.json"
)

$ErrorActionPreference = 'Stop'

function Get-FirstText {
    param(
        [Parameter(ValueFromRemainingArguments = $true)]
        $Values
    )
    foreach ($value in $Values) {
        if ($null -eq $value) { continue }
        $text = [string]$value
        if (-not [string]::IsNullOrWhiteSpace($text)) {
            return $text
        }
    }
    return $null
}

function Convert-ToTempC {
    param($Value)
    if ($null -eq $Value) { return $null }
    try { $num = [double]$Value } catch { return $null }
    if ([math]::Abs($num) -ge 1000) { $num = $num / 1000.0 }
    if ($num -lt 1 -or $num -gt 130) { return $null }
    return [math]::Round($num, 1)
}

function Get-LibreHardwareMonitorTemps {
    $rows = @()
    try {
        $sensors = Get-CimInstance -Namespace 'root/LibreHardwareMonitor' -ClassName Sensor -ErrorAction Stop |
            Where-Object { $_.SensorType -eq 'Temperature' }
        foreach ($sensor in $sensors) {
            $label = Get-FirstText $sensor.Name $sensor.Identifier 'Sensor'
            $matchText = "$label $($sensor.Identifier)"
            if ($matchText -notmatch 'CPU|Core|Package|Tctl|Tdie') { continue }
            $tempC = Convert-ToTempC $sensor.Value
            if ($null -eq $tempC) { continue }
            $rows += [pscustomobject]@{ label = $label; tempC = $tempC; source = 'LibreHardwareMonitor' }
        }
    } catch {}
    return $rows
}

function Get-OpenHardwareMonitorTemps {
    $rows = @()
    try {
        $sensors = Get-CimInstance -Namespace 'root/OpenHardwareMonitor' -ClassName Sensor -ErrorAction Stop |
            Where-Object { $_.SensorType -eq 'Temperature' }
        foreach ($sensor in $sensors) {
            $label = Get-FirstText $sensor.Name $sensor.Identifier 'Sensor'
            $matchText = "$label $($sensor.Identifier)"
            if ($matchText -notmatch 'CPU|Core|Package|Tctl|Tdie') { continue }
            $tempC = Convert-ToTempC $sensor.Value
            if ($null -eq $tempC) { continue }
            $rows += [pscustomobject]@{ label = $label; tempC = $tempC; source = 'OpenHardwareMonitor' }
        }
    } catch {}
    return $rows
}

function Get-AcpiThermalTemps {
    $rows = @()
    try {
        $zones = Get-CimInstance -Namespace 'root/wmi' -ClassName MSAcpi_ThermalZoneTemperature -ErrorAction Stop
        foreach ($zone in $zones) {
            if ($null -eq $zone.CurrentTemperature) { continue }
            $tempC = [math]::Round(($zone.CurrentTemperature / 10.0) - 273.15, 1)
            if ($tempC -lt 1 -or $tempC -gt 130) { continue }
            $label = Get-FirstText $zone.InstanceName 'ACPI Thermal Zone'
            $rows += [pscustomobject]@{ label = $label; tempC = $tempC; source = 'MSAcpi_ThermalZoneTemperature' }
        }
    } catch {}
    return $rows
}

$probes = @()
$probes += Get-LibreHardwareMonitorTemps
if (-not $probes) { $probes += Get-OpenHardwareMonitorTemps }
if (-not $probes) { $probes += Get-AcpiThermalTemps }

$payload = $null
if ($probes.Count -gt 0) {
    $sorted = $probes | Sort-Object tempC -Descending
    $hottest = $sorted[0]
    $status = 'ok'
    $summary = '宿主机温度正常'
    if ($hottest.tempC -ge 95) {
        $status = 'critical'
        $summary = '宿主机 CPU 温度过高'
    } elseif ($hottest.tempC -ge 85) {
        $status = 'warn'
        $summary = '宿主机 CPU 温度偏高'
    }

    $payload = [ordered]@{
        source = $hottest.source
        updatedAt = (Get-Date).ToString('o')
        status = $status
        summary = $summary
        detail = "最高 $($hottest.tempC)°C（$($hottest.label)）"
        tempC = $hottest.tempC
        label = $hottest.label
        probes = @($sorted | ForEach-Object {
            [ordered]@{
                label = $_.label
                tempC = $_.tempC
                source = $_.source
            }
        })
    }
} else {
    $payload = [ordered]@{
        source = 'windows-host'
        updatedAt = (Get-Date).ToString('o')
        status = 'unavailable'
        summary = '宿主机温度不可读'
        detail = '当前未能从 LibreHardwareMonitor / OpenHardwareMonitor / ACPI 热区读到可用温度。'
        probes = @()
    }
}

$dir = Split-Path -Parent $OutputPath
if ($dir) {
    New-Item -ItemType Directory -Force -Path $dir | Out-Null
}

$payload | ConvertTo-Json -Depth 6 | Set-Content -Encoding UTF8 -Path $OutputPath
Write-Host "Wrote host thermal bridge: $OutputPath"
Write-Host ("Summary: " + $payload.summary)
Write-Host ("Detail: " + $payload.detail)
