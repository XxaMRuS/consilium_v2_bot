# -*- coding: utf-8 -*-
# Скрипт для исправления типа user_id во всех таблицах

import logging
from database_postgres import get_db_connection, release_db_connection

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def fix_all_user_id_types():
    """Изменяет тип user_id с INTEGER на BIGINT во всех таблицах."""
    conn = get_db_connection()
    cur = conn.cursor()

    try:
        # Получаем все таблицы с user_id типа integer
        cur.execute("""
            SELECT table_name, column_name, data_type
            FROM information_schema.columns
            WHERE column_name = 'user_id' AND data_type = 'integer'
            AND table_schema = 'public'
        """)
        problem_tables = cur.fetchall()

        if not problem_tables:
            logger.info("✅ Все поля user_id уже имеют тип BIGINT")
            return

        logger.info(f"📊 Найдено {len(problem_tables)} таблиц для исправления:")
        for table in problem_tables:
            logger.info(f"  - {table[0]}.{table[1]}: {table[2]}")

        # Исправляем каждую таблицу
        for table_name, column_name, data_type in problem_tables:
            try:
                logger.info(f"🔧 Исправление таблицы {table_name}...")

                # Получаем внешние ключи
                cur.execute(f"""
                    SELECT constraint_name
                    FROM information_schema.table_constraints
                    WHERE table_name = '{table_name}' AND constraint_type = 'FOREIGN KEY'
                """)
                foreign_keys = cur.fetchall()

                # Удаляем внешние ключи
                for fk in foreign_keys:
                    constraint_name = fk[0]
                    logger.info(f"   Удаление внешнего ключа: {constraint_name}")
                    cur.execute(f"ALTER TABLE {table_name} DROP CONSTRAINT {constraint_name}")

                # Изменяем тип
                cur.execute(f"ALTER TABLE {table_name} ALTER COLUMN user_id TYPE BIGINT")

                # Восстанавливаем внешние ключи (если есть связь с users)
                try:
                    cur.execute(f"""
                        ALTER TABLE {table_name}
                        ADD CONSTRAINT {table_name}_user_id_fkey
                        FOREIGN KEY (user_id) REFERENCES users(telegram_id)
                    """)
                    logger.info(f"   Внешний ключ восстановлен")
                except:
                    logger.info(f"   Внешний ключ не восстановлен (таблица не ссылается на users)")

                conn.commit()
                logger.info(f"✅ Таблица {table_name} исправлена")

            except Exception as e:
                logger.error(f"❌ Ошибка при исправлении таблицы {table_name}: {e}")
                conn.rollback()

        logger.info("✅ Все таблицы успешно исправлены")

    except Exception as e:
        logger.error(f"❌ Ошибка при исправлении типов: {e}")
        conn.rollback()
        raise
    finally:
        release_db_connection(conn)

if __name__ == '__main__':
    logger.info("🔧 Начало исправления типа user_id во всех таблицах...")
    fix_all_user_id_types()
    logger.info("✅ Исправление завершено")
