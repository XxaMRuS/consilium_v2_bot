# -*- coding: utf-8 -*-
# Скрипт для включения соревнований на скорость

import logging
from database_postgres import get_db_connection, release_db_connection

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def enable_competitions():
    """Включает соревнования для всех упражнений."""
    conn = get_db_connection()
    cur = conn.cursor()

    try:
        # Включаем соревнования для всех упражнений
        cur.execute("""
            UPDATE exercises
            SET is_speed_competition = TRUE, speed_points_pool = 1000
        """)
        affected_rows = cur.rowcount
        conn.commit()

        logger.info(f"✅ Включено соревнований для {affected_rows} упражнений")

        # Показываем, какие упражнения теперь имеют соревнования
        cur.execute("""
            SELECT id, name, is_speed_competition, speed_points_pool
            FROM exercises
            WHERE is_speed_competition = TRUE
        """)
        exercises = cur.fetchall()

        logger.info("📊 Упражнения с соревнованиями:")
        for ex in exercises:
            logger.info(f"  #{ex[0]}: {ex[1]} - {ex[3]} очков")

    except Exception as e:
        logger.error(f"❌ Ошибка: {e}")
        conn.rollback()
        raise
    finally:
        release_db_connection(conn)

if __name__ == '__main__':
    logger.info("🚀 Включение соревнований...")
    enable_competitions()
    logger.info("✅ Завершено")
