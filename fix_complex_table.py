"""Скрипт для исправления таблицы complexes"""
import logging
from database_postgres import get_db_connection

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def fix_complexes_table():
    """Исправляет структуру таблицы complexes."""
    conn = get_db_connection()
    cur = conn.cursor()

    try:
        logger.info("🔧 Проверяю структуру таблицы complexes...")

        # Проверяем текущие колонки
        cur.execute("""
            SELECT column_name FROM information_schema.columns
            WHERE table_name = 'complexes'
        """)
        existing_columns = {row[0] for row in cur.fetchall()}
        logger.info(f"Текущие колонки: {existing_columns}")

        # Добавляем недостающие колонки
        if 'type' not in existing_columns:
            cur.execute("ALTER TABLE complexes ADD COLUMN type VARCHAR(50) DEFAULT 'for_time'")
            logger.info("✅ Добавлена колонка 'type'")

        if 'week' not in existing_columns:
            cur.execute("ALTER TABLE complexes ADD COLUMN week INTEGER DEFAULT 0")
            logger.info("✅ Добавлена колонка 'week'")

        if 'difficulty' not in existing_columns:
            cur.execute("ALTER TABLE complexes ADD COLUMN difficulty VARCHAR(20) DEFAULT 'beginner'")
            logger.info("✅ Добавлена колонка 'difficulty'")

        conn.commit()
        logger.info("✅ Таблица complexes успешно обновлена!")

        # Показываем финальную структуру
        cur.execute("""
            SELECT column_name, data_type FROM information_schema.columns
            WHERE table_name = 'complexes'
            ORDER BY ordinal_position
        """)
        columns = cur.fetchall()
        logger.info("📋 Финальная структура:")
        for col in columns:
            logger.info(f"   - {col[0]}: {col[1]}")

        return True

    except Exception as e:
        logger.error(f"❌ Ошибка: {e}")
        conn.rollback()
        return False
    finally:
        conn.close()

if __name__ == "__main__":
    print("Starting complexes table fix...")
    success = fix_complexes_table()

    if success:
        print("SUCCESS! Table complexes updated!")
        print("Now restart the bot and try creating a complex again.")
    else:
        print("ERROR! Check logs.")
