"""
Обработчики для PvP-вызовов (Дуэли между пользователями)
Полностью кнопочный интерфейс с системой ставок
"""
import logging
from datetime import datetime, timedelta
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from debug_utils import debug_print, log_call
from database_postgres import (
    create_pvp_challenge, accept_pvp_challenge, reject_pvp_challenge,
    get_pvp_challenge, get_user_active_challenge, calculate_pvp_scores,
    finish_expired_pvp_challenges, add_user, get_user_workouts,
    get_user_by_username, get_active_users, get_user_active_challenges,
    get_user_pvp_history, get_user_info, check_active_challenge_between,
    get_user_group, get_user_scoreboard_total, cancel_pvp_challenge_and_refund,
    get_exercises_for_pvp, get_complexes_for_pvp, submit_pvp_exercise_result,
    confirm_pvp_challenge_result, get_exercise_name_by_id, get_complex_name_by_id
)

logger = logging.getLogger(__name__)

# ==================== ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ====================
async def safe_callback_answer(query, text=None):
    """Безопасно отвечает на callback query, обрабатывая ошибки."""
    try:
        await query.answer(text)
    except Exception as e:
        logger.error(f"Failed to answer callback query: {e}")
        # Не прерываем выполнение программы даже если answer не удался

# ==================== CONSTANTES ====================
PVP_MENU_CALLBACK = "pvp_menu"
PVP_NEW_CHALLENGE_CALLBACK = "pvp_new_challenge"
PVP_MY_CHALLENGES_CALLBACK = "pvp_my_challenges"
PVP_HISTORY_CALLBACK = "pvp_history"
PVP_STATS_CALLBACK = "pvp_stats"
PVP_COINS_CALLBACK = "pvp_coins"
PVP_LEADERBOARD_CALLBACK = "pvp_leaderboard"
PVP_BACK_TO_MAIN = "pvp_back_to_main"

PVP_CHALLENGE_USER_PREFIX = "pvp_challenge_user_"
PVP_BET_PREFIX = "pvp_bet_"
PVP_ACCEPT_PREFIX = "pvp_accept_"
PVP_REJECT_PREFIX = "pvp_reject_"
PVP_CANCEL_PREFIX = "pvp_cancel_"
PVP_EXERCISE_TYPE_PREFIX = "pvp_exercise_type_"
PVP_EXERCISE_SELECT_PREFIX = "pvp_exercise_select_"
PVP_RESULT_SUBMIT_PREFIX = "pvp_result_submit_"
PVP_RESULT_CONFIRM_PREFIX = "pvp_result_confirm_"

BET_AMOUNTS = [10, 25, 50, 100]

# Глобальный словарь для отслеживания сообщений создателей вызовов
# {challenge_id: {'chat_id': int, 'message_id': int, 'opponent_id': int, 'bet': int, 'opponent_name': str, 'created_at': datetime}}
pending_challenger_messages = {}


# ==================== ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ====================

async def update_challenger_status(context: ContextTypes.DEFAULT_TYPE, challenge_id: int, status_text: str):
    """Обновляет сообщение создателя вызова"""
    if challenge_id not in pending_challenger_messages:
        return

    msg_data = pending_challenger_messages[challenge_id]

    try:
        await context.bot.edit_message_text(
            chat_id=msg_data['chat_id'],
            message_id=msg_data['message_id'],
            text=status_text,
            parse_mode='Markdown'
        )
    except Exception as e:
        logger.error(f"Ошибка обновления сообщения создателя: {e}")


async def check_challenge_timeout(context: ContextTypes.DEFAULT_TYPE):
    """Проверяет таймауты вызовов (2 минуты)"""
    from datetime import datetime, timedelta

    now = datetime.now()
    timeout_challenges = []

    for challenge_id, msg_data in list(pending_challenger_messages.items()):
        created_at = msg_data['created_at']
        if now - created_at > timedelta(minutes=2):
            timeout_challenges.append(challenge_id)

    # Обрабатываем истёкшие вызовы
    for challenge_id in timeout_challenges:
        if challenge_id in pending_challenger_messages:
            msg_data = pending_challenger_messages[challenge_id]

            # Отменяем вызов и возвращаем ставку
            from database_postgres import cancel_pvp_challenge_and_refund
            success, message, challenger_id, opponent_id, bet = cancel_pvp_challenge_and_refund(
                challenge_id, msg_data['chat_id']
            )

            # Отправляем уведомление о таймауте
            opponent_name = msg_data['opponent_name']
            timeout_text = (
                f"⏰ ВРЕМЯ ВЫШЛО\n\n"
                f"❌ {opponent_name} не ответил на вызов\n"
            )

            if bet > 0:
                timeout_text += f"💰 Ставка {bet} очков возвращена вам"

            await update_challenger_status(context, challenge_id, timeout_text)

            # Уведомляем соперника
            try:
                await context.bot.send_message(
                    chat_id=msg_data['opponent_id'],
                    text="⏰ Время принятия вызова истекло\n\n❌ Вызов автоматически отменён",
                    parse_mode='Markdown'
                )
            except Exception as e:
                logger.error(f"Ошибка отправки уведомления о таймауте: {e}")

            # Удаляем из словаря
            del pending_challenger_messages[challenge_id]


# ==================== ОСНОВНОЕ PvP МЕНЮ ====================
@log_call
async def pvp_main_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Главное меню PvP"""
    debug_print(f"🔥 pvp_handlers: pvp_main_menu: ВЫЗВАНА")

    query = update.callback_query if update.callback_query else None
    user_id = update.effective_user.id
    user_first_name = update.effective_user.first_name

    # Регистрируем пользователя
    add_user(user_id, user_first_name, update.effective_user.last_name,
             update.effective_user.username or f"User{user_id}")

    # Получаем статистику пользователя
    user_score = get_user_scoreboard_total(user_id) or 0
    user_group = get_user_group(user_id) or 'newbie'

    group_emoji = "🌱" if user_group == "newbie" else "🏆"
    group_name = "Новички" if user_group == "newbie" else "Профи"

    # Получаем количество активных вызовов
    active_challenges = get_user_active_challenges(user_id)
    active_count = len(active_challenges) if active_challenges else 0

    text = (
        f"⚔️ PvP - ДУЭЛИ\n\n"
        f"━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"👤 Игрок: {user_first_name}\n"
        f"🏆 FruNStatus: {user_score}\n"
        f"{group_emoji} Лига: {group_name}\n"
        f"🔥 Активных дуэлей: {active_count}\n\n"
        f"━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"💡 FruNStatus = твой ранг (каждые 100 = медаль!)\n"
        f"   Чем выше статус - тем выше ставка!\n\n"
        f"Выберите действие:"
    )

    keyboard = [
        [InlineKeyboardButton("🎯 Новый вызов", callback_data=PVP_NEW_CHALLENGE_CALLBACK)],
        [InlineKeyboardButton("⚔️ Мои вызовы", callback_data=PVP_MY_CHALLENGES_CALLBACK)],
        [InlineKeyboardButton("📚 История", callback_data=PVP_HISTORY_CALLBACK)],
        [InlineKeyboardButton("📊 Статистика", callback_data=PVP_STATS_CALLBACK)],
        [InlineKeyboardButton("◀️ Назад", callback_data="back_to_main")]
    ]

    if query:
        await query.edit_message_text(text, parse_mode='Markdown', reply_markup=InlineKeyboardMarkup(keyboard))
    else:
        await update.message.reply_text(text, parse_mode='Markdown', reply_markup=InlineKeyboardMarkup(keyboard))

    debug_print(f"📤 pvp_main_menu: ВОЗВРАТ")


# ==================== НОВЫЙ ВЫЗОВ ====================
@log_call
async def pvp_show_challenge_candidates(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показывает список пользователей для вызова"""
    debug_print(f"🔥 pvp_handlers: pvp_show_challenge_candidates: ВЫЗВАНА")

    query = update.callback_query
    await safe_callback_answer(query)

    user_id = update.effective_user.id
    user_score = get_user_scoreboard_total(user_id) or 0

    # Получаем группу текущего пользователя
    user_group = get_user_group(user_id)
    if not user_group:
        user_group = 'newbie'

    # Получаем список активных пользователей (кроме себя)
    all_active_users = get_active_users(limit=50, exclude_user_id=user_id)

    # Фильтруем по группе и активным вызовам
    available_users = []
    for user_data in all_active_users:
        candidate_id, first_name, username, score = user_data
        candidate_group = get_user_group(candidate_id)

        # Показываем только пользователей своей группы без активных вызовов
        if candidate_group == user_group and not check_active_challenge_between(user_id, candidate_id):
            available_users.append((candidate_id, first_name, username, score))

    if not available_users:
        group_emoji = "🌱" if user_group == "newbie" else "🏆"
        group_name = "Новички" if user_group == "newbie" else "Профи"

        await query.edit_message_text(
            f"❌ Нет доступных соперников\n\n"
            f"📊 Ваша лига: {group_emoji} {group_name}\n"
            f"💡 Все игроки вашей лиги уже имеют активные дуэли.",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("◀️ Назад", callback_data=PVP_MENU_CALLBACK)
            ]])
        )
        debug_print(f"📤 pvp_show_challenge_candidates: ВОЗВРАТ (нет соперников)")
        return

    group_emoji = "🌱" if user_group == "newbie" else "🏆"
    group_name = "Новички" if user_group == "newbie" else "Профи"

    text = f"🎯 ВЫБЕРИТЕ СОПЕРНИКА\n📊 Лига: {group_emoji} {group_name}\n💰 Ваши очки: {user_score}\n\n"

    keyboard = []
    for candidate_id, first_name, username, score in available_users[:10]:  # Максимум 10 кнопок
        username_str = username or f"User{candidate_id}"
        username_display = username_str if username_str.startswith("@") else f"@{username_str}"

        text += f"👤 {first_name} ({username_display}) - {score} 💰\n"
        keyboard.append([
            InlineKeyboardButton(f"Вызвать {first_name}", callback_data=f"{PVP_CHALLENGE_USER_PREFIX}{candidate_id}")
        ])

    keyboard.append([InlineKeyboardButton("◀️ Назад", callback_data=PVP_MENU_CALLBACK)])

    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard))
    debug_print(f"📤 pvp_show_challenge_candidates: ВОЗВРАТ")


