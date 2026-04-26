# -*- coding: utf-8 -*-
"""
Простой Rate Limiter для защиты от флуда
"""

import logging
import asyncio
from collections import defaultdict
from datetime import datetime, timedelta
from functools import wraps

logger = logging.getLogger(__name__)


class RateLimiter:
    """Класс для ограничения частоты запросов"""

    def __init__(self):
        # Хранилище запросов: {user_id: [timestamp1, timestamp2, ...]}
        self.user_requests = defaultdict(list)
        # Хранилище блокировок: {user_id: blocked_until}
        self.blocked_users = {}

    def check_rate_limit(self, user_id: int, max_requests: int = 10,
                        period: int = 60, block_duration: int = 300) -> tuple:
        """
        Проверяет rate limit для пользователя

        Args:
            user_id: ID пользователя
            max_requests: Максимальное количество запросов
            period: Период в секундах
            block_duration: Время блокировки при превышении (секунды)

        Returns:
            (allowed: bool, remaining_requests: int, retry_after: int)
        """
        now = datetime.now()

        # Проверяем, не заблокирован ли пользователь
        if user_id in self.blocked_users:
            blocked_until = self.blocked_users[user_id]
            if now < blocked_until:
                retry_after = int((blocked_until - now).total_seconds()) + 1
                return False, 0, retry_after
            else:
                # Блокировка истекла, удаляем
                del self.blocked_users[user_id]

        # Очищаем старые записи
        self.user_requests[user_id] = [
            req_time for req_time in self.user_requests[user_id]
            if now - req_time < timedelta(seconds=period)
        ]

        # Проверяем лимит
        request_count = len(self.user_requests[user_id])

        if request_count >= max_requests:
            # Превышен лимит - блокируем
            self.blocked_users[user_id] = now + timedelta(seconds=block_duration)
            retry_after = block_duration
            logger.warning(f"Rate limit превышен для user_id={user_id}, заблокирован на {block_duration}с")
            return False, 0, retry_after

        # Добавляем текущий запрос
        self.user_requests[user_id].append(now)

        remaining = max_requests - request_count - 1
        return True, remaining, 0

    def reset_user(self, user_id: int):
        """Сбрасывает лимиты для конкретного пользователя"""
        if user_id in self.user_requests:
            del self.user_requests[user_id]
        if user_id in self.blocked_users:
            del self.blocked_users[user_id]


# Глобальный экземпляр
rate_limiter = RateLimiter()


def rate_limit(max_requests: int = 10, period: int = 60,
               block_duration: int = 300, error_message: str = None):
    """
    Декоратор для rate limiting

    Args:
        max_requests: Максимальное количество запросов
        period: Период в секундах
        block_duration: Время блокировки при превышении
        error_message: Кастомное сообщение об ошибке

    Usage:
        @rate_limit(max_requests=5, period=60)
        async def my_handler(update, context):
            pass
    """
    def decorator(func):
        @wraps(func)
        async def wrapper(update, context, *args, **kwargs):
            user_id = update.effective_user.id

            allowed, remaining, retry_after = rate_limiter.check_rate_limit(
                user_id, max_requests, period, block_duration
            )

            if not allowed:
                # Формируем сообщение об ошибке
                if error_message is None:
                    minutes = retry_after // 60
                    seconds = retry_after % 60
                    if minutes > 0:
                        error_msg = f"⚠️ Слишком много запросов. Попробуйте через {minutes}мин {seconds}сек."
                    else:
                        error_msg = f"⚠️ Слишком много запросов. Попробуйте через {retry_again}сек."
                else:
                    error_msg = error_message

                # Отправляем сообщение
                try:
                    if hasattr(update, 'message'):
                        await update.message.reply_text(error_msg)
                    elif hasattr(update, 'callback_query'):
                        await update.callback_query.answer(error_msg, show_alert=True)
                except Exception as e:
                    logger.error(f"Не удалось отправить сообщение о rate limit: {e}")

                return None

            # Вызываем оригинальную функцию
            return await func(update, context, *args, **kwargs)

        return wrapper
    return decorator


async def check_user_rate_limit(user_id: int, max_requests: int = 10,
                                period: int = 60) -> tuple:
    """
    Проверка rate limit для использования в коде

    Returns:
        (allowed: bool, remaining: int, retry_after: int)
    """
    return rate_limiter.check_rate_limit(user_id, max_requests, period)


def reset_user_rate_limit(user_id: int):
    """Сброс rate limit для пользователя"""
    rate_limiter.reset_user(user_id)


# ==================== ПРИМЕРЫ ИСПОЛЬЗОВАНИЯ ====================

if __name__ == "__main__":
    # Пример использования
    async def test_rate_limiter():
        # Тест rate limiter
        user_id = 12345

        # 10 запросов должны пройти
        for i in range(10):
            allowed, remaining, retry_after = rate_limiter.check_rate_limit(user_id)
            print(f"Запрос {i+1}: allowed={allowed}, remaining={remaining}")

        # 11-й запрос должен быть заблокирован
        allowed, remaining, retry_after = rate_limiter.check_rate_limit(user_id)
        print(f"Запрос 11: allowed={allowed}, retry_after={retry_after}")

        # Сброс
        rate_limiter.reset_user(user_id)
        print("После сброса:")
        allowed, remaining, retry_after = rate_limiter.check_rate_limit(user_id)
        print(f"Запрос после сброса: allowed={allowed}, remaining={remaining}")