# -*- coding: utf-8 -*-
# Скрипт для исправления типа user_id в таблице workouts

import logging
from database_postgres import get_db_connection, release_db_connection

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def fix_workouts_user_id_type():
    """Изменяет тип user_id с INTEGER на BIGINT в таблице workouts."""
    conn = get_db_connection()
    cur = conn.cursor()

    try:
        # Проверяем текущий тип
        cur.execute("""
            SELECT data_type
            FROM information_schema.columns
            WHERE table_name = 'workouts' AND column_name = 'user_id'
        """)
        current_type = cur.fetchone()[0]
        logger.info(f"Текущий тип user_id: {current_type}")

        if current_type == 'integer':
            # Изменяем тип на BIGINT
            logger.info("Изменение типа user_id с INTEGER на BIGINT...")

            # Сначала удаляем внешние ключи, если они есть
            cur.execute("""
                SELECT constraint_name
                FROM information_schema.table_constraints
                WHERE table_name = 'workouts' AND constraint_type = 'FOREIGN KEY'
            """)
            foreign_keys = cur.fetchall()

            for fk in foreign_keys:
                constraint_name = fk[0]
                logger.info(f"Удаление внешнего ключа: {constraint_name}")
                cur.execute(f"ALTER TABLE workouts DROP CONSTRAINT {constraint_name}")

            # Изменяем тип
            cur.execute("ALTER TABLE workouts ALTER COLUMN user_id TYPE BIGINT")

            # Восстанавливаем внешние ключи
            cur.execute("""
                ALTER TABLE workouts
                ADD CONSTRAINT workouts_user_id_fkey
                FOREIGN KEY (user_id) REFERENCES users(telegram_id)
            """)

            conn.commit()
            logger.info("✅ Тип user_id успешно изменён на BIGINT")

        elif current_type == 'bigint':
            logger.info("✅ Тип user_id уже BIGINT, изменений не требуется")

        else:
            logger.warning(f"⚠️ Неожиданный тип: {current_type}")

    except Exception as e:
        logger.error(f"❌ Ошибка при изменении типа: {e}")
        conn.rollback()
        raise
    finally:
        release_db_connection(conn)

if __name__ == '__main__':
    logger.info("🔧 Начало исправления типа user_id...")
    fix_workouts_user_id_type()
    logger.info("✅ Исправление завершено")
