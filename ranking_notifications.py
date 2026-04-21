# -*- coding: utf-8 -*-
# Модуль уведомлений об изменениях в рейтинге

import logging
from datetime import datetime
from telegram import Bot
from database_postgres import get_db_connection, release_db_connection, dict_cursor

logger = logging.getLogger(__name__)

# ==================== ИНИЦИАЛИЗАЦИЯ ТАБЛИЦЫ ====================

def init_ranking_notifications_table():
    """Создаёт таблицу для хранения предыдущих позиций."""
    conn = get_db_connection()
    cur = conn.cursor()

    try:
        cur.execute("""
            CREATE TABLE IF NOT EXISTS user_rankings (
                id SERIAL PRIMARY KEY,
                user_id BIGINT NOT NULL,
                exercise_id INTEGER,
                complex_id INTEGER,
                category VARCHAR(50) NOT NULL,
                previous_position INTEGER,
                current_position INTEGER,
                last_notification_date DATE,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(user_id, exercise_id, complex_id, category)
            )
        """)

        # Индексы для быстрого поиска
        cur.execute("""
            CREATE INDEX IF NOT EXISTS idx_user_rankings_user
            ON user_rankings(user_id)
        """)
        cur.execute("""
            CREATE INDEX IF NOT EXISTS idx_user_rankings_exercise
            ON user_rankings(exercise_id)
        """)
        cur.execute("""
            CREATE INDEX IF NOT EXISTS idx_user_rankings_complex
            ON user_rankings(complex_id)
        """)
        cur.execute("""
            CREATE INDEX IF NOT EXISTS idx_user_rankings_category
            ON user_rankings(category)
        """)

        conn.commit()
        logger.info("✅ Таблица user_rankings создана")

    except Exception as e:
        logger.error(f"❌ Ошибка создания таблицы user_rankings: {e}")
        conn.rollback()
    finally:
        release_db_connection(conn)


# ==================== ФУНКЦИИ РАСЧЁТА РЕЙТИНГОВ ====================

def get_workouts_leaderboard(limit=100):
    """Получает топ по тренировкам."""
    conn = get_db_connection()
    cur = dict_cursor(conn)

    try:
        cur.execute("""
            SELECT
                u.telegram_id as user_id,
                u.first_name,
                u.username,
                COUNT(w.id) as workout_count
            FROM workouts w
            JOIN users u ON w.user_id = u.telegram_id
            GROUP BY u.telegram_id, u.first_name, u.username
            ORDER BY workout_count DESC
            LIMIT %s
        """, (limit,))

        return cur.fetchall()
    except Exception as e:
        logger.error(f"Ошибка получения топа тренировок: {e}")
        return []
    finally:
        release_db_connection(conn)


def get_challenges_leaderboard(limit=100):
    """Получает топ по челленджам."""
    conn = get_db_connection()
    cur = dict_cursor(conn)

    try:
        cur.execute("""
            SELECT
                u.telegram_id as user_id,
                u.first_name,
                u.username,
                COUNT(DISTINCT cp.challenge_id) as challenge_count
            FROM user_challenge_progress cp
            JOIN users u ON cp.user_id = u.telegram_id
            WHERE cp.completed = TRUE
            GROUP BY u.telegram_id, u.first_name, u.username
            ORDER BY challenge_count DESC
            LIMIT %s
        """, (limit,))

        return cur.fetchall()
    except Exception as e:
        logger.error(f"Ошибка получения топа челленджей: {e}")
        return []
    finally:
        release_db_connection(conn)


def get_complexes_leaderboard(limit=100):
    """Получает топ по комплексам."""
    conn = get_db_connection()
    cur = dict_cursor(conn)

    try:
        cur.execute("""
            SELECT
                u.telegram_id as user_id,
                u.first_name,
                u.username,
                COUNT(DISTINCT w.complex_id) as complex_count
            FROM workouts w
            JOIN users u ON w.user_id = u.telegram_id
            WHERE w.complex_id IS NOT NULL
            GROUP BY u.telegram_id, u.first_name, u.username
            ORDER BY complex_count DESC
            LIMIT %s
        """, (limit,))

        return cur.fetchall()
    except Exception as e:
        logger.error(f"Ошибка получения топа комплексов: {e}")
        return []
    finally:
        release_db_connection(conn)


def get_exercise_leaderboard(exercise_id, limit=100):
    """Получает топ по конкретному упражнению."""
    conn = get_db_connection()
    cur = dict_cursor(conn)

    try:
        cur.execute("""
            SELECT
                u.telegram_id as user_id,
                u.first_name,
                u.username,
                COUNT(w.id) as workout_count
            FROM workouts w
            JOIN users u ON w.user_id = u.telegram_id
            WHERE w.exercise_id = %s
            GROUP BY u.telegram_id, u.first_name, u.username
            ORDER BY workout_count DESC
            LIMIT %s
        """, (exercise_id, limit))

        return cur.fetchall()
    except Exception as e:
        logger.error(f"Ошибка получения топа упражнения {exercise_id}: {e}")
        return []
    finally:
        release_db_connection(conn)


# ==================== ФУНКЦИИ СОХРАНЕНИЯ И ЗАГРУЗКИ ПОЗИЦИЙ ====================

