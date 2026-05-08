# 适用机器：掌机（Windows）
# 系统 / OS：Windows
# 用途：在 Windows 环境下拉取 workspace 最新规则，并在需要时重启 OpenClaw gateway。
# 用法：
#   .\scripts\update-openclaw.ps1
#   或通过 .cmd 包装器：.\scripts\update-openclaw.cmd

[CmdletBinding()]
param(
    [switch]$AlwaysRestart
)

$ErrorActionPreference = 'Stop'

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$repoRoot = Split-Path -Parent $scriptDir

function Resolve-OpenClawCommand {
    $cmd = Get-Command openclaw.cmd -ErrorAction SilentlyContinue
    if ($cmd) { return $cmd.Source }

    $plain = Get-Command openclaw -ErrorAction SilentlyContinue
    if ($plain) { return $plain.Source }

    throw '找不到 openclaw / openclaw.cmd，请先确认 OpenClaw 已正确安装并在 PATH 中。'
}

Push-Location $repoRoot
try {
    Write-Host "📦 当前仓库: $repoRoot"

    $before = (git rev-parse HEAD).Trim()
    Write-Host "🔎 当前提交: $before"

    Write-Host '⬇️  开始拉取 GitHub 更新...'
    git pull --ff-only

    $after = (git rev-parse HEAD).Trim()
    $openclawCmd = Resolve-OpenClawCommand

    if ($AlwaysRestart -or $before -ne $after) {
        if ($before -ne $after) {
            Write-Host "✅ 检测到更新: $before -> $after"
        } else {
            Write-Host '♻️  未检测到新提交，但按要求执行重启。'
        }

        Write-Host '🔁 正在重启 OpenClaw gateway...'
        & $openclawCmd gateway restart
        Write-Host '✅ OpenClaw gateway 已重启。'
    }
    else {
        Write-Host 'ℹ️  没有检测到新的提交，跳过重启。'
    }
}
finally {
    Pop-Location
}
