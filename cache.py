# -*- coding: utf-8 -*-
"""
Простое кэширование для ускорения бота
Использует LRU cache для часто запрашиваемых данных
"""
from functools import lru_cache
import time
import logging
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

# Время жизни кэша в секундах
USER_CACHE_TTL = 60  # Данные пользователя кэшируем на 1 минуту
EXERCISES_CACHE_TTL = 300  # Упражнения на 5 минут
CHALLENGES_CACHE_TTL = 300  # Челленджи на 5 минут


class TimedCache:
    """Кэш с автоматическим устареванием"""

    def __init__(self, ttl=60):
        self.cache = {}
        self.ttl = ttl
        self.timestamps = {}

    def get(self, key):
        """Получить значение из кэша"""
        if key in self.cache:
            # Проверяем, не устарел ли кэш
            if key in self.timestamps:
                age = time.time() - self.timestamps[key]
                if age < self.ttl:
                    return self.cache[key]
                else:
                    # Устарел - удаляем
                    del self.cache[key]
                    del self.timestamps[key]
        return None

    def set(self, key, value):
        """Сохранить значение в кэш"""
        self.cache[key] = value
        self.timestamps[key] = time.time()

    def clear(self):
        """Очистить кэш"""
        self.cache.clear()
        self.timestamps.clear()

    def invalidate(self, key):
        """Удалить конкретное значение из кэша"""
        if key in self.cache:
            del self.cache[key]
        if key in self.timestamps:
            del self.timestamps[key]


# Глобальные экземпляры кэшей
user_cache = TimedCache(ttl=USER_CACHE_TTL)
exercises_cache = TimedCache(ttl=EXERCISES_CACHE_TTL)
challenges_cache = TimedCache(ttl=CHALLENGES_CACHE_TTL)


def cache_user_info(user_id, user_info):
    """Кэшировать информацию о пользователе"""
    cache_key = f"user_{user_id}"
    user_cache.set(cache_key, user_info)
    logger.debug(f"✅ Cached user info for {user_id}")


def get_cached_user_info(user_id):
    """Получить кэшированную информацию о пользователе"""
    cache_key = f"user_{user_id}"
    cached = user_cache.get(cache_key)
    if cached:
        logger.debug(f"✅ Hit cache for user {user_id}")
    return cached


def invalidate_user(user_id):
    """Удалить пользователя из кэша"""
    cache_key = f"user_{user_id}"
    user_cache.invalidate(cache_key)
    logger.debug(f"✅ Invalidated cache for user {user_id}")


def cache_exercises(exercises_list):
    """Кэшировать список упражнений"""
    exercises_cache.set("all_exercises", exercises_list)
    logger.debug(f"✅ Cached {len(exercises_list)} exercises")


def get_cached_exercises():
    """Получить кэшированный список упражнений"""
    cached = exercises_cache.get("all_exercises")
    if cached:
        logger.debug(f"✅ Hit cache for exercises")
    return cached


def cache_challenges(challenges_list):
    """Кэшировать список челленджей"""
    challenges_cache.set("all_challenges", challenges_list)
    logger.debug(f"✅ Cached {len(challenges_list)} challenges")


def get_cached_challenges():
    """Получить кэшированный список челленджей"""
    cached = challenges_cache.get("all_challenges")
    if cached:
        logger.debug(f"✅ Hit cache for challenges")
    return cached


def clear_all_caches():
    """Очистить все кэши"""
    user_cache.clear()
    exercises_cache.clear()
    challenges_cache.clear()
    logger.info("✅ All caches cleared")


# Декоратор для кэширования результатов функций
def timed_cache(ttl=60, key_prefix=""):
    """Декоратор для кэширования результатов функций с TTL"""

    def decorator(func):
        cache = TimedCache(ttl=ttl)

        def wrapper(*args, **kwargs):
            # Создаем ключ кэша из аргументов
            cache_key = f"{key_prefix}_{str(args)}_{str(kwargs)}"

            # Пытаемся получить из кэша
            result = cache.get(cache_key)
            if result is not None:
                return result

            # Если нет в кэше, вычисляем
            result = func(*args, **kwargs)
            cache.set(cache_key, result)
            return result

        return wrapper

    return decorator
