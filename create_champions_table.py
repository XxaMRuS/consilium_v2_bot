# -*- coding: utf-8 -*-
# Скрипт для создания таблицы чемпионов

import logging
from database_postgres import get_db_connection, release_db_connection

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def create_champions_table():
    """Создаёт таблицу чемпионов."""
    conn = get_db_connection()
    cur = conn.cursor()

    try:
        # Проверяем, существует ли таблица
        cur.execute("""
            SELECT EXISTS (
                SELECT FROM information_schema.tables
                WHERE table_name = 'champions'
            )
        """)
        exists = cur.fetchone()[0]

        if not exists:
            logger.info("🔧 Создание таблицы champions...")

            cur.execute("""
                CREATE TABLE champions (
                    id SERIAL PRIMARY KEY,
                    user_id BIGINT NOT NULL,
                    target_type VARCHAR(20) NOT NULL,
                    target_id INTEGER,
                    period_type VARCHAR(20) NOT NULL,
                    period_start DATE NOT NULL,
                    period_end DATE NOT NULL,
                    position INTEGER NOT NULL,
                    wins_score INTEGER NOT NULL,
                    first_place_count INTEGER DEFAULT 0,
                    second_place_count INTEGER DEFAULT 0,
                    third_place_count INTEGER DEFAULT 0,
                    mega_bonus INTEGER DEFAULT 0,
                    is_published BOOLEAN DEFAULT FALSE,
                    published_at TIMESTAMP,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY(user_id) REFERENCES users(telegram_id)
                )
            """)

            # Индексы для быстрого поиска
            cur.execute("""
                CREATE INDEX idx_champions_user ON champions(user_id)
            """)
            cur.execute("""
                CREATE INDEX idx_champions_period ON champions(period_type, period_start)
            """)
            cur.execute("""
                CREATE INDEX idx_champions_target ON champions(target_type, target_id)
            """)

            conn.commit()
            logger.info("✅ Таблица champions создана")
        else:
            logger.info("✅ Таблица champions уже существует")

    except Exception as e:
        logger.error(f"❌ Ошибка: {e}")
        conn.rollback()
        raise
    finally:
        release_db_connection(conn)

if __name__ == '__main__':
    logger.info("🚀 Создание таблицы чемпионов...")
    create_champions_table()
    logger.info("✅ Завершено")
