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

$updated = $false
$restarted = $false
$before = $null
$after = $null
$openclawCmd = $null

Push-Location $repoRoot
try {
    Write-Host '================ 掌机（Windows）OpenClaw 更新 =================' -ForegroundColor Cyan
    Write-Host '推荐场景：在掌机上同步最新规则并按需自动重启 gateway。' -ForegroundColor DarkCyan
    Write-Host "📦 当前仓库: $repoRoot"

    $before = (git rev-parse HEAD).Trim()
    Write-Host "🔎 更新前提交: $before"

    Write-Host '⬇️  开始拉取 GitHub 更新...'
    git pull --ff-only

    $after = (git rev-parse HEAD).Trim()
    $openclawCmd = Resolve-OpenClawCommand
    $updated = $before -ne $after

    if ($AlwaysRestart -or $updated) {
        if ($updated) {
            Write-Host "✅ 检测到更新: $before -> $after" -ForegroundColor Green
        } else {
            Write-Host '♻️  未检测到新提交，但按要求执行重启。' -ForegroundColor Yellow
        }

        Write-Host '🔁 正在重启 OpenClaw gateway...'
        & $openclawCmd gateway restart
        $restarted = $true
        Write-Host '✅ OpenClaw gateway 已重启。' -ForegroundColor Green
    }
    else {
        Write-Host 'ℹ️  没有检测到新的提交，跳过重启。' -ForegroundColor Yellow
    }

    Write-Host ''
    Write-Host '================ 更新结果摘要 ================' -ForegroundColor Cyan
    Write-Host ('- 当前机器应按：掌机（Windows）理解')
    Write-Host ("- 更新前提交：{0}" -f $before)
    Write-Host ("- 更新后提交：{0}" -f $after)
    Write-Host ("- 是否拉到新提交：{0}" -f ($(if ($updated) { '是' } else { '否' })))
    Write-Host ("- 是否执行 gateway 重启：{0}" -f ($(if ($restarted) { '是' } else { '否' })))
    Write-Host '- 下一步建议：'
    Write-Host '  1. 看下面的 gateway status 快查输出'
    Write-Host '  2. 打开 http://127.0.0.1:18789/'
    Write-Host '  3. 若是微信问题，再看 docs/掌机-Windows-OpenClaw-维护说明.md'

    Write-Host ''
    Write-Host '================ gateway status 快查 ================' -ForegroundColor Cyan
    try {
        & $openclawCmd gateway status
    }
    catch {
        Write-Warning ("gateway status 快查失败：{0}" -f $_.Exception.Message)
        Write-Host '你可以稍后手动执行：openclaw gateway status'
    }
}
finally {
    Pop-Location
}
