@echo off
REM Запуск ngrok для VK Mini App

echo 🌐 Запуск ngrok...
echo.

REM Проверяем установлен ли ngrok
where ngrok >nul 2>nul
if %ERRORLEVEL% NEQ 0 (
    echo ❌ Ngrok не установлен!
    echo.
    echo 1. Скачай ngrok: https://ngrok.com/download
    echo 2. Распакуй в папку
    echo 3. Добавь в PATH
    echo.
    pause
    exit /b 1
)

REM Запуск ngrok
ngrok http 8000

pause
