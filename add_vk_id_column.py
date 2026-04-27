#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Миграция: Добавление поля vk_id в таблицу users
"""

import logging
from database_postgres import get_db_connection, release_db_connection

logger = logging.getLogger(__name__)

def migrate():
    """Добавляет колонку vk_id в таблицу users"""
    conn = get_db_connection()
    cur = conn.cursor()
    
    try:
        # Проверяем, существует ли колонка
        cur.execute("""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name = 'users' AND column_name = 'vk_id'
        """)
        
        if cur.fetchone():
            logger.info("Колонка vk_id уже существует")
            return True
        
        # Добавляем колонку
        cur.execute("""
            ALTER TABLE users 
            ADD COLUMN vk_id BIGINT UNIQUE
        """)
        
        # Создаём индекс для быстрого поиска
        cur.execute("""
            CREATE INDEX idx_users_vk_id ON users(vk_id)
        """)
        
        conn.commit()
        logger.info("✅ Миграция успешна: добавлена колонка vk_id")
        return True
        
    except Exception as e:
        logger.error(f"❌ Ошибка миграции: {e}")
        conn.rollback()
        return False
    finally:
        release_db_connection(conn)

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    migrate()
