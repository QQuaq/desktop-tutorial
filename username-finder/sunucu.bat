@echo off
chcp 65001 >nul
cd /d "%~dp0"
title Kullanici adi arama (LAN sunucu)

echo.
echo  Kurulum / derleme (ilk sefer biraz surer)...
call npm ci
if errorlevel 1 (
  call npm install
)
call npm run build
if errorlevel 1 (
  echo Derleme basarisiz.
  pause
  exit /b 1
)

echo.
echo  Sunucu basliyor — sadece bu ag / bu PC...
call node scripts/print-lan-urls.mjs
call npm run start:lan

pause