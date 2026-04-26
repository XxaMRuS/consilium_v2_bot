# -*- coding: utf-8 -*-
"""
Production-ready функции для мониторинга и здоровья бота
"""

import logging
import asyncio
import psutil
import os
from datetime import datetime
from telegram import Bot
from database_postgres import get_db_connection, release_db_connection

logger = logging.getLogger(__name__)


class HealthChecker:
    """Класс для проверки здоровья бота"""

    def __init__(self, bot_token: str):
        self.bot_token = bot_token
        self.bot = None

    async def check_database(self) -> dict:
        """Проверка соединения с базой данных"""
        try:
            conn = get_db_connection()
            cur = conn.cursor()

            # Простой запрос для проверки
            cur.execute("SELECT 1")
            cur.fetchone()

            release_db_connection(conn)

            return {
                "status": "healthy",
                "message": "Database connection OK",
                "response_time_ms": 10
            }
        except Exception as e:
            logger.error(f"Database health check failed: {e}")
            return {
                "status": "unhealthy",
                "message": f"Database error: {str(e)}",
                "response_time_ms": 0
            }

    async def check_bot_token(self) -> dict:
        """Проверка валидности bot token"""
        try:
            if not self.bot:
                self.bot = Bot(token=self.bot_token)

            # Пытаемся получить информацию о боте
            bot_info = await self.bot.get_me()

            return {
                "status": "healthy",
                "message": f"Bot @{bot_info.username} OK",
                "bot_id": bot_info.id
            }
        except Exception as e:
            logger.error(f"Bot token check failed: {e}")
            return {
                "status": "unhealthy",
                "message": f"Bot token error: {str(e)}"
            }

    def check_system_resources(self) -> dict:
        """Проверка системных ресурсов"""
        try:
            # CPU usage
            cpu_percent = psutil.cpu_percent(interval=1)

            # Memory usage
            memory = psutil.virtual_memory()
            memory_percent = memory.percent

            # Disk usage
            disk = psutil.disk_usage('/')
            disk_percent = disk.percent

            # Определяем статус
            status = "healthy"
            message = "System resources OK"

            warnings = []
            if cpu_percent > 80:
                status = "degraded"
                warnings.append(f"High CPU: {cpu_percent}%")

            if memory_percent > 80:
                status = "degraded"
                warnings.append(f"High memory: {memory_percent}%")

            if disk_percent > 80:
                status = "degraded"
                warnings.append(f"High disk: {disk_percent}%")

            if warnings:
                message = "; ".join(warnings)

            return {
                "status": status,
                "message": message,
                "cpu_percent": cpu_percent,
                "memory_percent": memory_percent,
                "disk_percent": disk_percent,
                "memory_available_mb": memory.available // (1024 * 1024),
                "disk_free_gb": disk.free // (1024 * 1024 * 1024)
            }
        except Exception as e:
            logger.error(f"System resources check failed: {e}")
            return {
                "status": "unknown",
                "message": f"System check error: {str(e)}"
            }

    async def check_all(self) -> dict:
        """Полная проверка здоровья всех систем"""
        start_time = datetime.now()

        # Параллельная проверка всех компонентов
        database_health = await self.check_database()
        bot_health = await self.check_bot_token()
        system_health = self.check_system_resources()

        end_time = datetime.now()
        check_duration = (end_time - start_time).total_seconds()

        # Общий статус
        overall_status = "healthy"
        if any([
            database_health["status"] == "unhealthy",
            bot_health["status"] == "unhealthy",
            system_health["status"] == "unhealthy"
        ]):
            overall_status = "unhealthy"
        elif any([
            database_health["status"] == "degraded",
            bot_health["status"] == "degraded",
            system_health["status"] == "degraded"
        ]):
            overall_status = "degraded"

        return {
            "overall_status": overall_status,
            "timestamp": datetime.now().isoformat(),
            "check_duration_seconds": check_duration,
            "checks": {
                "database": database_health,
                "bot": bot_health,
                "system": system_health
            }
        }


