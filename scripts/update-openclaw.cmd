@echo off
REM 适用机器：掌机（Windows）
REM 系统 / OS：Windows
REM 用途：在 Windows 环境下调用 update-openclaw.ps1，同步 workspace 最新规则并按需重启 gateway。
setlocal
set "SCRIPT_DIR=%~dp0"
powershell -NoProfile -ExecutionPolicy Bypass -File "%SCRIPT_DIR%update-openclaw.ps1" %*
