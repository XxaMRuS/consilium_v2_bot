# -*- coding: utf-8 -*-
# Система уведомлений в канал

import logging
import os
from datetime import datetime
from dotenv import load_dotenv
from telegram import InlineKeyboardButton, InlineKeyboardMarkup

logger = logging.getLogger(__name__)

# ID канала для уведомлений (берём из .env или используем дефолтный)
load_dotenv()
CHANNEL_ID = int(os.getenv('NOTIFICATION_CHANNEL_ID', -1003634185270))
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

        # Перевод метрик
        metric_names = {
            'reps': 'Повторы',
            'time': 'Время (мин)',
            'weight': 'Вес (кг)',
            'distance': 'Дистанция (км)'
        }
        metric_text = metric_names.get(metric, metric)

        # Определяем сложность
        difficulty_emoji = {
            'beginner': '👶',
            'intermediate': '🤓',
            'advanced': '🏋️'
        }.get(difficulty, '👶')

        text = f"🆕 <b>НОВОЕ УПРАЖНЕНИЕ</b>\n\n"
        text += f"{difficulty_emoji} <b>{name}</b>\n\n"
        text += f"📝 {description}\n\n"
        text += f"📊 Метрика: {metric_text}\n"
        text += f"💎 Очки: {points}\n"
        text += f"🆔 ID: {exercise_id}\n\n"
        text += f"👤 Создал: {creator_name}\n"
        text += f"⏰ {datetime.now().strftime('%H:%M')}"

        message = await bot.send_message(
            chat_id=CHANNEL_ID,
            text=text,
            parse_mode="HTML"
        )

        # Создаем прямую ссылку на сообщение
        message_link = f"https://t.me/{CHANNEL_USERNAME.replace('@', '')}/{message.message_id}"
        await bot.edit_message_reply_markup(
            chat_id=CHANNEL_ID,
            message_id=message.message_id,
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("💬 Обсудить упражнение", url=message_link)
            ]])
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

        text = "🎯 <b>НОВЫЙ ЧЕЛЛЕНДЖ</b>\n\n"
        text += f"<b>{name}</b>\n\n"
        text += f"📝 {description}\n\n"
        text += f"⏰ Длительность: {duration_days} дней\n"
        text += f"🆔 ID: {challenge_id}\n\n"
        text += f"👤 Создал: {creator_name}\n"
        text += f"⏰ {datetime.now().strftime('%H:%M')}"

        await bot.send_message(
            chat_id=CHANNEL_ID,
            text=text,
            parse_mode="HTML"
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

        text = "🏋️ <b>НОВЫЙ КОМПЛЕКС</b>\n\n"
        text += f"{difficulty_emoji} <b>{name}</b>\n\n"
        text += f"📝 {description}\n\n"
        text += f"🆔 ID: {complex_id}\n\n"
        text += f"👤 Создал: {creator_name}\n"
        text += f"⏰ {datetime.now().strftime('%H:%M')}"

        await bot.send_message(
            chat_id=CHANNEL_ID,
            text=text,
            parse_mode="HTML"
        )
        logger.info(f"✅ Уведомление о комплексе отправлено: {name}")

    except Exception as e:
        logger.error(f"Ошибка отправки уведомления о комплексе: {e}")


async def notify_workout_completion(bot, workout_data):
    """Отправляет уведомление о выполнении тренировки в канал."""
    try:
        logger.info(f"🔔 Начинаю отправку уведомления о тренировке: {workout_data}")
        user_id = workout_data.get('user_id')
        user_name = workout_data.get('user_name', 'Пользователь')
        username = workout_data.get('username', '')
        exercise_name = workout_data.get('exercise_name', 'Упражнение')
        result_value = workout_data.get('result_value', '')
        video_link = workout_data.get('video_link', '')

        username_str = f"@{username}" if username else ""

        text = "💪 <b>ВЫПОЛНЕНА ТРЕНИРОВКА</b>\n\n"
        text += f"👤 {user_name} {username_str}\n"
        text += f"🏋️ {exercise_name}\n\n"

        if result_value:
            text += f"📊 Результат: <b>{result_value}</b>\n\n"

        if video_link:
            text += f"🎥 Видео: {video_link}\n\n"

        text += f"⏰ {datetime.now().strftime('%H:%M')}"
        text += f" | 🆔 ID: {user_id}"

        logger.info(f"📤 Отправка сообщения в канал {CHANNEL_ID}: {text[:100]}...")
        message = await bot.send_message(
            chat_id=CHANNEL_ID,
            text=text,
            parse_mode="HTML"
        )

        # Создаем прямую ссылку на сообщение для комментариев
        message_link = f"https://t.me/{CHANNEL_USERNAME.replace('@', '')}/{message.message_id}"
        logger.info(f"✅ Уведомление о тренировке отправлено: {user_name}")
        logger.info(f"🔗 Ссылка на сообщение: {message_link}")

        # Добавляем кнопку для обсуждения
        from telegram import InlineKeyboardButton, InlineKeyboardMarkup
        await bot.edit_message_reply_markup(
            chat_id=CHANNEL_ID,
            message_id=message.message_id,
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("💬 Прокомментируйте!", url=message_link)
            ]])
        )

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

        text = "🎯 <b>ВЫПОЛНЕН ЧЕЛЛЕНДЖ</b>\n\n"
        text += f"👤 {user_name} {username_str}\n"
        text += f"🎯 {challenge_name}\n\n"

        if result_value:
            text += f"📊 Результат: <b>{result_value}</b>\n\n"

        if video_link:
            text += f"🎥 Видео: {video_link}\n\n"

        text += f"💬 Прокомментируйте выполнение!\n"
        text += f"⏰ {datetime.now().strftime('%H:%M')}"
        text += f" | 🆔 ID: {user_id}"

        await bot.send_message(
            chat_id=CHANNEL_ID,
            text=text,
            parse_mode="HTML"
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

        text = "🏋️ <b>ВЫПОЛНЕН КОМПЛЕКС</b>\n\n"
        text += f"👤 {user_name} {username_str}\n"
        text += f"🏋️ {complex_name}\n\n"

        if video_link:
            text += f"🎥 Видео: {video_link}\n\n"

        text += f"💬 Прокомментируйте выполнение!\n"
        text += f"⏰ {datetime.now().strftime('%H:%M')}"
        text += f" | 🆔 ID: {user_id}"

        message = await bot.send_message(
            chat_id=CHANNEL_ID,
            text=text,
            parse_mode="HTML"
        )

        # Создаем прямую ссылку на сообщение
        message_link = f"https://t.me/{CHANNEL_USERNAME.replace('@', '')}/{message.message_id}"
        await bot.edit_message_reply_markup(
            chat_id=CHANNEL_ID,
            message_id=message.message_id,
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("💬 Прокомментируйте!", url=message_link)
            ]])
        )
        logger.info(f"✅ Уведомление о выполнении комплекса отправлено: {user_name}")

    except Exception as e:
        logger.error(f"Ошибка отправки уведомления о комплексе: {e}")


