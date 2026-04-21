# -*- coding: utf-8 -*-
# Система чемпионов

import logging
from datetime import datetime, timedelta
from calendar import monthrange
from database_postgres import get_db_connection, release_db_connection

logger = logging.getLogger(__name__)

def calculate_monthly_champions(year=None, month=None):
    """
    Рассчитывает чемпионов месяца для всех упражнений.

    Args:
        year: Год (по умолчанию текущий)
        month: Месяц (по умолчанию предыдущий)

    Returns:
        dict: Результаты расчета {exercise_id: [champion1, champion2, champion3]}
    """
    if year is None:
        # Если не указан, берем предыдущий месяц
        today = datetime.now()
        if today.month == 1:
            year = today.year - 1
            month = 12
        else:
            year = today.year
            month = today.month - 1

    logger.info(f"🏆 Расчет чемпионов за {month}.{year}")

    conn = get_db_connection()
    cur = conn.cursor()

    try:
        # Определяем дату начала и конца месяца
        start_date = datetime(year, month, 1)
        _, last_day = monthrange(year, month)
        end_date = datetime(year, month, last_day, 23, 59, 59)

        logger.info(f"Период: {start_date} - {end_date}")

        # Получаем все упражнения с is_speed_competition = TRUE
        cur.execute("""
            SELECT id, name, speed_points_pool
            FROM exercises
            WHERE is_speed_competition = TRUE
        """)
        exercises = cur.fetchall()

        if not exercises:
            logger.info("Нет упражнений с соревнованиями на скорость")
            return {}

        results = {}

        for exercise_id, exercise_name, points_pool in exercises:
            logger.info(f"Обработка упражнения: {exercise_name}")

            # Получаем все результаты за период
            cur.execute("""
                SELECT w.user_id, u.first_name, u.username,
                       w.result_value, w.date
                FROM workouts w
                JOIN users u ON w.user_id = u.telegram_id
                WHERE w.exercise_id = %s
                  AND w.date >= %s
                  AND w.date <= %s
                ORDER BY w.result_value ASC
            """, (exercise_id, start_date, end_date))

            workouts = cur.fetchall()

            if not workouts:
                logger.info(f"Нет результатов для упражнения {exercise_name}")
                continue

            # Считаем победные очки для каждого пользователя
            # 🥇 1 место = 3 очка, 🥈 2 место = 2 очка, 🥉 3 место = 1 очко
            user_scores = {}
            position = 1

            for workout in workouts:
                user_id = workout[0]

                if user_id not in user_scores:
                    user_scores[user_id] = {
                        'first_place': 0,
                        'second_place': 0,
                        'third_place': 0,
                        'total_score': 0,
                        'first_name': workout[1],
                        'username': workout[2]
                    }

                if position == 1:
                    user_scores[user_id]['first_place'] += 1
                    user_scores[user_id]['total_score'] += 3
                elif position == 2:
                    user_scores[user_id]['second_place'] += 1
                    user_scores[user_id]['total_score'] += 2
                elif position == 3:
                    user_scores[user_id]['third_place'] += 1
                    user_scores[user_id]['total_score'] += 1

                position += 1

            # Сортируем по очкам и берем топ-3
            sorted_users = sorted(
                user_scores.items(),
                key=lambda x: x[1]['total_score'],
                reverse=True
            )[:3]

            if not sorted_users:
                continue

            # Сохраняем чемпионов в базу
            for rank, (user_id, user_data) in enumerate(sorted_users, 1):
                cur.execute("""
                    INSERT INTO champions
                    (user_id, target_type, target_id, period_type, period_start, period_end,
                     position, wins_score, first_place_count, second_place_count, third_place_count)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """, (
                    user_id, 'exercise', exercise_id, 'month',
                    start_date.date(), end_date.date(),
                    rank,
                    user_data['total_score'],
                    user_data['first_place'],
                    user_data['second_place'],
                    user_data['third_place']
                ))

                # Начисляем мега-бонусы
                if rank == 1:
                    bonus = int(points_pool * 0.5) if points_pool else 5000
                elif rank == 2:
                    bonus = int(points_pool * 0.3) if points_pool else 3000
                else:  # rank == 3
                    bonus = int(points_pool * 0.2) if points_pool else 2000

                # Начисляем мега-бонус
                cur.execute("UPDATE users SET score = score + %s WHERE telegram_id = %s", (bonus, user_id))
                logger.info(f"Начислено {bonus} очков пользователю {user_id} ({rank} место в {exercise_name})")

            results[exercise_id] = sorted_users
            logger.info(f"Чемпионы '{exercise_name}': {len(sorted_users)} мест")

        conn.commit()
        logger.info(f"✅ Расчет чемпионов завершен. Обработано {len(results)} упражнений")
        return results

    except Exception as e:
        logger.error(f"Ошибка расчета чемпионов: {e}")
        conn.rollback()
        return {}
    finally:
        release_db_connection(conn)


