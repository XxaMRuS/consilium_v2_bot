#!/bin/bash
# Скрипт для запуска API на Render.com

echo "🚀 Starting Fitness Bot API..."

# Проверяем что это API сервер (не Telegram бот)
if [ "$RUN_API_SERVER" = "true" ]; then
    echo "📡 Starting REST API server..."
    python api_main.py
else
    echo "🤖 Starting Telegram bot..."
    python bot.py
fi
