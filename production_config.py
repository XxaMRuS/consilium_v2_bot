# -*- coding: utf-8 -*-
"""
Production-ready конфигурация и мониторинг
Расширяет базовый config.py без ломания существующего функционала
"""

import os
import logging
from dotenv import load_dotenv
from telegram import Bot

load_dotenv()

logger = logging.getLogger(__name__)


class ProductionConfig:
    """Production конфигурация для мониторинга и алертов"""

    # Admin Settings
    ADMIN_CHAT_ID = int(os.getenv('ADMIN_CHAT_ID', 0))  # Для алертов

    # Monitoring Settings
    ENABLE_HEALTH_CHECK = os.getenv('ENABLE_HEALTH_CHECK', 'true').lower() == 'true'
    ENABLE_METRICS = os.getenv('ENABLE_METRICS', 'true').lower() == 'true'
    ENABLE_ALERTS = os.getenv('ENABLE_ALERTS', 'true').lower() == 'true'

    # Alert Settings
    ALERT_ERROR_RATE_THRESHOLD = int(os.getenv('ALERT_ERROR_RATE_THRESHOLD', 10))  # ошибок в час
    ALERT_CPU_THRESHOLD = int(os.getenv('ALERT_CPU_THRESHOLD', 80))  # CPU %
    ALERT_MEMORY_THRESHOLD = int(os.getenv('ALERT_MEMORY_THRESHOLD', 80))  # Memory %

    # Rate Limiting Settings
    RATE_LIMIT_ENABLED = os.getenv('RATE_LIMIT_ENABLED', 'true').lower() == 'true'
    RATE_LIMIT_REQUESTS = int(os.getenv('RATE_LIMIT_REQUESTS', 20))
    RATE_LIMIT_PERIOD = int(os.getenv('RATE_LIMIT_PERIOD', 60))
    RATE_LIMIT_BLOCK_DURATION = int(os.getenv('RATE_LIMIT_BLOCK_DURATION', 300))

    @classmethod
    def get_admin_chat_id(cls) -> int:
        """Получить admin chat ID с fallback"""
        return cls.ADMIN_CHAT_ID if cls.ADMIN_CHAT_ID > 0 else None


def setup_production_monitoring(bot_token: str):
    """Настройка production мониторинга"""
    from health_monitor import init_health_monitoring

    if ProductionConfig.ENABLE_HEALTH_CHECK:
        admin_chat_id = ProductionConfig.get_admin_chat_id()
        init_health_monitoring(bot_token, admin_chat_id)
        logger.info("✅ Health monitoring enabled")
    else:
        logger.info("ℹ️ Health monitoring disabled")


def check_production_requirements() -> tuple:
    """Проверка требований для production"""
    warnings = []
    errors = []

    # Обязательные требования для production
    if not os.getenv('BOT_TOKEN'):
        errors.append("BOT_TOKEN не установлен")

    if not os.getenv('DATABASE_URL'):
        errors.append("DATABASE_URL не установлен")

    if os.getenv('ENVIRONMENT', 'development') == 'production':
        if not os.getenv('ADMIN_CHAT_ID'):
            warnings.append("ADMIN_CHAT_ID не установлен - алерты не будут отправляться")

        if not os.getenv('ENABLE_HEALTH_CHECK'):
            warnings.append("ENABLE_HEALTH_CHECK отключен - невозможно мониторить здоровье бота")

    return (len(errors) == 0, errors, warnings)


def log_startup_info():
    """Логировать информацию о запуске"""
    environment = os.getenv('ENVIRONMENT', 'development')

    logger.info(f"🚀 ================================================")
    logger.info(f"🚀 БОТ ЗАПУЩЕН")
    logger.info(f"🚀 ================================================")
    logger.info(f"🌍 Окружение: {environment}")
    logger.info(f"📊 Мониторинг: {'включен' if ProductionConfig.ENABLE_HEALTH_CHECK else 'выключен'}")
    logger.info(f"🚨 Алерты: {'включены' if ProductionConfig.ENABLE_ALERTS else 'выключены'}")
    logger.info(f"⏱️ Rate limiting: {'включен' if ProductionConfig.RATE_LIMIT_ENABLED else 'выключен'}")

    if environment == 'production':
        logger.info("⚠️ РЕЖИМ PRODUCTION - все проверки включены")
    else:
        logger.info("🔧 РЕЖИМ РАЗРАБОТКИ - упрощенные проверки")

    logger.info(f"🚀 ================================================")


# ==================== FASTAPI ENDPOINTS ДЛЯ RENDER ====================

async def health_check_endpoint():
    """
    Health check endpoint для Render и других хостингов

    Добавить в main.py:

    @app.get("/health")
    async def health():
        return await health_check_endpoint()
    """
    from health_monitor import get_health_status

    health_status = await get_health_status()

    # Возвращаем HTTP статус в зависимости от здоровья
    http_status = 200 if health_status["overall_status"] == "healthy" else 503

    return {
        "status": health_status["overall_status"],
        "timestamp": health_status["timestamp"],
        "checks": health_status["checks"]
    }, http_status


async def metrics_endpoint():
    """
    Metrics endpoint для мониторинга

    Добавить в main.py:

    @app.get("/metrics")
    async def metrics():
        return await metrics_endpoint()
    """
    from health_monitor import get_metrics

    metrics = get_metrics()
    return metrics


if __name__ == "__main__":
    # Тест конфигурации
    is_valid, errors, warnings = check_production_requirements()

    print("🔍 ПРОВЕРКА КОНФИГУРАЦИИ:")
    print(f"✅ Валидность: {'OK' if is_valid else 'ERROR'}")

    if errors:
        print("\n❌ ОШИБКИ:")
        for error in errors:
            print(f"  - {error}")

    if warnings:
        print("\n⚠️ ПРЕДУПРЕЖДЕНИЯ:")
        for warning in warnings:
            print(f"  - {warning}")

    if is_valid:
        print("\n✅ Конфигурация готова для production!")
        log_startup_info()
    else:
        print("\n❌ Исправьте ошибки перед запуском")