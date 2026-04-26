"""
Обработчики для спортивных челленджей
Пользовательская часть: просмотр, присоединение, выполнение упражнений
"""
import logging
from datetime import date
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, CallbackQueryHandler, MessageHandler, CommandHandler, filters, ConversationHandler
from debug_utils import debug_print, log_call
from database_postgres import (
    get_active_challenges, get_user_challenges, get_challenge_exercises,
    get_user_challenge_progress, join_challenge, complete_challenge_exercise,
    get_exercise_by_id, get_challenge_by_id
)
import channel_notifications
from formatters import format_number

logger = logging.getLogger(__name__)

# Вспомогательные функции
def format_exercise_result(value, metric):
    """Форматирует результат упражнения для отображения."""
    if metric == 'time':
        # Конвертируем секунды в формат мм:сс
        minutes = int(value) // 60
        seconds = int(value) % 60
        return f"{minutes:02d}:{seconds:02d}"
    else:
        # Для остальных метрик просто возвращаем значение
        return str(value)

# Константы
CHALLENGE_EXERCISE_INPUT = 40  # Ввод данных упражнения
CHALLENGE_PROOF_UPLOAD = 41    # Загрузка доказывания

# ==================== ПОКАЗ АКТИВНЫХ ЧЕЛЛЕНДЖЕЙ ====================