@log_call
async def pvp_select_challenge_type(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показывает выбор типа вызова (упражнение или стандартный)"""
    debug_print(f"🔥 pvp_handlers: pvp_select_challenge_type: ВЫЗВАНА")

    query = update.callback_query
    await safe_callback_answer(query)

    challenger_id = update.effective_user.id
    challenger_first_name = update.effective_user.first_name
    challenger_score = get_user_scoreboard_total(challenger_id) or 0

    # Извлекаем ID противника
    opponent_id = int(query.data.replace(PVP_CHALLENGE_USER_PREFIX, ""))

    # Получаем информацию о противнике
    opponent_info = get_user_info(opponent_id)
    if not opponent_info:
        await query.edit_message_text("❌ Ошибка: соперник не найден")
        debug_print(f"📤 pvp_select_challenge_type: ВОЗВРАТ (соперник не найден)")
        return

    opponent_name = opponent_info[1] or f"User{opponent_id}"
    opponent_username = opponent_info[3]
    opponent_score = opponent_info[4] or 0

    username_display = f"@{opponent_username}" if opponent_username else f"User{opponent_id}"

    text = (
        f"🎯 ВЫБЕРИТЕ ТИП ВЫЗОВА\n\n"
        f"━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"👤 Соперник: {opponent_name} ({username_display})\n\n"
        f"━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"🏆 Ваш FruNStatus: {challenger_score}\n"
        f"🏆 FruNStatus соперника: {opponent_score}\n\n"
        f"💡 Выберите тип дуэли:\n\n"
    )

    keyboard = [
        [
            InlineKeyboardButton("💪 Упражнение", callback_data=f"{PVP_EXERCISE_TYPE_PREFIX}exercise_{opponent_id}"),
            InlineKeyboardButton("⭐ Стандарт", callback_data=f"{PVP_EXERCISE_TYPE_PREFIX}default_{opponent_id}")
        ],
        [InlineKeyboardButton("◀️ Отмена", callback_data=PVP_NEW_CHALLENGE_CALLBACK)]
    ]

    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard))
    debug_print(f"📤 pvp_select_challenge_type: ВОЗВРАТ")


@log_call
async def pvp_select_exercise(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показывает список упражнений для вызовов с упражнениями"""
    debug_print(f"🔥 pvp_handlers: pvp_select_exercise: ВЫЗВАНА")

    query = update.callback_query
    await safe_callback_answer(query)

    # Извлекаем ID противника
    data = query.data.replace(PVP_EXERCISE_TYPE_PREFIX, "")
    parts = data.split("_")
    challenge_type = parts[0]  # 'exercise' or 'default'
    opponent_id = int(parts[1])

    if challenge_type == 'default':
        # Пропускаем выбор упражнения и переходим к ставке
        await pvp_select_bet_for_type(update, context, opponent_id, None, 'default')
        return

    # Получаем упражнения
    exercises = get_exercises_for_pvp()
    complexes = get_complexes_for_pvp()

    if not exercises and not complexes:
        await query.edit_message_text(
            "❌ Нет доступных упражнений\n\n"
            "💡 Попробуйте стандартный тип вызова",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("◀️ Назад", callback_data=PVP_NEW_CHALLENGE_CALLBACK)
            ]])
        )
        debug_print(f"📤 pvp_select_exercise: ВОЗВРАТ (нет упражнений)")
        return

    text = "💪 ВЫБЕРИТЕ УПРАЖНЕНИЕ\n\n━━━━━━━━━━━━━━━━━━━━━\n\n"

    keyboard = []

    # Добавляем упражнения
    if exercises:
        text += "🏋️ УПРАЖНЕНИЯ:\n\n"
        for exercise in exercises[:10]:
            # Распаковываем: (id, name, metric, difficulty)
            exercise_id = exercise[0]
            exercise_name = exercise[1]
            text += f"• {exercise_name}\n"
            keyboard.append([
                InlineKeyboardButton(f"{exercise_name}", callback_data=f"{PVP_EXERCISE_SELECT_PREFIX}exercise_{exercise_id}_{opponent_id}")
            ])

    # Добавляем комплексы
    if complexes:
        text += "\n📋 КОМПЛЕКСЫ:\n\n"
        for complex_data in complexes[:5]:
            # Распаковываем: (id, name, difficulty)
            complex_id = complex_data[0]
            complex_name = complex_data[1]
            text += f"• {complex_name}\n"
            keyboard.append([
                InlineKeyboardButton(f"{complex_name}", callback_data=f"{PVP_EXERCISE_SELECT_PREFIX}complex_{complex_id}_{opponent_id}")
            ])

    keyboard.append([InlineKeyboardButton("◀️ Назад", callback_data=PVP_NEW_CHALLENGE_CALLBACK)])

    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard))
    debug_print(f"📤 pvp_select_exercise: ВОЗВРАТ")


