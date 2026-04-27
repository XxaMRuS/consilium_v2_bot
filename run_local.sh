#!/bin/bash
# Запуск локального сервера для разработки

echo "🚀 Запуск локального сервера FastAPI..."

# Активируем виртуальное окружение (если есть)
if [ -d "venv" ]; then
    source venv/bin/activate
fi

# Запускаем сервер
python api_main.py
