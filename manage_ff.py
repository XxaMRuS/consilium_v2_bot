# -*- coding: utf-8 -*-
# Скрипт для управления FruN Fuel

import logging
import sys
from database_postgres import get_db_connection, release_db_connection, add_fun_fuel, get_fun_fuel_balance

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def list_users_with_ff():
    """Показывает всех пользователей с балансом FF."""
    conn = get_db_connection()
    cur = conn.cursor()

    try:
        cur.execute("""
            SELECT telegram_id, first_name, username, fun_fuel_balance
            FROM users
            WHERE fun_fuel_balance IS NOT NULL AND fun_fuel_balance > 0
            ORDER BY fun_fuel_balance DESC
        """)
        users = cur.fetchall()

        logger.info("💰 ПОЛЬЗОВАТЕЛИ С FF:")
        logger.info("-" * 80)

        for user in users:
            telegram_id, first_name, username, balance = user
            username_str = f"@{username}" if username else "(нет username)"
            logger.info(f"ID: {telegram_id} | {first_name} {username_str} | {balance} FF")

        logger.info("-" * 80)
        logger.info(f"Всего пользователей с FF: {len(users)}")

        return users

    except Exception as e:
        logger.error(f"❌ Ошибка: {e}")
        return []
    finally:
        release_db_connection(conn)


def get_user_info(telegram_id):
    """Получает информацию о пользователе."""
    conn = get_db_connection()
    cur = conn.cursor()

    try:
        cur.execute("""
            SELECT telegram_id, first_name, username, fun_fuel_balance
            FROM users
            WHERE telegram_id = %s
        """, (telegram_id,))

        user = cur.fetchone()
        return user

    except Exception as e:
        logger.error(f"❌ Ошибка: {e}")
        return None
    finally:
        release_db_connection(conn)


def add_ff_to_user(telegram_id, amount, description="Ручное начисление"):
    """Начисляет FF пользователю."""
    user = get_user_info(telegram_id)

    if not user:
        logger.error(f"❌ Пользователь с ID {telegram_id} не найден")
        return False

    current_balance = user[3] or 0

    try:
        add_fun_fuel(telegram_id, amount, description)
        new_balance = get_fun_fuel_balance(telegram_id)

        username = user[2]
        username_str = f"@{username}" if username else "(нет username)"

        logger.info(f"✅ FF НАЧИСЛЕНО:")
        logger.info(f"👤 {user[1]} {username_str} (ID: {telegram_id})")
        logger.info(f"💰 Было: {current_balance} FF")
        logger.info(f"➕ Начислено: {amount} FF")
        logger.info(f"💰 Стало: {new_balance} FF")
        logger.info(f"📝 Описание: {description}")

        return True

    except Exception as e:
        logger.error(f"❌ Ошибка начисления: {e}")
        return False


def show_user_balance(telegram_id):
    """Показывает баланс FF пользователя."""
    user = get_user_info(telegram_id)

    if not user:
        logger.error(f"❌ Пользователь с ID {telegram_id} не найден")
        return False

    username = user[2]
    username_str = f"@{username}" if username else "(нет username)"
    balance = user[3] or 0

    logger.info(f"💰 БАЛАНС FF:")
    logger.info(f"👤 {user[1]} {username_str} (ID: {telegram_id})")
    logger.info(f"💰 Баланс: {balance} FF")

    return True


def show_system_stats():
    """Показывает статистику системы FF."""
    conn = get_db_connection()
    cur = conn.cursor()

    try:
        cur.execute("SELECT SUM(fun_fuel_balance) FROM users WHERE fun_fuel_balance IS NOT NULL")
        total_ff = cur.fetchone()[0] or 0

        cur.execute("SELECT COUNT(*) FROM users WHERE fun_fuel_balance > 0")
        users_with_ff = cur.fetchone()[0]

        cur.execute("SELECT COUNT(*) FROM users")
        total_users = cur.fetchone()[0]

        logger.info("📊 СТАТИСТИКА СИСТЕМЫ FF:")
        logger.info("-" * 40)
        logger.info(f"💰 Всего FF в системе: {total_ff}")
        logger.info(f"👤 Пользователей с FF: {users_with_ff} из {total_users}")
        if total_users > 0:
            avg_ff = total_ff / total_users
            logger.info(f"📈 Средний FF на пользователя: {avg_ff:.2f}")
        logger.info("-" * 40)

    except Exception as e:
        logger.error(f"❌ Ошибка: {e}")
    finally:
        release_db_connection(conn)


if __name__ == '__main__':
    logger.info("💸 УПРАВЛЕНИЕ FRUN FUEL\n")

    if len(sys.argv) < 2:
        logger.info("📋 КОМАНДЫ:")
        logger.info("-" * 40)
        logger.info("1. Показать всех пользователей с FF:")
        logger.info("   python manage_ff.py list")
        logger.info("")
        logger.info("2. Показать баланс пользователя:")
        logger.info("   python manage_ff.py balance TELEGRAM_ID")
        logger.info("   Пример: python manage_ff.py balance 123456789")
        logger.info("")
        logger.info("3. Начислить FF пользователю:")
        logger.info("   python manage_ff.py add TELEGRAM_ID AMOUNT [DESCRIPTION]")
        logger.info("   Пример: python manage_ff.py add 123456789 100 \"Бонус за победу\"")
        logger.info("")
        logger.info("4. Статистика системы:")
        logger.info("   python manage_ff.py stats")
        logger.info("-" * 40)

    else:
        command = sys.argv[1].lower()

        if command == "list":
            logger.info("📋 Получение списка пользователей...\n")
            list_users_with_ff()

        elif command == "balance":
            if len(sys.argv) < 3:
                logger.error("❌ Укажите Telegram ID пользователя")
                logger.info("Пример: python manage_ff.py balance 123456789")
            else:
                try:
                    telegram_id = int(sys.argv[2])
                    show_user_balance(telegram_id)
                except ValueError:
                    logger.error("❌ Неверный формат ID. Используйте число.")

        elif command == "add":
            if len(sys.argv) < 4:
                logger.error("❌ Укажите Telegram ID и сумму")
                logger.info("Пример: python manage_ff.py add 123456789 100")
            else:
                try:
                    telegram_id = int(sys.argv[2])
                    amount = int(sys.argv[3])
                    description = sys.argv[4] if len(sys.argv) > 4 else "Ручное начисление"

                    logger.info(f"💰 Начисление {amount} FF пользователю {telegram_id}...\n")
                    add_ff_to_user(telegram_id, amount, description)

                except ValueError as e:
                    logger.error("❌ Неверный формат суммы или ID. Используйте числа.")

        elif command == "stats":
            show_system_stats()

        else:
            logger.error(f"❌ Неизвестная команда: {command}")
            logger.info("Используйте: list, balance, add, stats")
