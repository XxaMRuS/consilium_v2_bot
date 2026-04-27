@echo off
REM Запуск VK Tunnel с правильными параметрами

echo 🌐 Запуск VK Tunnel для VK Mini App...
echo.

REM Параметры
set APP_ID=54567668
set HTTP_PORT=8000
set HTTPS_PORT=6001

echo APP_ID: %APP_ID%
echo HTTP Port: %HTTP_PORT%
echo HTTPS Port: %HTTPS_PORT%
echo.

REM Запуск VK Tunnel
vk-tunnel --app-id=%APP_ID% --http-port=%HTTP_PORT% --https-port=%HTTPS_PORT% --mode=local

pause
