"""Скрипт для исправления структуры базы данных"""
import logging
from database_postgres import get_db_connection

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def fix_user_challenge_progress_table():
    """Обновляет таблицу user_challenge_progress до нужной схемы"""
    conn = get_db_connection()
    cur = conn.cursor()

    try:
        logger.info("Starting user_challenge_progress table update...")

        # Добавляем колонки если их нет
        logger.info("Adding exercise_id column...")
        cur.execute("""
            ALTER TABLE user_challenge_progress
            ADD COLUMN IF NOT EXISTS exercise_id INTEGER
        """)

        logger.info("Adding completed column...")
        cur.execute("""
            ALTER TABLE user_challenge_progress
            ADD COLUMN IF NOT EXISTS completed BOOLEAN DEFAULT FALSE
        """)

        logger.info("Adding result_value column...")
        cur.execute("""
            ALTER TABLE user_challenge_progress
            ADD COLUMN IF NOT EXISTS result_value FLOAT
        """)

        logger.info("Adding proof_link column...")
        cur.execute("""
            ALTER TABLE user_challenge_progress
            ADD COLUMN IF NOT EXISTS proof_link TEXT
        """)

        logger.info("Adding completed_at column...")
        cur.execute("""
            ALTER TABLE user_challenge_progress
            ADD COLUMN IF NOT EXISTS completed_at TIMESTAMP
        """)

        # Проверяем и обновляем первичный ключ
        logger.info("Checking primary key...")

        # Сначала получаем информацию о текущем PK
        cur.execute("""
            SELECT constraint_name
            FROM information_schema.table_constraints
            WHERE table_name = 'user_challenge_progress'
            AND constraint_type = 'PRIMARY KEY'
        """)
        pk_info = cur.fetchone()

        if pk_info:
            old_pk = pk_info[0]
            logger.info(f"Found old PK: {old_pk}")
            logger.info("Dropping old primary key...")
            cur.execute(f"""
                ALTER TABLE user_challenge_progress
                DROP CONSTRAINT {old_pk}
            """)

        logger.info("Creating new primary key (user_id, challenge_id, exercise_id)...")
        cur.execute("""
            ALTER TABLE user_challenge_progress
            ADD PRIMARY KEY (user_id, challenge_id, exercise_id)
        """)

        conn.commit()
        logger.info("Table user_challenge_progress updated successfully!")

        # Показываем структуру таблицы
        cur.execute("""
            SELECT column_name, data_type, is_nullable
            FROM information_schema.columns
            WHERE table_name = 'user_challenge_progress'
            ORDER BY ordinal_position
        """)
        columns = cur.fetchall()

        logger.info("New table structure:")
        for col in columns:
            logger.info(f"   - {col[0]}: {col[1]} (nullable: {col[2]})")

        return True

    except Exception as e:
        logger.error(f"Error during update: {e}")
        conn.rollback()
        return False
    finally:
        conn.close()

if __name__ == "__main__":
    print("Starting database fix...")
    success = fix_user_challenge_progress_table()

    if success:
        print("SUCCESS! Database updated successfully!")
        print("Now restart the bot and try completing an exercise again.")
    else:
        print("ERROR! Something went wrong. Check logs.")