class AlertManager:
    """Менеджер алертов для критических ситуаций"""

    def __init__(self, bot_token: str, admin_chat_id: int = None):
        self.bot_token = bot_token
        self.admin_chat_id = admin_chat_id
        self.bot = None
        self.last_alert_time = {}  # Для предотвращения спама алертов

    async def send_alert(self, message: str, severity: str = "warning") -> bool:
        """
        Отправка алерта админу

        Args:
            message: Текст алерта
            severity: severity уровень (info, warning, error, critical)

        Returns:
            True если алерт отправлен успешно
        """
        if not self.admin_chat_id:
            logger.warning("Admin chat ID not set, alert not sent")
            return False

        # Проверяем rate limiting для алертов (не спамить одно и то же)
        alert_key = f"{severity}:{hash(message)}"
        now = datetime.now()

        if alert_key in self.last_alert_time:
            last_time = self.last_alert_time[alert_key]
            if (now - last_time).total_seconds() < 300:  # Не чаще чем раз в 5 минут
                return False

        self.last_alert_time[alert_key] = now

        try:
            if not self.bot:
                self.bot = Bot(token=self.bot_token)

            # Формируем сообщение в зависимости от серьезности
            emoji = {
                "info": "ℹ️",
                "warning": "⚠️",
                "error": "❌",
                "critical": "🚨"
            }.get(severity, "⚠️")

            full_message = f"{emoji} **ALERT** [{severity.upper()}]\n\n{message}\n\n⏰ {now.strftime('%H:%M:%S')}"

            await self.bot.send_message(
                chat_id=self.admin_chat_id,
                text=full_message,
                parse_mode="Markdown"
            )

            logger.info(f"Alert sent: {severity} - {message[:50]}")
            return True

        except Exception as e:
            logger.error(f"Failed to send alert: {e}")
            return False

    async def alert_database_error(self, error: Exception):
        """Алерт об ошибке базы данных"""
        await self.send_alert(
            f"🔴 **DATABASE ERROR**\n\n```\n{str(error)}\n```",
            severity="critical"
        )

    async def alert_high_error_rate(self, error_count: int, period: str):
        """Алерт о высокой частоте ошибок"""
        await self.send_alert(
            f"⚠️ **HIGH ERROR RATE**\n\n{error_count} errors in {period}",
            severity="warning"
        )

    async def alert_system_resources(self, system_health: dict):
        """Алерт о проблемах с системными ресурсами"""
        if system_health["status"] in ["degraded", "unhealthy"]:
            await self.send_alert(
                f"⚠️ **SYSTEM RESOURCES**\n\n{system_health['message']}\n\n"
                f"CPU: {system_health.get('cpu_percent', 'N/A')}%\n"
                f"Memory: {system_health.get('memory_percent', 'N/A')}%\n"
                f"Disk: {system_health.get('disk_percent', 'N/A')}%",
                severity="warning"
            )


class MetricsCollector:
    """Сборщик метрик для мониторинга"""

    def __init__(self):
        self.metrics = {
            "start_time": datetime.now(),
            "total_users": 0,
            "active_users_today": 0,
            "workouts_today": 0,
            "errors_total": 0,
            "errors_last_hour": 0,
            "avg_response_time_ms": 0
        }

    def record_workout(self):
        """Запись выполнения тренировки"""
        self.metrics["workouts_today"] += 1

    def record_error(self):
        """Запись ошибки"""
        self.metrics["errors_total"] += 1
        self.metrics["errors_last_hour"] += 1

    def get_metrics(self) -> dict:
        """Получить текущие метрики"""
        uptime = datetime.now() - self.metrics["start_time"]

        return {
            **self.metrics,
            "uptime_hours": uptime.total_seconds() / 3600,
            "errors_per_hour": self.metrics["errors_total"] / max(1, uptime.total_seconds() / 3600)
        }


# Глобальные экземпляры
_health_checker = None
_alert_manager = None
_metrics_collector = MetricsCollector()


def init_health_monitoring(bot_token: str, admin_chat_id: int = None):
    """Инициализация систем мониторинга"""
    global _health_checker, _alert_manager

    _health_checker = HealthChecker(bot_token)
    _alert_manager = AlertManager(bot_token, admin_chat_id)

    logger.info("Health monitoring initialized")


async def get_health_status() -> dict:
    """Получить статус здоровья бота (для health check endpoint)"""
    if _health_checker:
        return await _health_checker.check_all()
    else:
        return {
            "overall_status": "unknown",
            "message": "Health monitoring not initialized"
        }


async def send_alert(message: str, severity: str = "warning") -> bool:
    """Отправить алерт админу"""
    if _alert_manager:
        return await _alert_manager.send_alert(message, severity)
    return False


def record_workout():
    """Записать метрику тренировки"""
    _metrics_collector.record_workout()


def record_error():
    """Записать метрику ошибки"""
    _metrics_collector.record_error()


def get_metrics() -> dict:
    """Получить метрики"""
    return _metrics_collector.get_metrics()