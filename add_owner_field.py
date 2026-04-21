# -*- coding: utf-8 -*-
# Скрипт для добавления поля is_owner

import logging
from database_postgres import get_db_connection, release_db_connection

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def add_owner_field():
    """Добавляет поле is_owner в таблицу users."""
    conn = get_db_connection()
    cur = conn.cursor()

    try:
        # Проверяем, существует ли колонка
        cur.execute("""
            SELECT column_name
            FROM information_schema.columns
            WHERE table_name = 'users' AND column_name = 'is_owner'
        """)
        exists = cur.fetchone()

        if not exists:
            logger.info("🔧 Добавление колонки is_owner...")

            # Добавляем колонку
            cur.execute("""
                ALTER TABLE users
                ADD COLUMN is_owner BOOLEAN DEFAULT FALSE
            """)

            conn.commit()
            logger.info("✅ Колонка is_owner добавлена")
        else:
            logger.info("✅ Колонка is_owner уже существует")

        # Показываем текущих владельцев
        cur.execute("""
            SELECT telegram_id, first_name, username, is_owner
            FROM users
            WHERE is_owner = TRUE
        """)
        owners = cur.fetchall()

        if owners:
            logger.info(f"📊 Текущие владельцы: {len(owners)}")
            for owner in owners:
                username = owner[2] or "нет username"
                logger.info(f"  - {owner[1]} (@{username})")
        else:
            logger.info("📊 Владельцев нет. Установите владельца вручную:")
            logger.info("  UPDATE users SET is_owner = TRUE WHERE telegram_id = ВАШ_ID;")

    except Exception as e:
        logger.error(f"❌ Ошибка: {e}")
        conn.rollback()
        raise
    finally:
        release_db_connection(conn)

def set_owner(telegram_id):
    """Устанавливает пользователя как владельца."""
    conn = get_db_connection()
    cur = conn.cursor()

    try:
        cur.execute("""
            UPDATE users
            SET is_owner = TRUE
            WHERE telegram_id = %s
            RETURNING first_name, username
        """, (telegram_id,))

        result = cur.fetchone()
        if result:
            first_name, username = result
            username_str = f"@{username}" if username else "(нет username)"
            logger.info(f"✅ {first_name} {username_str} установлен как владелец")
            conn.commit()
            return True
        else:
            logger.error(f"❌ Пользователь {telegram_id} не найден")
            return False

    except Exception as e:
        logger.error(f"❌ Ошибка: {e}")
        conn.rollback()
        return False
    finally:
        release_db_connection(conn)

if __name__ == '__main__':
    logger.info("🚀 Добавление поля владельца...")
    add_owner_field()

    # Раскомментируйте и установите свой ID:
    # set_owner(ВАШ_TELEGRAM_ID)

    logger.info("✅ Завершено")