def get_monthly_champions(year=None, month=None, exercise_id=None):
    """
    Получает чемпионов месяца из базы.

    Args:
        year: Год
        month: Месяц
        exercise_id: ID упражнения (опционально)

    Returns:
        list: Список чемпионов
    """
    conn = get_db_connection()
    cur = conn.cursor()

    try:
        if year is None:
            today = datetime.now()
            if today.month == 1:
                year = today.year - 1
                month = 12
            else:
                year = today.year
                month = today.month - 1

        # Определяем дату начала и конца месяца
        start_date = datetime(year, month, 1).date()
        _, last_day = monthrange(year, month)
        end_date = datetime(year, month, last_day).date()

        if exercise_id:
            cur.execute("""
                SELECT c.*, u.first_name, u.username, e.name as exercise_name
                FROM champions c
                JOIN users u ON c.user_id = u.telegram_id
                LEFT JOIN exercises e ON c.target_id = e.id
                WHERE c.period_type = 'month'
                  AND c.period_start = %s
                  AND c.period_end = %s
                  AND c.target_id = %s
                ORDER BY e.name, c.position
            """, (start_date, end_date, exercise_id))
        else:
            cur.execute("""
                SELECT c.*, u.first_name, u.username, e.name as exercise_name
                FROM champions c
                JOIN users u ON c.user_id = u.telegram_id
                LEFT JOIN exercises e ON c.target_id = e.id
                WHERE c.period_type = 'month'
                  AND c.period_start = %s
                  AND c.period_end = %s
                ORDER BY e.name, c.position
            """, (start_date, end_date))

        champions = cur.fetchall()
        return champions

    except Exception as e:
        logger.error(f"Ошибка получения чемпионов: {e}")
        return []
    finally:
        release_db_connection(conn)


if __name__ == '__main__':
    # Тестовый расчет
    logging.basicConfig(level=logging.INFO)
    results = calculate_monthly_champions()

    if results:
        print(f"\n🏆 РЕЗУЛЬТАТЫ РАСЧЕТА ЧЕМПИОНОВ:")
        for exercise_id, champions in results.items():
            print(f"\nУпражнение #{exercise_id}:")
            for rank, (user_id, user_data) in enumerate(champions, 1):
                username = user_data['username'] or 'Нет username'
                print(f"  {rank}. @{username} - {user_data['total_score']} очков")
    else:
        print("Нет результатов для отображения")


async def calculate_and_notify_champions(context=None):
    """
    Рассчитывает чемпионов и отправляет уведомления победителям.
    Используется для автоматического запуска по расписанию.

    Args:
        context: CallbackContext бота (для отправки уведомлений)

    Returns:
        dict: Результаты расчёта
    """
    logger.info("🏆 Автоматический расчёт чемпионов...")

    # Определяем прошлый месяц
    today = datetime.now()
    if today.month == 1:
        year = today.year - 1
        month = 12
    else:
        year = today.year
        month = today.month - 1

    # Проверяем, не рассчитывались ли уже чемпионы за этот период
    conn = get_db_connection()
    cur = conn.cursor()

    try:
        # Проверяем наличие записей чемпионов за этот период
        cur.execute("""
            SELECT COUNT(*) FROM monthly_champions
            WHERE year = %s AND month = %s
        """, (year, month))

        existing_count = cur.fetchone()[0]

        if existing_count > 0:
            logger.info(f"⚠️ Чемпионы за {month}.{year} уже рассчитаны ({existing_count} записей)")
            conn.close()
            return None

        # Выполняем расчёт
        results = calculate_monthly_champions(year, month)

        if not results:
            logger.info("Нет данных для расчёта чемпионов")
            return None

        # Отправляем уведомления победителям
        if context:
            bot = context.bot
            notified_count = 0

            for exercise_id, champions in results.items():
                # Получаем название упражнения
                cur.execute("SELECT name FROM exercises WHERE id = %s", (exercise_id,))
                exercise_row = cur.fetchone()
                exercise_name = exercise_row[0] if exercise_row else f"Упражнение #{exercise_id}"

                for rank, (user_id, user_data) in enumerate(champions, 1):
                    try:
                        # Определяем медаль
                        if rank == 1:
                            medal = "🥇"
                            bonus_percent = "50%"
                        elif rank == 2:
                            medal = "🥈"
                            bonus_percent = "30%"
                        else:
                            medal = "🥉"
                            bonus_percent = "20%"

                        first_name = user_data.get('first_name', 'Пользователь')
                        username = user_data.get('username')

                        notification_text = f"{medal} **ТЫ ЧЕМПИОН!**\n\n"
                        notification_text += f"🏆 {exercise_name}\n"
                        notification_text += f"📅 {month}.{year}\n"
                        notification_text += f"📍 Место: {rank}\n"
                        notification_text += f"💰 Мега-бонус: {bonus_percent} от банка\n\n"
                        notification_text += f"🎉 Поздравляем с победой!"

                        await bot.send_message(
                            chat_id=user_id,
                            text=notification_text,
                            parse_mode="Markdown"
                        )
                        notified_count += 1
                        logger.info(f"📬 Уведомление отправлено: {user_id} ({first_name})")

                    except Exception as e:
                        logger.error(f"Ошибка отправки уведомления {user_id}: {e}")

            logger.info(f"✅ Расчёт чемпионов завершён. Уведомлений отправлено: {notified_count}")

        return results

    except Exception as e:
        logger.error(f"Ошибка в автоматическом расчёте чемпионов: {e}")
        return None

    finally:
        release_db_connection(conn)