@log_call
async def pvp_handle_exercise_select(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обрабатывает выбор конкретного упражнения"""
    debug_print(f"🔥 pvp_handlers: pvp_handle_exercise_select: ВЫЗВАНА")

    query = update.callback_query
    await safe_callback_answer(query)

    # Извлекаем данные из callback_data
    data = query.data.replace(PVP_EXERCISE_SELECT_PREFIX, "")
    parts = data.split("_")

    # Формат: exercise_{exercise_id}_{opponent_id} или complex_{complex_id}_{opponent_id}
    exercise_type = parts[0]  # 'exercise' or 'complex'
    exercise_id = int(parts[1])
    opponent_id = int(parts[2])

    challenge_type = 'exercise'  # Это всегда exercise challenge

    # Передаем в функцию выбора ставки
    await pvp_select_bet_for_type(update, context, opponent_id, exercise_id, challenge_type)
    debug_print(f"📤 pvp_handle_exercise_select: ВОЗВРАТ")


@log_call
async def pvp_select_bet_for_type(update: Update, context: ContextTypes.DEFAULT_TYPE, opponent_id: int, exercise_id: int, challenge_type: str):
    """Показывает варианты ставок для вызова"""
    debug_print(f"🔥 pvp_handlers: pvp_select_bet_for_type: ВЫЗВАНА")

    query = update.callback_query if update.callback_query else update
    if query:
        await safe_callback_answer(query)

    challenger_id = update.effective_user.id
    challenger_first_name = update.effective_user.first_name
    challenger_score = get_user_scoreboard_total(challenger_id) or 0

    # Получаем информацию о противнике
    opponent_info = get_user_info(opponent_id)
    if not opponent_info:
        if query:
            await query.edit_message_text("❌ Ошибка: соперник не найден")
        debug_print(f"📤 pvp_select_bet_for_type: ВОЗВРАТ (соперник не найден)")
        return

    opponent_name = opponent_info[1] or f"User{opponent_id}"
    opponent_username = opponent_info[3]
    opponent_score = opponent_info[4] or 0

    username_display = f"@{opponent_username}" if opponent_username else f"User{opponent_id}"

    # Добавляем информацию о выбранном упражнении
    exercise_info = ""
    if challenge_type == 'exercise' and exercise_id:
        # Получаем название упражнения
        exercise_name = get_exercise_name_by_id(exercise_id)
        if exercise_name:
            exercise_info = f"💪 Упражнение: {exercise_name}\n\n"
        else:
            exercise_info = f"💪 Упражнение: #{exercise_id}\n\n"

    text = (
        f"🎯 ВЫЗОВ НА ДУЭЛЬ\n\n"
        f"━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"👤 Соперник: {opponent_name} ({username_display})\n\n"
        f"{exercise_info}"
        f"💰 СТАВКА FFCoin: Ваш выбор\n\n"
        f"━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"🏆 Ваш FruNStatus: {challenger_score}\n"
        f"🏆 FruNStatus соперника: {opponent_score}\n\n"
        f"💡 FruNStatus определяет макс. ставку\n\n"
        f"━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"Выберите ставку:"
    )

    keyboard = []
    bet_row = []
    for bet in BET_AMOUNTS:
        # Проверяем, хватает ли очков обоим игрокам
        can_afford = challenger_score >= bet and opponent_score >= bet
        bet_label = f"{bet} 💰" if can_afford else f"{bet} ❌"

        # Добавляем exercise_id и challenge_type в callback_data
        callback_data = f"{PVP_BET_PREFIX}{opponent_id}_{bet}_{exercise_id or 'None'}_{challenge_type}"
        bet_row.append(
            InlineKeyboardButton(bet_label, callback_data=callback_data)
        )

        # Добавляем по 2 кнопки в ряд
        if len(bet_row) == 2:
            keyboard.append(bet_row)
            bet_row = []

    # Добавляем оставшиеся кнопки
    if bet_row:
        keyboard.append(bet_row)

    keyboard.append([InlineKeyboardButton("◀️ Отмена", callback_data=PVP_NEW_CHALLENGE_CALLBACK)])

    if query:
        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard))
    debug_print(f"📤 pvp_select_bet_for_type: ВОЗВРАТ")


@log_call
async def pvp_select_bet(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показывает варианты ставок для вызова"""
    debug_print(f"🔥 pvp_handlers: pvp_select_bet: ВЫЗВАНА")

    query = update.callback_query
    await safe_callback_answer(query)

    challenger_id = update.effective_user.id
    challenger_first_name = update.effective_user.first_name
    challenger_score = get_user_scoreboard_total(challenger_id) or 0

    # Извлекаем ID противника
    opponent_id = int(query.data.replace(PVP_CHALLENGE_USER_PREFIX, ""))

    # Получаем информацию о противнике
    opponent_info = get_user_info(opponent_id)
    if not opponent_info:
        await query.edit_message_text("❌ Ошибка: соперник не найден")
        debug_print(f"📤 pvp_select_bet: ВОЗВРАТ (соперник не найден)")
        return

    opponent_name = opponent_info[1] or f"User{opponent_id}"
    opponent_username = opponent_info[3]
    opponent_score = opponent_info[4] or 0

    username_display = f"@{opponent_username}" if opponent_username else f"User{opponent_id}"

    text = (
        f"🎯 ВЫЗОВ НА ДУЭЛЬ\n\n"
        f"━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"👤 Соперник: {opponent_name} ({username_display})\n\n"
        f"💰 СТАВКА FFCoin: Ваш выбор\n\n"
        f"━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"🏆 Ваш FruNStatus: {challenger_score}\n"
        f"🏆 FruNStatus соперника: {opponent_score}\n\n"
        f"💡 FruNStatus определяет макс. ставку\n\n"
        f"━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"Выберите ставку:"
    )

    keyboard = []
    bet_row = []
    for bet in BET_AMOUNTS:
        # Проверяем, хватает ли очков обоим игрокам
        can_afford = challenger_score >= bet and opponent_score >= bet
        bet_label = f"{bet} 💰" if can_afford else f"{bet} ❌"

        bet_row.append(
            InlineKeyboardButton(bet_label, callback_data=f"{PVP_BET_PREFIX}{opponent_id}_{bet}")
        )

        # Добавляем по 2 кнопки в ряд
        if len(bet_row) == 2:
            keyboard.append(bet_row)
            bet_row = []

    # Добавляем оставшиеся кнопки
    if bet_row:
        keyboard.append(bet_row)

    keyboard.append([InlineKeyboardButton("◀️ Отмена", callback_data=PVP_NEW_CHALLENGE_CALLBACK)])

    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard))
    debug_print(f"📤 pvp_select_bet: ВОЗВРАТ")


