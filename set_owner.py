# -*- coding: utf-8 -*-
# Скрипт для установки владельца бота

import logging
from database_postgres import get_db_connection, release_db_connection

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def list_users():
    """Показывает всех пользователей для выбора владельца."""
    conn = get_db_connection()
    cur = conn.cursor()

    try:
        cur.execute("""
            SELECT telegram_id, first_name, username, is_owner
            FROM users
            ORDER BY telegram_id
        """)
        users = cur.fetchall()

        logger.info("📊 СПИСОК ПОЛЬЗОВАТЕЛЕЙ:")
        logger.info("-" * 80)

        for user in users:
            telegram_id, first_name, username, is_owner = user
            username_str = f"@{username}" if username else "(нет username)"
            owner_mark = " 👑" if is_owner else ""

            logger.info(f"ID: {telegram_id} | {first_name} {username_str}{owner_mark}")

        logger.info("-" * 80)
        logger.info(f"Всего пользователей: {len(users)}")

        return users

    except Exception as e:
        logger.error(f"❌ Ошибка: {e}")
        return []
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
            logger.info(f"✅ {first_name} {username_str} (ID: {telegram_id}) УСТАНОВЛЕН КАК ВЛАДЕЛЕЦ")
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
    logger.info("🔧 УПРАВЛЕНИЕ ВЛАДЕЛЬЦЕМ БОТА\n")

    # Показываем список пользователей
    users = list_users()

    # Запрашиваем ID
    logger.info("\n📋 ИНСТРУКЦИЯ:")
    logger.info("1. Скопируйте Telegram ID нужного пользователя из списка выше")
    logger.info("2. Запустите: python set_owner.py ВАШ_TELEGRAM_ID")
    logger.info("   Например: python set_owner.py 123456789")
    logger.info("3. Для удаления прав: python remove_owner.py ВАШ_TELEGRAM_ID")

    # Если передан аргумент командной строки
    import sys
    if len(sys.argv) > 1:
        try:
            telegram_id = int(sys.argv[1])
            logger.info(f"\n🔧 Установка владельца с ID: {telegram_id}...")
            if set_owner(telegram_id):
                logger.info("✅ ГОТОВО! Перезапустите бота")
        except ValueError:
            logger.error("❌ Неверный формат ID. Используйте число.")
