@echo off
REM 适用机器：掌机（Windows）
REM 系统 / OS：Windows
REM 用途：在 Windows 环境下调用 update-openclaw.ps1，同步 workspace 最新规则并按需重启 gateway。
setlocal
set "SCRIPT_DIR=%~dp0"
set "SHOULD_PAUSE="
echo %CMDCMDLINE% | find /I "%~f0" >nul && set "SHOULD_PAUSE=1"

echo ==================================================
echo 掌机（Windows）OpenClaw 更新入口
echo - 推荐直接双击这个 .cmd
echo - 它会进入 PowerShell 执行 git pull 和按需重启
echo ==================================================
powershell -NoProfile -ExecutionPolicy Bypass -File "%SCRIPT_DIR%update-openclaw.ps1" %*
set "EXITCODE=%ERRORLEVEL%"

if "%SHOULD_PAUSE%"=="1" (
  echo.
  if "%EXITCODE%"=="0" (
    echo 更新脚本执行完成。按任意键关闭窗口...
  ) else (
    echo 更新脚本执行失败，退出码：%EXITCODE%。按任意键关闭窗口...
  )
  pause >nul
)

exit /b %EXITCODE%
