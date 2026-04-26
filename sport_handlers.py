#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Обработчики модуля Спорт

import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler, MessageHandler, CommandHandler, CallbackQueryHandler, filters

from database_postgres import (
  get_exercises, get_exercise_by_id,
  get_all_complexes, get_complex_by_id, get_complex_exercises,
  get_challenges_by_status, join_challenge,
  get_user_stats, get_top_workouts, get_top_challenges, get_top_complexes,
  add_workout, get_complex_records, get_user_info,
  add_pvp_points_from_workout, get_pvp_setting
)

from debug_utils import debug_print, log_call
from formatters import format_number
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
SPORT_COMPLEX_DO = "sport_complex_do"
SPORT_COMPLEX_MODE_SEPARATE = "sport_complex_mode_separate"
SPORT_COMPLEX_MODE_SINGLE = "sport_complex_mode_single"
CALENDAR = "calendar"

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
        # Для остальных метрик применяем format_number чтобы убрать .0
        return format_number(value)

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
        [InlineKeyboardButton("📅 Календарь", callback_data=CALENDAR)],
        [InlineKeyboardButton("◀️ В главное меню", callback_data=SPORT_BACK_TO_MAIN)]
    ]

    text = "🏋️СПОРТ\n\nДобро пожаловать! Выбери раздел:"
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
        diff_emoji = "😊" if diff == "newbie" else "😎"

        button_text = f"{diff_emoji} {name} | {metric_icon} | ⭐{points}"
        keyboard.append([InlineKeyboardButton(button_text, callback_data=f"sport_exercise_view_{ex_id}")])

    keyboard.append([InlineKeyboardButton("🏆 Топ тренировок", callback_data=SPORT_TOP_WORKOUTS)])
    keyboard.append([InlineKeyboardButton("◀️ В меню спорта", callback_data=SPORT_MENU)])
    await query.edit_message_text("💪 Упражнения", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")

# ==================== ВЫПОЛНЕНИЕ УПРАЖНЕНИЙ ====================

@log_call
async def show_exercise_card(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показывает красивую карточку упражнения с кнопками 'Записать результат' и 'Отмена'."""
    query = update.callback_query
    await query.answer()

    # Формат: sport_exercise_view_{exercise_id}
    exercise_id = int(query.data.split("_")[-1])

    # Получаем информацию об упражнении
    exercise = get_exercise_by_id(exercise_id)
    if not exercise:
        await query.edit_message_text("❌ Упражнение не найдено")
        return

    ex_id, name, description, metric, points, week, difficulty = exercise

    metric_names = {'reps': 'Повторы', 'time': 'Время', 'weight': 'Вес (кг)', 'distance': 'Дистанция (км)'}
    metric_text = metric_names.get(metric, metric)

    difficulty_names = {'newbie': 'Новичок', 'beginner': 'Начинающий', 'intermediate': 'Средний', 'advanced': 'Продвинутый'}
    difficulty_text = difficulty_names.get(difficulty, difficulty)

    metric_icons = {'reps': '🔢', 'time': '⏱', 'weight': '🏋️', 'distance': '🏃'}
    metric_icon = metric_icons.get(metric, '📊')

    difficulty_emojis = {'newbie': '😊', 'beginner': '🌱', 'intermediate': '💪', 'advanced': '🔥'}
    difficulty_emoji = difficulty_emojis.get(difficulty, '💪')

    week_text = f"📅 Неделя {week}" if week else ""

    text = (
        f"🏋️ {name}\n\n"
        f"{difficulty_emoji} Сложность: {difficulty_text}\n"
        f"{metric_icon} Тип: {metric_text}\n"
        f"⭐ Очки: {format_number(points)}\n"
        f"{week_text}\n\n"
        f"📝 Описание:\n{description}\n\n"
    )

    keyboard = [
        [InlineKeyboardButton("✍️ Записать результат", callback_data=f"sport_exercise_do_{ex_id}")],
        [InlineKeyboardButton("❌ Отмена", callback_data=SPORT_EXERCISES)]
    ]

    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')


@log_call
async def start_workout(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показывает формат ввода и начинает ввод результата упражнения."""
    query = update.callback_query
    await query.answer()

    # Формат: sport_exercise_do_{exercise_id}
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
        f"🏋️ {name}\n\n"
        f"📊 Метрика: {metric_text}\n"
        f"📝 {description}\n\n"
        f"📝 Введите результат {input_format}\n"
        f"📌 Пример: {example}\n\n"
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
        f"✅ Результат: {format_number(result_value)}\n\n"
        f"📎 Отправьте ссылку на видео (YouTube, Яндекс.Диск) или прикрепите видео/фото!\n\n"
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
                "❌ Пожалуйста, отправьте ссылку на видео (начинается с http:// или https://)\n\n"
                "Или прикрепите видео/фото файл.",
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode='Markdown'
            )
            return WORKOUT_PROOF
    else:
        # Если нет ничего - требуем загрузить
        keyboard = [[InlineKeyboardButton("❌ Отмена", callback_data=SPORT_EXERCISES)]]
        await update.message.reply_text(
            "❌ Обязательно приложите фото, видео или ссылку на видео!\n\n"
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

        # Создаём callback для уведомлений о рекордах
        async def notify_record_callback(user_id, exercise_id, new_result, metric_type):
            try:
                from database_postgres import get_exercise_by_id, get_user_info
                exercise = get_exercise_by_id(exercise_id)
                exercise_name = exercise[1] if exercise else None
                user = get_user_info(user_id)
                user_name = user[1] if user else None

                await channel_notifications.notify_new_record(
                    context.bot,
                    user_id=user_id,
                    exercise_id=exercise_id,
                    new_result=new_result,
                    metric_type=metric_type,
                    user_name=user_name,
                    exercise_name=exercise_name
                )
            except Exception as e:
                logger.error(f"Ошибка в notify_record_callback: {e}")

        workout_id, achievements = add_workout(
            user_id=user_id,
            exercise_id=exercise_id,
            result_value=str(formatted_result),
            video_link=proof_link,
            metric=metric,
            notify_record_callback=notify_record_callback
        )

        # Начисляем PvP очки на основе настроек конвертации
        try:
            from database_postgres import get_exercise_by_id
            exercise_info = get_exercise_by_id(exercise_id)
            if exercise_info:
                base_points = exercise_info[4]  # points field
                pvp_points = add_pvp_points_from_workout(user_id, base_points, 'exercise')
                if pvp_points > 0:
                    print(f"DEBUG: Начислено {pvp_points} PvP Рейтинга за упражнение")
        except Exception as pvp_error:
            logger.error(f"Ошибка начисления PvP Рейтинга: {pvp_error}")

        success = True

        # Отправляем уведомление в канал о выполнении тренировки
        try:
            logger.info(f"🔔 Попытка отправить уведомление о тренировке для user_id={user_id}, exercise_id={exercise_id}")
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
                logger.info(f"📤 Вызов notify_workout_completion с данными: {workout_data}")
                await channel_notifications.notify_workout_completion(context.bot, workout_data)
            else:
                logger.warning(f"⚠️ Упражнение не найдено для exercise_id={exercise_id}")
        except Exception as e:
            logger.error(f"❌ Ошибка отправки уведомления о тренировке: {e}")
            import traceback
            traceback.print_exc()
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
            f"✅ УПРАЖНЕНИЕ ВЫПОЛНЕНО!\n\n"
            f"📊 Результат: {format_number(formatted_result)}\n\n"
            f"Отличная работа! Продолжайте в том же духе! 💪"
        )
        keyboard = [
            [
                InlineKeyboardButton("📢 Посмотреть в канале", url="https://t.me/MDFruN_Sports_Channel"),
                InlineKeyboardButton("💪 К упражнениям", callback_data=SPORT_EXERCISES)
            ]
        ]
    else:
        text = "❌ Ошибка при сохранении результата"
        keyboard = [[InlineKeyboardButton("◀️ Назад", callback_data=SPORT_EXERCISES)]]

    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(text, reply_markup=reply_markup)

    return ConversationHandler.END


async def cancel_workout(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Отмена выполнения упражнения."""
    context.user_data.clear()

    # Проверяем, есть ли callback_query (inline кнопка) или message (команда)
    if update.callback_query:
        await update.callback_query.answer()
        await update.callback_query.edit_message_text("❌ Выполнение отменено")
    elif update.message:
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
    await query.edit_message_text("🏆 Челленджи", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")

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
        'beginner': '😊',
        'pro': '😎'
    }

    for comp in complexes:
        comp_id = comp[0]
        name = comp[1]
        type_ = comp[3]  # type
        points = comp[4]
        difficulty = comp[5]  # difficulty

        type_icon = type_icons.get(type_, '❓')
        diff_emoji = difficulty_emojis.get(difficulty, '😊')

        button_text = f"{diff_emoji} {name} | {type_icon} | ⭐{points}"
        keyboard.append([InlineKeyboardButton(button_text, callback_data=f"{SPORT_COMPLEX_START}_{comp_id}")])

    keyboard.append([InlineKeyboardButton("🏆 Топ комплексов", callback_data=SPORT_TOP_COMPLEXES)])
    keyboard.append([InlineKeyboardButton("◀️ В меню спорта", callback_data=SPORT_MENU)])
    await query.edit_message_text("📦 Комплексы", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")


@log_call
async def show_complex_info(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показывает информацию о комплексе и позволяет его выполнить"""
    query = update.callback_query
    try:
        await query.answer()
    except:
        pass

    # Извлекаем complex_id из callback_data
    callback_data = query.data
    complex_id = int(callback_data.split(f"{SPORT_COMPLEX_START}_")[1])

    # Получаем данные комплекса
    complex_data = get_complex_by_id(complex_id)
    if not complex_data:
        keyboard = [[InlineKeyboardButton("◀️ В комплексы", callback_data=SPORT_COMPLEXES)]]
        await query.edit_message_text("❌ Комплекс не найден", reply_markup=InlineKeyboardMarkup(keyboard))
        return

    comp_id, name, description, comp_type, points, difficulty = complex_data

    # Получаем упражнения комплекса
    exercises = get_complex_exercises(complex_id)
    if not exercises:
        keyboard = [[InlineKeyboardButton("◀️ В комплексы", callback_data=SPORT_COMPLEXES)]]
        await query.edit_message_text("❌ Упражнения не найдены", reply_markup=InlineKeyboardMarkup(keyboard))
        return

    # Формируем красивую карточку комплекса
    difficulty_names = {
        'beginner': '😊 Новичок',
        'pro': '😎 Эксперт',
        'newbie': '🌱 Начинающий',
        'intermediate': '💪 Средний',
        'advanced': '🔥 Продвинутый'
    }
    difficulty_text = difficulty_names.get(difficulty, difficulty)

    metric_icons = {'reps': '🔢', 'time': '⏱', 'weight': '🏋️', 'distance': '🏃'}
    metric_names = {'reps': 'Повторы', 'time': 'Время (мин)', 'weight': 'Вес (кг)', 'distance': 'Дистанция (км)'}

    text = f"🏋️‍♂️ {name}\n\n"

    if description:
        text += f"📝 Описание:\n{description}\n\n"

    text += f"⭐ Очки: {format_number(points)}\n"
    text += f"🎯 Сложность: {difficulty_text}\n"
    text += f"📊 Упражнений: {len(exercises)}\n\n"

    text += "🏋️ Упражнения:\n\n"
    for i, ex in enumerate(exercises, 1):
        ex_id = ex[1] if len(ex) > 1 else 0
        ex_name = ex[2] if len(ex) > 2 else "Неизвестное"
        ex_desc = ex[3] if len(ex) > 3 else ""
        ex_metric = ex[4] if len(ex) > 4 else ""
        ex_reps = ex[5] if len(ex) > 5 else ""
        ex_points = ex[6] if len(ex) > 6 else 0

        metric_icon = metric_icons.get(ex_metric, '📊')
        metric_text = metric_names.get(ex_metric, ex_metric)

        text += f"{i}. **{ex_name}**\n"
        if ex_desc:
            # Обрезаем слишком длинное описание
            short_desc = ex_desc[:50] + "..." if len(ex_desc) > 50 else ex_desc
            text += f"   📝 {short_desc}\n"
        text += f"   📊 Метрика: {metric_text}"
        if ex_reps:
            text += f" | 🔢 Повторов: {format_number(ex_reps)}"
        text += f"\n   ⭐ Очки: {format_number(ex_points)}\n\n"

    keyboard = [
        [InlineKeyboardButton("💪 Начать выполнение", callback_data=f"{SPORT_COMPLEX_DO}_{complex_id}")],
        [InlineKeyboardButton("◀️ В комплексы", callback_data=SPORT_COMPLEXES)]
    ]

    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")


@log_call
async def start_complex_execution(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Начинает выполнение комплекса"""
    query = update.callback_query
    try:
        await query.answer()
    except:
        pass

    # Извлекаем complex_id из callback_data
    callback_data = query.data
    complex_id = int(callback_data.split(f"{SPORT_COMPLEX_DO}_")[1])

    # Получаем user_id
    user_id = update.effective_user.id

    # Получаем данные комплекса
    complex_data = get_complex_by_id(complex_id)
    if not complex_data:
        keyboard = [[InlineKeyboardButton("◀️ В комплексы", callback_data=SPORT_COMPLEXES)]]
        await query.edit_message_text("❌ Комплекс не найден", reply_markup=InlineKeyboardMarkup(keyboard))
        return

    comp_id, name, description, comp_type, points, difficulty = complex_data

    # Получаем упражнения комплекса
    exercises = get_complex_exercises(complex_id)
    if not exercises:
        keyboard = [[InlineKeyboardButton("◀️ В комплексы", callback_data=SPORT_COMPLEXES)]]
        await query.edit_message_text("❌ Упражнения не найдены", reply_markup=InlineKeyboardMarkup(keyboard))
        return

    # Сохраняем в контекст для выполнения
    context.user_data['current_complex'] = {
        'id': complex_id,
        'name': name,
        'points': points,  # Сохраняем базовые очки для PvP конвертации
        'exercises': exercises,
        'current_index': 0,
        'single_video_mode': False,
        'single_video_url': None
    }

    # Получаем рекорды комплекса для мотивации
    user_info = get_user_info(user_id)
    user_level = user_info[7] if user_info and len(user_info) > 7 else 'beginner'

    records = get_complex_records(complex_id, user_level, limit=3)

    # Предлагаем варианты выполнения
    text = f"🏋️ ВЫПОЛНЕНИЕ КОМПЛЕКСА\n\n"
    text += f"📦 {name}\n\n"
    text += f"Упражнений: {len(exercises)}\n\n"

    # Добавляем рекорды если есть
    if records:
        text += f"🏆 Топ-3 рекордов:\n"
        medals = ["🥇", "🥈", "🥉"]
        for i, record in enumerate(records[:3]):
            medal = medals[i] if i < len(medals) else "  "
            video_icon = " 📹" if record.get('video') else ""
            text += f"{medal} {record['display_name']} — {record['result']}{video_icon}\n"
        text += f"\n"

    text += f"Выберите удобный режим выполнения:"

    keyboard = [
        [InlineKeyboardButton("🎥 Отдельное видео для каждого упражнения", callback_data=f"{SPORT_COMPLEX_MODE_SEPARATE}_{complex_id}")],
        [InlineKeyboardButton("📹 Одно видео на весь комплекс", callback_data=f"{SPORT_COMPLEX_MODE_SINGLE}_{complex_id}")],
        [InlineKeyboardButton("❌ Отмена", callback_data=SPORT_COMPLEXES)]
    ]

    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")


@log_call
async def set_complex_mode(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Устанавливает режим выполнения комплекса"""
    query = update.callback_query
    try:
        await query.answer()
    except:
        pass

    callback_data = query.data

    if callback_data.startswith(SPORT_COMPLEX_MODE_SEPARATE):
        # Отдельные видео для каждого упражнения
        complex_data = context.user_data.get('current_complex')
        if complex_data:
            complex_data['single_video_mode'] = False
        await start_complex_exercise(update, context)

    elif callback_data.startswith(SPORT_COMPLEX_MODE_SINGLE):
        # Единое видео на все упражнения
        complex_data = context.user_data.get('current_complex')
        if complex_data:
            complex_data['single_video_mode'] = True
        await request_single_video(update, context)


async def request_single_video(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Запрашивает единое видео для всех упражнений комплекса"""
    query = update.callback_query if update.callback_query else update.message

    complex_data = context.user_data.get('current_complex')
    if not complex_data:
        text = "❌ Ошибка выполнения комплекса"
        keyboard = [[InlineKeyboardButton("◀️ В комплексы", callback_data=SPORT_COMPLEXES)]]
        if hasattr(query, 'edit_message_text'):
            await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard))
        else:
            await query.reply_text(text, reply_markup=InlineKeyboardMarkup(keyboard))
        return

    text = f"📹 ЕДИНОЕ ВИДЕО ДЛЯ ВСЕХ УПРАЖНЕНИЙ\n\n"
    text += f"📦 {complex_data['name']}\n\n"
    text += f"Отправьте ссылку на видео с выполнением всех упражнений комплекса.\n\n"
    text += f"После этого вы будете вводить количество или время для каждого упражнения."

    keyboard = [[InlineKeyboardButton("❌ Отмена", callback_data=SPORT_COMPLEXES)]]

    if hasattr(query, 'edit_message_text'):
        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")
    else:
        await query.reply_text(text, reply_markup=InlineKeyboardMarkup(keyboard))


async def start_complex_exercise(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показывает текущее упражнение комплекса для выполнения"""
    query = update.callback_query if update.callback_query else update.message
    user_id = update.effective_user.id

    complex_data = context.user_data.get('current_complex')
    if not complex_data:
        text = "❌ Ошибка выполнения комплекса"
        keyboard = [[InlineKeyboardButton("◀️ В комплексы", callback_data=SPORT_COMPLEXES)]]
        if hasattr(query, 'edit_message_text'):
            await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard))
        else:
            await query.reply_text(text, reply_markup=InlineKeyboardMarkup(keyboard))
        return

    exercises = complex_data['exercises']
    current_index = complex_data['current_index']

    if current_index >= len(exercises):
        # Все упражнения выполнены - завершаем комплекс
        await complete_complex(update, context)
        return

    # Текущее упражнение
    exercise = exercises[current_index]
    ex_id = exercise[1]  # exercise_id
    ex_name = exercise[2] if len(exercise) > 2 else "Упражнение"
    ex_desc = exercise[3] if len(exercise) > 3 else ""
    ex_metric_raw = exercise[4] if len(exercise) > 4 else ""
    ex_reps = exercise[5] if len(exercise) > 5 else ""

    # Перевод метрик
    metric_names = {
        'reps': 'Повторы',
        'time': 'Время (мин)',
        'weight': 'Вес (кг)',
        'distance': 'Дистанция (км)'
    }
    ex_metric = metric_names.get(ex_metric_raw, ex_metric_raw)

    # Сохраняем ID текущего упражнения
    context.user_data['current_exercise_id'] = ex_id

    # Определяем уровень пользователя
    user_info = get_user_info(user_id)
    user_level = user_info[7] if user_info and len(user_info) > 7 else 'beginner'

    # Получаем рекорды комплекса
    records = get_complex_records(complex_data['id'], user_level, limit=3)

    # Формируем текст
    text = f"🏋️ ВЫПОЛНЕНИЕ КОМПЛЕКСА\n\n"
    text += f"📦 {complex_data['name']}\n\n"
    text += f"🏋️ Упражнение {current_index + 1}/{len(exercises)}: **{ex_name}**\n\n"

    # Добавляем описание если есть
    if ex_desc:
        text += f"📝 {ex_desc}\n\n"

    if ex_metric:
        text += f"📊 Метрика: {ex_metric} | "
    if ex_reps:
        text += f"🔢 Повторов: {ex_reps}"

    text += f"\n\n"

    # Добавляем рекорды если есть
    if records:
        text += f"🏆 Рекорды ({user_level}):\n"
        medals = ["🥇", "🥈", "🥉"]
        for i, record in enumerate(records[:3]):
            medal = medals[i] if i < len(medals) else "  "
            video_icon = " 📹" if record.get('video') else ""
            text += f"{medal} {record['display_name']} — {record['result']}{video_icon}\n"
    else:
        text += f"🏆 Рекордов пока нет — стань первым!\n"

    text += f"\n"

    # Запрос в зависимости от метрики - ПЕРВЫМ ДЕЛАЕМ!
    if ex_metric_raw == 'time':
        text += f"⏰ Введите время, за которое вы сделали упражнение (формат: 23:15):\n\n"
    else:
        text += f"🔢 Введите количество, которое вы сделали:\n\n"

    # ПОТОМ просим видео
    text += f"📹 После этого пришлите ссылку на видео или фото для подтверждения."

    keyboard = [[InlineKeyboardButton("❌ Отмена", callback_data=SPORT_COMPLEXES)]]

    if hasattr(query, 'edit_message_text'):
        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")
    else:
        await query.reply_text(text, reply_markup=InlineKeyboardMarkup(keyboard))


async def complete_complex(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Завершает выполнение комплекса"""
    query = update.callback_query if update.callback_query else update.message
    user_id = update.effective_user.id

    complex_data = context.user_data.get('current_complex')
    if not complex_data:
        text = "❌ Ошибка завершения комплекса"
        keyboard = [[InlineKeyboardButton("◀️ В меню спорта", callback_data=SPORT_MENU)]]
        if hasattr(query, 'edit_message_text'):
            await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard))
        else:
            await query.reply_text(text, reply_markup=InlineKeyboardMarkup(keyboard))
        return

    # Добавляем запись о выполнении комплекса
    try:
        from database_postgres import add_workout
        workout_id, achievements = add_workout(
            user_id=user_id,
            complex_id=complex_data['id'],
            result_value="Выполнен",
            video_link="",
            user_level="beginner"
        )

        # Начисляем PvP очки на основе настроек конвертации
        try:
            base_points = complex_data.get('points', 0)
            pvp_points = add_pvp_points_from_workout(user_id, base_points, 'complex')
            if pvp_points > 0:
                print(f"DEBUG: Начислено {pvp_points} PvP очков за комплекс")
        except Exception as pvp_error:
            logger.error(f"Ошибка начисления PvP очков за комплекс: {pvp_error}")

        # Отправляем уведомление в канал
        try:
            logger.info(f"🔔 Попытка отправить уведомление о выполнении комплекса для user_id={user_id}")
            user = update.effective_user
            completion_data = {
                'user_id': user_id,
                'user_name': user.first_name or "Пользователь",
                'username': user.username,
                'complex_name': complex_data['name'],
                'video_link': ''
            }
            logger.info(f"📤 Вызов notify_complex_completion с данными: {completion_data}")
            import channel_notifications
            await channel_notifications.notify_complex_completion(context.bot, completion_data)
        except Exception as e:
            logger.error(f"❌ Ошибка отправки уведомления о комплексе: {e}")
            import traceback
            traceback.print_exc()

        # Получаем рекорды комплекса для статистики
        user_info = get_user_info(user_id)
        user_level = user_info[7] if user_info and len(user_info) > 7 else 'beginner'

        records = get_complex_records(complex_data['id'], user_level, limit=3)

        # Формируем красивую финальную карточку
        text = f"🏆 КОМПЛЕКС ВЫПОЛНЕН! 🏆\n\n"
        text += f"📦 {complex_data['name']}\n\n"

        # Добавляем рекорды если есть
        if records:
            text += f"🏆 Топ-3 рекордов:\n"
            medals = ["🥇", "🥈", "🥉"]
            for i, record in enumerate(records[:3]):
                medal = medals[i] if i < len(medals) else "  "
                video_icon = " 📹" if record.get('video') else ""
                text += f"{medal} {record['display_name']} — {record['result']}{video_icon}\n"
            text += f"\n"

        # Добавляем случайную мотивацию
        motivation_phrases = [
            "💪 Невероятный прогресс! Так держать!",
            "🚀 Ты становишься сильнее с каждым упражнением!",
            "🎯 Покорил новую высоту! Готов к новым вызовам?",
            "⚡ Отличная работа! Ты — настоящий чемпион!",
            "🔥 Ты молодец! Продолжай в том же духе!",
            "💫 Это было впечатляюще! Следующий уровень ждёт!",
            "🌟 Ты показал классный результат! Так держать!",
            "🏅 Ты заслужил медаль за это выполнение!"
        ]

        import random
        motivation = random.choice(motivation_phrases)
        text += f"{motivation}\n\n"

        text += f"📈 Продолжай улучшать свои результаты!\n"
        text += f"🎯 Следующий комплекс уже ждёт тебя."

        keyboard = [
            [
                InlineKeyboardButton("📢 Посмотреть в канале", url="https://t.me/MDFruN_Sports_Channel"),
                InlineKeyboardButton("🏠 В меню спорта", callback_data=SPORT_MENU)
            ]
        ]

        if hasattr(query, 'edit_message_text'):
            await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")
        else:
            await query.reply_text(text, reply_markup=InlineKeyboardMarkup(keyboard))

    except Exception as e:
        logger.error(f"Ошибка завершения комплекса: {e}")
        text = f"❌ Ошибка при сохранении комплекса"
        keyboard = [[InlineKeyboardButton("◀️ В меню спорта", callback_data=SPORT_MENU)]]
        if hasattr(query, 'edit_message_text'):
            await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard))
        else:
            await query.reply_text(text, reply_markup=InlineKeyboardMarkup(keyboard))

    finally:
        # Очищаем контекст
        context.user_data.pop('current_complex', None)
        context.user_data.pop('current_exercise_id', None)


async def handle_complex_exercise_result(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обрабатывает результат упражнения комплекса"""
    user_id = update.effective_user.id

    # Проверяем, выполняется ли комплекс
    complex_data = context.user_data.get('current_complex')
    if not complex_data:
        return False  # Не наш обработчик

    try:
        message = update.message
        result_value = message.text.strip()

        # Проверяем, является ли это ссылкой на видео
        if result_value.startswith(('http://', 'https://')):
            # Это ссылка на видео - пользователь сначала отправил видео
            # Сохраняем видео и просим ввести результат
            # Получаем метрику текущего упражнения для правильного текста
            exercises = complex_data['exercises']
            current_index = complex_data['current_index']
            exercise = exercises[current_index]
            ex_metric_raw = exercise[4] if len(exercise) > 4 else ""

            if ex_metric_raw == 'time':
                prompt_text = "Теперь введите время, за которое вы сделали упражнение."
            else:
                prompt_text = "Теперь введите количество, которое вы сделали."

            if complex_data.get('single_video_mode') and not complex_data.get('single_video_url'):
                # Режим единого видео
                complex_data['single_video_url'] = result_value
                await message.reply_text(f"✅ Видео принято! {prompt_text}")
                return True
            else:
                # Режим отдельных видео - сохраняем для текущего упражнения
                context.user_data[f'video_exercise_{current_index}'] = result_value
                await message.reply_text(f"✅ Видео/фото принято! {prompt_text}")
                return True

        # Текущее упражнение
        exercises = complex_data['exercises']
        current_index = complex_data['current_index']
        exercise = exercises[current_index]
        ex_id = exercise[1]  # exercise_id

        # Определяем видео ссылку
        if complex_data.get('single_video_mode'):
            video_link = complex_data.get('single_video_url', '')
        else:
            video_link = context.user_data.get(f'video_exercise_{current_index}', '')

        # Сохраняем результат упражнения
        from database_postgres import add_workout
        workout_id, achievements = add_workout(
            user_id=user_id,
            exercise_id=ex_id,
            result_value=result_value,
            video_link=video_link,
            user_level="beginner"
        )

        # Отправляем уведомление о выполнении упражнения в канал
        try:
            from database_postgres import get_exercise_by_id
            exercise_info = get_exercise_by_id(ex_id)
            if exercise_info:
                exercise_name = exercise_info[1]  # name
                user = update.effective_user
                workout_data = {
                    'user_id': user_id,
                    'user_name': user.first_name or "Пользователь",
                    'username': user.username,
                    'exercise_name': exercise_name,
                    'result_value': str(result_value),
                    'video_link': video_link if video_link and not video_link.startswith(('photo_', 'video_', 'document_')) else ''
                }
                logger.info(f"📤 Вызов notify_workout_completion для упражнения комплекса: {workout_data}")
                import channel_notifications
                await channel_notifications.notify_workout_completion(context.bot, workout_data)
        except Exception as e:
            logger.error(f"❌ Ошибка отправки уведомления об упражнении комплекса: {e}")
            import traceback
            traceback.print_exc()

        # Очищаем временное хранение видео для этого упражнения
        context.user_data.pop(f'video_exercise_{current_index}', None)

        # Переходим к следующему упражнению
        complex_data['current_index'] += 1

        if complex_data['current_index'] >= len(exercises):
            # Все упражнения выполнены
            await complete_complex(update, context)
        else:
            # Показываем следующее упражнение
            await start_complex_exercise(update, context)

        return True  # Мы обработали это сообщение

    except Exception as e:
        logger.error(f"Ошибка обработки упражнения комплекса: {e}")
        return False


async def handle_complex_media(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обрабатывает медиа файлы для упражнений комплекса"""
    user_id = update.effective_user.id

    # Проверяем, выполняется ли комплекс
    complex_data = context.user_data.get('current_complex')
    if not complex_data:
        return False  # Не наш обработчик

    # Если режим единого видео, обрабатываем в handle_complex_exercise_result
    if complex_data.get('single_video_mode') and not complex_data.get('single_video_url'):
        return False  # Пусть обработает текстовая функция

    try:
        message = update.message
        video_link = await extract_video_link(message)

        if not video_link:
            await message.reply_text("❌ Не удалось получить ссылку на медиа файл")
            return True

        # Сохраняем видео для текущего упражнения
        current_index = complex_data['current_index']
        context.user_data[f'video_exercise_{current_index}'] = video_link

        # Получаем метрику для правильного текста
        exercises = complex_data['exercises']
        exercise = exercises[current_index]
        ex_metric_raw = exercise[4] if len(exercise) > 4 else ""

        if ex_metric_raw == 'time':
            prompt_text = "Теперь введите время, за которое вы сделали упражнение."
        else:
            prompt_text = "Теперь введите количество, которое вы сделали."

        await message.reply_text(f"✅ Видео/фото принято! {prompt_text}")
        return True

    except Exception as e:
        logger.error(f"Ошибка обработки медиа комплекса: {e}")
        return False


async def extract_video_link(message):
    """Извлекает ссылку на видео из сообщения"""
    if message.video:
        video = message.video
        file = await video.get_file()
        return file.file_path
    elif message.photo:
        photo = message.photo[-1]
        file = await photo.get_file()
        return file.file_path
    elif message.document:
        document = message.document
        file = await document.get_file()
        return file.file_path
    elif message.text and message.text.startswith(('http://', 'https://')):
        return message.text.strip()
    else:
        return None


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

    await query.edit_message_text("📊 РЕЙТИНГИ", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")

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

    text = "💪 ТОП-10 ТРЕНИРОВОК\n\n"
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

    text = "🏆 ТОП-10 ЧЕЛЛЕНДЖЕЙ\n\n"
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

    text = "📦 ТОП-10 КОМПЛЕКСОВ\n\n"
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
        f"📈 МОЯ СТАТИСТИКА\n\n"
        f"💪 Тренировок: {workouts}\n"
        f"🏆 Челленджей: {challenges}\n"
        f"📦 Комплексов: {complexes}\n\n"
        f"🔥 Продолжай в том же духе!"
    )

    keyboard = [[InlineKeyboardButton("◀️ В меню спорта", callback_data=SPORT_MENU)]]
    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")

# ==================== CONVERSATION HANDLER ДЛЯ УПРАЖНЕНИЙ ====================

workout_conversation = ConversationHandler(
    entry_points=[
        CallbackQueryHandler(start_workout, pattern='^sport_workout_start_'),
        CallbackQueryHandler(start_workout, pattern='^sport_exercise_do_')
    ],
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

