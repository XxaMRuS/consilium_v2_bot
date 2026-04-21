# -*- coding: utf-8 -*-
# Система уведомлений в канал

import logging
from datetime import datetime

logger = logging.getLogger(__name__)

# ID канала для уведомлений
CHANNEL_ID = -100363185270
CHANNEL_USERNAME = "@MDFruN_Sports_Channel"

async def notify_new_exercise(bot, exercise_data, creator_name):
    """Отправляет уведомление о новом упражнении в канал."""
    try:
        exercise_id = exercise_data.get('id')
        name = exercise_data.get('name', 'Без названия')
        description = exercise_data.get('description', '')
        metric = exercise_data.get('metric', '')
        difficulty = exercise_data.get('difficulty', 'beginner')
        points = exercise_data.get('points', 0)

        # Определяем сложность
        difficulty_emoji = {
            'beginner': '👶',
            'intermediate': '🤓',
            'advanced': '🏋️'
        }.get(difficulty, '👶')

        text = f"🆕 **НОВОЕ УПРАЖНЕНИЕ**\n\n"
        text += f"{difficulty_emoji} **{name}**\n\n"
        text += f"📝 {description}\n\n"
        text += f"📊 Метрика: {metric}\n"
        text += f"💎 Очки: {points}\n"
        text += f"🆔 ID: {exercise_id}\n\n"
        text += f"👤 Создал: {creator_name}\n"
        text += f"⏰ {datetime.now().strftime('%H:%M')}"

        await bot.send_message(
            chat_id=CHANNEL_ID,
            text=text,
            parse_mode="Markdown"
        )
        logger.info(f"✅ Уведомление о новом упражнении отправлено: {name}")

    except Exception as e:
        logger.error(f"Ошибка отправки уведомления об упражнении: {e}")


async def notify_new_challenge(bot, challenge_data, creator_name):
    """Отправляет уведомление о новом челлендже в канал."""
    try:
        challenge_id = challenge_data.get('id')
        name = challenge_data.get('name', 'Без названия')
        description = challenge_data.get('description', '')
        duration_days = challenge_data.get('duration_days', 7)

        text = "🎯 **НОВЫЙ ЧЕЛЛЕНДЖ**\n\n"
        text += f"**{name}**\n\n"
        text += f"📝 {description}\n\n"
        text += f"⏰ Длительность: {duration_days} дней\n"
        text += f"🆔 ID: {challenge_id}\n\n"
        text += f"👤 Создал: {creator_name}\n"
        text += f"⏰ {datetime.now().strftime('%H:%M')}"

        await bot.send_message(
            chat_id=CHANNEL_ID,
            text=text,
            parse_mode="Markdown"
        )
        logger.info(f"✅ Уведомление о челлендже отправлено: {name}")

    except Exception as e:
        logger.error(f"Ошибка отправки уведомления о челлендже: {e}")


async def notify_new_complex(bot, complex_data, creator_name):
    """Отправляет уведомление о новом комплексе в канал."""
    try:
        complex_id = complex_data.get('id')
        name = complex_data.get('name', 'Без названия')
        description = complex_data.get('description', '')
        difficulty = complex_data.get('difficulty', 'beginner')

        difficulty_emoji = {
            'beginner': '👶',
            'intermediate': '🤓',
            'advanced': '🏋️'
        }.get(difficulty, '👶')

        text = "🏋️ **НОВЫЙ КОМПЛЕКС**\n\n"
        text += f"{difficulty_emoji} **{name}**\n\n"
        text += f"📝 {description}\n\n"
        text += f"🆔 ID: {complex_id}\n\n"
        text += f"👤 Создал: {creator_name}\n"
        text += f"⏰ {datetime.now().strftime('%H:%M')}"

        await bot.send_message(
            chat_id=CHANNEL_ID,
            text=text,
            parse_mode="Markdown"
        )
        logger.info(f"✅ Уведомление о комплексе отправлено: {name}")

    except Exception as e:
        logger.error(f"Ошибка отправки уведомления о комплексе: {e}")


