# -*- coding: utf-8 -*-
"""
AI-функции для фитнес-бота
Умный тренер, анализ фото, рекомендации, анализ прогресса
"""
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, CallbackQueryHandler, MessageHandler, CommandHandler, filters, ConversationHandler
from ai_coach import ai_coach
from database_postgres import get_user_info, get_user_workouts

logger = logging.getLogger(__name__)

# Константы для состояний
ASK_QUESTION = 1
WAITING_PHOTO = 2

# ==================== ГЛАВНОЕ МЕНЮ AI ====================

AI_MENU = "ai_menu"
AI_ADVICE = "ai_advice"
AI_PHOTO = "ai_photo"
AI_RECOMMEND = "ai_recommend"
AI_PROGRESS = "ai_progress"


async def ai_menu_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показывает меню AI-функций"""
    query = update.callback_query if update.callback_query else update.message

    # Проверяем доступность AI
    available = ai_coach.is_available()

    text = "🤖 **AI-ТРЕНЕР**\n\n"
    text += "Умные функции для твоих тренировок:\n\n"

    if available['yandex']:
        text += "✅ Умный тренер (YandexGPT)\n"
    else:
        text += "❌ Умный тренер (не доступен)\n"

    if available['gemini']:
        text += "✅ Анализ фото (Gemini)\n"
    else:
        text += "❌ Анализ фото (не доступен)\n"

    if available['groq']:
        text += "✅ Мгновенные советы (Groq)\n"
    else:
        text += "❌ Мгновенные советы (не доступен)\n"

    if available['groq']:
        text += "✅ Анализ прогресса (Groq)\n"
    else:
        text += "❌ Анализ прогресса (не доступен)\n"

    keyboard = [
        [InlineKeyboardButton("💬 Спросить тренера", callback_data=AI_ADVICE)],
        [InlineKeyboardButton("📸 Анализ фото", callback_data=AI_PHOTO)],
        [InlineKeyboardButton("⚡ Быстрый совет", callback_data=AI_RECOMMEND)],
        [InlineKeyboardButton("📊 Анализ прогресса", callback_data=AI_PROGRESS)],
        [InlineKeyboardButton("◀️ В меню", callback_data="sport")]
    ]

    reply_markup = InlineKeyboardMarkup(keyboard)

    try:
        if query.message:
            await query.edit_message_text(text, reply_markup=reply_markup, parse_mode="Markdown")
        else:
            await update.message.reply_text(text, reply_markup=reply_markup, parse_mode="Markdown")
    except:
        if query.message:
            await query.edit_message_text(text, reply_markup=reply_markup)
        else:
            await update.message.reply_text(text, reply_markup=reply_markup)


# ==================== УМНЫЙ ТРЕНЕР (YANDEX) ====================

async def ai_advice_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Начинает диалог с умным тренером"""
    query = update.callback_query
    await query.answer()

    if not ai_coach.is_available()['yandex']:
        await query.edit_message_text("❌ YandexGPT не подключён. Добавьте YANDEX_API_KEY.")
        return ConversationHandler.END

    keyboard = [[InlineKeyboardButton("◀️ Отмена", callback_data=AI_MENU)]]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await query.edit_message_text(
        "💬 **СПРОСИ ТРЕНЕРА**\n\n"
        "Задай вопрос о тренировках, питании или мотивации!\n\n"
        "Например:\n"
        '• "Как улучшить результаты в отжиманиях?"\n'
        '• "Как восстановиться после тренировки?"\n'
        '• "Как не бросить тренировки?"\n\n'
        "Введи свой вопрос:",
        reply_markup=reply_markup,
        parse_mode="Markdown"
    )

    return ASK_QUESTION


