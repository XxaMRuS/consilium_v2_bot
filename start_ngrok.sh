#!/bin/bash
# Запуск ngrok для VK Mini App

echo "🌐 Запуск ngrok..."
echo ""

# Проверяем установлен ли ngrok
if ! command -v ngrok &> /dev/null; then
    echo "❌ Ngrok не установлен!"
    echo ""
    echo "1. Скачай ngrok: https://ngrok.com/download"
    echo "2. Распакуй и добавь в PATH"
    echo "3. Или установи через: brew install ngrok"
    echo ""
    exit 1
fi

# Запуск ngrok
ngrok http 8000