async def notify_workout_completion(bot, workout_data):
    """Отправляет уведомление о выполнении тренировки в канал."""
    try:
        user_id = workout_data.get('user_id')
        user_name = workout_data.get('user_name', 'Пользователь')
        username = workout_data.get('username', '')
        exercise_name = workout_data.get('exercise_name', 'Упражнение')
        result_value = workout_data.get('result_value', '')
        video_link = workout_data.get('video_link', '')

        username_str = f"@{username}" if username else ""

        text = "💪 **ВЫПОЛНЕНА ТРЕНИРОВКА**\n\n"
        text += f"👤 {user_name} {username_str}\n"
        text += f"🏋️ {exercise_name}\n\n"

        if result_value:
            text += f"📊 Результат: **{result_value}**\n\n"

        if video_link:
            text += f"🎥 Видео: {video_link}\n\n"

        text += f"⏰ {datetime.now().strftime('%H:%M')}"
        text += f" | 🆔 ID: {user_id}"

        await bot.send_message(
            chat_id=CHANNEL_ID,
            text=text,
            parse_mode="Markdown"
        )
        logger.info(f"✅ Уведомление о тренировке отправлено: {user_name}")

    except Exception as e:
        logger.error(f"Ошибка отправки уведомления о тренировке: {e}")


async def notify_challenge_completion(bot, completion_data):
    """Отправляет уведомление о выполнении челленджа в канал."""
    try:
        user_id = completion_data.get('user_id')
        user_name = completion_data.get('user_name', 'Пользователь')
        username = completion_data.get('username', '')
        challenge_name = completion_data.get('challenge_name', 'Челлендж')
        result_value = completion_data.get('result_value', '')
        video_link = completion_data.get('video_link', '')

        username_str = f"@{username}" if username else ""

        text = "🎯 **ВЫПОЛНЕН ЧЕЛЛЕНДЖ**\n\n"
        text += f"👤 {user_name} {username_str}\n"
        text += f"🎯 {challenge_name}\n\n"

        if result_value:
            text += f"📊 Результат: **{result_value}**\n\n"

        if video_link:
            text += f"🎥 Видео: {video_link}\n\n"

        text += f"💬 Прокомментируйте выполнение!\n"
        text += f"⏰ {datetime.now().strftime('%H:%M')}"
        text += f" | 🆔 ID: {user_id}"

        await bot.send_message(
            chat_id=CHANNEL_ID,
            text=text,
            parse_mode="Markdown"
        )
        logger.info(f"✅ Уведомление о выполнении челленджа отправлено: {user_name}")

    except Exception as e:
        logger.error(f"Ошибка отправки уведомления о челлендже: {e}")


async def notify_complex_completion(bot, completion_data):
    """Отправляет уведомление о выполнении комплекса в канал."""
    try:
        user_id = completion_data.get('user_id')
        user_name = completion_data.get('user_name', 'Пользователь')
        username = completion_data.get('username', '')
        complex_name = completion_data.get('complex_name', 'Комплекс')
        video_link = completion_data.get('video_link', '')

        username_str = f"@{username}" if username else ""

        text = "🏋️ **ВЫПОЛНЕН КОМПЛЕКС**\n\n"
        text += f"👤 {user_name} {username_str}\n"
        text += f"🏋️ {complex_name}\n\n"

        if video_link:
            text += f"🎥 Видео: {video_link}\n\n"

        text += f"💬 Прокомментируйте выполнение!\n"
        text += f"⏰ {datetime.now().strftime('%H:%M')}"
        text += f" | 🆔 ID: {user_id}"

        await bot.send_message(
            chat_id=CHANNEL_ID,
            text=text,
            parse_mode="Markdown"
        )
        logger.info(f"✅ Уведомление о выполнении комплекса отправлено: {user_name}")

    except Exception as e:
        logger.error(f"Ошибка отправки уведомления о комплексе: {e}")