async def ai_advice_receive(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Получает вопрос и отправляет ответ"""
    question = update.message.text

    if not question:
        await update.message.reply_text("❌ Введите вопрос текстом")
        return ASK_QUESTION

    # Отправляем "печатает..."
    await update.message.chat.send_action("typing")

    try:
        # Получаем данные пользователя
        user_id = update.effective_user.id
        user_info = get_user_info(user_id)

        if user_info:
            user_data = {
                'first_name': user_info[3] or update.effective_user.first_name,
                'user_group': user_info[7] if len(user_info) > 7 else 'newbie',
                'score': user_info[6] if len(user_info) > 6 else 0
            }
        else:
            user_data = {
                'first_name': update.effective_user.first_name,
                'user_group': 'newbie',
                'score': 0
            }

        # Получаем совет от AI
        advice = await ai_coach.get_training_advice(user_data, question)

        # Отправляем ответ
        keyboard = [[InlineKeyboardButton("◀️ В AI меню", callback_data=AI_MENU)]]
        reply_markup = InlineKeyboardMarkup(keyboard)

        await update.message.reply_text(
            f"💬 **СОВЕТ ТРЕНЕРА**\n\n{advice}",
            reply_markup=reply_markup,
            parse_mode="Markdown"
        )

    except Exception as e:
        logger.error(f"Ошибка получения совета: {e}")
        await update.message.reply_text(
            "❌ Произошла ошибка. Попробуйте позже."
        )

    return ConversationHandler.END


async def ai_advice_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Отменяет диалог"""
    await ai_menu_command(update, context)
    return ConversationHandler.END


# ==================== АНАЛИЗ ФОТО (GEMINI) ====================

async def ai_photo_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Начинает анализ фото"""
    query = update.callback_query
    await query.answer()

    if not ai_coach.is_available()['gemini']:
        await query.edit_message_text("❌ Gemini не подключён. Добавьте GEMINI_API_KEY.")
        return ConversationHandler.END

    keyboard = [[InlineKeyboardButton("◀️ Отмена", callback_data=AI_MENU)]]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await query.edit_message_text(
        "📸 **АНАЛИЗ ФОТО**\n\n"
        "Отправь фото с выполнением упражнения!\n\n"
        "Я проанализирую:\n"
        "✅ Правильность техники\n"
        "💡 Конкретные советы\n"
        "⭐ Оценку от 1 до 10\n\n"
        "Жду фото...",
        reply_markup=reply_markup,
        parse_mode="Markdown"
    )

    return WAITING_PHOTO


async def ai_photo_receive(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Получает фото и анализирует"""
    message = update.message

    if not message.photo:
        await message.reply_text("❌ Отправьте фото, а не текст или файл")
        return WAITING_PHOTO

    # Отправляем "анализирую..."
    await message.chat.send_action("typing")

    try:
        # Получаем самое большое фото
        photo = message.photo[-1]
        file = await photo.get_file()

        # Скачиваем фото
        photo_data = await file.download_as_bytearray()

        # Определяем название упражнения (из контекста или по умолчанию)
        exercise_name = context.user_data.get('last_exercise', 'упражнение')

        # Анализируем фото
        analysis = await ai_coach.analyze_workout_photo(photo_data, exercise_name)

        # Отправляем результат
        keyboard = [[InlineKeyboardButton("◀️ В AI меню", callback_data=AI_MENU)]]
        reply_markup = InlineKeyboardMarkup(keyboard)

        await message.reply_text(
            f"📸 **АНАЛИЗ ФОТО**\n\n{analysis}",
            reply_markup=reply_markup,
            parse_mode="Markdown"
        )

    except Exception as e:
        logger.error(f"Ошибка анализа фото: {e}")
        await message.reply_text(
            "❌ Не удалось проанализировать фото. Попробуйте позже."
        )

    return ConversationHandler.END


async def ai_photo_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Отменяет анализ"""
    await ai_menu_command(update, context)
    return ConversationHandler.END


# ==================== БЫСТРЫЙ СОВЕТ (GROQ) ====================

async def ai_recommend(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Даёт быструю рекомендацию"""
    query = update.callback_query
    await query.answer()

    if not ai_coach.is_available()['groq']:
        await query.edit_message_text("❌ Groq не подключён. Добавьте GROQ_API_KEY.")
        return

    # Отправляем "генерирую..."
    await query.message.chat.send_action("typing")

    try:
        # Получаем данные пользователя
        user_id = update.effective_user.id
        user_info = get_user_info(user_id)

        if user_info:
            user_data = {
                'first_name': user_info[3] or update.effective_user.first_name,
                'user_group': user_info[7] if len(user_info) > 7 else 'newbie',
                'score': user_info[6] if len(user_info) > 6 else 0
            }
        else:
            user_data = {
                'first_name': update.effective_user.first_name,
                'user_group': 'newbie',
                'score': 0
            }

        # Получаем последнюю тренировку
        workouts = get_user_workouts(user_id, limit=1)

        if workouts:
            last_workout = {
                'last_exercise': workouts[0].get('exercise_name', 'Неизвестно'),
                'streak': len(workouts)  # Упрощённо
            }
        else:
            last_workout = {
                'last_exercise': 'Нет тренировок',
                'streak': 0
            }

        # Получаем рекомендацию
        recommendation = await ai_coach.get_quick_recommendation(user_data, last_workout)

        # Отправляем результат
        keyboard = [[InlineKeyboardButton("◀️ В AI меню", callback_data=AI_MENU)]]
        reply_markup = InlineKeyboardMarkup(keyboard)

        await query.edit_message_text(
            f"⚡ **БЫСТРЫЙ СОВЕТ**\n\n{recommendation}",
            reply_markup=reply_markup,
            parse_mode="Markdown"
        )

    except Exception as e:
        logger.error(f"Ошибка получения рекомендации: {e}")
        await query.edit_message_text(
            "❌ Не удалось получить рекомендацию. Попробуйте позже."
        )


# ==================== АНАЛИЗ ПРОГРЕССА (DEEPSEEK) ====================

async def ai_progress(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Анализирует прогресс пользователя через Groq"""
    query = update.callback_query
    await query.answer()

    if not ai_coach.is_available()['groq']:
        await query.edit_message_text("❌ Groq не подключён. Добавьте GROQ_API_KEY.")
        return

    # Отправляем "анализирую..."
    await query.message.chat.send_action("typing")

    try:
        # Получаем данные пользователя
        user_id = update.effective_user.id
        user_info = get_user_info(user_id)

        if user_info:
            user_data = {
                'first_name': user_info[3] or update.effective_user.first_name,
                'user_group': user_info[7] if len(user_info) > 7 else 'newbie',
                'score': user_info[6] if len(user_info) > 6 else 0
            }
        else:
            user_data = {
                'first_name': update.effective_user.first_name,
                'user_group': 'newbie',
                'score': 0
            }

        # Получаем историю тренировок
        workouts = get_user_workouts(user_id, limit=50)

        # Формируем историю для анализа
        workout_history = []
        for workout in workouts:
            workout_history.append({
                'date': workout.get('date', ''),
                'exercise': workout.get('exercise_name', ''),
                'result': workout.get('result_value', '')
            })

        # Анализируем прогресс
        analysis = await ai_coach.analyze_user_progress(user_data, workout_history)

        # Отправляем результат
        keyboard = [[InlineKeyboardButton("◀️ В AI меню", callback_data=AI_MENU)]]
        reply_markup = InlineKeyboardMarkup(keyboard)

        await query.edit_message_text(
            f"📊 **АНАЛИЗ ПРОГРЕССА**\n\n{analysis}",
            reply_markup=reply_markup,
            parse_mode="Markdown"
        )

    except Exception as e:
        logger.error(f"Ошибка анализа прогресса: {e}")
        await query.edit_message_text(
            "❌ Не удалось проанализировать прогресс. Попробуйте позже."
        )


# =================️ CONVERSATION HANDLERS ====================

# ConversationHandler для вопросов тренеру
ai_advice_conversation = ConversationHandler(
    entry_points=[CallbackQueryHandler(ai_advice_start, pattern=f"^{AI_ADVICE}$")],
    states={
        ASK_QUESTION: [MessageHandler(filters.TEXT & ~filters.COMMAND, ai_advice_receive)],
    },
    fallbacks=[CallbackQueryHandler(ai_advice_cancel, pattern=f"^{AI_MENU}$")],
)

# ConversationHandler для анализа фото
ai_photo_conversation = ConversationHandler(
    entry_points=[CallbackQueryHandler(ai_photo_start, pattern=f"^{AI_PHOTO}$")],
    states={
        WAITING_PHOTO: [MessageHandler(filters.PHOTO, ai_photo_receive)],
    },
    fallbacks=[CallbackQueryHandler(ai_photo_cancel, pattern=f"^{AI_MENU}$")],
)