@log_call
async def pvp_send_challenge_with_bet(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Отправляет вызов с выбранной ставкой"""
    debug_print(f"🔥 pvp_handlers: pvp_send_challenge_with_bet: ВЫЗВАНА")

    query = update.callback_query
    await safe_callback_answer(query)

    challenger_id = update.effective_user.id
    challenger_first_name = update.effective_user.first_name

    # Извлекаем ID противника, ставку, exercise_id и challenge_type
    data = query.data.replace(PVP_BET_PREFIX, "")
    parts = data.split("_")
    opponent_id = int(parts[0])
    bet = int(parts[1])
    exercise_id = parts[2] if len(parts) > 2 and parts[2] != 'None' else None
    challenge_type = parts[3] if len(parts) > 3 else 'default'

    # Проверяем, что пользователи в одной лиге
    challenger_group = get_user_group(challenger_id) or 'newbie'
    opponent_group = get_user_group(opponent_id) or 'newbie'

    if challenger_group != opponent_group:
        group_emoji_challenger = "🌱" if challenger_group == "newbie" else "🏆"
        group_name_challenger = "Новички" if challenger_group == "newbie" else "Профи"
        group_emoji_opponent = "🌱" if opponent_group == "newbie" else "🏆"
        group_name_opponent = "Новички" if opponent_group == "newbie" else "Профи"

        await query.edit_message_text(
            f"❌ Нельзя вызвать соперника из другой лиги!\n\n"
            f"👤 Вы: {group_emoji_challenger} {group_name_challenger}\n"
            f"🎯 Соперник: {group_emoji_opponent} {group_name_opponent}\n\n"
            f"💡 PvP-вызовы возможны только внутри одной лиги.",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("◀️ Назад", callback_data=PVP_NEW_CHALLENGE_CALLBACK)
            ]])
        )
        debug_print(f"📤 pvp_send_challenge_with_bet: ВОЗВРАТ (разные лиги)")
        return

    # Проверяем, хватает ли очков
    challenger_score = get_user_scoreboard_total(challenger_id) or 0
    opponent_score = get_user_scoreboard_total(opponent_id) or 0

    if challenger_score < bet or opponent_score < bet:
        await query.edit_message_text(
            f"❌ Недостаточно очков!\n\n"
            f"💰 Ставка: {bet}\n"
            f"📊 Ваши очки: {challenger_score}\n"
            f"📊 Очки соперника: {opponent_score}\n\n"
            f"💡 У одного из игроков недостаточно очков для этой ставки.",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("◀️ Назад", callback_data=PVP_NEW_CHALLENGE_CALLBACK)
            ]])
        )
        debug_print(f"📤 pvp_send_challenge_with_bet: ВОЗВРАТ (недостаточно очков)")
        return

    # Создаём вызов с параметрами
    challenge_id, message = create_pvp_challenge(
        challenger_id,
        opponent_id,
        bet=bet,
        exercise_id=exercise_id,
        challenge_type=challenge_type
    )

    if challenge_id is None:
        await query.edit_message_text(f"❌ {message}")
        debug_print(f"📤 pvp_send_challenge_with_bet: ВОЗВРАТ (ошибка создания)")
        return

    # Формируем текст вызова в зависимости от типа
    challenge_type_text = ""
    if challenge_type == 'exercise' and exercise_id:
        # Получаем название упражнения из базы данных
        exercise_name = get_exercise_name_by_id(exercise_id)
        if exercise_name:
            challenge_type_text = f"💪 Упражнение: {exercise_name}\n"
        else:
            challenge_type_text = f"💪 Упражнение: #{exercise_id}\n"

    # Отправляем вызов сопернику
    keyboard = [
        [
            InlineKeyboardButton("✅ Принять", callback_data=f"{PVP_ACCEPT_PREFIX}{challenge_id}"),
            InlineKeyboardButton("❌ Отклонить", callback_data=f"{PVP_REJECT_PREFIX}{challenge_id}")
        ]
    ]

    text = (
        f"⚔️ ВАС ВЫЗВАЛИ НА ДУЭЛЬ!\n\n"
        f"━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"👤 Противник: {challenger_first_name}\n"
        f"{challenge_type_text}"
        f"💰 Ставка: {bet} очков\n"
        f"⏱️ Время: 24 часа\n"
        f"🏆 Победитель получает ставку проигравшего!\n\n"
        f"━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"⏳ У вас есть 2 минуты для принятия."
    )

    try:
        await context.bot.send_message(
            chat_id=opponent_id,
            text=text,
            parse_mode='Markdown',
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
    except Exception as e:
        logger.error(f"Ошибка отправки вызова: {e}")
        await query.edit_message_text(f"❌ Не удалось отправить вызов: {e}")
        debug_print(f"📤 pvp_send_challenge_with_bet: ВОЗВРАТ (ошибка отправки)")
        return

    # Получаем информацию о противнике для отображения
    opponent_info = get_user_info(opponent_id)
    opponent_username = opponent_info[3] if opponent_info else ""
    opponent_name_display = f"@{opponent_username}" if opponent_username else f"User{opponent_id}"

    # Отправляем сообщение создателю и сохраняем его информацию
    status_message = await query.edit_message_text(
        f"⏳ ОЖИДАНИЕ ОТВЕТА\n\n"
        f"━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"👤 От: {opponent_name_display}\n"
        f"{challenge_type_text}"
        f"💰 Ставка: {bet} очков\n"
        f"🔄 Статус: вызов отправлен\n"
        f"⏱️ Макс. время ожидания: 2 минуты\n\n"
        f"━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"📊 Ваши очки: {challenger_score - bet}",
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("🎮 В меню", callback_data=PVP_MENU_CALLBACK)
        ]])
    )

    # Сохраняем информацию о сообщении для последующего обновления
    pending_challenger_messages[challenge_id] = {
        'chat_id': challenger_id,
        'message_id': status_message.message_id,
        'opponent_id': opponent_id,
        'bet': bet,
        'opponent_name': opponent_name_display,
        'created_at': datetime.now()
    }

    # Запускаем фоновую задачу для проверки таймаута
    if context.job_queue:
        context.job_queue.run_repeating(
            check_challenge_timeout,
            interval=30,  # Проверяем каждые 30 секунд
            first=10,     # Первая проверка через 10 секунд
            name=f"check_timeout_{challenge_id}"
        )

    debug_print(f"📤 pvp_send_challenge_with_bet: ВОЗВРАТ")


# ==================== ПРИНЯТИЕ/ОТКЛОНЕНИЕ ВЫЗОВА ====================
@log_call
async def pvp_accept_challenge(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Принятие вызова"""
    debug_print(f"🔥 pvp_handlers: pvp_accept_challenge: ВЫЗВАНА")

    query = update.callback_query
    await safe_callback_answer(query)

    opponent_id = update.effective_user.id
    challenge_id = int(query.data.replace(PVP_ACCEPT_PREFIX, ""))

    # Принимаем вызов
    success, message = accept_pvp_challenge(challenge_id, opponent_id)

    if not success:
        await query.edit_message_text(f"❌ {message}")
        debug_print(f"📤 pvp_accept_challenge: ВОЗВРАТ (ошибка)")
        return

    # Получаем информацию о вызове
    challenge_data = get_pvp_challenge(challenge_id)
    if not challenge_data:
        await query.edit_message_text("❌ Вызов не найден")
        debug_print(f"📤 pvp_accept_challenge: ВОЗВРАТ (вызов не найден)")
        return

    challenger_id, start_time, end_time, bet = challenge_data[1], challenge_data[3], challenge_data[4], challenge_data[9] if len(challenge_data) > 9 else 0

    # Форматируем дату красиво (БЕЗ микросекунд)
    from datetime import datetime
    if isinstance(end_time, str):
        end_time_dt = datetime.fromisoformat(end_time.replace('Z', '+00:00'))
    else:
        end_time_dt = end_time
    end_time_formatted = end_time_dt.strftime("%d.%m.%Y %H:%M")

    # Редактируем сообщение
    await query.edit_message_text(
        f"✅ ВЫ ПРИНЯЛИ ВЫЗОВ!\n\n"
        f"⏱️ Дуэль до: {end_time_formatted}\n"
        f"💰 Ставка: {bet} очков\n"
        f"💪 Выполняйте упражнения для победы!"
    )

    # Обновляем сообщение создателя вызова
    if challenge_id in pending_challenger_messages:
        opponent_info = get_user_info(opponent_id)
        opponent_username = opponent_info[3] if opponent_info else ""
        opponent_name_display = f"@{opponent_username}" if opponent_username else "Ваш соперник"

        acceptance_text = (
            f"✅ ВЫЗОВ ПРИНЯТ!\n\n"
            f"🎉 {opponent_name_display} согласился на дуэль!\n"
            f"⏱️ Дуэль до: {end_time_formatted}\n"
            f"💰 Ставка: {bet} очков\n"
            f"💪 Используйте /my_pvp для проверки статуса"
        )

        await update_challenger_status(context, challenge_id, acceptance_text)

        # Удаляем из списка ожидающих
        del pending_challenger_messages[challenge_id]

        # Удаляем job для проверки таймаута
        if context.job_queue:
            jobs = context.job_queue.get_jobs_by_name(f"check_timeout_{challenge_id}")
            for job in jobs:
                job.schedule_removal()
    else:
        # Если сообщения нет в словаре, отправляем обычное уведомление
        try:
            await context.bot.send_message(
                chat_id=challenger_id,
                text=f"✅ **ВАШ ВЫЗОВ ПРИНЯТ!**\n\n"
                     f"⏱️ Дуэль началась!\n"
                     f"💰 Ставка: {bet} очков\n"
                     f"⏱️ Время до конца: {end_time}\n\n"
                     f"💪 Используйте /my_pvp для проверки статуса",
                parse_mode='Markdown'
            )
        except Exception as e:
            logger.error(f"Ошибка уведомления: {e}")

    debug_print(f"📤 pvp_accept_challenge: ВОЗВРАТ")


@log_call
async def pvp_reject_challenge(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Отклонение вызова"""
    debug_print(f"🔥 pvp_handlers: pvp_reject_challenge: ВЫЗВАНА")

    query = update.callback_query
    await safe_callback_answer(query)

    opponent_id = update.effective_user.id
    challenge_id = int(query.data.replace(PVP_REJECT_PREFIX, ""))

    # Отклоняем вызов
    success = reject_pvp_challenge(challenge_id, opponent_id)

    if not success:
        await query.edit_message_text("❌ Ошибка отклонения вызова")
        debug_print(f"📤 pvp_reject_challenge: ВОЗВРАТ (ошибка)")
        return

    await query.edit_message_text("❌ Вы отклонили вызов и проиграли duel!\n💰 Ваша ставка перешла сопернику.")

    # Обновляем сообщение создателя вызова
    if challenge_id in pending_challenger_messages:
        opponent_info = get_user_info(opponent_id)
        opponent_username = opponent_info[3] if opponent_info else ""
        opponent_name_display = f"@{opponent_username}" if opponent_username else "Ваш соперник"

        rejection_text = (
            f"❌ ВЫЗОВ ОТКЛОНЁН\n\n"
            f"🚫 {opponent_name_display} отказался от дуэли\n"
            f"💰 Вы выиграли! Ставка соперника ваша!\n"
            f"💰 Ставка возвращена вам"
        )

        await update_challenger_status(context, challenge_id, rejection_text)

        # Удаляем из списка ожидающих
        del pending_challenger_messages[challenge_id]

        # Удаляем job для проверки таймаута
        if context.job_queue:
            jobs = context.job_queue.get_jobs_by_name(f"check_timeout_{challenge_id}")
            for job in jobs:
                job.schedule_removal()
    else:
        # Если вызов уже был обработан (например, таймаут), просто логируем
        logger.info(f"Вызов {challenge_id} уже обработан или удалён")

    debug_print(f"📤 pvp_reject_challenge: ВОЗВРАТ")


# ==================== МОИ ВЫЗОВЫ ====================
@log_call
async def pvp_my_challenges(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показывает активные вызовы пользователя"""
    debug_print(f"🔥 pvp_handlers: pvp_my_challenges: ВЫЗВАНА")

    query = update.callback_query
    await safe_callback_answer(query)

    user_id = update.effective_user.id

    # Получаем активные вызовы
    active_challenges = get_user_active_challenges(user_id)

    if not active_challenges:
        await query.edit_message_text(
            "⚔️ **МОИ ВЫЗОВЫ**\n\n"
            "━━━━━━━━━━━━━━━━━━━━━\n\n"
            "❌ У вас нет активных дуэлей\n\n"
            "💡 Создайте новый вызов чтобы начать!",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("🎮 Назад", callback_data=PVP_MENU_CALLBACK)
            ]])
        )
        debug_print(f"📤 pvp_my_challenges: ВОЗВРАТ (нет вызовов)")
        return

    text = "⚔️ **МОИ ВЫЗОВЫ**\n\n━━━━━━━━━━━━━━━━━━━━━\n\n"

    keyboard = []

    for challenge in active_challenges:
        challenge_id, challenger_id, opponent_id, start_time, end_time, status, \
        challenger_score, opponent_score, winner_id = challenge[:9]

        # Получаем ставку, если есть
        bet = challenge[12] if len(challenge) > 12 else 0

        # Получаем информацию о вызове с упражнением
        challenge_type = challenge[13] if len(challenge) > 13 else 'default'
        exercise_id = challenge[14] if len(challenge) > 14 else None
        challenger_result = challenge[15] if len(challenge) > 15 else None
        opponent_result = challenge[16] if len(challenge) > 16 else None
        challenger_confirmed = challenge[17] if len(challenge) > 17 else False
        opponent_confirmed = challenge[18] if len(challenge) > 18 else False

        # Определяем роль пользователя
        is_challenger = user_id == challenger_id
        opponent_id_val = opponent_id if is_challenger else challenger_id

        # Получаем информацию о противнике
        opponent_info = get_user_info(opponent_id_val)
        opponent_name = opponent_info[1] if opponent_info else f"User{opponent_id_val}"
        opponent_username = opponent_info[3] if opponent_info else ""

        username_display = f"@{opponent_username}" if opponent_username else f"User{opponent_id_val}"

        # Конвертируем время
        if isinstance(end_time, str):
            end_time_dt = datetime.fromisoformat(end_time)
        else:
            end_time_dt = end_time

        # Считаем оставшееся время
        now = datetime.now()
        remaining = end_time_dt - now
        if remaining.total_seconds() > 0:
            total_seconds = int(remaining.total_seconds())
            hours = total_seconds // 3600
            minutes = (total_seconds % 3600) // 60
            time_left = f"{hours}ч {minutes}м"
        else:
            time_left = "Завершено"

        # Определяем мой счёт и счёт противника
        my_score = challenger_score if is_challenger else opponent_score
        opp_score = opponent_score if is_challenger else challenger_score

        # Статус
        status_emoji = "⏳" if status == 'pending' else "⚔️"
        status_text = "Ожидает" if status == 'pending' else "Активна"

        text += f"{status_emoji} **vs {opponent_name}**\n"
        text += f"📊 **Счёт:** {my_score} vs {opp_score} 💪\n"

        # Добавляем информацию об упражнении, если это вызов с упражнением
        if challenge_type == 'exercise' and exercise_id:
            # Получаем название упражнения
            exercise_name = get_exercise_name_by_id(exercise_id)
            display_exercise = exercise_name if exercise_name else f"#{exercise_id}"
            text += f"💪 **Упражнение:** {display_exercise}\n"

            # Показываем результаты
            my_result = challenger_result if is_challenger else opponent_result
            opp_result = opponent_result if is_challenger else challenger_result
            my_confirmed = challenger_confirmed if is_challenger else opponent_confirmed
            opp_confirmed = opponent_confirmed if is_challenger else challenger_confirmed

            if my_result:
                confirmed_text = " (подтверждён)" if my_confirmed else ""
                text += f"📊 **Ваш результат:** {my_result}{confirmed_text}\n"
            else:
                text += f"📊 **Ваш результат:** Не отправлен\n"

            if opp_result:
                opp_confirmed_text = " (подтверждён)" if opp_confirmed else ""
                text += f"📊 **Результат соперника:** {opp_result}{opp_confirmed_text}\n"
            else:
                text += f"📊 **Результат соперника:** Не отправлен\n"

        text += f"💰 **Ставка:** {bet} очков\n" if bet > 0 else ""
        text += f"⏱️ **Осталось:** {time_left}\n"
        text += f"📋 **Статус:** {status_text}\n\n"
        text += "━━━━━━━━━━━━━━━━━━━━━\n\n"

        # Добавляем кнопки для вызовов с упражнениями
        if challenge_type == 'exercise' and exercise_id:
            my_result = challenger_result if is_challenger else opponent_result
            my_confirmed = challenger_confirmed if is_challenger else opponent_confirmed

            # Кнопка отправки результата
            keyboard.append([
                InlineKeyboardButton(
                    f"📝 {'Изменить результат' if my_result else 'Загрузить результат'}",
                    callback_data=f"{PVP_RESULT_SUBMIT_PREFIX}{challenge_id}"
                )
            ])

            # Кнопка подтверждения результата, если он отправлен но не подтверждён
            if my_result and not my_confirmed:
                keyboard.append([
                    InlineKeyboardButton(
                        f"✅ Подтвердить результат",
                        callback_data=f"{PVP_RESULT_CONFIRM_PREFIX}{challenge_id}"
                    )
                ])

        # Добавляем кнопку отмены для обоих участников
        if status in ['pending', 'active']:
            keyboard.append([
                InlineKeyboardButton("❌ Отменить", callback_data=f"{PVP_CANCEL_PREFIX}{challenge_id}")
            ])

    keyboard.append([InlineKeyboardButton("🔄 Обновить", callback_data=PVP_MY_CHALLENGES_CALLBACK)])
    keyboard.append([InlineKeyboardButton("🎮 Назад", callback_data=PVP_MENU_CALLBACK)])

    await query.edit_message_text(text, parse_mode='Markdown', reply_markup=InlineKeyboardMarkup(keyboard))
    debug_print(f"📤 pvp_my_challenges: ВОЗВРАТ")


