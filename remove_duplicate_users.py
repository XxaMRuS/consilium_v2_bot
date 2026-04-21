# -*- coding: utf-8 -*-
# Скрипт для удаления дубликатов пользователей

import logging
from database_postgres import get_db_connection, release_db_connection

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def remove_duplicate_users():
    """Находит и удаляет дубликаты пользователей, оставляя только активные."""
    conn = get_db_connection()
    cur = conn.cursor()

    try:
        # Находим всех дубликатов по username
        cur.execute("""
            SELECT username, COUNT(*) as count
            FROM users
            WHERE username IS NOT NULL
            GROUP BY username
            HAVING COUNT(*) > 1
            ORDER BY count DESC
        """)
        duplicates = cur.fetchall()

        if not duplicates:
            logger.info("✅ Дубликатов не найдено")
            return

        logger.info(f"📊 Найдено {len(duplicates)} дубликатов username")

        removed_count = 0

        for username, count in duplicates:
            logger.info(f"\n🔍 Обработка дубликата @{username} ({count} пользователей):")

            # Получаем всех пользователей с этим username
            cur.execute("""
                SELECT telegram_id, first_name, score, user_group, registered_at
                FROM users
                WHERE username = %s
                ORDER BY score DESC, registered_at DESC
            """, (username,))
            users = cur.fetchall()

            # Первый пользователь - оставляем (у него больше очков или зарегистрирован позже)
            keep_user = users[0]
            remove_users = users[1:]

            logger.info(f"   ✅ Оставляем: ID={keep_user[0]}, Score={keep_user[2]}")

            # Проверяем, есть ли данные у удаляемых пользователей
            for user in remove_users:
                user_id = user[0]

                # Проверяем наличие данных
                cur.execute("SELECT COUNT(*) FROM workouts WHERE user_id = %s", (user_id,))
                workouts = cur.fetchone()[0]

                cur.execute("SELECT COUNT(*) FROM user_challenges WHERE user_id = %s", (user_id,))
                challenges = cur.fetchone()[0]

                cur.execute("SELECT COUNT(*) FROM user_achievements WHERE user_id = %s", (user_id,))
                achievements = cur.fetchone()[0]

                cur.execute("SELECT COUNT(*) FROM coin_transactions WHERE user_id = %s", (user_id,))
                coins = cur.fetchone()[0]

                total_data = workouts + challenges + achievements + coins

                if total_data > 0:
                    logger.warning(f"   ⚠️ ВНИМАНИЕ: У пользователя ID={user_id} есть данные:")
                    logger.warning(f"      - Workouts: {workouts}")
                    logger.warning(f"      - Challenges: {challenges}")
                    logger.warning(f"      - Achievements: {achievements}")
                    logger.warning(f"      - Coins: {coins}")
                    logger.warning(f"   ❌ НЕ удаляем (есть данные)")
                else:
                    # Удаляем пользователя
                    logger.info(f"   🗑️ Удаляем: ID={user_id}, Score={user[2]} (нет данных)")

                    # Удаляем из связанных таблиц (на всякий случай)
                    cur.execute("DELETE FROM user_rankings WHERE user_id = %s", (user_id,))
                    cur.execute("DELETE FROM user_workouts WHERE user_id = %s", (user_id,))
                    cur.execute("DELETE FROM user_challenge_progress WHERE user_id = %s", (user_id,))
                    cur.execute("DELETE FROM pvp_history WHERE user_id = %s", (user_id,))
                    cur.execute("DELETE FROM wheel_spins WHERE user_id = %s", (user_id,))
                    cur.execute("DELETE FROM wheel_win_history WHERE user_id = %s", (user_id,))
                    cur.execute("DELETE FROM scoreboard WHERE user_id = %s", (user_id,))

                    # Удаляем самого пользователя
                    cur.execute("DELETE FROM users WHERE telegram_id = %s", (user_id,))

                    removed_count += 1

        conn.commit()
        logger.info(f"\n✅ Удалено {removed_count} дубликатов пользователей")

    except Exception as e:
        logger.error(f"❌ Ошибка при удалении дубликатов: {e}")
        conn.rollback()
        raise
    finally:
        release_db_connection(conn)

if __name__ == '__main__':
    logger.info("🔧 Начало удаления дубликатов пользователей...")
    remove_duplicate_users()
    logger.info("✅ Удаление завершено")
