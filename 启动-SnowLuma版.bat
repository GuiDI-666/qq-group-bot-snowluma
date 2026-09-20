@echo off
chcp 936 >nul
title QQ机器人 启动（SnowLuma 版）
cd /d "%~dp0"
setlocal enabledelayedexpansion

echo ==========================================
echo   QQ机器人  一键启动（SnowLuma 协议端 + NoneBot 业务框架）
echo ==========================================
echo.
echo   协议端：SnowLuma（hook 真实 QQ 客户端，WebUI 5099）
echo   业务端：NoneBot（群管功能，WebUI 无 / 端口 8081）
echo   与旧栈『启动机器人.bat』(NapCat) 互不影响，可并存
echo   关闭本窗口只停业务框架；协议端在另一个 SnowLuma 窗口里
echo.

if not exist "%~dp0SnowLuma\launcher.bat" (
  echo [错误] 没找到 SnowLuma\launcher.bat
  echo   请先双击『一键部署-SnowLuma版.bat』，或见 docs\部署说明.md
  echo.
  pause
  exit /b 1
)

netstat -ano | findstr /c:"LISTENING" | findstr /c:":5099" >nul
if !errorlevel! equ 0 (
  echo [提示] 5099 端口已有监听，SnowLuma 可能已在运行，本次跳过启动协议端。
) else (
  echo [1/2] 启动 SnowLuma 协议端（新窗口）...
  start "SnowLuma 协议端" /D "%~dp0SnowLuma" cmd /c launcher.bat
  echo       等待协议端就绪（约 10 秒）...
  timeout /t 10 /nobreak >nul
)

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


echo [2/2] 启动业务框架，使用 Python：!PY!
echo.
if not exist "%~dp0logs" mkdir "%~dp0logs"
echo 业务框架输出重定向到 logs\bot.log（实时日志可打开该文件查看）
pushd "%~dp0qq-group-bot"
"!PY!" -u bot.py >> "%~dp0logs\bot.log" 2>&1
popd

echo.
echo 业务框架已退出（详情见 logs\bot.log 末尾）。
echo   若提示端口 8081 被占用，说明已有一份在跑，先双击『关闭-SnowLuma版.bat』。
echo   若协议端也需停止，关闭标题为『SnowLuma 协议端』的窗口即可。
pause
