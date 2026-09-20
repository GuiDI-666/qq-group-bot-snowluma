@echo off
chcp 936 >nul
title QQ机器人 自检（SnowLuma 版）
cd /d "%~dp0"
setlocal enabledelayedexpansion

echo ==========================================
echo   QQ机器人  全网自检（SnowLuma 版）
echo ==========================================
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
  rem 自检不需要 nonebot：退而求其次，用任意可用 Python
  for /f "delims=" %%P in ('where python 2^>nul ^| findstr /i /v "WindowsApps"') do (
    if not defined PY set "PY=%%P"
  )
)
for /d %%D in ("%USERPROFILE%\.workbuddy\binaries\python\versions\*") do (
  if not defined PY if exist "%%D\python.exe" set "PY=%%D\python.exe"
)

if not defined PY (
  echo [错误] 没找到可用的 Python，无法自检。请先跑『一键部署-SnowLuma版.bat』。
  pause
  exit /b 1
)

rem ---------- 固定 Python 输出编码，与本窗口 chcp 936 一致，避免中文乱码 ----------
set "PYTHONUTF8=0"
set "PYTHONIOENCODING=gbk"


"!PY!" "%~dp0deploy\snowluma_ctl.py" check

echo.
echo 自检结束。报告细节见上方输出；对照 docs\部署说明-SnowLuma版.md 排障章节。
pause