# ==================== ИСТОРИЯ ВЫЗОВОВ ====================
@log_call
async def pvp_show_history(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показывает историю вызовов"""
    debug_print(f"🔥 pvp_handlers: pvp_show_history: ВЫЗВАНА")

    query = update.callback_query
    await safe_callback_answer(query)

    user_id = update.effective_user.id

    # Получаем историю
    history = get_user_pvp_history(user_id, limit=10)

    if not history:
        await query.edit_message_text(
            "📚 **ИСТОРИЯ ВЫЗОВОВ**\n\n"
            "━━━━━━━━━━━━━━━━━━━━━\n\n"
            "❌ Нет завершённых дуэлей\n\n"
            "💡 Начните новый вызов чтобы создать историю!",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("🎮 Назад", callback_data=PVP_MENU_CALLBACK)
            ]])
        )
        debug_print(f"📤 pvp_show_history: ВОЗВРАТ (нет истории)")
        return

    text = "📜 **ИСТОРИЯ ВЫЗОВОВ**\n\n━━━━━━━━━━━━━━━━━━━━━\n\n"

    # Считаем статистику
    wins = 0
    losses = 0
    draws = 0

    for i, record in enumerate(history, 1):
        challenge_id, challenger_id, opponent_id, start_time, end_time, status, \
        challenger_score, opponent_score, winner_id, \
        challenger_name, challenger_username, opponent_name, opponent_username = record

        # Получаем ставку
        bet = record[14] if len(record) > 14 else 0

        # Определяем результат
        if winner_id == user_id:
            result = "🏆 Победа"
            wins += 1
        elif winner_id is None:
            result = "🤝 Ничья"
            draws += 1
        else:
            result = "😔 Поражение"
            losses += 1

        # Определяем противника
        if user_id == challenger_id:
            opponent_display = opponent_name or f"User{opponent_id}"
            my_score = challenger_score
            opp_score = opponent_score
        else:
            opponent_display = challenger_name or f"User{challenger_id}"
            my_score = opponent_score
            opp_score = challenger_score

        # Конвертируем время
        if isinstance(end_time, str):
            end_time_dt = datetime.fromisoformat(end_time)
        else:
            end_time_dt = end_time

        text += f"{i}. {result} vs {opponent_display}\n"
        text += f"   Счёт: {my_score} vs {opp_score} 💪\n"
        text += f"   Ставка: {bet} 💰\n" if bet > 0 else ""
        text += f"   Дата: {end_time_dt.strftime('%d.%m.%Y %H:%M')}\n\n"

    # Добавляем статистику
    total_games = wins + losses + draws
    win_rate = (wins / total_games * 100) if total_games > 0 else 0

    text += f"\n📊 **СТАТИСТИКА:**\n"
    text += f"━━━━━━━━━━━━━━━━━━━━━\n\n"
    text += f"🏆 **Побед:** {wins}\n"
    text += f"😔 **Поражений:** {losses}\n"
    text += f"🤝 **Ничьих:** {draws}\n"
    text += f"📈 **Win Rate:** {win_rate:.1f}%\n"

    keyboard = [[InlineKeyboardButton("🎮 Назад", callback_data=PVP_MENU_CALLBACK)]]

    await query.edit_message_text(text, parse_mode='Markdown', reply_markup=InlineKeyboardMarkup(keyboard))
    debug_print(f"📤 pvp_show_history: ВОЗВРАТ")


# ==================== СТАТИСТИКА ====================
@log_call
async def pvp_show_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показывает PvP-статистику пользователя"""
    debug_print(f"🔥 pvp_handlers: pvp_show_stats: ВЫЗВАНА")

    query = update.callback_query
    await safe_callback_answer(query)

    user_id = update.effective_user.id
    user_first_name = update.effective_user.first_name

    # Получаем информацию о пользователе
    user_info = get_user_info(user_id)
    if not user_info:
        await query.edit_message_text("❌ Пользователь не найден")
        debug_print(f"📤 pvp_show_stats: ВОЗВРАТ (пользователь не найден)")
        return

    user_score = user_info[4] or 0
    user_group = user_info[6] if len(user_info) > 6 else 'newbie'

    group_emoji = "🌱" if user_group == "newbie" else "🏆"
    group_name = "Новички" if user_group == "newbie" else "Профи"

    # Получаем историю для статистики
    history = get_user_pvp_history(user_id, limit=1000)  # Берем много для точной статистики

    wins = 0
    losses = 0
    draws = 0
    total_bet_won = 0
    total_bet_lost = 0

    for record in history:
        result = record[3]  # 'win', 'loss', 'draw'
        bet = record[4] if len(record) > 4 else 0
        score_change = record[5] if len(record) > 5 else 0
        winner_id = record[11] if len(record) > 11 else None

        if result == 'win':
            wins += 1
            total_bet_won += abs(score_change) if score_change > 0 else bet
        elif result == 'loss':
            losses += 1
            total_bet_lost += abs(score_change) if score_change < 0 else bet
        elif result == 'draw':
            draws += 1

    total_games = wins + losses + draws
    win_rate = (wins / total_games * 100) if total_games > 0 else 0

    text = (
        f"📊 **PvP СТАТИСТИКА**\n\n"
        f"👤 Игрок: {user_first_name}\n"
        f"{group_emoji} Лига: {group_name}\n"
        f"💰 Баланс: {user_score} очков\n\n"
        f"⚔️ **ИСТОРИЯ ДУЭЛЕЙ:**\n"
        f"🏆 Побед: {wins}\n"
        f"😔 Поражений: {losses}\n"
        f"🤝 Ничьих: {draws}\n"
        f"📈 Win Rate: {win_rate:.1f}%\n\n"
    )

    if total_games > 0:
        text += f"💰 **СТАВКИ:**\n"
        text += f"✅ Выиграно: {total_bet_won} очков\n"
        text += f"❌ Проиграно: {total_bet_lost} очков\n"
        text += f"📊 Профит: {total_bet_won - total_bet_lost:+d} очков\n\n"

    if total_games == 0:
        text += f"💡 У вас пока нет завершённых дуэлей.\n"
        text += f"🎯 Создайте свой первый вызов!"

    keyboard = [[InlineKeyboardButton("🎮 Назад", callback_data=PVP_MENU_CALLBACK)]]

    await query.edit_message_text(text, parse_mode='Markdown', reply_markup=InlineKeyboardMarkup(keyboard))
    debug_print(f"📤 pvp_show_stats: ВОЗВРАТ")


# ==================== ОТМЕНА ВЫЗОВА ====================
@log_call
async def pvp_cancel_challenge(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Отмена вызова для обоих участников с возвратом ставки"""
    debug_print(f"🔥 pvp_handlers: pvp_cancel_challenge: ВЫЗВАНА")

    query = update.callback_query
    await safe_callback_answer(query)

    user_id = update.effective_user.id
    challenge_id = int(query.data.replace(PVP_CANCEL_PREFIX, ""))

    # Отменяем вызов и возвращаем ставки
    success, message, challenger_id, opponent_id, bet = cancel_pvp_challenge_and_refund(challenge_id, user_id)

    if not success:
        await query.answer(f"❌ {message}", show_alert=True)
        debug_print(f"📤 pvp_cancel_challenge: ВОЗВРАТ ({message})")
        return

    # Формируем сообщение об отмене
    text = f"✅ ВЫЗОВ ОТМЕНЁН\n\n"
    if bet > 0:
        refund_amount = int(bet * 0.8)
        text += f"💰 Возвращено {refund_amount} очков (20% штраф за отмену)\n\n"
    text += f"ℹ️ {message}"

    # Отправляем сообщение текущему пользователю
    await query.edit_message_text(
        text,
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("◀️ В меню", callback_data=PVP_MENU_CALLBACK)
        ]])
    )

    # Уведомляем оппонента об отмене
    try:
        opponent_id = opponent_id if user_id == challenger_id else challenger_id
        opponent_info = get_user_info(opponent_id)

        if opponent_info:
            opponent_name = opponent_info[1] if opponent_info else f"User{opponent_id}"

            await context.bot.send_message(
                chat_id=opponent_id,
                text=f"⚠️ **ВЫЗОВ ОТМЕНЁН**\n\n"
                     f"❌ Ваш противник отменил дуэль\n"
                     f"💰 Ставка {bet} очков возвращена вам" if bet > 0 else "⚠️ **ВЫЗОВ ОТМЕНЁН**\n\n❌ Ваш противник отменил дуэль",
                parse_mode='Markdown'
            )
    except Exception as e:
        logger.error(f"Ошибка отправки уведомления об отмене: {e}")

    # Удаляем из списка ожидающих и останавливаем задачу проверки таймаута
    if challenge_id in pending_challenger_messages:
        del pending_challenger_messages[challenge_id]

    if context.job_queue:
        jobs = context.job_queue.get_jobs_by_name(f"check_timeout_{challenge_id}")
        for job in jobs:
            job.schedule_removal()

    debug_print(f"📤 pvp_cancel_challenge: ВОЗВРАТ")


# ==================== ЗАДАЧА ДЛЯ АВТОМАТИЧЕСКОГО ЗАВЕРШЕНИЯ ====================
@log_call
async def finish_expired_pvp_challenges_task(context: ContextTypes.DEFAULT_TYPE):
    """Задача для автоматического завершения истёкших вызовов"""
    debug_print(f"🔥 pvp_handlers: finish_expired_pvp_challenges_task: ВЫЗВАНА")

    try:
        count = finish_expired_pvp_challenges()
        if count > 0:
            logger.info(f"✅ Завершено {count} истёкших PvP-вызовов")
        debug_print(f"📤 finish_expired_pvp_challenges_task: ВОЗВРАТ ({count} завершено)")
    except Exception as e:
        logger.error(f"Ошибка завершения PvP-вызовов: {e}")
        debug_print(f"📤 finish_expired_pvp_challenges_task: ОШИБКА {e}")


# ==================== УСТАРЕВШИЕ ФУНКЦИИ ДЛЯ СОВМЕСТИМОСТИ ====================
@log_call
async def challenge_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Устаревшая команда - перенаправление на новое меню"""
    debug_print(f"🔥 pvp_handlers: challenge_command: ВЫЗВАНА (устарела)")
    await pvp_main_menu(update, context)


@log_call
async def my_pvp_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Устаревшая команда - перенаправление на мои вызовы"""
    debug_print(f"🔥 pvp_handlers: my_pvp_command: ВЫЗВАНА (устарела)")
    await pvp_my_challenges(update, context)


# ==================== ОБРАБОТЧИКИ ДЛЯ НЕДОСТАЮЩИХ КНОПОК ====================
@log_call
async def pvp_coins_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обрабатывает кнопку 'Ставки на FF'"""
    debug_print(f"🔥 pvp_handlers: pvp_coins_callback: ВЫЗВАНА")

    query = update.callback_query
    await safe_callback_answer(query)

    text = (
        "⚡ **СТАВКИ НА FF**\n\n"
        "💡 Функция в разработке!\n\n"
        "Скоро здесь появится:\n"
        "• Ставки на FruN Fuel\n"
        "• Турниры с призовыми\n"
        "• Усиление ставок"
    )

    keyboard = [
        [InlineKeyboardButton("◀️ В меню", callback_data=PVP_MENU_CALLBACK)]
    ]

    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.edit_message_text(text, reply_markup=reply_markup, parse_mode='Markdown')
    debug_print(f"📤 pvp_coins_callback: ВОЗВРАТ")


@log_call
async def pvp_leaderboard_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обрабатывает кнопку 'Лидерборд'"""
    debug_print(f"🔥 pvp_handlers: pvp_leaderboard_callback: ВЫЗВАНА")

    query = update.callback_query
    await safe_callback_answer(query)

    text = (
        "🏆 **ЛИДЕРБОРД**\n\n"
        "💡 Функция в разработке!\n\n"
        "Скоро здесь появится:\n"
        "• Рейтинг лучших игроков\n"
        "• Статистика побед\n"
        "• Достижения"
    )

    keyboard = [
        [InlineKeyboardButton("◀️ В меню", callback_data=PVP_MENU_CALLBACK)]
    ]

    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.edit_message_text(text, reply_markup=reply_markup, parse_mode='Markdown')
    debug_print(f"📤 pvp_leaderboard_callback: ВОЗВРАТ")


# ==================== УПРАЖНЕНИЯ И РЕЗУЛЬТАТЫ ====================
@log_call
async def pvp_show_exercise_result_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показывает экран ввода результата для вызовов с упражнениями"""
    debug_print(f"🔥 pvp_handlers: pvp_show_exercise_result_input: ВЫЗВАНА")

    query = update.callback_query
    await safe_callback_answer(query)

    user_id = update.effective_user.id

    # Получаем активные вызовы
    active_challenges = get_user_active_challenges(user_id)

    if not active_challenges:
        await query.edit_message_text(
            "❌ Нет активных дуэлей\n\n"
            "💡 Создайте новый вызов чтобы начать!",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("🎮 Назад", callback_data=PVP_MENU_CALLBACK)
            ]])
        )
        debug_print(f"📤 pvp_show_exercise_result_input: ВОЗВРАТ (нет вызовов)")
        return

    # Ищем вызовы с упражнениями
    exercise_challenges = []
    for challenge in active_challenges:
        challenge_id, challenger_id, opponent_id, start_time, end_time, status, \
        challenger_score, opponent_score, winner_id = challenge[:9]

        # Проверяем challenge_type и exercise_id
        challenge_type = challenge[13] if len(challenge) > 13 else 'default'
        exercise_id = challenge[14] if len(challenge) > 14 else None

        if challenge_type == 'exercise' and exercise_id:
            # Получаем результаты участников
            challenger_result = challenge[15] if len(challenge) > 15 else None
            opponent_result = challenge[16] if len(challenge) > 16 else None
            challenger_confirmed = challenge[17] if len(challenge) > 17 else False
            opponent_confirmed = challenge[18] if len(challenge) > 18 else False

            exercise_challenges.append({
                'challenge_id': challenge_id,
                'challenger_id': challenger_id,
                'opponent_id': opponent_id,
                'exercise_id': exercise_id,
                'end_time': end_time,
                'status': status,
                'challenger_result': challenger_result,
                'opponent_result': opponent_result,
                'challenger_confirmed': challenger_confirmed,
                'opponent_confirmed': opponent_confirmed,
                'is_challenger': user_id == challenger_id
            })

    if not exercise_challenges:
        await query.edit_message_text(
            "❌ Нет активных дуэлей с упражнениями\n\n"
            "💡 Создайте новый вызов с упражнением!",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("🎮 Назад", callback_data=PVP_MENU_CALLBACK)
            ]])
        )
        debug_print(f"📤 pvp_show_exercise_result_input: ВОЗВРАТ (нет вызовов с упражнениями)")
        return

    text = "💪 ВВОД РЕЗУЛЬТАТОВ\n\n━━━━━━━━━━━━━━━━━━━━━\n\n"

    keyboard = []

    for challenge in exercise_challenges:
        challenge_id = challenge['challenge_id']
        exercise_id = challenge['exercise_id']
        is_challenger = challenge['is_challenger']

        # Получаем название упражнения для отображения
        exercise_name = get_exercise_name_by_id(exercise_id) if exercise_id else None
        display_exercise = exercise_name if exercise_name else f"Упражнение #{exercise_id}"

        # Определяем роль пользователя
        if is_challenger:
            my_result = challenge['challenger_result']
            my_confirmed = challenge['challenger_confirmed']
            opponent_result = challenge['opponent_result']
            opponent_confirmed = challenge['opponent_confirmed']
        else:
            my_result = challenge['opponent_result']
            my_confirmed = challenge['opponent_confirmed']
            opponent_result = challenge['challenger_result']
            opponent_confirmed = challenge['challenger_confirmed']

        # Формируем статус
        result_status = "❌ Не отправлен"
        if my_result:
            result_status = f"✅ Отправлен: {my_result}"
            if my_confirmed:
                result_status += " (подтверждён)"

        opponent_status = "❌ Не отправлен"
        if opponent_result:
            opponent_status = f"✅ Отправлен: {opponent_result}"
            if opponent_confirmed:
                opponent_status += " (подтверждён)"

        text += f"🏋️ {display_exercise}\n"
        text += f"📊 Ваш результат: {result_status}\n"
        text += f"📊 Результат соперника: {opponent_status}\n\n"

        # Добавляем кнопку отправки результата
        keyboard.append([
            InlineKeyboardButton(
                f"📝 Загрузить результат",
                callback_data=f"{PVP_RESULT_SUBMIT_PREFIX}{challenge_id}"
            )
        ])

        # Добавляем кнопку подтверждения, если результат отправлен
        if my_result and not my_confirmed:
            keyboard.append([
                InlineKeyboardButton(
                    f"✅ Подтвердить результат",
                    callback_data=f"{PVP_RESULT_CONFIRM_PREFIX}{challenge_id}"
                )
            ])

        text += "━━━━━━━━━━━━━━━━━━━━━\n\n"

    keyboard.append([InlineKeyboardButton("🔄 Обновить", callback_data="pvp_refresh_results")])
    keyboard.append([InlineKeyboardButton("🎮 Назад", callback_data=PVP_MENU_CALLBACK)])

    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard))
    debug_print(f"📤 pvp_show_exercise_result_input: ВОЗВРАТ")