def save_user_rankings(category, leaderboard, exercise_id=None, complex_id=None):
    """Сохраняет текущие позиции в базу."""
    conn = get_db_connection()
    cur = conn.cursor()

    try:
        for position, user_data in enumerate(leaderboard, 1):
            user_id = user_data['user_id']

            cur.execute("""
                INSERT INTO user_rankings (user_id, exercise_id, complex_id, category, current_position, previous_position)
                VALUES (%s, %s, %s, %s, %s,
                    (SELECT current_position FROM user_rankings
                     WHERE user_id = %s AND exercise_id = %s AND complex_id = %s AND category = %s))
                ON CONFLICT (user_id, exercise_id, complex_id, category)
                DO UPDATE SET
                    previous_position = EXCLUDED.previous_position,
                    current_position = %s,
                    updated_at = CURRENT_TIMESTAMP
            """, (user_id, exercise_id, complex_id, category, position,
                  user_id, exercise_id, complex_id, category, position))

        conn.commit()
        logger.info(f"✅ Сохранены позиции для категории {category}")

    except Exception as e:
        logger.error(f"Ошибка сохранения позиций: {e}")
        conn.rollback()
    finally:
        release_db_connection(conn)


# ==================== ФУНКЦИЯ ОТПРАВКИ УВЕДОМЛЕНИЙ ====================

async def send_ranking_notifications(bot_token):
    """Отправляет уведомления об изменениях в рейтинге."""
    bot = Bot(token=bot_token)
    conn = get_db_connection()
    cur = dict_cursor(conn)

    try:
        # Получаем пользователей, у которых изменилась позиция
        cur.execute("""
            SELECT
                user_id,
                exercise_id,
                complex_id,
                category,
                previous_position,
                current_position,
                last_notification_date
            FROM user_rankings
            WHERE current_position IS NOT NULL
                AND previous_position IS NOT NULL
                AND current_position != previous_position
                AND (last_notification_date IS NULL OR last_notification_date < CURRENT_DATE)
            ORDER BY category, current_position
        """)

        changes = cur.fetchall()

        if not changes:
            logger.info("ℹ️ Нет изменений в рейтинге для уведомлений")
            return

        logger.info(f"📊 Найдено {len(changes)} изменений в рейтинге")

        # Группируем изменения по пользователям
        user_changes = {}
        for change in changes:
            user_id = change['user_id']
            if user_id not in user_changes:
                user_changes[user_id] = []
            user_changes[user_id].append(change)

        # Отправляем уведомления каждому пользователю
        notifications_sent = 0
        for user_id, changes_list in user_changes.items():
            try:
                # Формируем сообщение
                message = "📊 **ТВОЙ РЕЙТИНГ ОБНОВЛЁН**\n\n"

                # Сортируем изменения по значимости
                changes_list.sort(key=lambda x: abs(x['previous_position'] - x['current_position']), reverse=True)

                for change in changes_list[:5]:  # Максимум 5 изменений в сообщении
                    category = change['category']
                    old_pos = change['previous_position']
                    new_pos = change['current_position']

                    delta = old_pos - new_pos

                    if delta > 0:
                        emoji = "📈"
                        action = "поднялся"
                    elif delta < 0:
                        emoji = "📉"
                        action = "опустился"
                    else:
                        continue

                    category_name = {
                        'workouts': 'Тренировки',
                        'challenges': 'Челленджи',
                        'complexes': 'Комплексы'
                    }.get(category, category)

                    message += f"{emoji} {category_name}: {old_pos} → {new_pos} место\n"

                message += "\n💪 Продолжай в том же духе!"

                # Отправляем сообщение
                await bot.send_message(
                    chat_id=user_id,
                    text=message,
                    parse_mode="Markdown"
                )

                # Обновляем дату последнего уведомления
                cur.execute("""
                    UPDATE user_rankings
                    SET last_notification_date = CURRENT_DATE
                    WHERE user_id = %s
                """, (user_id,))

                notifications_sent += 1
                logger.info(f"✅ Уведомление отправлено пользователю {user_id}")

            except Exception as e:
                logger.error(f"❌ Ошибка отправки уведомления пользователю {user_id}: {e}")

        conn.commit()
        logger.info(f"📊 Отправлено {notifications_sent} уведомлений о рейтинге")

    except Exception as e:
        logger.error(f"❌ Ошибка при отправке уведомлений: {e}")
    finally:
        release_db_connection(conn)


# ==================== ГЛАВНАЯ ФУНКЦИЯ ОБНОВЛЕНИЯ РЕЙТИНГА ====================

async def update_rankings_and_notify(bot_token):
    """
    Главная функция, которая:
    1. Получает текущие топы
    2. Сравнивает с предыдущими позициями
    3. Отправляет уведомления об изменениях
    """
    logger.info("🔄 Начало обновления рейтингов...")

    try:
        # Обновляем топ по тренировкам
        workouts_top = get_workouts_leaderboard(limit=100)
        save_user_rankings('workouts', workouts_top)

        # Обновляем топ по челленджам
        challenges_top = get_challenges_leaderboard(limit=100)
        save_user_rankings('challenges', challenges_top)

        # Обновляем топ по комплексам
        complexes_top = get_complexes_leaderboard(limit=100)
        save_user_rankings('complexes', complexes_top)

        logger.info("✅ Рейтинги обновлены")

        # Отправляем уведомления
        await send_ranking_notifications(bot_token)

    except Exception as e:
        logger.error(f"❌ Ошибка при обновлении рейтингов: {e}")


if __name__ == '__main__':
    # Тестовый запуск
    from dotenv import load_dotenv
    import os

    load_dotenv()
    BOT_TOKEN = os.getenv('BOT_TOKEN')

    # Инициализируем таблицу
    init_ranking_notifications_table()

    # Обновляем рейтинги
    import asyncio
    asyncio.run(update_rankings_and_notify(BOT_TOKEN))
