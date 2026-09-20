@echo off
chcp 936 >nul
title QQ机器人 账号切换（SnowLuma 版）
cd /d "%~dp0"
setlocal enabledelayedexpansion

echo ==========================================
echo   QQ机器人  账号切换（SnowLuma 协议端）
echo ==========================================
echo.
echo   把「在 5099 网页点卸载、再加载账号」变成一条命令
echo   自动做：卸载其它账号 hook - 校正协议端配置 - 重载目标账号
echo   做不到：QQ 客户端换号（需人工登录，密码/手机验证）
echo.

rem ---------- 挑一个 Python ----------
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
  echo [错误] 没找到可用的 Python。请先跑『一键部署-SnowLuma版.bat』。
  pause
  exit /b 1
)

rem ---------- 固定 Python 输出编码，与本窗口 chcp 936 一致 ----------
set "PYTHONUTF8=0"
set "PYTHONIOENCODING=gbk"

if /i "%~1"=="list" goto :list
if /i "%~1"=="ls" goto :list

set "TARGET=%~1"
if defined TARGET goto :run
echo 提示：直接回车 = 使用 部署配置.json 里配置的账号
set /p TARGET=请输入目标 QQ 号：
:run
"!PY!" "%~dp0deploy\snowluma_account.py" switch "!TARGET!"
goto :done

:list
"!PY!" "%~dp0deploy\snowluma_account.py" list

:done
echo.
echo ------------------------------------------------------------
echo 查看当前所有账号与 hook 状态：
echo   切换账号.bat list
echo 只卸载某个账号：
echo   "%PY%" "%~dp0deploy\snowluma_account.py" unload 目标QQ
echo ------------------------------------------------------------
pause