@log_call
async def pvp_submit_exercise_result(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обрабатывает отправку результата упражнения"""
    debug_print(f"🔥 pvp_handlers: pvp_submit_exercise_result: ВЫЗВАНА")

    query = update.callback_query
    await safe_callback_answer(query)

    challenge_id = int(query.data.replace(PVP_RESULT_SUBMIT_PREFIX, ""))
    user_id = update.effective_user.id

    # Получаем информацию о вызове
    challenge_data = get_pvp_challenge(challenge_id)
    if not challenge_data:
        await query.edit_message_text("❌ Вызов не найден")
        debug_print(f"📤 pvp_submit_exercise_result: ВОЗВРАТ (вызов не найден)")
        return

    # Проверяем, что это вызов с упражнением
    challenge_type = challenge_data[13] if len(challenge_data) > 13 else 'default'
    if challenge_type != 'exercise':
        await query.edit_message_text("❌ Это не вызов с упражнением")
        debug_print(f"📤 pvp_submit_exercise_result: ВОЗВРАТ (не вызов с упражнением)")
        return

    # Устанавливаем состояние для ввода результата
    context.user_data['waiting_challenge_id'] = challenge_id
    context.user_data['conversation_state'] = 'waiting_exercise_result'

    exercise_id = challenge_data[14] if len(challenge_data) > 14 else 'Неизвестно'

    # Получаем название упражнения для отображения
    exercise_name = get_exercise_name_by_id(exercise_id) if exercise_id != 'Неизвестно' else None
    display_exercise = exercise_name if exercise_name else f"Упражнение #{exercise_id}"

    await query.edit_message_text(
        f"📝 ВВОД РЕЗУЛЬТАТА\n\n"
        f"━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"🏋️ {display_exercise}\n\n"
        f"💡 Введите ваш результат (например: 50 кг, 30 раз, 5 минут)\n\n"
        f"⏳ У вас есть 2 минуты для ввода",
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("❌ Отмена", callback_data=PVP_MY_CHALLENGES_CALLBACK)
        ]])
    )

    debug_print(f"📤 pvp_submit_exercise_result: ВОЗВРАТ")


@log_call
async def pvp_handle_exercise_result_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обрабатывает текстовый ввод результата упражнения"""
    debug_print(f"🔥 pvp_handlers: pvp_handle_exercise_result_input: ВЫЗВАНА")

    user_id = update.effective_user.id
    message_text = update.message.text

    # Проверяем состояние
    if context.user_data.get('conversation_state') != 'waiting_exercise_result':
        return

    challenge_id = context.user_data.get('waiting_challenge_id')
    if not challenge_id:
        await update.message.reply_text("❌ Ошибка: вызов не найден")
        debug_print(f"📤 pvp_handle_exercise_result_input: ВОЗВРАТ (нет challenge_id)")
        return

    # Сохраняем результат
    success, message = submit_pvp_exercise_result(challenge_id, user_id, message_text)

    # Очищаем состояние
    context.user_data.pop('waiting_challenge_id', None)
    context.user_data.pop('conversation_state', None)

    if success:
        await update.message.reply_text(
            f"✅ РЕЗУЛЬТАТ ЗАГРУЖЕН!\n\n"
            f"📊 Ваш результат: {message_text}\n\n"
            f"💡 Вы можете изменить его в любое время до завершения дуэли.\n"
            f"✅ Не забудьте подтвердить результат после завершения упражнения!",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("🔄 Обновить", callback_data="pvp_refresh_results")
            ]])
        )
    else:
        await update.message.reply_text(f"❌ {message}")

    debug_print(f"📤 pvp_handle_exercise_result_input: ВОЗВРАТ")


