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
    get_user_group, get_user_scoreboard_total, cancel_pvp_challenge_and_refund
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
                f"⏰ **ВРЕМЯ ВЫШЛО**\n\n"
                f"❌ {opponent_name} не ответил на вызов\n"
            )

            if bet > 0:
                timeout_text += f"💰 Ставка {bet} очков возвращена вам"

            await update_challenger_status(context, challenge_id, timeout_text)

            # Уведомляем соперника
            try:
                await context.bot.send_message(
                    chat_id=msg_data['opponent_id'],
                    text="⏰ **Время принятия вызова истекло**\n\n❌ Вызов автоматически отменён",
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
        f"⚔️ **PvP - ДУЭЛИ**\n\n"
        f"━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"👤 **Игрок:** {user_first_name}\n"
        f"🏆 **FruNStatus:** {user_score}\n"
        f"{group_emoji} **Лига:** {group_name}\n"
        f"🔥 **Активных дуэлей:** {active_count}\n\n"
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

    text = f"🎯 **ВЫБЕРИТЕ СОПЕРНИКА**\n📊 Лига: {group_emoji} {group_name}\n💰 Ваши очки: {user_score}\n\n"

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
    opponent_score = opponent_info[4] or 0  # score находится на индексе 4

    username_display = f"@{opponent_username}" if opponent_username else f"User{opponent_id}"

    text = (
        f"🎯 **ВЫЗОВ НА ДУЭЛЬ**\n\n"
        f"━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"👤 **Соперник:** {opponent_name} ({username_display})\n\n"
        f"💰 **СТАВКА FFCoin:** Ваш выбор\n\n"
        f"━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"🏆 **Ваш FruNStatus:** {challenger_score}\n"
        f"🏆 **FruNStatus соперника:** {opponent_score}\n\n"
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

    # Извлекаем ID противника и ставку
    data = query.data.replace(PVP_BET_PREFIX, "")
    opponent_id, bet = data.split("_")
    opponent_id = int(opponent_id)
    bet = int(bet)

    # Проверяем, что пользователи в одной лиге
    challenger_group = get_user_group(challenger_id) or 'newbie'
    opponent_group = get_user_group(opponent_id) or 'newbie'

    if challenger_group != opponent_group:
        group_emoji_challenger = "🌱" if challenger_group == "newbie" else "🏆"
        group_name_challenger = "Новички" if challenger_group == "newbie" else "Профи"
        group_emoji_opponent = "🌱" if opponent_group == "newbie" else "🏆"
        group_name_opponent = "Новички" if opponent_group == "newbie" else "Профи"

        await query.edit_message_text(
            f"❌ **Нельзя вызвать соперника из другой лиги!**\n\n"
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
            f"❌ **Недостаточно очков!**\n\n"
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

    # Создаём вызов с ставкой
    challenge_id, message = create_pvp_challenge(challenger_id, opponent_id, bet)

    if challenge_id is None:
        await query.edit_message_text(f"❌ {message}")
        debug_print(f"📤 pvp_send_challenge_with_bet: ВОЗВРАТ (ошибка создания)")
        return

    # Отправляем вызов сопернику
    keyboard = [
        [
            InlineKeyboardButton("✅ Принять", callback_data=f"{PVP_ACCEPT_PREFIX}{challenge_id}"),
            InlineKeyboardButton("❌ Отклонить", callback_data=f"{PVP_REJECT_PREFIX}{challenge_id}")
        ]
    ]

    text = (
        f"⚔️ **ВАС ВЫЗВАЛИ НА ДУЭЛЬ!**\n\n"
        f"━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"👤 **Противник:** {challenger_first_name}\n"
        f"💰 **Ставка:** {bet} очков\n"
        f"⏱️ **Время:** 24 часа\n"
        f"🏆 **Победитель получает ставку проигравшего!**\n\n"
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
        f"⏳ **ОЖИДАНИЕ ОТВЕТА**\n\n"
        f"━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"👤 **От:** {opponent_name_display}\n"
        f"💰 **Ставка:** {bet} очков\n"
        f"🔄 **Статус:** вызов отправлен\n"
        f"⏱️ **Макс. время ожидания:** 2 минуты\n\n"
        f"━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"📊 **Ваши очки:** {challenger_score - bet}",
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

    challenger_id, start_time, end_time, bet = challenge_data[1], challenge_data[3], challenge_data[4], challenge_data[12] if len(challenge_data) > 12 else 0

    # Редактируем сообщение
    await query.edit_message_text(
        f"✅ **ВЫ ПРИНЯЛИ ВЫЗОВ!**\n\n"
        f"⏱️ Дуэль до: {end_time}\n"
        f"💰 Ставка: {bet} очков\n"
        f"💪 Выполняйте упражнения для победы!"
    )

    # Обновляем сообщение создателя вызова
    if challenge_id in pending_challenger_messages:
        opponent_info = get_user_info(opponent_id)
        opponent_username = opponent_info[3] if opponent_info else ""
        opponent_name_display = f"@{opponent_username}" if opponent_username else "Ваш соперник"

        acceptance_text = (
            f"✅ **ВЫЗОВ ПРИНЯТ!**\n\n"
            f"🎉 {opponent_name_display} согласился на дуэль!\n"
            f"⏱️ Дуэль до: {end_time}\n"
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

    await query.edit_message_text("❌ Вы отклонили вызов")

    # Обновляем сообщение создателя вызова
    if challenge_id in pending_challenger_messages:
        opponent_info = get_user_info(opponent_id)
        opponent_username = opponent_info[3] if opponent_info else ""
        opponent_name_display = f"@{opponent_username}" if opponent_username else "Ваш соперник"

        rejection_text = (
            f"❌ **ВЫЗОВ ОТКЛОНЁН**\n\n"
            f"🚫 {opponent_name_display} отказался от дуэли\n"
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
        challenger_score, opponent_score, winner_id = challenge

        # Получаем ставку, если есть
        bet = challenge[12] if len(challenge) > 12 else 0

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
        text += f"💰 **Ставка:** {bet} очков\n" if bet > 0 else ""
        text += f"⏱️ **Осталось:** {time_left}\n"
        text += f"📋 **Статус:** {status_text}\n\n"
        text += "━━━━━━━━━━━━━━━━━━━━━\n\n"

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
        winner_id = record[8]
        bet = record[14] if len(record) > 14 else 0

        if winner_id == user_id:
            wins += 1
            total_bet_won += bet
        elif winner_id is None:
            draws += 1
        else:
            losses += 1
            total_bet_lost += bet

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
    text = f"✅ **ВЫЗОВ ОТМЕНЁН**\n\n"
    if bet > 0:
        text += f"💰 Ставка {bet} очков возвращена обоим участникам\n\n"
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
