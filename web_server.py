# -*- coding: utf-8 -*-
"""
Минимальный веб-сервер для Render health check
"""
from flask import Flask
import threading
import logging

logger = logging.getLogger(__name__)

app = Flask(__name__)

@app.route('/')
def health():
    """Health check endpoint для Render"""
    return "Bot is running", 200

@app.route('/health')
def health_detailed():
    """Детальный health check"""
    return {
        "status": "ok",
        "service": "fitness-bot",
        "message": "Bot is running"
    }, 200

def run_web():
    """Запускает веб-сервер в отдельном потоке"""
    try:
        logger.info("🌐 Веб-сервер запущен на порту 10000")
        app.run(host='0.0.0.0', port=10000, threaded=True)
    except Exception as e:
        logger.error(f"❌ Ошибка веб-сервера: {e}")

def start_web_server():
    """Запускает веб-сервер в фоновом потоке"""
    thread = threading.Thread(target=run_web, daemon=True)
    thread.start()
    logger.info("✅ Веб-сервер запущен в фоновом режиме")
    return thread