@log_call
async def challenges_list(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показывает список активных челленджей."""
    query = update.callback_query
    await query.answer()

    challenges = get_active_challenges()

    if not challenges:
        text = (
            "🏆 ЧЕЛЛЕНДЖИ\n\n"
            "❌ Активных челленджей пока нет\n\n"
            "Ждите интересные соревнования!"
        )
        keyboard = [[InlineKeyboardButton("◀️ Назад", callback_data="sport_back")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(text, reply_markup=reply_markup, parse_mode='Markdown')
        return

    text = "🏆 АКТИВНЫЕ ЧЕЛЛЕНДЖИ\n\nВыберите челлендж:"

    keyboard = []
    for ch in challenges[:7]:  # Показываем первые 7
        ch_id, name, description, metric, target_value, start_date, end_date, bonus_points, participants = ch

        start_date_str = start_date.strftime('%d.%m') if start_date else '?'
        end_date_str = end_date.strftime('%d.%m') if end_date else '?'

        button_text = f"🏆 {name} | {start_date_str}-{end_date_str} | 👥{participants}"
        keyboard.append([InlineKeyboardButton(button_text, callback_data=f"sport_challenge_{ch_id}")])

    keyboard.append([InlineKeyboardButton("📋 Мои челленджи", callback_data="sport_my_challenges")])
    keyboard.append([InlineKeyboardButton("◀️ Назад", callback_data="sport_back")])

    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.edit_message_text(text, reply_markup=reply_markup, parse_mode='Markdown')


@log_call
async def my_challenges_list(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показывает челленджи пользователя."""
    query = update.callback_query
    await query.answer()

    user_id = update.effective_user.id
    challenges = get_user_challenges(user_id)

    if not challenges:
        text = (
            "🏆 МОИ ЧЕЛЛЕНДЖИ\n\n"
            "❌ Вы еще не участвуете в челленджах\n\n"
            "Присоединяйтесь к активным челленджам!"
        )
        keyboard = [[InlineKeyboardButton("◀️ Назад", callback_data="sport_challenges")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(text, reply_markup=reply_markup, parse_mode='Markdown')
        return

    text = "🏆 МОИ ЧЕЛЛЕНДЖИ\n\nВыберите челлендж:"

    keyboard = []
    for ch in challenges:
        ch_id, name, description, metric, target_value, start_date, end_date, bonus_points, completed, joined_at = ch

        start_date_str = start_date.strftime('%d.%m') if start_date else '?'
        end_date_str = end_date.strftime('%d.%m') if end_date else '?'

        status_emoji = {True: '✅', False: '🔥'}
        status_text = status_emoji.get(completed, '❓')

        button_text = f"{status_text} {name} | {start_date_str}-{end_date_str}"
        keyboard.append([InlineKeyboardButton(button_text, callback_data=f"sport_my_challenge_{ch_id}")])

    keyboard.append([InlineKeyboardButton("◀️ Назад", callback_data="sport_challenges")])

    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.edit_message_text(text, reply_markup=reply_markup, parse_mode='Markdown')


# ==================== ПРОСМОТР ЧЕЛЛЕНДЖА ====================

@log_call
async def show_challenge_info(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показывает информацию о челлендже."""
    query = update.callback_query
    await query.answer()

    challenge_id = int(query.data.split("_")[-1])
    user_id = update.effective_user.id

    from database_postgres import get_challenge_by_id
    challenge = get_challenge_by_id(challenge_id)

    if not challenge:
        text = "❌ Челлендж не найден"
        keyboard = [[InlineKeyboardButton("◀️ К списку", callback_data="sport_challenges")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(text, reply_markup=reply_markup)
        return

    ch_id, name, description, target_type, target_id, metric, target_value, start_date, end_date, bonus_points, entry_fee, prize_pool, is_coin = challenge

    # Проверяем участие пользователя
    user_challenges = get_user_challenges(user_id)
    is_joined = any(ch[0] == challenge_id for ch in user_challenges)

    # Определяем статус челленджа
    today = date.today()
    if start_date and end_date:
        if start_date <= today <= end_date:
            status_text = '🔥 Активен'
        elif end_date < today:
            status_text = '❌ Завершен'
        else:
            status_text = '⏳ Скоро начнется'
    else:
        status_text = '❓'

    start_date_str = start_date.strftime('%d.%m.%Y') if start_date else '?'
    end_date_str = end_date.strftime('%d.%m.%Y') if end_date else '?'

    metric_names = {'reps': 'Повторы', 'time': 'Время (мин)', 'weight': 'Вес (кг)', 'distance': 'Дистанция (км)'}
    metric_text = metric_names.get(metric, metric)

    # Для пользователей показываем участие
    # Извлекаем статус завершения из user_challenges
    user_challenge = next((ch for ch in user_challenges if ch[0] == challenge_id), None)
    if user_challenge and user_challenge[8]:  # completed
        status_text = '✅ Вы участвуете'
    elif is_joined:
        status_text = '🔥 Активен'

    text = (
        f"🏆 {name}\n\n"
        f"📝 {description}\n\n"
        f"📊 Цель: {format_number(target_value)} {metric_text}\n"
        f"📅 Период: {start_date_str} - {end_date_str}\n"
        f"⭐ Бонус: {bonus_points} очков\n"
        f"📈 Статус: {status_text}\n"
    )

    # Кнопки в зависимости от участия
    if is_joined:
        keyboard = [
            [InlineKeyboardButton("🏋️ Упражнения", callback_data=f"sport_challenge_exercises_{challenge_id}")],
            [InlineKeyboardButton("📊 Прогресс", callback_data=f"sport_challenge_progress_{challenge_id}")],
            [InlineKeyboardButton("◀️ К списку", callback_data="sport_challenges")]
        ]
    else:
        keyboard = [
            [InlineKeyboardButton("✅ Присоединиться", callback_data=f"sport_challenge_join_{challenge_id}")],
            [InlineKeyboardButton("◀️ К списку", callback_data="sport_challenges")]
        ]

    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.edit_message_text(text, reply_markup=reply_markup, parse_mode='Markdown')


# ==================== УПРАЖНЕНИЯ В ЧЕЛЛЕНДЖЕ ====================

@log_call
async def show_challenge_exercises(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показывает упражнения челленджа с прогрессом."""
    query = update.callback_query
    await query.answer()

    challenge_id = int(query.data.split("_")[-1])
    user_id = update.effective_user.id

    exercises = get_challenge_exercises(challenge_id)
    progress = get_user_challenge_progress(user_id, challenge_id)

    if not exercises:
        text = "❌ Упражнений нет"
        keyboard = [[InlineKeyboardButton("◀️ Назад", callback_data=f"sport_my_challenge_{challenge_id}")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(text, reply_markup=reply_markup)
        return

    # Создаем словарь прогресса для быстрого доступа
    progress_dict = {p[0]: p for p in progress}

    from database_postgres import get_challenge_by_id
    challenge = get_challenge_by_id(challenge_id)
    challenge_name = challenge[1] if challenge else "Челлендж"

    # Считаем выполненные упражнения
    completed_count = sum(1 for p in progress if p[1])  # p[1] = completed
    total_count = len(exercises)

    text = (
        f"🏆 {challenge_name}\n\n"
        f"🏋️ УПРАЖНЕНИЯ ({completed_count}/{total_count} выполнено)\n\n"
    )

    keyboard = []
    for ex in exercises:
        ex_id, name, description, metric, points, week, difficulty = ex

        # Проверяем статус упражнения
        if ex_id in progress_dict and progress_dict[ex_id][1]:  # completed
            result_value = progress_dict[ex_id][2]  # result_value
            has_proof = progress_dict[ex_id][3] is not None  # proof_link
            checkbox = '✅'
            formatted_result = format_exercise_result(result_value, metric)
            status_text = f" (выполнил: {formatted_result})"
            if has_proof:
                status_text += " 📎"
        else:
            checkbox = '⬜'
            status_text = ""

        button_text = f"{checkbox} {name}{status_text}"
        keyboard.append([InlineKeyboardButton(button_text, callback_data=f"sport_challenge_do_exercise_{challenge_id}_{ex_id}")])

    keyboard.append([InlineKeyboardButton("◀️ Назад", callback_data=f"sport_my_challenge_{challenge_id}")])

    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.edit_message_text(text, reply_markup=reply_markup, parse_mode='Markdown')


# ==================== ВЫПОЛНЕНИЕ УПРАЖНЕНИЯ ====================

@log_call
async def start_challenge_exercise(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Начинает выполнение упражнения из челленджа."""
    query = update.callback_query
    await query.answer()

    callback_data = query.data
    parts = callback_data.split("_")
    # Формат: sport_challenge_do_exercise_{challenge_id}_{exercise_id}
    challenge_id = int(parts[-2])
    exercise_id = int(parts[-1])

    # Сохраняем данные для следующего шага
    context.user_data['current_challenge_id'] = challenge_id
    context.user_data['current_exercise_id'] = exercise_id

    # Получаем информацию об упражнении
    exercise = get_exercise_by_id(exercise_id)
    if not exercise:
        await query.edit_message_text("❌ Упражнение не найдено")
        return

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
        f"Введите результат {input_format}\n"
        f"📌 Пример: {example}\n\n"
        f"📹 Нам нужно убедиться в правильности выполнения упражнения. Пришлите ссылку на видео или фото."
    )

    keyboard = [[InlineKeyboardButton("❌ Отмена", callback_data=f"sport_my_challenge_{challenge_id}")]]
    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')

    return CHALLENGE_EXERCISE_INPUT


@log_call
async def input_exercise_result(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обрабатывает ввод результата упражнения."""
    if not update.message or not update.message.text:
        return CHALLENGE_EXERCISE_INPUT

    result_text = update.message.text.strip()
    exercise_id = context.user_data.get('current_exercise_id')

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
                        return CHALLENGE_EXERCISE_INPUT
                    result_value = minutes * 60 + seconds  # Конвертируем в секунды
                    if result_value <= 0:
                        await update.message.reply_text("❌ Время должно быть положительным")
                        return CHALLENGE_EXERCISE_INPUT
                else:
                    await update.message.reply_text("❌ Неверный формат. Используйте мм:сс (например: 23:15)")
                    return CHALLENGE_EXERCISE_INPUT
            else:
                await update.message.reply_text("❌ Для времени используйте формат мм:сс (например: 23:15)")
                return CHALLENGE_EXERCISE_INPUT
        else:
            # Для остальных метрик - просто число
            result_value = float(result_text)
            if result_value <= 0:
                await update.message.reply_text("❌ Значение должно быть положительным числом")
                return CHALLENGE_EXERCISE_INPUT
    except ValueError:
        if metric == 'time':
            await update.message.reply_text("❌ Неверный формат. Используйте мм:сс (например: 23:15)")
        else:
            await update.message.reply_text("❌ Введите число")
        return CHALLENGE_EXERCISE_INPUT

    context.user_data['exercise_result'] = result_value
    context.user_data['exercise_metric'] = metric  # Сохраняем метрику для форматирования

    keyboard = [[InlineKeyboardButton("❌ Отмена", callback_data="sport_cancel")]]
    await update.message.reply_text(
        f"✅ Результат: {result_value}\n\n"
        f"📎 Отправьте ссылку на видео (YouTube, Vimeo) или прикрепите видео/фото!\n\n"
        f"⚠️ Без доказательства упражнение не будет засчитано.",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode='Markdown'
    )

    return CHALLENGE_PROOF_UPLOAD


@log_call
async def upload_exercise_proof(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обрабатывает загрузку доказательства упражнения."""
    user_id = update.effective_user.id
    challenge_id = context.user_data.get('current_challenge_id')
    exercise_id = context.user_data.get('current_exercise_id')
    result_value = context.user_data.get('exercise_result')

    print(f"🔥 DEBUG upload_exercise_proof: user_id={user_id}, challenge_id={challenge_id}, exercise_id={exercise_id}, result_value={result_value}")

    if not all([challenge_id, exercise_id, result_value]):
        await update.message.reply_text("❌ Ошибка: данные утеряны. Начните заново.")
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
            keyboard = [[InlineKeyboardButton("❌ Отмена", callback_data="sport_cancel")]]
            await update.message.reply_text(
                "❌ Пожалуйста, отправьте ссылку на видео (начинается с http:// или https://)\n\n"
                "Или прикрепите видео/фото файл.",
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode='Markdown'
            )
            return CHALLENGE_PROOF_UPLOAD
    else:
        # Если нет ничего - требуем загрузить
        keyboard = [[InlineKeyboardButton("❌ Отмена", callback_data="sport_cancel")]]
        await update.message.reply_text(
            "❌ Обязательно приложите фото, видео или ссылку на видео!\n\n"
            "Без доказательства упражнение не будет засчитано.",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='Markdown'
        )
        return CHALLENGE_PROOF_UPLOAD

    print(f"🔥 DEBUG Доказательство получено: proof_link={proof_link}")

    # Сохраняем результат
    success, status = complete_challenge_exercise(user_id, challenge_id, exercise_id, result_value, proof_link)
    print(f"🔥 DEBUG Результат сохранения: success={success}, status={status}")

    # Отправляем уведомление в канал о выполнении челленджа
    if success and status == 'completed':
        try:
            challenge = get_challenge_by_id(challenge_id)
            if challenge:
                challenge_name = challenge[1]  # name
                user = update.effective_user
                completion_data = {
                    'user_id': user_id,
                    'user_name': user.first_name or "Пользователь",
                    'username': user.username,
                    'challenge_name': challenge_name,
                    'result_value': '',  # Challenge completion doesn't have a single result value
                    'video_link': proof_link if proof_link and not proof_link.startswith(('photo_', 'video_', 'document_')) else ''
                }
                await channel_notifications.notify_challenge_completion(context.bot, completion_data)
        except Exception as e:
            logger.error(f"Ошибка отправки уведомления о челлендже: {e}")

    # Получаем метрику для форматирования результата
    exercise = get_exercise_by_id(exercise_id)
    metric = exercise[3] if exercise else None

    print(f"🔥 DEBUG Метрика упражнения: metric={metric}")

    context.user_data.clear()

    if success:
        if status == 'completed':
            text = (
                f"🎉 ПОТРЯСАЮЩЕ!\n\n"
                f"🏆 ЧЕЛЛЕНДЖ ЗАВЕРШЕН!\n\n"
                f"⭐ Вы выполнили все упражнения и получили бонусные очки!"
            )
            keyboard = [[InlineKeyboardButton("🏋️ Мои челленджи", callback_data="sport_my_challenges")]]
        else:
            formatted_result = format_exercise_result(result_value, metric) if metric else str(result_value)
            text = (
                f"✅ УПРАЖНЕНИЕ ВЫПОЛНЕНО!\n\n"
                f"📊 Результат: {format_number(formatted_result)}\n\n"
                f"Продолжайте в том же духе! Остались еще упражнения 💪"
            )
            keyboard = [[InlineKeyboardButton("🏋️ К упражнениям", callback_data=f"sport_challenge_exercises_{challenge_id}")]]
    else:
        text = "❌ Ошибка при сохранении результата"
        keyboard = [[InlineKeyboardButton("◀️ Назад", callback_data=f"sport_challenge_exercises_{challenge_id}")]]

    print(f"🔥 DEBUG Отправляем сообщение: {text[:50]}...")

    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(text, reply_markup=reply_markup)

    return ConversationHandler.END


async def cancel_challenge_exercise(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Отмена выполнения упражнения."""
    context.user_data.clear()

    # Проверяем, есть ли callback_query (inline кнопка) или message (команда)
    if update.callback_query:
        await update.callback_query.answer()
        await update.callback_query.edit_message_text("❌ Выполнение отменено")
    elif update.message:
        await update.message.reply_text("❌ Выполнение отменено")

    return ConversationHandler.END


# ==================== ПРИСОЕДИНЕНИЕ К ЧЕЛЛЕНДЖУ ====================

@log_call
async def join_challenge_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обрабатывает присоединение к челленджу."""
    query = update.callback_query
    await query.answer()

    challenge_id = int(query.data.split("_")[-1])
    user_id = update.effective_user.id

    # Проверяем даты
    from database_postgres import get_challenge_by_id
    challenge = get_challenge_by_id(challenge_id)

    if not challenge:
        await query.edit_message_text("❌ Челлендж не найден")
        return

    ch_id, name, description, target_type, target_id, metric, target_value, start_date, end_date, bonus_points, entry_fee, prize_pool, is_coin = challenge

    today = date.today()
    if end_date < today:
        await query.edit_message_text("❌ Челлендж уже завершен")
        return
    if start_date > today:
        await query.edit_message_text("❌ Челлендж еще не начался")
        return

    # Присоединяем
    success = join_challenge(user_id, challenge_id)

    if success:
        text = (
            f"✅ ВЫ ПРИСОЕДИНИЛИСЬ!\n\n"
            f"🏆 {name}\n\n"
            f"Теперь выполняйте упражнения и получайте бонусные очки!\n\n"
            f"Удачи! 💪"
        )
        keyboard = [[InlineKeyboardButton("🏋️ Упражнения", callback_data=f"sport_challenge_exercises_{challenge_id}")]]
    else:
        text = "❌ Ошибка при присоединении"
        keyboard = [[InlineKeyboardButton("◀️ Назад", callback_data="sport_challenges")]]

    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.edit_message_text(text, reply_markup=reply_markup, parse_mode='Markdown')


# ==================== PROGRESS ====================

@log_call
async def show_challenge_progress(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показывает детальную информацию о прогрессе в челлендже."""
    query = update.callback_query
    await query.answer()

    challenge_id = int(query.data.split("_")[-1])
    user_id = update.effective_user.id

    exercises = get_challenge_exercises(challenge_id)
    progress = get_user_challenge_progress(user_id, challenge_id)

    from database_postgres import get_challenge_by_id
    challenge = get_challenge_by_id(challenge_id)
    challenge_name = challenge[1] if challenge else "Челлендж"

    # Создаем словарь прогресса
    progress_dict = {p[0]: p for p in progress}

    text = f"📊 ПРОГРЕСС: {challenge_name}\n\n"

    for ex in exercises:
        ex_id, name, description, metric, points, week, difficulty = ex

        if ex_id in progress_dict:
            p = progress_dict[ex_id]
            if p[1]:  # completed
                completed_at = p[4].strftime('%d.%m %H:%M') if p[4] else '?'
                text += f"✅ {name}\n   Результат: {p[2]} | {completed_at}\n\n"
            else:
                text += f"⬜ {name} - не выполнено\n\n"
        else:
            text += f"⬜ {name} - не начато\n\n"

    completed_count = sum(1 for p in progress if p[1])
    total_count = len(exercises)

    text += f"\nВсего выполнено: {completed_count}/{total_count}"

    keyboard = [[InlineKeyboardButton("◀️ Назад", callback_data=f"sport_my_challenge_{challenge_id}")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.edit_message_text(text, reply_markup=reply_markup, parse_mode='Markdown')


# ==================== CONVERSATION HANDLER ====================

challenge_exercise_conversation = ConversationHandler(
    entry_points=[CallbackQueryHandler(start_challenge_exercise, pattern='^sport_challenge_do_exercise_')],
    states={
        CHALLENGE_EXERCISE_INPUT: [
            MessageHandler(filters.TEXT & ~filters.COMMAND, input_exercise_result),
            MessageHandler(filters.PHOTO | filters.VIDEO | filters.Document.ALL, upload_exercise_proof)
        ],
        CHALLENGE_PROOF_UPLOAD: [
            MessageHandler(filters.PHOTO | filters.VIDEO | filters.Document.ALL, upload_exercise_proof),
            MessageHandler(filters.TEXT & ~filters.COMMAND, upload_exercise_proof)  # Для текстовых ссылок
        ],
    },
    fallbacks=[
        CommandHandler('cancel', cancel_challenge_exercise),
        CallbackQueryHandler(cancel_challenge_exercise, pattern='^sport_cancel$')
    ],
)