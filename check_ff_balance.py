# -*- coding: utf-8 -*-
# Скрипт для проверки и пополнения баланса FF

import logging
from database_postgres import get_db_connection, release_db_connection

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def check_and_topup_ff_balance():
    """Проверяет и пополняет баланс FF для всех пользователей."""
    conn = get_db_connection()
    cur = conn.cursor()

    try:
        # Проверяем текущий баланс всех пользователей
        cur.execute("""
            SELECT telegram_id, first_name, username, fun_fuel_balance
            FROM users
            ORDER BY fun_fuel_balance DESC
        """)
        users = cur.fetchall()

        logger.info(f"📊 Всего пользователей: {len(users)}")
        logger.info("💰 Текущие балансы FF:")

        users_without_ff = []

        for user in users:
            telegram_id, first_name, username, balance = user
            username_str = f"@{username}" if username else "(нет username)"

            if balance is None or balance < 100:
                users_without_ff.append(telegram_id)
                logger.info(f"  ❌ {first_name} {username_str} - {balance} FF (нужно пополнить)")
            else:
                logger.info(f"  ✅ {first_name} {username_str} - {balance} FF")

        # Пополняем баланс тем, у кого меньше 100 FF
        if users_without_ff:
            logger.info(f"\n🔧 Пополнение баланса для {len(users_without_ff)} пользователей...")

            for user_id in users_without_ff:
                # Добавляем 100 FF
                cur.execute("""
                    UPDATE users
                    SET fun_fuel_balance = fun_fuel_balance + 100
                    WHERE telegram_id = %s
                """, (user_id,))

            conn.commit()
            logger.info("✅ Баланс пополнен на 100 FF для пользователей с низким балансом")
        else:
            logger.info("✅ У всех пользователей достаточно FF")

    except Exception as e:
        logger.error(f"❌ Ошибка: {e}")
        conn.rollback()
        raise
    finally:
        release_db_connection(conn)

if __name__ == '__main__':
    logger.info("🔍 Проверка баланса FF...")
    check_and_topup_ff_balance()
    logger.info("✅ Завершено")
