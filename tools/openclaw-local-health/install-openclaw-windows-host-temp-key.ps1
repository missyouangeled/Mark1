[CmdletBinding()]
param(
    [string]$AuthorizedKeysPath = "$HOME\.ssh\authorized_keys"
)

$ErrorActionPreference = 'Stop'

$key = @'
ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAICd8h24Ui7kjP84fsAVdJL1Xi8/A5REtQLkka6UaSa6D openclaw-windows-host-temp
'@

$sshDir = Split-Path -Parent $AuthorizedKeysPath
if (-not (Test-Path -LiteralPath $sshDir)) {
    New-Item -ItemType Directory -Force -Path $sshDir | Out-Null
}

$existing = ''
if (Test-Path -LiteralPath $AuthorizedKeysPath) {
    $existing = Get-Content -LiteralPath $AuthorizedKeysPath -Raw -ErrorAction SilentlyContinue
}

$trimmedKey = $key.Trim()
if ($existing -notmatch [regex]::Escape($trimmedKey)) {
    if ($existing -and -not $existing.EndsWith("`n")) {
        Add-Content -LiteralPath $AuthorizedKeysPath -Value ''
    }
    Add-Content -LiteralPath $AuthorizedKeysPath -Value $trimmedKey
}

& icacls.exe $sshDir /inheritance:r /grant:r "$env:USERNAME:(OI)(CI)F" "SYSTEM:(OI)(CI)F" | Out-Null
& icacls.exe $AuthorizedKeysPath /inheritance:r /grant:r "$env:USERNAME:F" "SYSTEM:F" | Out-Null

Write-Host ("User: " + (& whoami.exe))
Write-Host ("AuthorizedKeysPath: " + $AuthorizedKeysPath)
Write-Host 'Temp SSH key installed.'
