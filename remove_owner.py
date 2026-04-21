# -*- coding: utf-8 -*-
# Скрипт для удаления прав владельца

import logging
import sys
from database_postgres import get_db_connection, release_db_connection

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def remove_owner(telegram_id):
    """Убирает права владельца."""
    conn = get_db_connection()
    cur = conn.cursor()

    try:
        cur.execute("""
            UPDATE users
            SET is_owner = FALSE
            WHERE telegram_id = %s
            RETURNING first_name, username
        """, (telegram_id,))

        result = cur.fetchone()
        if result:
            first_name, username = result
            username_str = f"@{username}" if username else "(нет username)"
            logger.info(f"✅ {first_name} {username_str} (ID: {telegram_id}) БОЛЬНЕ НЕ ВЛАДЕЛЕЦ")
            conn.commit()
            return True
        else:
            logger.error(f"❌ Пользователь с ID {telegram_id} не найден")
            return False

    except Exception as e:
        logger.error(f"❌ Ошибка: {e}")
        conn.rollback()
        return False
    finally:
        release_db_connection(conn)


if __name__ == '__main__':
    if len(sys.argv) < 2:
        logger.info("Использование: python remove_owner.py TELEGRAM_ID")
        logger.info("Пример: python remove_owner.py 123456789")
    else:
        try:
            telegram_id = int(sys.argv[1])
            logger.info(f"🔧 Удаление прав владельца для ID: {telegram_id}...")
            if remove_owner(telegram_id):
                logger.info("✅ ГОТОВО!")
        except ValueError:
            logger.error("❌ Неверный формат ID. Используйте число.")
