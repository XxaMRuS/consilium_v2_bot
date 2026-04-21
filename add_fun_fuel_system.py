# -*- coding: utf-8 -*-
# Скрипт для добавления системы FruN Fuel

import logging
from database_postgres import get_db_connection, release_db_connection

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def add_fun_fuel_system():
    """Добавляет систему FruN Fuel в базу данных."""
    conn = get_db_connection()
    cur = conn.cursor()

    try:
        # Проверяем, существует ли колонка
        cur.execute("""
            SELECT column_name
            FROM information_schema.columns
            WHERE table_name = 'users' AND column_name = 'fun_fuel_balance'
        """)
        exists = cur.fetchone()

        if not exists:
            logger.info("🔧 Добавление колонки fun_fuel_balance...")

            # Добавляем колонку
            cur.execute("""
                ALTER TABLE users
                ADD COLUMN fun_fuel_balance INTEGER DEFAULT 100
            """)

            # Устанавливаем начальный баланс для существующих пользователей
            cur.execute("""
                UPDATE users
                SET fun_fuel_balance = 100
                WHERE fun_fuel_balance IS NULL
            """)

            conn.commit()
            logger.info("✅ Система FruN Fuel добавлена")
        else:
            logger.info("✅ Система FruN Fuel уже существует")

    except Exception as e:
        logger.error(f"❌ Ошибка: {e}")
        conn.rollback()
        raise
    finally:
        release_db_connection(conn)

if __name__ == '__main__':
    logger.info("🚀 Добавление системы FruN Fuel...")
    add_fun_fuel_system()
    logger.info("✅ Завершено")
