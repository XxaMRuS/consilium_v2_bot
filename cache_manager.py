# -*- coding: utf-8 -*-
"""
Система кэширования для ускорения частых запросов
"""
import time
import logging
from functools import wraps
from typing import Dict, Any, Optional, Callable

logger = logging.getLogger(__name__)

class SimpleCache:
    """Простой in-memory кэш с TTL"""

    def __init__(self, default_ttl: int = 300):  # 5 минут по умолчанию
        self._cache: Dict[str, tuple] = {}
        self.default_ttl = default_ttl

    def get(self, key: str) -> Optional[Any]:
        """Получает значение из кэша"""
        if key in self._cache:
            value, expiry = self._cache[key]
            if time.time() < expiry:
                return value
            else:
                # Устарел - удаляем
                del self._cache[key]
        return None

    def set(self, key: str, value: Any, ttl: Optional[int] = None) -> None:
        """Сохраняет значение в кэш"""
        ttl = ttl if ttl is not None else self.default_ttl
        expiry = time.time() + ttl
        self._cache[key] = (value, expiry)

    def delete(self, key: str) -> None:
        """Удаляет значение из кэша"""
        if key in self._cache:
            del self._cache[key]

    def clear(self) -> None:
        """Очищает весь кэш"""
        self._cache.clear()

    def cleanup(self) -> int:
        """Удаляет устаревшие записи, возвращает количество удаленных"""
        current_time = time.time()
        to_delete = [k for k, (_, expiry) in self._cache.items() if expiry < current_time]

        for key in to_delete:
            del self._cache[key]

        return len(to_delete)


# Глобальный экземпляр кэша
cache = SimpleCache(default_ttl=300)  # 5 минут

# Декоратор для кэширования результатов функций
def cached(ttl: int = 300, key_prefix: str = ""):
    """
    Декоратор для кэширования результатов функций

    Args:
        ttl: Время жизни кэша в секундах
        key_prefix: Префикс для ключа кэша
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            # Генерируем ключ кэша
            cache_key = f"{key_prefix}{func.__name__}_{str(args)}_{str(kwargs)}"

            # Пробуем получить из кэша
            cached_value = cache.get(cache_key)
            if cached_value is not None:
                logger.debug(f"✅ Cache hit: {cache_key}")
                return cached_value

            # Если нет в кэше - вычисляем
            result = func(*args, **kwargs)

            # Сохраняем в кэш
            cache.set(cache_key, result, ttl=ttl)
            logger.debug(f"💾 Cache saved: {cache_key}")

            return result
        return wrapper
    return decorator


# Кэши для конкретных данных
class DataCache:
    """Кэши для конкретных типов данных"""

    @staticmethod
    def get_user_info(user_id: int) -> Optional[dict]:
        """Получает информацию о пользователе из кэша"""
        return cache.get(f"user_info_{user_id}")

    @staticmethod
    def set_user_info(user_id: int, info: dict, ttl: int = 300):
        """Сохраняет информацию о пользователе в кэш"""
        cache.set(f"user_info_{user_id}", info, ttl=ttl)

    @staticmethod
    def get_exercises() -> Optional[list]:
        """Получает список упражнений из кэша"""
        return cache.get("exercises_list")

    @staticmethod
    def set_exercises(exercises: list, ttl: int = 600):
        """Сохраняет список упражнений в кэш (10 минут)"""
        cache.set("exercises_list", exercises, ttl=ttl)

    @staticmethod
    def get_challenges() -> Optional[list]:
        """Получает список челленджей из кэша"""
        return cache.get("challenges_list")

    @staticmethod
    def set_challenges(challenges: list, ttl: int = 600):
        """Сохраняет список челленджей в кэш (10 минут)"""
        cache.set("challenges_list", challenges, ttl=ttl)

    @staticmethod
    def invalidate_user(user_id: int) -> None:
        """Инвалидирует весь кэш пользователя"""
        cache.delete(f"user_info_{user_id}")

    @staticmethod
    def invalidate_exercises() -> None:
        """Инвалидирует кэш упражнений"""
        cache.delete("exercises_list")

    @staticmethod
    def invalidate_challenges() -> None:
        """Инвалидирует кэш челленджей"""
        cache.delete("challenges_list")

    @staticmethod
    def cleanup_expired() -> int:
        """Очищает устаревшие записи"""
        return cache.cleanup()


# Функция для автоматической очистки кэша
def start_cache_cleanup(interval: int = 300):
    """
    Запускает периодическую очистку кэша

    Args:
        interval: Интервал очистки в секундах (по умолчанию 5 минут)
    """
    import threading

    def cleanup_worker():
        while True:
            try:
                deleted = DataCache.cleanup_expired()
                if deleted > 0:
                    logger.info(f"🧹 Очищено {deleted} устаревших записей кэша")
                time.sleep(interval)
            except Exception as e:
                logger.error(f"❌ Ошибка очистки кэша: {e}")
                time.sleep(interval)

    thread = threading.Thread(target=cleanup_worker, daemon=True)
    thread.start()
    logger.info("🔄 Автоматическая очистка кэша запущена")
