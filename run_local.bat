@echo off
REM Запуск локального сервера для разработки (Windows)

echo 🚀 Запуск локального сервера FastAPI...

REM Активируем виртуальное окружение (если есть)
if exist venv\Scripts\activate.bat (
    call venv\Scripts\activate.bat
)

REM Запускаем сервер
python api_main.py

pause