@log_call
async def pvp_confirm_exercise_result(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Подтверждает результат участника"""
    debug_print(f"🔥 pvp_handlers: pvp_confirm_exercise_result: ВЫЗВАНА")

    query = update.callback_query
    await safe_callback_answer(query)

    user_id = update.effective_user.id
    challenge_id = int(query.data.replace(PVP_RESULT_CONFIRM_PREFIX, ""))

    # Подтверждаем результат
    success, message, both_confirmed = confirm_pvp_challenge_result(challenge_id, user_id)

    if success:
        if both_confirmed:
            # Оба участника подтвердили - завершаем вызов
            from database_postgres import complete_pvp_challenge
            complete_success, complete_message = complete_pvp_challenge(challenge_id)

            await query.edit_message_text(
                f"✅ РЕЗУЛЬТАТ ПОДТВЕРЖДЁН!\n\n"
                f"🎉 Оба участника подтвердили результаты!\n\n"
                f"{complete_message}",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("🎮 В меню", callback_data=PVP_MENU_CALLBACK)
                ]])
            )
        else:
            await query.edit_message_text(
                f"✅ РЕЗУЛЬТАТ ПОДТВЕРЖДЁН!\n\n"
                f"💡 Ожидайте подтверждения от соперника.\n"
                f"🔄 Дуэль завершится автоматически после обоих подтверждений.",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("🔄 Обновить", callback_data="pvp_refresh_results")
                ]])
            )
    else:
        await query.edit_message_text(f"❌ {message}")

    debug_print(f"📤 pvp_confirm_exercise_result: ВОЗВРАТ")


@log_call
async def pvp_refresh_results(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обновляет экран результатов"""
    debug_print(f"🔥 pvp_handlers: pvp_refresh_results: ВЫЗВАНА")
    await pvp_show_exercise_result_input(update, context)
    debug_print(f"📤 pvp_refresh_results: ВОЗВРАТ")
