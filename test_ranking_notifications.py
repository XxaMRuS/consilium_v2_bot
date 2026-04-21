# -*- coding: utf-8 -*-
# Тестовый скрипт для системы уведомлений о рейтинге

import asyncio
import logging
from dotenv import load_dotenv
import os
from ranking_notifications import (
    init_ranking_notifications_table,
    get_workouts_leaderboard,
    get_challenges_leaderboard,
    get_complexes_leaderboard,
    save_user_rankings,
    update_rankings_and_notify
)

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

def test_leaderboard_functions():
    """Тестирует функции получения топов."""
    logger.info("🧪 Тестирование функций получения топов...")

    # Топ по тренировкам
    workouts_top = get_workouts_leaderboard(limit=10)
    logger.info(f"💪 Топ-10 тренировок: {len(workouts_top)} записей")
    if workouts_top:
        logger.info(f"   1 место: {workouts_top[0]['first_name']} - {workouts_top[0]['workout_count']} тренировок")

    # Топ по челленджам
    challenges_top = get_challenges_leaderboard(limit=10)
    logger.info(f"🏆 Топ-10 челленджей: {len(challenges_top)} записей")
    if challenges_top:
        logger.info(f"   1 место: {challenges_top[0]['first_name']} - {challenges_top[0]['challenge_count']} челленджей")

    # Топ по комплексам
    complexes_top = get_complexes_leaderboard(limit=10)
    logger.info(f"📦 Топ-10 комплексов: {len(complexes_top)} записей")
    if complexes_top:
        logger.info(f"   1 место: {complexes_top[0]['first_name']} - {complexes_top[0]['complex_count']} комплексов")

    return len(workouts_top) > 0 or len(challenges_top) > 0 or len(complexes_top) > 0


def test_save_rankings():
    """Тестирует сохранение позиций."""
    logger.info("💾 Тестирование сохранения позиций...")

    # Получаем топы
    workouts_top = get_workouts_leaderboard(limit=10)
    challenges_top = get_challenges_leaderboard(limit=10)
    complexes_top = get_complexes_leaderboard(limit=10)

    # Сохраняем позиции
    save_user_rankings('workouts', workouts_top)
    save_user_rankings('challenges', challenges_top)
    save_user_rankings('complexes', complexes_top)

    logger.info("✅ Позиции сохранены")
    return True


async def test_full_update():
    """Тестирует полный цикл обновления."""
    logger.info("🔄 Тестирование полного цикла обновления...")

    load_dotenv()
    BOT_TOKEN = os.getenv('BOT_TOKEN')

    if not BOT_TOKEN:
        logger.error("❌ BOT_TOKEN не найден в .env файле")
        return False

    await update_rankings_and_notify(BOT_TOKEN)
    logger.info("✅ Полный цикл обновления завершён")
    return True


def main():
    """Главная функция тестирования."""
    logger.info("🚀 Начало тестирования системы уведомлений о рейтинге")

    try:
        # Шаг 1: Инициализация таблицы
        logger.info("📊 Шаг 1: Инициализация таблицы...")
        init_ranking_notifications_table()

        # Шаг 2: Тестирование функций получения топов
        logger.info("\n📊 Шаг 2: Тестирование функций получения топов...")
        has_data = test_leaderboard_functions()

        if not has_data:
            logger.warning("⚠️ В базе нет данных для тестирования")
            logger.info("💡 Создайте несколько тренировок/челленджей и запустите тест снова")
            return

        # Шаг 3: Тестирование сохранения позиций
        logger.info("\n📊 Шаг 3: Тестирование сохранения позиций...")
        test_save_rankings()

        # Шаг 4: Тестирование полного цикла обновления
        logger.info("\n📊 Шаг 4: Тестирование полного цикла обновления...")
        asyncio.run(test_full_update())

        logger.info("\n✅ Все тесты пройдены успешно!")

    except Exception as e:
        logger.error(f"❌ Ошибка при тестировании: {e}")
        import traceback
        traceback.print_exc()


if __name__ == '__main__':
    main()
