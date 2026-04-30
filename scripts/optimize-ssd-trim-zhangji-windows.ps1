# 适用机器：掌机（Windows）
# 系统 / OS：Windows
# 用途：对本机 SSD 卷执行 Analyze + ReTrim（需要管理员权限）
# 用法：以管理员身份运行
#   powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\optimize-ssd-trim-zhangji-windows.ps1

[CmdletBinding()]
param(
    [string[]]$DriveLetters = @('C', 'D')
)

$ErrorActionPreference = 'Stop'

foreach ($drive in $DriveLetters) {
    Write-Host "==> Analyze $drive:" -ForegroundColor Cyan
    Optimize-Volume -DriveLetter $drive -Analyze -Verbose

    Write-Host "==> ReTrim $drive:" -ForegroundColor Cyan
    Optimize-Volume -DriveLetter $drive -ReTrim -Verbose
}

Write-Host "`n==> Volume summary" -ForegroundColor Green
Get-Volume | Select-Object DriveLetter,FileSystemLabel,SizeRemaining,Size | Format-Table -AutoSize
