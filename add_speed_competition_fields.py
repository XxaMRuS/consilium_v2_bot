# -*- coding: utf-8 -*-
# Скрипт для добавления полей соревнований на скорость

import logging
from database_postgres import get_db_connection, release_db_connection

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def add_speed_competition_fields():
    """Добавляет поля соревнований на скорость в таблицу exercises."""
    conn = get_db_connection()
    cur = conn.cursor()

    try:
        # Проверяем существование колонок
        cur.execute("""
            SELECT column_name
            FROM information_schema.columns
            WHERE table_name = 'exercises'
            AND column_name IN ('is_speed_competition', 'speed_points_pool')
        """)
        existing = [row[0] for row in cur.fetchall()]

        # Добавляем is_speed_competition
        if 'is_speed_competition' not in existing:
            logger.info("🔧 Добавление колонки is_speed_competition...")
            cur.execute("""
                ALTER TABLE exercises
                ADD COLUMN is_speed_competition BOOLEAN DEFAULT FALSE
            """)
            logger.info("✅ Колонка is_speed_competition добавлена")
        else:
            logger.info("✅ Колонка is_speed_competition уже существует")

        # Добавляем speed_points_pool
        if 'speed_points_pool' not in existing:
            logger.info("🔧 Добавление колонки speed_points_pool...")
            cur.execute("""
                ALTER TABLE exercises
                ADD COLUMN speed_points_pool INTEGER DEFAULT 1000
            """)
            logger.info("✅ Колонка speed_points_pool добавлена")
        else:
            logger.info("✅ Колонка speed_points_pool уже существует")

        conn.commit()
        logger.info("✅ Поля соревнований на скорость добавлены")

    except Exception as e:
        logger.error(f"❌ Ошибка: {e}")
        conn.rollback()
        raise
    finally:
        release_db_connection(conn)

if __name__ == '__main__':
    logger.info("🚀 Добавление полей соревнований на скорость...")
    add_speed_competition_fields()
    logger.info("✅ Завершено")
