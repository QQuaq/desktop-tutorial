@echo off
setlocal
rem PS5 Chrome - Windows baslatici. Cift tiklayin veya: ps5chrome.bat [--url https://...] [--port 8080]
cd /d "%~dp0"
chcp 65001 >nul

set "PYCMD="
where py >nul 2>nul && set "PYCMD=py -3"
if not defined PYCMD (
  where python >nul 2>nul && set "PYCMD=python"
)
if not defined PYCMD (
  echo Python 3.9+ bulunamadi.
  echo Kurmak icin:  winget install Python.Python.3.12
  echo veya https://www.python.org/downloads/ adresinden indirin ^(kurulumda "Add to PATH" secin^).
  pause
  exit /b 1
)

%PYCMD% -m ps5chrome %*
if errorlevel 1 pause
endlocal
