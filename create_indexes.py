# -*- coding: utf-8 -*-
"""
Создаёт индексы для оптимизации частых запросов
Запустить один раз для создания индексов
"""
from database_postgres import get_db_connection, release_db_connection
import logging

logger = logging.getLogger(__name__)

def create_performance_indexes():
    """Создаёт индексы для ускорения запросов"""

    indexes = [
        # Индексы для users
        "CREATE INDEX IF NOT EXISTS idx_users_username ON users(username);",
        "CREATE INDEX IF NOT EXISTS idx_users_telegram_id ON users(telegram_id);",
        "CREATE INDEX IF NOT EXISTS idx_users_score ON users(score DESC);",
        "CREATE INDEX IF NOT EXISTS idx_users_group ON users(user_group);",

        # Индексы для workouts
        "CREATE INDEX IF NOT EXISTS idx_workouts_user_id ON workouts(user_id);",
        "CREATE INDEX IF NOT EXISTS idx_workouts_exercise_id ON workouts(exercise_id);",
        "CREATE INDEX IF NOT EXISTS idx_workouts_date ON workouts(date DESC);",
        "CREATE INDEX IF NOT EXISTS idx_workouts_user_date ON workouts(user_id, date DESC);",

        # Индексы для challenges
        "CREATE INDEX IF NOT EXISTS idx_challenges_active ON challenges(is_active) WHERE is_active = TRUE;",
        "CREATE INDEX IF NOT EXISTS idx_challenges_dates ON challenges(start_date, end_date);",

        # Индексы для user_challenges
        "CREATE INDEX IF NOT EXISTS idx_user_challenges_user ON user_challenges(user_id);",
        "CREATE INDEX IF NOT EXISTS idx_user_challenges_challenge ON user_challenges(challenge_id);",

        # Индексы для pvp_challenges
        "CREATE INDEX IF NOT EXISTS idx_pvp_challenges_status ON pvp_challenges(status);",
        "CREATE INDEX IF NOT EXISTS idx_pvp_challenges_creator ON pvp_challenges(creator_id);",
        "CREATE INDEX IF NOT EXISTS idx_pvp_challenges_opponent ON pvp_challenges(opponent_id);",

        # Индексы для fun_fuel (FF система)
        "CREATE INDEX IF NOT EXISTS idx_fun_fuel_user ON fun_fuel(user_id);",
    ]

    conn = get_db_connection()
    cur = conn.cursor()

    try:
        logger.info("🔧 Начинаю создание индексов...")

        for i, index_sql in enumerate(indexes, 1):
            try:
                cur.execute(index_sql)
                logger.info(f"✅ Индекс {i}/{len(indexes)} создан")
            except Exception as e:
                logger.warning(f"⚠️ Индекс {i} не создан: {e}")

        conn.commit()
        logger.info(f"✅ Создание индексов завершено! Создано/проверено {len(indexes)} индексов")

    except Exception as e:
        logger.error(f"❌ Ошибка создания индексов: {e}")
        conn.rollback()
    finally:
        release_db_connection(conn)

if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)
    create_performance_indexes()
    print("\n✅ Индексы созданы! Перезапустите бота.")
