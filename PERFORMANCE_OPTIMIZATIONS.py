# -*- coding: utf-8 -*-
"""
ОПТИМИЗАЦИЯ ПРОИЗВОДИТЕЛЬНОСТИ БОТА
====================================

НАЙДЕННЫЕ ПРОБЛЕМЫ:
==================

1. ⚠️ КРИТИЧНО: Нет индекса на users.telegram_id
   - 27 запросов используют WHERE telegram_id
   - Каждый запрос сканирует всю таблицу users

2. ⚠️ КРИТИЧНО: get_user_group() не имеет кэша
   - Вызывается в цикле для каждого пользователя в PvP
   - N+1 проблема: 100 пользователей = 100 запросов

3. ⚠️ ВАЖНО: get_fun_fuel_balance() не имеет кэша
   - 23 вызова по коду
   - Запускается при каждом показе баланса

4. ⚠️ ВАЖНО: N+1 проблема в pvp_handlers.py:206
   - get_user_group() вызывается в цикле для всех кандидатов

5. ⚠️ СРЕДНЕ: Множественные избыточные запросы
   - get_user_info() имеет кэш но TTL=60с может быть мало
   - Частые запросы одной и той же информации

РЕШЕНИЯ:
=========

1. Создать индекс на users.telegram_id
2. Добавить кэш для get_user_group()
3. Добавить кэш для get_fun_fuel_balance()
4. Оптимизировать цикл в pvp_select_opponent()
5. Увеличить TTL для get_user_info() до 300 секунд

ОЖИДАЕМЫЙ РЕЗУЛЬТАТ:
=====================
- Ускорение реакции на кнопки: 2-5x
- Снижение нагрузки на БД: 60-80%
- Устранение задержек при показе списков
"""

# ============================================================
# ОПТИМИЗАЦИЯ 1: Создание индекса на users.telegram_id
# ============================================================

def create_critical_indexes():
    """Создает критически важные индексы для производительности"""
    import logging
    from database_postgres import get_db_connection

    logger = logging.getLogger(__name__)
    conn = get_db_connection()
    cur = conn.cursor()

    try:
        # Самый важный индекс!
        cur.execute("""
            CREATE INDEX IF NOT EXISTS idx_users_telegram_id
            ON users(telegram_id);
        """)
        logger.info("✅ Создан индекс idx_users_telegram_id")

        # Индексы для часто запрашиваемых полей
        cur.execute("""
            CREATE INDEX IF NOT EXISTS idx_users_user_group
            ON users(user_group);
        """)
        logger.info("✅ Создан индекс idx_users_user_group")

        cur.execute("""
            CREATE INDEX IF NOT EXISTS idx_users_score
            ON users(score);
        """)
        logger.info("✅ Создан индекс idx_users_score")

        cur.execute("""
            CREATE INDEX IF NOT EXISTS idx_pvp_challenges_status
            ON pvp_challenges(status)
            WHERE status IN ('pending', 'active');
        """)
        logger.info("✅ Создан индекс idx_pvp_challenges_status")

        cur.execute("""
            CREATE INDEX IF NOT EXISTS idx_workouts_user_id
            ON workouts(user_id);
        """)
        logger.info("✅ Создан индекс idx_workouts_user_id")

        cur.execute("""
            CREATE INDEX IF NOT EXISTS idx_workouts_date
            ON workouts(DATE(date));
        """)
        logger.info("✅ Создан индекс idx_workouts_date")

        conn.commit()
        logger.info("🚀 Все критические индексы созданы!")

    except Exception as e:
        logger.error(f"❌ Ошибка создания индексов: {e}")
        conn.rollback()
    finally:
        from database_postgres import release_db_connection
        release_db_connection(conn)


# ============================================================
# ОПТИМИЗАЦИЯ 2: Кэширование get_user_group
# ============================================================

def get_user_group_cached(user_id):
    """Получает группу пользователя с кэшированием"""
    from cache_manager import DataCache
    from database_postgres import get_db_connection

    # Проверяем кэш
    cache_key = f"user_group_{user_id}"
    cached = DataCache._cache_get(cache_key)
    if cached is not None:
        return cached

    # Запрашиваем из БД
    conn = get_db_connection()
    cur = conn.cursor()

    try:
        cur.execute("""
            SELECT user_group
            FROM users
            WHERE telegram_id = %s
        """, (user_id,))

        row = cur.fetchone()
        from database_postgres import release_db_connection
        release_db_connection(conn)

        result = row[0] if row else None

        # Кэшируем на 5 минут
        DataCache._cache_set(cache_key, result, ttl=300)
        return result

    except Exception as e:
        import logging
        logging.error(f"Ошибка получения группы: {e}")
        from database_postgres import release_db_connection
        release_db_connection(conn)
        return None


# ============================================================
# ОПТИМИЗАЦИЯ 3: Кэширование get_fun_fuel_balance
# ============================================================

def get_fun_fuel_balance_cached(user_id):
    """Получает баланс FF с кэшированием"""
    from cache_manager import DataCache
    from database_postgres import get_db_connection

    # Проверяем кэш
    cache_key = f"fun_fuel_{user_id}"
    cached = DataCache._cache_get(cache_key)
    if cached is not None:
        return cached

    # Запрашиваем из БД
    conn = get_db_connection()
    cur = conn.cursor()

    try:
        cur.execute("SELECT fun_fuel_balance FROM users WHERE telegram_id = %s", (user_id,))
        result = cur.fetchone()

        balance = result[0] if result else 0

        # Кэшируем на 60 секунд
        DataCache._cache_set(cache_key, balance, ttl=60)
        return balance

    except Exception as e:
        import logging
        logging.error(f"Ошибка получения баланса FF: {e}")
        return 0
    finally:
        from database_postgres import release_db_connection
        release_db_connection(conn)


# ============================================================
# ОПТИМИЗАЦИЯ 4: Batch запрос для групп пользователей
# ============================================================

def get_users_groups_batch(user_ids):
    """Получает группы для списка пользователей одним запросом"""
    if not user_ids:
        return {}

    from database_postgres import get_db_connection
    conn = get_db_connection()
    cur = conn.cursor()

    try:
        cur.execute("""
            SELECT telegram_id, user_group
            FROM users
            WHERE telegram_id = ANY(%s)
        """, (list(user_ids),))

        result = {row[0]: row[1] for row in cur.fetchall()}

        from database_postgres import release_db_connection
        release_db_connection(conn)
        return result

    except Exception as e:
        import logging
        logging.error(f"Ошибка пакетного получения групп: {e}")
        from database_postgres import release_db_connection
        release_db_connection(conn)
        return {}


if __name__ == "__main__":
    print("🚀 Применение оптимизаций производительности...")
    create_critical_indexes()
    print("✅ Оптимизации завершены!")