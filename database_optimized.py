# -*- coding: utf-8 -*-
"""
Оптимизированные функции работы с базой данных
Использует кэширование для ускорения частых запросов
"""
import logging
from database_postgres import get_db_connection, release_db_connection
from cache_manager import DataCache

logger = logging.getLogger(__name__)

def get_user_info_optimized(user_id: int) -> dict:
    """
    Получает информацию о пользователе с кэшированием

    Args:
        user_id: Telegram ID пользователя

    Returns:
        dict: Информация о пользователе
    """
    # Пробуем получить из кэша
    cached = DataCache.get_user_info(user_id)
    if cached:
        logger.debug(f"✅ Cache hit for user {user_id}")
        return cached

    # Если нет в кэше - запрашиваем из БД
    conn = get_db_connection()
    cur = conn.cursor()

    try:
        cur.execute("""
            SELECT id, telegram_id, username, first_name, last_name,
                   registered_at, score, user_group
            FROM users
            WHERE telegram_id = %s
        """, (user_id,))

        result = cur.fetchone()

        if result:
            user_info = {
                'id': result[0],
                'telegram_id': result[1],
                'username': result[2],
                'first_name': result[3],
                'last_name': result[4],
                'registered_at': result[5],
                'score': result[6],
                'user_group': result[7]
            }

            # Сохраняем в кэш на 5 минут (300 сек)
            DataCache.set_user_info(user_id, user_info, ttl=300)
            logger.debug(f"💾 User {user_id} saved to cache")

            return user_info
        else:
            return None

    except Exception as e:
        logger.error(f"❌ Error getting user {user_id}: {e}")
        return None
    finally:
        release_db_connection(conn)


def get_exercises_optimized(active_only: bool = True) -> list:
    """
    Получает список упражнений с кэшированием

    Args:
        active_only: Только активные упражнения

    Returns:
        list: Список упражнений
    """
    # Пробуем получить из кэша
    cached = DataCache.get_exercises()
    if cached:
        logger.debug("✅ Cache hit for exercises")
        return cached

    # Если нет в кэше - запрашиваем из БД
    from database_postgres import get_exercises

    exercises = get_exercises(active_only=active_only)

    # Сохраняем в кэш на 10 минут (600 сек)
    DataCache.set_exercises(exercises, ttl=600)
    logger.debug(f"💾 {len(exercises)} exercises saved to cache")

    return exercises


def get_challenges_optimized(active_only: bool = True) -> list:
    """
    Получает список челленджей с кэшированием

    Args:
        active_only: Только активные челленджи

    Returns:
        list: Список челленджов
    """
    # Пробуем получить из кэша
    cached = DataCache.get_challenges()
    if cached:
        logger.debug("✅ Cache hit for challenges")
        return cached

    # Если нет в кэше - запрашиваем из БД
    from database_postgres import get_challenges_by_status

    if active_only:
        challenges = get_challenges_by_status(is_active=True)
    else:
        challenges = get_challenges_by_status()

    # Сохраняем в кэш на 10 минут (600 сек)
    DataCache.set_challenges(challenges, ttl=600)
    logger.debug(f"💾 {len(challenges)} challenges saved to cache")

    return challenges


def invalidate_user_cache(user_id: int) -> None:
    """
    Инвалидирует кэш пользователя

    Args:
        user_id: Telegram ID пользователя
    """
    DataCache.invalidate_user(user_id)
    logger.debug(f"🗑️ Cache invalidated for user {user_id}")


def invalidate_exercises_cache() -> None:
    """Инвалидирует кэш упражнений"""
    DataCache.invalidate_exercises()
    logger.debug("🗑️ Exercises cache invalidated")


def invalidate_challenges_cache() -> None:
    """Инвалидирует кэш челленджей"""
    DataCache.invalidate_challenges()
    logger.debug("🗑️ Challenges cache invalidated")
