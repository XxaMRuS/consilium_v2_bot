#!/bin/bash
# Запуск VK Tunnel с правильными параметрами

echo "🌐 Запуск VK Tunnel для VK Mini App..."
echo ""

# Параметры
APP_ID=54567668
HTTP_PORT=8000
HTTPS_PORT=6001

echo "APP_ID: $APP_ID"
echo "HTTP Port: $HTTP_PORT"
echo "HTTPS Port: $HTTPS_PORT"
echo ""

# Запуск VK Tunnel
vk-tunnel --app-id=$APP_ID --http-port=$HTTP_PORT --https-port=$HTTPS_PORT --mode=local
