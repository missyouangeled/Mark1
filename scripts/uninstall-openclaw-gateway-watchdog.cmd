@echo off
REM 适用机器：掌机（Windows）
REM 系统 / OS：Windows
setlocal
set "SCRIPT_DIR=%~dp0"
powershell -NoProfile -ExecutionPolicy Bypass -File "%SCRIPT_DIR%uninstall-openclaw-gateway-watchdog.ps1" %*
