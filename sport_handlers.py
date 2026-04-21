#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Обработчики модуля Спорт

import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler, MessageHandler, CommandHandler, CallbackQueryHandler, filters

from database_postgres import (
  get_exercises, get_exercise_by_id,
  get_all_complexes, get_challenges_by_status, join_challenge,
  get_user_stats, get_top_workouts, get_top_challenges, get_top_complexes,
  add_workout
)

from debug_utils import debug_print, log_call
import channel_notifications

logger = logging.getLogger(__name__)

# ==================== КОНСТАНТЫ ====================
SPORT_MENU = "sport_menu"
SPORT_EXERCISES = "sport_exercises"
SPORT_CHALLENGES = "sport_challenges"
SPORT_COMPLEXES = "sport_complexes"
SPORT_RATINGS = "sport_ratings"
SPORT_MY_STATS = "sport_my_stats"
SPORT_TOP_WORKOUTS = "sport_top_workouts"
SPORT_TOP_CHALLENGES = "sport_top_challenges"
SPORT_TOP_COMPLEXES = "sport_top_complexes"
SPORT_BACK_TO_MAIN = "sport_back_to_main"
SPORT_WORKOUT_START = "sport_workout_start"
SPORT_CHALLENGE_JOIN = "sport_challenge_join"
SPORT_COMPLEX_START = "sport_complex_start"

REPS = 1
TIME = 2
VIDEO = 3

# Состояния для ConversationHandler выполнения упражнений
WORKOUT_INPUT = 50      # Ввод результата упражнения
WORKOUT_PROOF = 51      # Загрузка доказательства (видео/фото)

# Вспомогательная функция для форматирования результата
def format_workout_result(value, metric):
    """Форматирует результат упражнения для отображения."""
    if metric == 'time':
        # Конвертируем секунды в формат мм:сс
        minutes = int(value) // 60
        seconds = int(value) % 60
        return f"{minutes:02d}:{seconds:02d}"
    else:
        # Для остальных метрик просто возвращаем значение
        return str(value)

# ==================== ГЛАВНОЕ МЕНЮ ====================

@log_call
async def sport_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    try:
        await query.answer()
    except:
        pass

    keyboard = [
        [InlineKeyboardButton("💪 Тренировки", callback_data=SPORT_EXERCISES)],
        [InlineKeyboardButton("🏆 Челленджи", callback_data=SPORT_CHALLENGES)],
        [InlineKeyboardButton("📦 Комплексы", callback_data=SPORT_COMPLEXES)],
        [InlineKeyboardButton("📊 Рейтинги", callback_data=SPORT_RATINGS)],
        [InlineKeyboardButton("📈 Моя статистика", callback_data=SPORT_MY_STATS)],
        [InlineKeyboardButton("◀️ В главное меню", callback_data=SPORT_BACK_TO_MAIN)]
    ]

    text = "🏋️**СПОРТ**\n\nДобро пожаловать! Выбери раздел:"
    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")

# ==================== УПРАЖНЕНИЯ ====================