async def notify_new_record(bot, user_id, exercise_id, new_result, metric_type, user_name=None, exercise_name=None):
    """Отправляет уведомление о новом личном рекорде в канал."""
    try:
        from database_postgres import get_exercise_by_id, get_user_info

        # Получаем информацию об упражнении
        if not exercise_name:
            exercise = get_exercise_by_id(exercise_id)
            if exercise:
                exercise_name = exercise[1]  # name
            else:
                exercise_name = "Упражнение"

        # Получаем информацию о пользователе
        if not user_name:
            user = get_user_info(user_id)
            if user:
                user_name = user[1]  # name

        # Форматируем результат
        metric_names = {'reps': 'раз', 'time': 'сек', 'weight': 'кг', 'distance': 'км'}
        metric_text = metric_names.get(metric_type, metric_type)

        text = "🏆 <b>НОВЫЙ ЛИЧНЫЙ РЕКОРД</b>\n\n"
        text += f"👤 {user_name or 'Пользователь'}\n"
        text += f"🏋️ {exercise_name}\n\n"
        text += f"📊 Результат: <b>{new_result} {metric_text}</b>\n\n"
        text += f"🆔 ID: {user_id}"
        text += f" | ⏰ {datetime.now().strftime('%H:%M')}"

        await bot.send_message(
            chat_id=CHANNEL_ID,
            text=text,
            parse_mode="HTML"
        )
        logger.info(f"✅ Уведомление о новом рекорде отправлено: {user_name}")

    except Exception as e:
        logger.error(f"Ошибка отправки уведомления о рекорде: {e}")
