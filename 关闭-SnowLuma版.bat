@echo off
chcp 936 >nul
title QQ机器人 停止（SnowLuma 版）
cd /d "%~dp0"
setlocal enabledelayedexpansion

echo ==========================================
echo   QQ机器人  停止（SnowLuma 协议端 + NoneBot 业务框架）
echo ==========================================
echo 只停本套（SnowLuma + 业务框架），不会动旧栈 NapCat / 看门狗。
echo.

rem ---------- 挑一个"装了 nonebot"的 Python ----------
set "PY="
if exist "%~dp0venv\Scripts\python.exe" set "PY=%~dp0venv\Scripts\python.exe"
if not defined PY if exist "%~dp0.venv\Scripts\python.exe" set "PY=%~dp0.venv\Scripts\python.exe"

if not defined PY (
  for /f "delims=" %%P in ('where python 2^>nul ^| findstr /i /v "WindowsApps"') do (
    if not defined PY (
      "%%P" -c "import nonebot" >nul 2>nul
      if !errorlevel! equ 0 set "PY=%%P"
    )
  )
)

for /d %%D in ("%USERPROFILE%\.workbuddy\binaries\python\versions\*") do (
  if not defined PY if exist "%%D\python.exe" (
    "%%D\python.exe" -c "import nonebot" >nul 2>nul
    if !errorlevel! equ 0 set "PY=%%D\python.exe"
  )
)

if not defined PY (
  echo [错误] 没有找到"已安装 nonebot"的 Python 解释器。
  echo   请先双击『一键部署-SnowLuma版.bat』自动准备环境。
  echo.
  pause
  exit /b 1
)

rem ---------- 固定 Python 输出编码，与本窗口 chcp 936 一致，避免中文乱码 ----------
set "PYTHONUTF8=0"
set "PYTHONIOENCODING=gbk"


"!PY!" "%~dp0deploy\snowluma_ctl.py" stop

echo.
pause