@log_call
async def exercises_list(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    try:
        await query.answer()
    except:
        pass

    exercises = get_exercises(active_only=True)
    if not exercises:
        keyboard = [[InlineKeyboardButton("◀️ В меню спорта", callback_data=SPORT_MENU)]]
        await query.edit_message_text("❌ Активных упражнений пока нет.", reply_markup=InlineKeyboardMarkup(keyboard))
        return

    keyboard = []
    for ex in exercises:
        ex_id, name, metric, points, week, diff = ex
        metric_icon = "⏱" if metric == "time" else "🔢"
        diff_emoji = "🙂" if diff == "newbie" else "🤓"

        button_text = f"{diff_emoji} {name} | {metric_icon} | ⭐{points}"
        keyboard.append([InlineKeyboardButton(button_text, callback_data=f"{SPORT_WORKOUT_START}_{ex_id}")])

    keyboard.append([InlineKeyboardButton("🏆 Топ тренировок", callback_data=SPORT_TOP_WORKOUTS)])
    keyboard.append([InlineKeyboardButton("◀️ В меню спорта", callback_data=SPORT_MENU)])
    await query.edit_message_text("💪 **Упражнения**", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")

# ==================== ВЫПОЛНЕНИЕ УПРАЖНЕНИЙ ====================

@log_call
async def start_workout(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Начинает выполнение упражнения."""
    query = update.callback_query
    await query.answer()

    # Формат: sport_workout_start_{exercise_id}
    exercise_id = int(query.data.split("_")[-1])

    # Сохраняем ID упражнения
    context.user_data['current_workout_exercise_id'] = exercise_id

    # Получаем информацию об упражнении
    exercise = get_exercise_by_id(exercise_id)
    if not exercise:
        await query.edit_message_text("❌ Упражнение не найдено")
        return ConversationHandler.END

    ex_id, name, description, metric, points, week, difficulty = exercise

    metric_names = {'reps': 'Повторы', 'time': 'Время', 'weight': 'Вес (кг)', 'distance': 'Дистанция (км)'}
    metric_text = metric_names.get(metric, metric)

    # Определяем формат ввода и пример
    if metric == 'time':
        input_format = "в формате мм:сс (например: 23:15)"
        example = "23:15"
    else:
        input_format = f"({metric_text})"
        example = "60"

    text = (
        f"🏋️ **{name}**\n\n"
        f"📊 Метрика: {metric_text}\n"
        f"📝 {description}\n\n"
        f"Введите результат {input_format}\n"
        f"📌 Пример: {example}"
    )

    keyboard = [[InlineKeyboardButton("❌ Отмена", callback_data=SPORT_EXERCISES)]]
    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')

    return WORKOUT_INPUT


@log_call
async def input_workout_result(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обрабатывает ввод результата упражнения."""
    if not update.message or not update.message.text:
        return WORKOUT_INPUT

    result_text = update.message.text.strip()
    exercise_id = context.user_data.get('current_workout_exercise_id')

    # Получаем метрику упражнения
    exercise = get_exercise_by_id(exercise_id)
    if not exercise:
        await update.message.reply_text("❌ Упражнение не найдено")
        return ConversationHandler.END

    ex_id, name, description, metric, points, week, difficulty = exercise

    # Обрабатываем результат в зависимости от метрики
    try:
        if metric == 'time':
            # Парсим формат мм:сс
            if ':' in result_text:
                parts = result_text.split(':')
                if len(parts) == 2:
                    minutes = int(parts[0])
                    seconds = int(parts[1])
                    if seconds >= 60:
                        await update.message.reply_text("❌ Секунды должны быть меньше 60. Пример: 23:15")
                        return WORKOUT_INPUT
                    result_value = minutes * 60 + seconds  # Конвертируем в секунды
                    if result_value <= 0:
                        await update.message.reply_text("❌ Время должно быть положительным")
                        return WORKOUT_INPUT
                else:
                    await update.message.reply_text("❌ Неверный формат. Используйте мм:сс (например: 23:15)")
                    return WORKOUT_INPUT
            else:
                await update.message.reply_text("❌ Для времени используйте формат мм:сс (например: 23:15)")
                return WORKOUT_INPUT
        else:
            # Для остальных метрик - просто число
            result_value = float(result_text)
            if result_value <= 0:
                await update.message.reply_text("❌ Значение должно быть положительным числом")
                return WORKOUT_INPUT
    except ValueError:
        if metric == 'time':
            await update.message.reply_text("❌ Неверный формат. Используйте мм:сс (например: 23:15)")
        else:
            await update.message.reply_text("❌ Введите число")
        return WORKOUT_INPUT

    # Сохраняем результат и метрику
    context.user_data['workout_result'] = result_value
    context.user_data['workout_metric'] = metric

    keyboard = [[InlineKeyboardButton("❌ Отмена", callback_data=SPORT_EXERCISES)]]
    await update.message.reply_text(
        f"✅ Результат: {result_value}\n\n"
        f"📎 **Отправьте ссылку на видео (YouTube, Яндекс.Диск) или прикрепите видео/фото!**\n\n"
        f"⚠️ Без доказательства упражнение не будет засчитано.",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode='Markdown'
    )

    return WORKOUT_PROOF


@log_call
async def upload_workout_proof(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обрабатывает загрузку доказательства упражнения."""
    try:
        user_id = update.effective_user.id
        exercise_id = context.user_data.get('current_workout_exercise_id')
        result_value = context.user_data.get('workout_result')
        metric = context.user_data.get('workout_metric')

        print(f"DEBUG workout: user_id={user_id}, exercise_id={exercise_id}, result_value={result_value}, metric={metric}")

        if not all([exercise_id, result_value]):
            await update.message.reply_text("❌ Ошибка: данные утеряны. Начните заново.")
            return ConversationHandler.END
    except Exception as e:
        print(f"ERROR in upload_workout_proof START: {e}")
        logger.error(f"Error in upload_workout_proof START: {e}")
        await update.message.reply_text("❌ Ошибка при обработке данных")
        return ConversationHandler.END

    # Обрабатываем вложение (фото/видео/документ/ссылка) - ОБЯЗАТЕЛЬНО!
    proof_link = None

    if update.message.photo:
        # Фото
        photo = update.message.photos[-1]
        proof_link = f"photo_{photo.file_id}"
    elif update.message.video:
        # Видео файл
        proof_link = f"video_{update.message.video.file_id}"
    elif update.message.document:
        # Документ файл
        proof_link = f"document_{update.message.document.file_id}"
    elif update.message.text and update.message.text.strip():
        # Текстовая ссылка на видео (YouTube, Vimeo и т.д.)
        text = update.message.text.strip()
        # Простая проверка на ссылку
        if text.startswith('http://') or text.startswith('https://'):
            proof_link = text
        else:
            keyboard = [[InlineKeyboardButton("❌ Отмена", callback_data=SPORT_EXERCISES)]]
            await update.message.reply_text(
                "❌ **Пожалуйста, отправьте ссылку на видео (начинается с http:// или https://)**\n\n"
                "Или прикрепите видео/фото файл.",
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode='Markdown'
            )
            return WORKOUT_PROOF
    else:
        # Если нет ничего - требуем загрузить
        keyboard = [[InlineKeyboardButton("❌ Отмена", callback_data=SPORT_EXERCISES)]]
        await update.message.reply_text(
            "❌ **Обязательно приложите фото, видео или ссылку на видео!**\n\n"
            "Без доказательства упражнение не будет засчитано.",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='Markdown'
        )
        return WORKOUT_PROOF

    print(f"DEBUG workout proof: proof_link={proof_link}")

    # Подготавливаем результат в правильном формате
    if metric == 'time':
        # Для времени - секунды как целое число
        formatted_result = int(result_value)
    elif metric == 'reps':
        # Для повторов - целое число
        formatted_result = int(result_value)
    else:
        # Для остальных метрик (вес, дистанция) - можно float
        formatted_result = result_value

    print(f"DEBUG formatted result: {formatted_result} (type: {type(formatted_result).__name__})")

    # Сохраняем результат в базу данных
    try:
        print(f"DEBUG calling add_workout: user_id={user_id}, exercise_id={exercise_id}, result_value={formatted_result}, proof_link={proof_link}, metric={metric}")

        workout_id, achievements = add_workout(
            user_id=user_id,
            exercise_id=exercise_id,
            result_value=str(formatted_result),
            video_link=proof_link,
            metric=metric
        )
        success = True

        # Отправляем уведомление в канал о выполнении тренировки
        try:
            exercise = get_exercise_by_id(exercise_id)
            if exercise:
                exercise_name = exercise[1]  # name
                user = update.effective_user
                workout_data = {
                    'user_id': user_id,
                    'user_name': user.first_name or "Пользователь",
                    'username': user.username,
                    'exercise_name': exercise_name,
                    'result_value': format_workout_result(formatted_result, metric),
                    'video_link': proof_link if proof_link and not proof_link.startswith(('photo_', 'video_', 'document_')) else ''
                }
                await channel_notifications.notify_workout_completion(context.bot, workout_data)
        except Exception as e:
            logger.error(f"Ошибка отправки уведомления о тренировке: {e}")
        print(f"DEBUG workout save: success=True, workout_id={workout_id}, achievements={achievements}")
    except Exception as e:
        logger.error(f"Error saving workout: {e}")
        success = False
        print(f"DEBUG workout save: success=False, error={e}")
        import traceback
        traceback.print_exc()  # Печатаем полный стек ошибок

    context.user_data.clear()

    if success:
        formatted_result = format_workout_result(result_value, metric) if metric else str(result_value)
        text = (
            f"✅ **УПРАЖНЕНИЕ ВЫПОЛНЕНО!**\n\n"
            f"📊 Результат: {formatted_result}\n\n"
            f"Отличная работа! Продолжайте в том же духе! 💪"
        )
        keyboard = [[InlineKeyboardButton("💪 К упражнениям", callback_data=SPORT_EXERCISES)]]
    else:
        text = "❌ Ошибка при сохранении результата"
        keyboard = [[InlineKeyboardButton("◀️ Назад", callback_data=SPORT_EXERCISES)]]

    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(text, reply_markup=reply_markup)

    return ConversationHandler.END


async def cancel_workout(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Отмена выполнения упражнения."""
    context.user_data.clear()
    await update.message.reply_text("❌ Выполнение отменено")
    return ConversationHandler.END

# ==================== ЧЕЛЛЕНДЖИ ====================

@log_call
async def challenges_list(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    try:
        await query.answer()
    except:
        pass

    challenges = get_challenges_by_status("active")
    if not challenges:
        keyboard = [[InlineKeyboardButton("◀️ В меню спорта", callback_data=SPORT_MENU)]]
        await query.edit_message_text("🏆 Активных челленджей пока нет.", reply_markup=InlineKeyboardMarkup(keyboard))
        return

    keyboard = []
    for ch in challenges:
        ch_id = ch[0]
        name = ch[1]
        description = ch[2]
        bonus = ch[9]
        start_date = ch[7]
        end_date = ch[8]

        start_date_str = start_date.strftime('%d.%m') if start_date else '?'
        end_date_str = end_date.strftime('%d.%m') if end_date else '?'

        # Компактная кнопка с названием и датами
        button_text = f"🏆 {name} | {start_date_str}-{end_date_str} | +{bonus}"
        keyboard.append([InlineKeyboardButton(button_text, callback_data=f"{SPORT_CHALLENGE_JOIN}_{ch_id}")])

    keyboard.append([InlineKeyboardButton("🏆 Топ челленджей", callback_data=SPORT_TOP_CHALLENGES)])
    keyboard.append([InlineKeyboardButton("◀️ В меню спорта", callback_data=SPORT_MENU)])
    await query.edit_message_text("🏆 **Челленджи**", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")

# ==================== КОМПЛЕКСЫ ====================

@log_call
async def complexes_list(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    try:
        await query.answer()
    except:
        pass

    complexes = get_all_complexes(active_only=True)
    if not complexes:
        keyboard = [[InlineKeyboardButton("◀️ В меню спорта", callback_data=SPORT_MENU)]]
        await query.edit_message_text("📦 Активных комплексов пока нет.", reply_markup=InlineKeyboardMarkup(keyboard))
        return

    keyboard = []

    # Словари для перевода
    type_icons = {
        'for_time': '⏱',
        'for_reps': '🔢'
    }
    difficulty_emojis = {
        'beginner': '🙂',
        'pro': '🤓'
    }

    for comp in complexes:
        comp_id = comp[0]
        name = comp[1]
        type_ = comp[3]  # type
        points = comp[4]
        difficulty = comp[5]  # difficulty

        type_icon = type_icons.get(type_, '❓')
        diff_emoji = difficulty_emojis.get(difficulty, '🙂')

        button_text = f"{diff_emoji} {name} | {type_icon} | ⭐{points}"
        keyboard.append([InlineKeyboardButton(button_text, callback_data=f"{SPORT_COMPLEX_START}_{comp_id}")])

    keyboard.append([InlineKeyboardButton("🏆 Топ комплексов", callback_data=SPORT_TOP_COMPLEXES)])
    keyboard.append([InlineKeyboardButton("◀️ В меню спорта", callback_data=SPORT_MENU)])
    await query.edit_message_text("📦 **Комплексы**", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")

# ==================== РЕЙТИНГИ ====================

@log_call
async def sport_ratings(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    try:
        await query.answer()
    except:
        pass

    keyboard = [
        [InlineKeyboardButton("💪 Топ тренировок", callback_data=SPORT_TOP_WORKOUTS)],
        [InlineKeyboardButton("🏆 Топ челленджей", callback_data=SPORT_TOP_CHALLENGES)],
        [InlineKeyboardButton("📦 Топ комплексов", callback_data=SPORT_TOP_COMPLEXES)],
        [InlineKeyboardButton("◀️ В меню спорта", callback_data=SPORT_MENU)]
    ]

    await query.edit_message_text("📊 **РЕЙТИНГИ**", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")

@log_call
async def sport_top_workouts(update: Update, context: ContextTypes.DEFAULT_TYPE):
    from database_postgres import get_top_workouts
    query = update.callback_query
    try:
        await query.answer()
    except:
        pass

    top = get_top_workouts(limit=10)
    if not top:
        keyboard = [[InlineKeyboardButton("◀️ В рейтинги", callback_data=SPORT_RATINGS)]]
        await query.edit_message_text("Пока нет данных.", reply_markup=InlineKeyboardMarkup(keyboard))
        return

    text = "💪 **ТОП-10 ТРЕНИРОВОК**\n\n"
    for i, u in enumerate(top, 1):
        username = f"@{u[1]}" if u[1] else ""
        text += f"{i}. {u[0]} {username} - {u[2]} тренировок\n"

    keyboard = [[InlineKeyboardButton("◀️ В рейтинги", callback_data=SPORT_RATINGS)]]
    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard))

@log_call
async def sport_top_challenges(update: Update, context: ContextTypes.DEFAULT_TYPE):
    from database_postgres import get_top_challenges
    query = update.callback_query
    try:
        await query.answer()
    except:
        pass

    top = get_top_challenges(limit=10)
    if not top:
        keyboard = [[InlineKeyboardButton("◀️ В рейтинги", callback_data=SPORT_RATINGS)]]
        await query.edit_message_text("Пока нет данных.", reply_markup=InlineKeyboardMarkup(keyboard))
        return

    text = "🏆 **ТОП-10 ЧЕЛЛЕНДЖЕЙ**\n\n"
    for i, u in enumerate(top, 1):
        username = f"@{u[1]}" if u[1] else ""
        text += f"{i}. {u[0]} {username} - {u[2]} челленджей\n"

    keyboard = [[InlineKeyboardButton("◀️ В рейтинги", callback_data=SPORT_RATINGS)]]
    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard))

@log_call
async def sport_top_complexes(update: Update, context: ContextTypes.DEFAULT_TYPE):
    from database_postgres import get_top_complexes
    query = update.callback_query
    try:
        await query.answer()
    except:
        pass

    top = get_top_complexes(limit=10)
    if not top:
        keyboard = [[InlineKeyboardButton("◀️ В рейтинги", callback_data=SPORT_RATINGS)]]
        await query.edit_message_text("Пока нет данных.", reply_markup=InlineKeyboardMarkup(keyboard))
        return

    text = "📦 **ТОП-10 КОМПЛЕКСОВ**\n\n"
    for i, u in enumerate(top, 1):
        username = f"@{u[1]}" if u[1] else ""
        text += f"{i}. {u[0]} {username} - {u[2]} комплексов\n"

    keyboard = [[InlineKeyboardButton("◀️ В рейтинги", callback_data=SPORT_RATINGS)]]
    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard))

@log_call
async def sport_my_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    try:
        await query.answer()
    except:
        pass

    user_id = update.effective_user.id
    workouts, challenges, complexes = get_user_stats(user_id)

    text = (
        f"📈 **МОЯ СТАТИСТИКА**\n\n"
        f"💪 Тренировок: {workouts}\n"
        f"🏆 Челленджей: {challenges}\n"
        f"📦 Комплексов: {complexes}\n\n"
        f"🔥 Продолжай в том же духе!"
    )

    keyboard = [[InlineKeyboardButton("◀️ В меню спорта", callback_data=SPORT_MENU)]]
    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")

# ==================== CONVERSATION HANDLER ДЛЯ УПРАЖНЕНИЙ ====================

workout_conversation = ConversationHandler(
    entry_points=[CallbackQueryHandler(start_workout, pattern='^sport_workout_start_')],
    states={
        WORKOUT_INPUT: [
            MessageHandler(filters.TEXT & ~filters.COMMAND, input_workout_result),
        ],
        WORKOUT_PROOF: [
            MessageHandler(filters.PHOTO | filters.VIDEO | filters.Document.ALL, upload_workout_proof),
            MessageHandler(filters.TEXT & ~filters.COMMAND, upload_workout_proof)  # Для текстовых ссылок
        ],
    },
    fallbacks=[
        CommandHandler('cancel', cancel_workout),
        CallbackQueryHandler(cancel_workout, pattern=f'^{SPORT_EXERCISES}$')
    ],
)

