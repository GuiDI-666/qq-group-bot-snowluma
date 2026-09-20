@echo off
chcp 936 >nul
title QQ机器人 一键部署（SnowLuma 版）
cd /d "%~dp0"
setlocal enabledelayedexpansion

echo ==========================================
echo   QQ机器人  一键部署（SnowLuma 协议端 + NoneBot 业务框架）
echo ==========================================
echo.
echo   本脚本会依次完成：
echo     1. 准备 Python 环境并安装 nonebot 依赖（走国内镜像）
echo     2. 解压 SnowLuma 发行包到 SnowLuma\ （没有包会给出下载地址）
echo     3. 写入 OneBot v11 网络配置（HTTP 3100 / WS 3001 / 连业务框架 8081）
echo     4. 体检：确认内核与 hook 组件齐全
echo.
echo   需要你手工完成的只有：让桌面版 QQ 处于登录状态 + 首次扫码登录小号。
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
  for /f "delims=" %%P in ('where python 2^>nul ^| findstr /i /v "WindowsApps"') do (
    if not defined PY set "PY=%%P"
  )
)
for /d %%D in ("%USERPROFILE%\.workbuddy\binaries\python\versions\*") do (
  if not defined PY if exist "%%D\python.exe" set "PY=%%D\python.exe"
)

if not defined PY (
  echo [错误] 本机没找到任何 Python，无法继续。
  echo   请先安装 Python 3.9~3.13（安装时勾选 Add to PATH），再重跑本脚本。
  echo   下载：https://mirrors.aliyun.com/python-release/windows/
  echo.
  pause
  exit /b 1
)

echo 使用 Python：!PY!
echo.
rem ---------- 固定 Python 输出编码，与本窗口 chcp 936 一致，避免中文乱码 ----------
set "PYTHONUTF8=0"
set "PYTHONIOENCODING=gbk"


"!PY!" "%~dp0deploy\snowluma_deploy.py"

echo.
echo 部署流程结束。按任意键关闭窗口。
pause
