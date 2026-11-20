@echo off
chcp 65001 >nul
cd /d "%~dp0"
title PS5 Altyazi Cevirmeni

if exist "PS5Altyazi\PS5Altyazi.exe" (
  start "" "PS5Altyazi\PS5Altyazi.exe"
  exit /b 0
)

set "PY="
where py >nul 2>nul && set "PY=py -3"
if not defined PY (
  where python >nul 2>nul && set "PY=python"
)
if not defined PY (
  echo.
  echo  Python bulunamadi. Kuruluyor (winget)...
  winget install -e --id Python.Python.3.12 --accept-package-agreements --accept-source-agreements
  echo.
  echo  Python kuruldu. Bu pencereyi kapatip baslat.bat'i TEKRAR calistirin.
  pause
  exit /b 1
)

if not exist ".venv\Scripts\pythonw.exe" (
  echo.
  echo  Ilk kurulum (bir kez, 1-3 dakika)...
  %PY% -m venv .venv
  if errorlevel 1 (
    echo Sanal ortam olusturulamadi.
    pause
    exit /b 1
  )
)

".venv\Scripts\python.exe" -m pip install --disable-pip-version-check -q -r requirements.txt
if errorlevel 1 (
  echo Paketler kurulamadi. Internet baglantisini kontrol edin.
  pause
  exit /b 1
)

start "" ".venv\Scripts\pythonw.exe" -m ps5sub
