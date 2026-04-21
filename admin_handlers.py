"""
Админ-панель с системой ролей и инлайн-кнопками
Уровни: 1=модератор, 2=админ, 3=владелец
"""
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, CommandHandler, CallbackQueryHandler, ConversationHandler, MessageHandler, filters
from debug_utils import debug_print, log_call
from database_postgres import (
    is_admin, get_admin_level, add_admin, remove_admin, get_all_admins,
    get_admin_level_name, get_user_info
)
import channel_notifications

logger = logging.getLogger(__name__)

# ==================== ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ====================
async def safe_callback_answer(query, text=None):
    """Безопасно отвечает на callback query, обрабатывая ошибки."""
    try:
        await query.answer(text)
    except Exception as e:
        logger.error(f"Failed to answer callback query: {e}")
        # Не прерываем выполнение программы даже если answer не удался

# ==================== КОНСТАНТЫ ====================

ADMIN_PANEL_CALLBACK = "admin_panel"
ADMIN_LIST_CALLBACK = "admin_list"
ADMIN_ADD_CALLBACK = "admin_add"
ADMIN_REMOVE_CALLBACK = "admin_remove"
ADMIN_BACK_CALLBACK = "admin_back"

# Уровни доступа
MODERATOR_LEVEL = 1
ADMIN_LEVEL = 2
OWNER_LEVEL = 3

# Состояния для добавления админа
WAITING_FOR_USERNAME = 1
WAITING_FOR_LEVEL = 2


# ================= ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ====================

def escape_markdown(text):
    """Экранирует спецсимволы для Markdown."""
    if not text:
        return text
    # Экранируем символы, которые ломают Markdown
    text = text.replace('_', '\\_')
    text = text.replace('*', '\\*')
    text = text.replace('[', '\\[')
    text = text.replace(']', '\\]')
    text = text.replace('(', '\\(')
    text = text.replace(')', '\\)')
    text = text.replace('~', '\\~')
    text = text.replace('`', '\\`')
    text = text.replace('>', '\\>')
    text = text.replace('#', '\\#')
    text = text.replace('+', '\\+')
    text = text.replace('=', '\\=')
    text = text.replace('|', '\\|')
    text = text.replace('{', '\\{')
    text = text.replace('}', '\\}')
    text = text.replace('.', '\\.')
    text = text.replace('!', '\\!')
    text = text.replace('-', '\\-')
    return text

def validate_text_input(text, max_length=500):
    """Проверяет текст на недопустимые символы."""
    if not text:
        return True, ""

    # Проверяем длину
    if len(text) > max_length:
        return False, f"Текст должен быть не более {max_length} символов"

    # Проверяем на потенциально проблемные символы
    problematic_chars = ['<', '>', '\x00', '\x01', '\x02', '\x03', '\x04', '\x05']
    for char in problematic_chars:
        if char in text:
            return False, "Текст содержит недопустимые символы"

    return True, ""

# ==================== ДЕКОРАТОР ДЛЯ ПРОВЕРКИ ПРАВ ====================

def admin_required(level=1):
    """Декоратор для проверки прав админа.

    Args:
        level: Минимальный уровень доступа (1=модератор, 2=админ, 3=владелец)

    Returns:
        Декоратор для async функции
    """
    def decorator(func):
        async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE):
            user_id = update.effective_user.id

            if not is_admin(user_id):
                await update.message.reply_text("❌ У вас нет прав для выполнения этой команды.")
                return

            user_level = get_admin_level(user_id)
            if user_level < level:
                level_name = get_admin_level_name(level)
                your_level = get_admin_level_name(user_level)
                await update.message.reply_text(
                    f"❌ Требуется уровень: {level_name}\n"
                    f"Ваш уровень: {your_level}"
                )
                return

            return await func(update, context)
        return wrapper
    return decorator


# ==================== КОМАНДЫ ====================

@log_call
async def my_admin_level_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показывает ваш уровень админа (для всех)."""
    user_id = update.effective_user.id

    if not is_admin(user_id):
        await update.message.reply_text(
            "❌ **ВЫ НЕ АДМИНИСТРАТОР**\n\n"
            "Вы не имеете административных прав.",
            parse_mode='Markdown'
        )
        return

    level = get_admin_level(user_id)
    level_name = get_admin_level_name(level)

    # Получаем информацию о том, кто добавил
    from database_postgres import get_db_connection
    conn = get_db_connection()
    cur = conn.cursor()

    try:
        cur.execute("""
            SELECT added_by, added_at
            FROM admins
            WHERE user_id = %s
        """, (user_id,))

        result = cur.fetchone()
        if result:
            added_by, added_at = result

            # Получаем информацию о добавившем
            adder_info = get_user_info(added_by) if added_by else None
            if adder_info:
                adder_name = adder_info[1] or f"User{added_by}"
                adder_username = f"@{adder_info[3]}" if adder_info[3] else ""
                adder_display = f"{adder_name} {adder_username}".strip()
            else:
                adder_display = "Система"

            added_at_str = added_at.strftime('%d.%m.%Y %H:%M') if added_at else "Неизвестно"

            text = (
                f"⭐ **ВАШ УРОВЕНЬ**\n\n"
                f"━━━━━━━━━━━━━━━━━━━━━\n\n"
                f"{level_name}\n\n"
                f"📅 **Добавлен:** {added_at_str}\n"
                f"👤 **Кем добавлен:** {adder_display}\n"
            )
        else:
            text = f"{level_name}"

    except Exception as e:
        logger.error(f"Ошибка получения информации об админе: {e}")
        text = f"{level_name}"
    finally:
        cur.close()
        conn.close()

    await update.message.reply_text(text, parse_mode='Markdown')


@log_call
@admin_required(level=1)
async def admins_list_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показывает список всех админов (для level >= 1)."""
    user_id = update.effective_user.id
    user_level = get_admin_level(user_id)

    admins = get_all_admins()

    if not admins:
        await update.message.reply_text(
            "📋 **СПИСОК АДМИНОВ**\n\n"
            "━━━━━━━━━━━━━━━━━━━━━\n\n"
            "❌ Администраторов нет",
            parse_mode='Markdown'
        )
        return

    text = "📋 **СПИСОК АДМИНОВ**\n\n━━━━━━━━━━━━━━━━━━━━━\n\n"

    for admin in admins:
        admin_user_id, username, first_name, level, added_by, added_at, added_by_username, added_by_name = admin

        level_name = get_admin_level_name(level)
        username_display = f"@{username}" if username else f"User{admin_user_id}"
        first_name_display = first_name or ""

        added_at_str = added_at.strftime('%d.%m.%Y') if added_at else "?"

        if added_by_username:
            adder_display = f"@{added_by_username}"
        elif added_by_name:
            adder_display = added_by_name
        elif added_by:
            adder_display = f"User{added_by}"
        else:
            adder_display = "Система"

        text += f"{level_name} **{first_name_display}** {username_display}\n"
        text += f"   👤 Добавлен: {adder_display}\n"
        text += f"   📅 Дата: {added_at_str}\n\n"

    # Добавляем инструкции для владельца
    if user_level >= OWNER_LEVEL:
        text += "━━━━━━━━━━━━━━━━━━━━━\n\n"
        text += "💡 Используйте /admin_panel для управления"

    await update.message.reply_text(text, parse_mode='Markdown')


@log_call
@admin_required(level=2)
async def admin_panel_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Главное админ-меню (для level >= 2)."""
    user_id = update.effective_user.id
    user_level = get_admin_level(user_id)

    level_name = get_admin_level_name(user_level)

    text = (
        f"⚙️ **АДМИН-ПАНЕЛЬ**\n\n"
        f"━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"👤 Ваш уровень: {level_name}\n\n"
        f"━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"Выберите раздел:"
    )

    keyboard = [
        [
            InlineKeyboardButton("🏋️ Упражнения", callback_data="admin_exercises"),
            InlineKeyboardButton("🏆 Челленджи", callback_data="admin_challenges")
        ],
        [
            InlineKeyboardButton("🔗 Комплексы", callback_data="admin_complexes"),
            InlineKeyboardButton("👥 Админы", callback_data="admin_admins_menu")
        ],
        [
            InlineKeyboardButton("📊 Статистика", callback_data="admin_stats"),
            InlineKeyboardButton("🔙 Закрыть", callback_data="admin_close")
        ]
    ]

    reply_markup = InlineKeyboardMarkup(keyboard)

    if update.message:
        await update.message.reply_text(text, reply_markup=reply_markup, parse_mode='Markdown')
    else:
        query = update.callback_query
        await query.edit_message_text(text, reply_markup=reply_markup, parse_mode='Markdown')


# ==================== CALLBACK HANDLERS ====================

async def admin_list_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показывает список админов (callback)."""
    query = update.callback_query
    await safe_callback_answer(query)

    admins = get_all_admins()

    if not admins:
        text = (
            "📋 **СПИСОК АДМИНОВ**\n\n"
            "━━━━━━━━━━━━━━━━━━━━━\n\n"
            "❌ Администраторов нет"
        )
    else:
        text = "📋 **СПИСОК АДМИНОВ**\n\n━━━━━━━━━━━━━━━━━━━━━\n\n"

        for admin in admins:
            admin_user_id, username, first_name, level, added_by, added_at, added_by_username, added_by_name = admin

            level_name = get_admin_level_name(level)
            username_display = f"@{username}" if username else f"User{admin_user_id}"
            first_name_display = first_name or ""

            text += f"{level_name} **{first_name_display}** {username_display}\n\n"

    keyboard = [[InlineKeyboardButton("🔙 Назад", callback_data=ADMIN_PANEL_CALLBACK)]]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await query.edit_message_text(text, reply_markup=reply_markup, parse_mode='Markdown')


async def admin_add_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Начинает процесс добавления админа."""
    query = update.callback_query
    await safe_callback_answer(query)

    keyboard = [[InlineKeyboardButton("❌ Отмена", callback_data="admin_cancel_add")]]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await query.edit_message_text(
        "➕ **ДОБАВИТЬ АДМИНА**\n\n"
        "━━━━━━━━━━━━━━━━━━━━━\n\n"
        "📝 Введите username или ID пользователя:\n\n"
        "Примеры:\n"
        "• @username\n"
        "• 123456789",
        reply_markup=reply_markup,
        parse_mode='Markdown'
    )

    context.user_data['admin_add_state'] = WAITING_FOR_USERNAME
    return WAITING_FOR_USERNAME


async def admin_add_username(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обрабатывает ввод username для добавления админа."""
    username_input = update.message.text.strip()

    # Проверка отмены
    if username_input.lower() == '/cancel':
        await update.message.reply_text("❌ Операция отменена")
        context.user_data.clear()
        return ConversationHandler.END

    # Определяем user_id
    if username_input.startswith('@'):
        username = username_input[1:]
        # Ищем пользователя по username
        from database_postgres import get_db_connection
        conn = get_db_connection()
        cur = conn.cursor()

        try:
            cur.execute("SELECT telegram_id FROM users WHERE username = %s", (username,))
            result = cur.fetchone()
            if not result:
                await update.message.reply_text(
                    f"❌ Пользователь @{username} не найден\n\n"
                    f"❌ Для отмены введите /cancel",
                    parse_mode='Markdown'
                )
                return WAITING_FOR_USERNAME

            target_user_id = result[0]
        finally:
            cur.close()
            conn.close()
    else:
        # Попробуем распарсить как число
        try:
            target_user_id = int(username_input)
        except ValueError:
            await update.message.reply_text(
                "❌ Неверный формат. Введите @username или числовой ID\n\n"
                "❌ Для отмены введите /cancel",
                parse_mode='Markdown'
            )
            return WAITING_FOR_USERNAME

    # Проверяем, что пользователь существует
    target_user_info = get_user_info(target_user_id)
    if not target_user_info:
        await update.message.reply_text(
            f"❌ Пользователь не найден\n\n"
            f"❌ Для отмены введите /cancel",
            parse_mode='Markdown'
        )
        return WAITING_FOR_USERNAME

    # Сохраняем target_user_id и показываем выбор уровня
    context.user_data['admin_add_target_id'] = target_user_id

    target_name = target_user_info[1] or f"User{target_user_id}"
    target_username = f"@{target_user_info[3]}" if target_user_info[3] else ""

    text = (
        f"➕ **ДОБАВИТЬ АДМИНА**\n\n"
        f"━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"👤 Пользователь: **{target_name}** {target_username}\n\n"
        f"━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"Выберите уровень:"
    )

    keyboard = [
        [
            InlineKeyboardButton("🛡️ Модератор (1)", callback_data="admin_add_level_1")
        ],
        [
            InlineKeyboardButton("⭐ Админ (2)", callback_data="admin_add_level_2")
        ],
        [
            InlineKeyboardButton("👑 Владелец (3)", callback_data="admin_add_level_3")
        ],
        [
            InlineKeyboardButton("❌ Отмена", callback_data="admin_add_cancel")
        ]
    ]

    await update.message.reply_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')
    return WAITING_FOR_LEVEL


async def admin_add_level(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обрабатывает выбор уровня админа."""
    query = update.callback_query
    await safe_callback_answer(query)

    level = int(query.data.split('_')[-1])
    target_user_id = context.user_data.get('admin_add_target_id')
    added_by = update.effective_user.id

    if not target_user_id:
        await query.edit_message_text("❌ Ошибка: пользователь не выбранен")
        context.user_data.clear()
        return ConversationHandler.END

    # Добавляем админа
    success = add_admin(target_user_id, level, added_by)

    if not success:
        await query.edit_message_text("❌ Ошибка добавления админа")
        context.user_data.clear()
        return ConversationHandler.END

    level_name = get_admin_level_name(level)
    target_user_info = get_user_info(target_user_id)
    target_name = target_user_info[1] or f"User{target_user_id}"

    text = (
        f"✅ **АДМИН ДОБАВЛЕН**\n\n"
        f"━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"👤 Пользователь: **{target_name}**\n"
        f"⭐ Уровень: {level_name}\n\n"
        f"📬 Уведомление отправлено"
    )

    keyboard = [[InlineKeyboardButton("🔙 В панель", callback_data=ADMIN_PANEL_CALLBACK)]]
    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')

    # Отправляем уведомление новому админу
    try:
        await context.bot.send_message(
            chat_id=target_user_id,
            text=f"🎉 **ВЫ НАЗНАЧЕНЫ АДМИНИСТРАТОРОМ**\n\n"
                 f"━━━━━━━━━━━━━━━━━━━━━\n\n"
                 f"⭐ Ваш уровень: {level_name}\n\n"
                 f"📋 Используйте /admin_panel для управления",
            parse_mode='Markdown'
        )
    except Exception as e:
        logger.error(f"Ошибка отправки уведомления новому админу: {e}")

    context.user_data.clear()
    return ConversationHandler.END


async def admin_add_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Отменяет добавление админа."""
    context.user_data.clear()

    # Если это callback query
    if update.callback_query:
        query = update.callback_query
        await safe_callback_answer(query)

        keyboard = [[InlineKeyboardButton("🔙 В админы", callback_data="admin_admins_menu")]]
        reply_markup = InlineKeyboardMarkup(keyboard)

        try:
            await query.edit_message_text(
                "❌ **Добавление админа отменено**",
                reply_markup=reply_markup,
                parse_mode='Markdown'
            )
        except Exception as e:
            logger.error(f"Ошибка при отмене добавления админа: {e}")
    # Если это message (команда /cancel)
    elif update.message:
        await update.message.reply_text("❌ Добавление админа отменено")

    return ConversationHandler.END


async def admin_remove_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показывает список админов для удаления."""
    query = update.callback_query
    await safe_callback_answer(query)

    user_id = update.effective_user.id
    user_level = get_admin_level(user_id)

    if user_level < OWNER_LEVEL:
        await query.answer("❌ Только владельцы могут удалять админов", show_alert=True)
        return

    admins = get_all_admins()

    if not admins:
        text = (
            "❌ **УДАЛИТЬ АДМИНА**\n\n"
            "━━━━━━━━━━━━━━━━━━━━━\n\n"
            "❌ Администраторов нет"
        )
        keyboard = [[InlineKeyboardButton("🔙 Назад", callback_data=ADMIN_PANEL_CALLBACK)]]
        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')
        return

    text = "❌ **УДАЛИТЬ АДМИНА**\n\n━━━━━━━━━━━━━━━━━━━━━\n\nВыберите администратора:"

    keyboard = []

    for admin in admins:
        admin_user_id, username, first_name, level, added_by, added_at, added_by_username, added_by_name = admin

        # Нельзя удалить самого себя
        if admin_user_id == user_id:
            continue

        level_name = get_admin_level_name(level)
        username_display = username or str(admin_user_id)
        first_name_display = first_name or "Пользователь"

        button_label = f"{level_name} {first_name_display} (@{username_display})" if username else f"{level_name} {first_name_display}"

        keyboard.append([
            InlineKeyboardButton(f"❌ {button_label}", callback_data=f"admin_remove_{admin_user_id}")
        ])

    keyboard.append([InlineKeyboardButton("🔙 Назад", callback_data=ADMIN_PANEL_CALLBACK)])

    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')


async def admin_remove_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Подтверждает удаление админа."""
    query = update.callback_query
    await safe_callback_answer(query)

    user_id = update.effective_user.id
    target_admin_id = int(query.data.replace("admin_remove_", ""))

    # Удаляем админа
    success = remove_admin(target_admin_id, user_id)

    if not success:
        await query.edit_message_text(
            "❌ Ошибка удаления админа",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("🔙 В панель", callback_data=ADMIN_PANEL_CALLBACK)
            ]])
        )
        return

    target_info = get_user_info(target_admin_id)
    target_name = target_info[1] or f"User{target_admin_id}" if target_info else f"User{target_admin_id}"

    text = (
        f"✅ **АДМИН УДАЛЁН**\n\n"
        f"━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"👤 Пользователь: **{target_name}**\n\n"
        f"⚠️ Права администратора отозваны"
    )

    keyboard = [[InlineKeyboardButton("🔙 В панель", callback_data=ADMIN_PANEL_CALLBACK)]]
    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')

    # Отправляем уведомление удалённому админу
    try:
        await context.bot.send_message(
            chat_id=target_admin_id,
            text="⚠️ **ВАШИ АДМИНСКИЕ ПРАВА ОТМЕНЕНЫ**\n\n"
                 "Вы больше не являетесь администратором.",
            parse_mode='Markdown'
        )
    except Exception as e:
        logger.error(f"Ошибка отправки уведомления об удалении админа: {e}")


async def admin_back_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Возврат в главное меню."""
    query = update.callback_query
    await safe_callback_answer(query)

    # Можно добавить переход в главное меню бота
    await query.edit_message_text(
        "🔙 Возращение в главное меню\n\n"
        "Используйте /menu для главного меню или /admin_panel для повторного входа"
    )


# ==================== CONVERSATION HANDLERS ====================

# Создаём ConversationHandler для добавления админа
admin_add_conversation = ConversationHandler(
    entry_points=[CallbackQueryHandler(admin_add_start, pattern=f'^{ADMIN_ADD_CALLBACK}$')],
    states={
        WAITING_FOR_USERNAME: [
            MessageHandler(filters.TEXT & ~filters.COMMAND, admin_add_username),
            CallbackQueryHandler(admin_add_cancel, pattern='^admin_cancel_add$')
        ],
        WAITING_FOR_LEVEL: [
            CallbackQueryHandler(admin_add_level, pattern='^admin_add_level_'),
            CallbackQueryHandler(admin_add_cancel, pattern='^admin_add_cancel$')
        ],
    },
    fallbacks=[CommandHandler('cancel', admin_add_cancel)],
)

# ConversationHandler для упражнений будет создан в конце файла (после определения всех функций)


# ==================== СТАРАЯ СИСТЕМА АДМИНИСТРИРОВАНИЯ УПРАЖНЕНИЙ ====================
# Эти функции нужны для обратной совместимости с существующей системой

# Константы для состояний диалога добавления упражнений
EXERCISE_NAME = 1
EXERCISE_DESC = 2
EXERCISE_METRIC = 3
EXERCISE_POINTS = 4
EXERCISE_WEEK = 5
EXERCISE_DIFF = 6

# Константы для состояний диалога редактирования упражнений
EDIT_EXERCISE_NAME = 11
EDIT_EXERCISE_DESC = 12
EDIT_EXERCISE_METRIC = 13
EDIT_EXERCISE_POINTS = 14
EDIT_EXERCISE_DIFF = 15

# Константы для состояний диалога добавления челленджей
CHALLENGE_NAME = 20
CHALLENGE_DESC = 21
CHALLENGE_MULTI_EXERCISE_SELECT = 29  # Выбор нескольких упражнений для челленджа
CHALLENGE_METRIC = 24
CHALLENGE_TARGET_VALUE = 25
CHALLENGE_START_DATE = 26
CHALLENGE_END_DATE = 27
CHALLENGE_BONUS_POINTS = 28

# Константы для состояний диалога добавления комплексов
COMPLEX_NAME = 40
COMPLEX_DESC = 41
COMPLEX_TYPE = 42
COMPLEX_POINTS = 43
COMPLEX_DIFFICULTY = 44
COMPLEX_EXERCISE_SELECT = 45  # Выбор упражнений для комплекса

# Константы для состояний диалога редактирования челленджев
EDIT_CHALLENGE_NAME = 30
EDIT_CHALLENGE_DESC = 31
EDIT_CHALLENGE_TARGET_VALUE = 32
EDIT_CHALLENGE_DATES = 33
EDIT_CHALLENGE_BONUS_POINTS = 34


async def admin_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Старое админ-меню (для обратной совместимости)."""
    # Перенаправляем на новую админ-панель
    await admin_panel_command(update, context)


# Функция admin_callback удалена, так как она блокировала специфичные обработчики
# Все админские callbacks теперь обрабатываются своими специализированными функциями

async def admin_exercise_add_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Начинает процесс добавления упражнения."""
    query = update.callback_query
    await safe_callback_answer(query)

    await query.edit_message_text(
        "📝 **Добавить упражнение**\n\n"
        "Введите название упражнения:",
        parse_mode='Markdown'
    )

    return EXERCISE_NAME


async def admin_exercise_add_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обрабатывает ввод названия упражнения."""
    logger.info(f"🔵 admin_exercise_add_name вызван! update: {update}, context.user_data: {context.user_data}")

    # Проверяем, есть ли сообщение
    if not update.message or not update.message.text:
        logger.warning("❌ Нет сообщения или текста")
        return EXERCISE_NAME

    name = update.message.text
    logger.info(f"📝 Введено название: {name}")

    if len(name) > 100:
        keyboard = [[InlineKeyboardButton("❌ Отмена", callback_data="admin_cancel_exercise")]]
        await update.message.reply_text("❌ Слишком длинное название (макс. 100 символов)", reply_markup=InlineKeyboardMarkup(keyboard))
        return EXERCISE_NAME

    context.user_data['exercise_name'] = name
    logger.info(f"✅ Название сохранено: {name}")

    keyboard = [[InlineKeyboardButton("❌ Отмена", callback_data="admin_cancel_exercise")]]
    await update.message.reply_text(
        f"✅ Название: {name}\n\n"
        f"Введите описание упражнения:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

    return EXERCISE_DESC


async def admin_exercise_add_desc(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обрабатывает ввод описания упражнения."""
    if not update.message or not update.message.text:
        return EXERCISE_DESC

    desc = update.message.text

    if len(desc) > 500:
        keyboard = [[InlineKeyboardButton("❌ Отмена", callback_data="admin_cancel_exercise")]]
        await update.message.reply_text("❌ Слишком длинное описание (макс. 500 символов)", reply_markup=InlineKeyboardMarkup(keyboard))
        return EXERCISE_DESC

    context.user_data['exercise_desc'] = desc

    # Показываем варианты метрик
    keyboard = [
        [
            InlineKeyboardButton("🔢 Повторы", callback_data="ex_metric_reps"),
            InlineKeyboardButton("⏱ Время (мин)", callback_data="ex_metric_time")
        ],
        [
            InlineKeyboardButton("🏋️ Вес (кг)", callback_data="ex_metric_weight"),
            InlineKeyboardButton("🏃 Дистанция (км)", callback_data="ex_metric_distance")
        ],
        [InlineKeyboardButton("❌ Отмена", callback_data="admin_cancel_exercise")]
    ]

    await update.message.reply_text(
        f"✅ Описание сохранено\n\n"
        f"Выберите тип метрики:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

    return EXERCISE_METRIC


async def admin_exercise_add_metric(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обрабатывает выбор метрики упражнения."""
    query = update.callback_query
    await safe_callback_answer(query)

    metric = query.data.replace('ex_metric_', '')
    context.user_data['exercise_metric'] = metric

    metric_names = {
        'reps': 'Повторы',
        'time': 'Время (мин)',
        'weight': 'Вес (кг)',
        'distance': 'Дистанция (км)'
    }

    await query.edit_message_text(
        f"✅ Метрика: {metric_names.get(metric, metric)}\n\n"
        f"Введите количество очков за упражнение:"
    )

    return EXERCISE_POINTS


async def admin_exercise_add_points(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обрабатывает ввод очков упражнения."""
    if not update.message or not update.message.text:
        return EXERCISE_POINTS

    points_text = update.message.text

    try:
        points = int(points_text)
        if points < 1 or points > 1000:
            keyboard = [[InlineKeyboardButton("❌ Отмена", callback_data="admin_cancel_exercise")]]
            await update.message.reply_text("❌ Очки должны быть от 1 до 1000", reply_markup=InlineKeyboardMarkup(keyboard))
            return EXERCISE_POINTS
    except ValueError:
        keyboard = [[InlineKeyboardButton("❌ Отмена", callback_data="admin_cancel_exercise")]]
        await update.message.reply_text("❌ Введите число от 1 до 1000", reply_markup=InlineKeyboardMarkup(keyboard))
        return EXERCISE_POINTS

    context.user_data['exercise_points'] = points
    context.user_data['exercise_week'] = None  # Пропускаем неделю

    # Показываем варианты сложности
    keyboard = [
        [
            InlineKeyboardButton("🙂 Новичок", callback_data="ex_diff_beginner"),
            InlineKeyboardButton("🤓 Профи", callback_data="ex_diff_pro")
        ],
        [InlineKeyboardButton("❌ Отмена", callback_data="admin_cancel_exercise")]
    ]

    await update.message.reply_text(
        f"✅ Очки: {points}\n\n"
        f"Выберите уровень сложности:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

    return EXERCISE_DIFF  # Сразу переходим к выбору сложности


async def admin_exercise_add_week(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обрабатывает выбор недели (пропуск)."""
    query = update.callback_query
    await safe_callback_answer(query)

    # Пропускаем выбор недели и переходим к сложности
    context.user_data['exercise_week'] = None

    # Показываем варианты сложности
    keyboard = [
        [
            InlineKeyboardButton("Новичок", callback_data="ex_diff_beginner"),
            InlineKeyboardButton("Профи", callback_data="ex_diff_pro")
        ]
    ]

    await query.edit_message_text(
        f"Выберите уровень сложности:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

    return EXERCISE_DIFF


async def admin_exercise_add_diff(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обрабатывает выбор сложности и сохраняет упражнение."""
    query = update.callback_query
    await safe_callback_answer(query)

    diff = query.data.replace('ex_diff_', '')

    # Собираем данные
    name = context.user_data.get('exercise_name', '')
    desc = context.user_data.get('exercise_desc', '')
    metric = context.user_data.get('exercise_metric', 'reps')
    points = context.user_data.get('exercise_points', 10)
    week = context.user_data.get('exercise_week')
    diff_map = {'beginner': 'newbie', 'pro': 'pro'}
    difficulty = diff_map.get(diff, 'newbie')

    # Тексты для отображения
    difficulty_text = 'Новичок' if difficulty == 'newbie' else 'Профи'
    metric_names = {'reps': 'Повторы', 'time': 'Время', 'weight': 'Вес', 'distance': 'Дистанция'}
    metric_text = metric_names.get(metric, metric)

    # Добавляем упражнение в базу
    try:
        from database_postgres import add_exercise

        # Вызываем функцию добавления упражнения
        exercise_id = add_exercise(name, desc, metric, points, week, difficulty)

        if exercise_id:
            # Отправляем уведомление в канал
            try:
                exercise_data = {
                    'id': exercise_id,
                    'name': name,
                    'description': desc,
                    'metric': metric,
                    'difficulty': difficulty,
                    'points': points
                }
                creator_name = update.effective_user.first_name or "Админ"
                await channel_notifications.notify_new_exercise(context.bot, exercise_data, creator_name)
            except Exception as e:
                logger.error(f"Ошибка отправки уведомления об упражнении: {e}")

            keyboard = [[InlineKeyboardButton("◀️ В админ-меню", callback_data="admin")]]
            await query.edit_message_text(
                f"✅ **УПРАЖНЕНИЕ ДОБАВЛЕНО**\n\n"
                f"📝 Название: {name}\n"
                f"📊 Тип: {metric_text}\n"
                f"⭐ Очки: {points}\n"
                f"🎯 Сложность: {difficulty_text}\n\n"
                f"Упражнение успешно добавлено в каталог!",
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode='Markdown'
            )
        else:
            await query.edit_message_text("❌ Ошибка при добавлении упражнения (возможно, упражнение с таким названием уже существует)")
    except Exception as e:
        logger.error(f"Ошибка добавления упражнения: {e}")
        await query.edit_message_text(f"❌ Ошибка: {e}")

    context.user_data.clear()
    return ConversationHandler.END


async def admin_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Отмена добавления упражнения."""
    if update.callback_query:
        await update.callback_query.answer()
        from telegram import InlineKeyboardButton, InlineKeyboardMarkup
        keyboard = [[InlineKeyboardButton("◀️ В упражнения", callback_data="admin_exercises")]]
        try:
            await update.callback_query.edit_message_text("❌ Добавление упражнения отменено", reply_markup=InlineKeyboardMarkup(keyboard))
        except:
            pass
    elif update.message:
        await update.message.reply_text("❌ Добавление упражнения отменено")

    context.user_data.clear()
    return ConversationHandler.END


# ==================== ФУНКЦИИ ДЛЯ ЧЕЛЛЕНДЖЕВ ====================

async def admin_challenge_add_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Начинает процесс добавления челленджа."""
    query = update.callback_query
    await safe_callback_answer(query)

    await query.edit_message_text(
        "🏆 **Создать челлендж**\n\n"
        "Введите название челленджа:",
        parse_mode='Markdown'
    )

    return CHALLENGE_NAME


async def admin_challenge_add_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обрабатывает ввод названия челленджа."""
    if not update.message or not update.message.text:
        return CHALLENGE_NAME

    name = update.message.text.strip()

    if len(name) > 100:
        keyboard = [[InlineKeyboardButton("❌ Отмена", callback_data="admin_cancel_challenge")]]
        await update.message.reply_text("❌ Слишком длинное название (макс. 100 символов)", reply_markup=InlineKeyboardMarkup(keyboard))
        return CHALLENGE_NAME

    if len(name) == 0:
        await update.message.reply_text("❌ Название не может быть пустым")
        return CHALLENGE_NAME

    context.user_data['challenge_name'] = name

    keyboard = [[InlineKeyboardButton("❌ Отмена", callback_data="admin_cancel_challenge")]]
    await update.message.reply_text(
        f"✅ Название: {name}\n\n"
        f"Введите описание челленджа:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

    return CHALLENGE_DESC


async def admin_challenge_add_desc(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обрабатывает ввод описания челленджа."""
    if not update.message or not update.message.text:
        return CHALLENGE_DESC

    desc = update.message.text.strip()

    if len(desc) > 500:
        keyboard = [[InlineKeyboardButton("❌ Отмена", callback_data="admin_cancel_challenge")]]
        await update.message.reply_text("❌ Слишком длинное описание (макс. 500 символов)", reply_markup=InlineKeyboardMarkup(keyboard))
        return CHALLENGE_DESC

    context.user_data['challenge_desc'] = desc

    # Инициализируем список для выбранных упражнений
    context.user_data['challenge_selected_exercises'] = []

    from database_postgres import get_all_exercises

    exercises = get_all_exercises()

    if not exercises:
        keyboard = [[InlineKeyboardButton("❌ Отмена", callback_data="admin_cancel_challenge")]]
        await update.message.reply_text(
            "❌ В базе нет упражнений!\n\n"
            "Сначала создайте упражнения через меню Упражнения",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        return CHALLENGE_DESC

    # Формируем список упражнений для выбора (с чекбоксами)
    keyboard = []
    for ex in exercises[:10]:  # Показываем первые 10
        ex_id, name, metric, points, week, diff = ex
        diff_text = '🙂' if diff == 'newbie' else '🤓'
        button_text = f"⬜ {diff_text} {name}"
        keyboard.append([InlineKeyboardButton(button_text, callback_data=f"ch_multi_ex_{ex_id}")])

    keyboard.append([InlineKeyboardButton("➕ Еще упражнения", callback_data="ch_multi_ex_more")])
    keyboard.append([InlineKeyboardButton("✅ Готово", callback_data="ch_multi_ex_done")])
    keyboard.append([InlineKeyboardButton("❌ Отмена", callback_data="admin_cancel_challenge")])

    await update.message.reply_text(
        "✅ Описание сохранено\n\n"
        "🏆 **ВЫБЕРИТЕ УПРАЖНЕНИЯ**\n\n"
        "Можно выбрать несколько упражнений (хоть одно, хоть десять)\n"
        "Нажимай на упражнения для выбора, затем 'Готово':",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

    return CHALLENGE_MULTI_EXERCISE_SELECT


async def admin_challenge_multi_exercise_select(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обрабатывает выбор нескольких упражнений для сложного челленджа."""
    query = update.callback_query
    await safe_callback_answer(query)

    callback_data = query.data

    # Обработка кнопок
    if callback_data == "ch_multi_ex_done":
        # Проверяем, что выбран хотя бы одно упражнение
        selected = context.user_data.get('challenge_selected_exercises', [])
        if not selected:
            await query.answer("❌ Выберите хотя бы одно упражнение!", show_alert=True)
            return CHALLENGE_MULTI_EXERCISE_SELECT

        # Переходим к выбору метрики
        keyboard = [
            [
                InlineKeyboardButton("🔢 Повторы", callback_data="ch_metric_reps"),
                InlineKeyboardButton("⏱ Время (мин)", callback_data="ch_metric_time")
            ],
            [
                InlineKeyboardButton("🏋️ Вес (кг)", callback_data="ch_metric_weight"),
                InlineKeyboardButton("🏃 Дистанция (км)", callback_data="ch_metric_distance")
            ],
            [InlineKeyboardButton("❌ Отмена", callback_data="admin_cancel_challenge")]
        ]

        selected_count = len(selected)
        await query.edit_message_text(
            f"✅ Выбрано упражнений: {selected_count}\n\n"
            f"Выберите тип метрики для подсчета прогресса:",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='Markdown'
        )

        return CHALLENGE_METRIC

    elif callback_data.startswith("ch_multi_ex_"):
        # Добавляем/убираем упражнение из списка
        exercise_id = int(callback_data.split("_")[-1])

        # Инициализируем список если его нет
        if 'challenge_selected_exercises' not in context.user_data:
            context.user_data['challenge_selected_exercises'] = []

        selected = context.user_data['challenge_selected_exercises']

        if exercise_id in selected:
            selected.remove(exercise_id)
        else:
            selected.append(exercise_id)

        # Перерисовываем список с обновленными галочками
        from database_postgres import get_all_exercises
        exercises = get_all_exercises()

        keyboard = []
        for ex in exercises[:10]:  # Показываем первые 10
            ex_id, name, metric, points, week, diff = ex
            diff_text = '🙂' if diff == 'newbie' else '🤓'

            # Показываем галочку если упражнение выбрано
            checkbox = '✅' if ex_id in selected else '⬜'
            button_text = f"{checkbox} {diff_text} {name}"
            keyboard.append([InlineKeyboardButton(button_text, callback_data=f"ch_multi_ex_{ex_id}")])

        keyboard.append([InlineKeyboardButton("➕ Еще упражнения", callback_data="ch_multi_ex_more")])
        keyboard.append([InlineKeyboardButton("✅ Готово", callback_data="ch_multi_ex_done")])
        keyboard.append([InlineKeyboardButton("❌ Отмена", callback_data="admin_cancel_challenge")])

        selected_count = len(selected)
        await query.edit_message_text(
            f"🏆 **Сложный челлендж**\n\n"
            f"Выбрано упражнений: {selected_count}\n\n"
            f"Выберите упражнения для челленджа:",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='Markdown'
        )

        return CHALLENGE_MULTI_EXERCISE_SELECT


async def admin_challenge_add_metric(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обрабатывает выбор метрики челленджа."""
    query = update.callback_query
    await safe_callback_answer(query)

    metric = query.data.replace('ch_metric_', '')
    context.user_data['challenge_metric'] = metric

    metric_names = {
        'reps': 'Повторы',
        'time': 'Время (мин)',
        'weight': 'Вес (кг)',
        'distance': 'Дистанция (км)'
    }

    await query.edit_message_text(
        f"✅ Метрика: {metric_names.get(metric, metric)}\n\n"
        f"Введите целевое значение (число):"
    )

    return CHALLENGE_TARGET_VALUE


async def admin_challenge_add_target_value(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обрабатывает ввод целевого значения челленджа."""
    if not update.message or not update.message.text:
        return CHALLENGE_TARGET_VALUE

    value_text = update.message.text.strip()

    try:
        target_value = float(value_text)
        if target_value <= 0:
            keyboard = [[InlineKeyboardButton("❌ Отмена", callback_data="admin_cancel_challenge")]]
            await update.message.reply_text("❌ Значение должно быть положительным числом", reply_markup=InlineKeyboardMarkup(keyboard))
            return CHALLENGE_TARGET_VALUE
    except ValueError:
        keyboard = [[InlineKeyboardButton("❌ Отмена", callback_data="admin_cancel_challenge")]]
        await update.message.reply_text("❌ Введите число", reply_markup=InlineKeyboardMarkup(keyboard))
        return CHALLENGE_TARGET_VALUE

    context.user_data['challenge_target_value'] = target_value

    keyboard = [[InlineKeyboardButton("❌ Отмена", callback_data="admin_cancel_challenge")]]
    await update.message.reply_text(
        f"✅ Целевое значение: {target_value}\n\n"
        f"Введите дату начала (формат: ДД.М.ГГГГ, например: 25.04.2026):",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

    return CHALLENGE_START_DATE


async def admin_challenge_add_start_date(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обрабатывает ввод даты начала челленджа."""
    if not update.message or not update.message.text:
        return CHALLENGE_START_DATE

    date_text = update.message.text.strip()

    try:
        from datetime import datetime
        start_date = datetime.strptime(date_text, '%d.%m.%Y').date()

        # Проверяем, что дата не в прошлом
        from datetime import date
        if start_date < date.today():
            keyboard = [[InlineKeyboardButton("❌ Отмена", callback_data="admin_cancel_challenge")]]
            await update.message.reply_text("❌ Дата начала не может быть в прошлом", reply_markup=InlineKeyboardMarkup(keyboard))
            return CHALLENGE_START_DATE

        context.user_data['challenge_start_date'] = start_date

        keyboard = [[InlineKeyboardButton("❌ Отмена", callback_data="admin_cancel_challenge")]]
        await update.message.reply_text(
            f"✅ Дата начала: {date_text}\n\n"
            f"Введите дату окончания (формат: ДД.М.ГГГГ):",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

        return CHALLENGE_END_DATE

    except ValueError:
        keyboard = [[InlineKeyboardButton("❌ Отмена", callback_data="admin_cancel_challenge")]]
        await update.message.reply_text("❌ Неверный формат даты. Используйте ДД.М.ГГГГ (например: 25.04.2026)", reply_markup=InlineKeyboardMarkup(keyboard))
        return CHALLENGE_START_DATE


async def admin_challenge_add_end_date(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обрабатывает ввод даты окончания челленджа."""
    if not update.message or not update.message.text:
        return CHALLENGE_END_DATE

    date_text = update.message.text.strip()

    try:
        from datetime import datetime
        end_date = datetime.strptime(date_text, '%d.%m.%Y').date()

        # Проверяем, что дата окончания после даты начала
        start_date = context.user_data.get('challenge_start_date')
        if start_date and end_date <= start_date:
            keyboard = [[InlineKeyboardButton("❌ Отмена", callback_data="admin_cancel_challenge")]]
            await update.message.reply_text("❌ Дата окончания должна быть после даты начала", reply_markup=InlineKeyboardMarkup(keyboard))
            return CHALLENGE_END_DATE

        context.user_data['challenge_end_date'] = end_date

        keyboard = [[InlineKeyboardButton("❌ Отмена", callback_data="admin_cancel_challenge")]]
        await update.message.reply_text(
            f"✅ Дата окончания: {date_text}\n\n"
            f"Введите бонусные очки за выполнение:",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

        return CHALLENGE_BONUS_POINTS

    except ValueError:
        keyboard = [[InlineKeyboardButton("❌ Отмена", callback_data="admin_cancel_challenge")]]
        await update.message.reply_text("❌ Неверный формат даты. Используйте ДД.М.ГГГГ (например: 30.04.2026)", reply_markup=InlineKeyboardMarkup(keyboard))
        return CHALLENGE_END_DATE


async def admin_challenge_add_bonus_points(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обрабатывает ввод бонусных очков и сохраняет челлендж."""
    if not update.message or not update.message.text:
        return CHALLENGE_BONUS_POINTS

    points_text = update.message.text.strip()

    try:
        bonus_points = int(points_text)
        if bonus_points < 0 or bonus_points > 10000:
            keyboard = [[InlineKeyboardButton("❌ Отмена", callback_data="admin_cancel_challenge")]]
            await update.message.reply_text("❌ Очки должны быть от 0 до 10000", reply_markup=InlineKeyboardMarkup(keyboard))
            return CHALLENGE_BONUS_POINTS
    except ValueError:
        keyboard = [[InlineKeyboardButton("❌ Отмена", callback_data="admin_cancel_challenge")]]
        await update.message.reply_text("❌ Введите целое число", reply_markup=InlineKeyboardMarkup(keyboard))
        return CHALLENGE_BONUS_POINTS

    # Собираем данные
    name = context.user_data.get('challenge_name', '')
    desc = context.user_data.get('challenge_desc', '')
    metric = context.user_data.get('challenge_metric', 'reps')
    target_value = context.user_data.get('challenge_target_value', 100)
    start_date = context.user_data.get('challenge_start_date')
    end_date = context.user_data.get('challenge_end_date')
    selected_exercises = context.user_data.get('challenge_selected_exercises', [])

    if not selected_exercises:
        await update.message.reply_text("❌ Ошибка: не выбраны упражнения")
        return CHALLENGE_BONUS_POINTS

    # Добавляем челлендж в базу
    try:
        from database_postgres import add_challenge

        # Создаем челлендж с упражнениями
        challenge_id = add_challenge(name, desc, 'challenge', None, metric, target_value, start_date, end_date, bonus_points, selected_exercises)

        if challenge_id:
            # Отправляем уведомление в канал
            try:
                challenge_data = {
                    'id': challenge_id,
                    'name': name,
                    'description': desc,
                    'duration_days': (end_date - start_date).days if end_date and start_date else 7
                }
                creator_name = update.effective_user.first_name or "Админ"
                await channel_notifications.notify_new_challenge(context.bot, challenge_data, creator_name)
            except Exception as e:
                logger.error(f"Ошибка отправки уведомления о челлендже: {e}")

            # Показываем информацию о выбранных упражнениях
            from database_postgres import get_exercise_by_id
            exercise_names = []
            for ex_id in selected_exercises:
                ex = get_exercise_by_id(ex_id)
                if ex:
                    exercise_names.append(ex[1])  # ex[1] - название упражнения

            exercises_text = "\n".join([f"• {name}" for name in exercise_names])
            keyboard = [[InlineKeyboardButton("◀️ В челленджи", callback_data="admin_challenges")]]
            await update.message.reply_text(
                f"✅ **ЧЕЛЛЕНДЖ СОЗДАН**\n\n"
                f"🏆 Название: {name}\n"
                f"📊 Цель: {target_value} {metric}\n"
                f"📅 Период: {start_date} - {end_date}\n"
                f"⭐ Бонус: {bonus_points} очков\n\n"
                f"🏋️ **Упражнения ({len(selected_exercises)}):**\n{exercises_text}\n\n"
                f"Челлендж успешно создан!",
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode='Markdown'
            )
        else:
            await update.message.reply_text("❌ Ошибка при создании челленджа")
    except Exception as e:
        logger.error(f"Ошибка создания челленджа: {e}")
        await update.message.reply_text(f"❌ Ошибка: {e}")

    context.user_data.clear()
    return ConversationHandler.END


async def admin_challenge_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Отмена создания челленджа."""
    if update.callback_query:
        await update.callback_query.answer()
        keyboard = [[InlineKeyboardButton("◀️ В челленджи", callback_data="admin_challenges")]]
        try:
            await update.callback_query.edit_message_text("❌ Создание челленджа отменено", reply_markup=InlineKeyboardMarkup(keyboard))
        except:
            pass
    elif update.message:
        await update.message.reply_text("❌ Создание челленджа отменено")

    context.user_data.clear()
    return ConversationHandler.END


async def admin_view_challenge_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показывает детальную информацию о челлендже."""
    query = update.callback_query
    logger.info(f"🔍 admin_view_challenge_callback СТАРТ: {query.data}")
    await safe_callback_answer(query)

    # Получаем challenge_id из callback_data
    challenge_id = int(query.data.split("_")[-1])

    from database_postgres import get_challenge_by_id
    from datetime import date

    challenge = get_challenge_by_id(challenge_id)

    if not challenge:
        text = "❌ Челлендж не найден"
        keyboard = [[InlineKeyboardButton("◀️ К списку", callback_data="admin_list_challenges")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(text, reply_markup=reply_markup)
        return

    ch_id, name, description, target_type, target_id, metric, target_value, start_date, end_date, bonus_points, entry_fee, prize_pool, is_coin = challenge

    # Определяем статус челленджа
    today = date.today()
    if start_date and end_date:
        if start_date <= today <= end_date:
            status_text = '✅ Активен'
        elif end_date < today:
            status_text = '❌ Завершен'
        else:
            status_text = '⏳ Скоро начнется'
    else:
        status_text = '❌ Завершен'

    start_date_str = start_date.strftime('%d.%m.%Y') if start_date else 'Не указана'
    end_date_str = end_date.strftime('%d.%m.%Y') if end_date else 'Не указана'

    metric_names = {'reps': 'Повторы', 'time': 'Время (мин)', 'weight': 'Вес (кг)', 'distance': 'Дистанция (км)'}
    metric_text = metric_names.get(metric, metric)

    text = (
        f"🏆 **{name}**\n\n"
        f"📝 **Описание:** {description}\n\n"
        f"📊 **Цель:** {target_value} {metric_text}\n"
        f"📅 **Период:** {start_date_str} - {end_date_str}\n"
        f"⭐ **Бонус:** {bonus_points} очков\n"
        f"📈 **Статус:** {status_text}\n"
    )

    keyboard = [
        [InlineKeyboardButton("🗑 Удалить", callback_data=f"admin_delete_challenge_{challenge_id}")],
        [InlineKeyboardButton("◀️ К списку", callback_data="admin_list_challenges")]
    ]

    reply_markup = InlineKeyboardMarkup(keyboard)
    logger.info(f"📝 Редактируем сообщение с текстом: {text[:50]}...")
    try:
        await query.edit_message_text(text, reply_markup=reply_markup, parse_mode='Markdown')
        logger.info(f"✅ Сообщение отредактировано успешно")
    except Exception as e:
        if "not modified" not in str(e):
            logger.error(f"🏔️ Не удалось обновить сообщение: {e}")
        else:
            logger.debug(f"Сообщение не изменилось, пропускаем: {e}")


async def admin_delete_challenge_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Удаление челленджа."""
    query = update.callback_query
    await safe_callback_answer(query)

    # Получаем challenge_id из callback_data
    challenge_id = int(query.data.split("_")[-1])

    from database_postgres import get_challenge_by_id, delete_challenge

    challenge = get_challenge_by_id(challenge_id)

    if not challenge:
        text = "❌ Челлендж не найден"
        keyboard = [[InlineKeyboardButton("◀️ К списку", callback_data="admin_list_challenges")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(text, reply_markup=reply_markup)
        return

    challenge_name = challenge[1]

    text = f"🗑 **УДАЛЕНИЕ ЧЕЛЛЕНДЖА**\n\n❓ Вы действительно хотите удалить челлендж **{challenge_name}**?"

    keyboard = [
        [InlineKeyboardButton("✅ Да, удалить", callback_data=f"admin_confirm_delete_challenge_{challenge_id}")],
        [InlineKeyboardButton("❌ Отмена", callback_data=f"admin_view_challenge_{challenge_id}")]
    ]

    reply_markup = InlineKeyboardMarkup(keyboard)
    try:
        await query.edit_message_text(text, reply_markup=reply_markup, parse_mode='Markdown')
    except Exception as e:
        if "not modified" not in str(e):
            logger.error(f"Ошибка при показе диалога удаления челленджа: {e}")
        else:
            logger.debug(f"Сообщение не изменилось, пропускаем: {e}")


async def admin_confirm_delete_challenge_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Подтверждение удаления челленджа."""
    query = update.callback_query
    await safe_callback_answer(query)

    # Получаем challenge_id из callback_data
    challenge_id = int(query.data.split("_")[-1])

    from database_postgres import get_challenge_by_id, delete_challenge

    challenge = get_challenge_by_id(challenge_id)

    if not challenge:
        text = "❌ Челлендж не найден"
        keyboard = [[InlineKeyboardButton("◀️ К списку", callback_data="admin_list_challenges")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(text, reply_markup=reply_markup)
        return

    challenge_name = challenge[1]

    # Удаляем челлендж из БД
    try:
        delete_challenge(challenge_id)
        text = f"✅ **ЧЕЛЛЕНДЖ УДАЛЁН**\n\nЧеллендж **{challenge_name}** успешно удалён!"
    except Exception as e:
        logger.error(f"Ошибка удаления челленджа: {e}")
        text = f"❌ Ошибка при удалении челленджа: {e}"

    keyboard = [[InlineKeyboardButton("◀️ К списку", callback_data="admin_list_challenges")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    try:
        await query.edit_message_text(text, reply_markup=reply_markup, parse_mode='Markdown')
    except Exception as e:
        if "not modified" not in str(e):
            logger.error(f"Ошибка при подтверждении удаления челленджа: {e}")
        else:
            logger.debug(f"Сообщение не изменилось, пропускаем: {e}")


# ==================== НОВЫЕ CALLBACK HANDLERS ДЛЯ АДМИН-ПАНЕЛИ ====================

async def admin_admins_menu_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Подменю управления админами."""
    query = update.callback_query
    await safe_callback_answer(query)

    user_id = update.effective_user.id
    user_level = get_admin_level(user_id)

    text = (
        f"👥 **УПРАВЛЕНИЕ АДМИНАМИ**\n\n"
        f"━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"Выберите действие:"
    )

    keyboard = [
        [
            InlineKeyboardButton("📋 Список админов", callback_data=ADMIN_LIST_CALLBACK)
        ]
    ]

    # Кнопки добавления/удаления (только для владельцев)
    if user_level >= OWNER_LEVEL:
        keyboard.append([
            InlineKeyboardButton("➕ Добавить админа", callback_data=ADMIN_ADD_CALLBACK)
        ])
        keyboard.append([
            InlineKeyboardButton("❌ Удалить админа", callback_data=ADMIN_REMOVE_CALLBACK)
        ])

    keyboard.append([
        InlineKeyboardButton("🔙 Назад в панель", callback_data=ADMIN_PANEL_CALLBACK)
    ])

    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')


async def admin_exercises_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показывает меню управления упражнениями."""
    query = update.callback_query
    await safe_callback_answer(query)

    text = (
        "🏋️ **УПРАВЛЕНИЕ УПРАЖНЕНИЯМИ**\n\n"
        "Здесь ты сможешь:\n"
        "• 📝 Добавлять новые упражнения\n"
        "• ✏️ Редактировать существующие\n"
        "• 🗑️ Удалять упражнения\n\n"
        "⚠️ **Функционал в разработке**\n\n"
        "Пока используй команду `/addexercise` для добавления упражнений"
    )

    keyboard = [
        [InlineKeyboardButton("➕ Добавить упражнение", callback_data="admin_add_exercise")],
        [InlineKeyboardButton("📋 Список упражнений", callback_data="admin_list_exercises")],
        [InlineKeyboardButton("◀️ Назад", callback_data="admin_back_to_panel")]
    ]

    reply_markup = InlineKeyboardMarkup(keyboard)
    try:
        await query.edit_message_text(text, reply_markup=reply_markup, parse_mode='Markdown')
    except Exception as e:
        if "not modified" not in str(e):
            logger.error(f"Ошибка при открытии меню упражнений: {e}")
        else:
            logger.debug(f"Сообщение не изменилось, пропускаем: {e}")


async def admin_challenges_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показывает меню управления челленджами."""
    query = update.callback_query
    await safe_callback_answer(query)

    text = (
        "🏆 **УПРАВЛЕНИЕ ЧЕЛЛЕНДЖАМИ**\n\n"
        "Здесь ты сможешь:\n"
        "• 📝 Создавать новые челленджи\n"
        "• 🗑️ Удалять челленджи\n\n"
        "⚠️ **Редактирование недоступно**\n"
        "Если нужно изменить - удалите и создайте заново\n\n"
        "Выберите действие:"
    )

    keyboard = [
        [InlineKeyboardButton("➕ Создать челлендж", callback_data="admin_add_challenge")],
        [InlineKeyboardButton("📋 Список челленджей", callback_data="admin_list_challenges")],
        [InlineKeyboardButton("◀️ Назад", callback_data="admin_back_to_panel")]
    ]

    reply_markup = InlineKeyboardMarkup(keyboard)
    try:
        await query.edit_message_text(text, reply_markup=reply_markup, parse_mode='Markdown')
    except Exception as e:
        if "not modified" not in str(e):
            logger.error(f"Ошибка при открытии меню челленджей: {e}")
        else:
            logger.debug(f"Сообщение не изменилось, пропускаем: {e}")


async def admin_complexes_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показывает меню управления комплексами."""
    query = update.callback_query
    await safe_callback_answer(query)

    text = (
        "🔗 **УПРАВЛЕНИЕ КОМПЛЕКСАМИ**\n\n"
        "Здесь ты сможешь:\n"
        "• 📝 Создавать новые комплексы\n"
        "• ✏️ Редактировать существующие\n"
        "• 🗑️ Удалять комплексы\n\n"
        "⚠️ **Функционал в разработке**\n\n"
        "Пока используй команду `/newcomplex` для создания комплексов"
    )

    keyboard = [
        [InlineKeyboardButton("➕ Создать комплекс", callback_data="admin_add_complex")],
        [InlineKeyboardButton("📋 Список комплексов", callback_data="admin_list_complexes")],
        [InlineKeyboardButton("◀️ Назад", callback_data="admin_back_to_panel")]
    ]

    reply_markup = InlineKeyboardMarkup(keyboard)
    try:
        await query.edit_message_text(text, reply_markup=reply_markup, parse_mode='Markdown')
    except Exception as e:
        if "not modified" not in str(e):
            logger.error(f"Ошибка при открытии меню комплексов: {e}")
        else:
            logger.debug(f"Сообщение не изменилось, пропускаем: {e}")


async def admin_stats_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показывает статистику бота."""
    query = update.callback_query
    await safe_callback_answer(query)

    # Импортируем функции статистики
    from database_postgres import get_db_connection

    try:
        conn = get_db_connection()
        cur = conn.cursor()

        # Получаем статистику пользователей
        cur.execute("SELECT COUNT(*) FROM users")
        total_users = cur.fetchone()[0]

        # Получаем статистику админов
        cur.execute("SELECT COUNT(*) FROM admins")
        total_admins = cur.fetchone()[0]

        # Получаем количество упражнений
        cur.execute("SELECT COUNT(*) FROM exercises")
        total_exercises = cur.fetchone()[0]

        # Получаем количество комплексов
        cur.execute("SELECT COUNT(*) FROM complexes")
        total_complexes = cur.fetchone()[0]

        # Получаем количество челленджей
        cur.execute("SELECT COUNT(*) FROM challenges")
        total_challenges = cur.fetchone()[0]

        cur.close()
        conn.close()

        text = (
            f"📊 **СТАТИСТИКА БОТА**\n\n"
            f"━━━━━━━━━━━━━━━━━━━━━\n\n"
            f"👥 **Пользователи:** {total_users}\n"
            f"⭐ **Админы:** {total_admins}\n"
            f"🏋️ **Упражнения:** {total_exercises}\n"
            f"🔗 **Комплексы:** {total_complexes}\n"
            f"🏆 **Челленджи:** {total_challenges}\n\n"
            f"━━━━━━━━━━━━━━━━━━━━━\n\n"
        )

        keyboard = [[InlineKeyboardButton("🔙 Назад", callback_data=ADMIN_PANEL_CALLBACK)]]
        try:
            await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')
        except Exception as edit_error:
            if "not modified" not in str(edit_error):
                logger.error(f"Ошибка при отображении статистики: {edit_error}")
            else:
                logger.debug(f"Сообщение не изменилось, пропускаем: {edit_error}")

    except Exception as e:
        logger.error(f"Ошибка получения статистики: {e}")
        try:
            await query.edit_message_text(f"❌ Ошибка получения статистики: {e}")
        except Exception as edit_error:
            if "not modified" not in str(edit_error):
                logger.error(f"Ошибка при отображении ошибки статистики: {edit_error}")


async def admin_close_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Закрывает админ-панель."""
    query = update.callback_query
    await safe_callback_answer(query)

    text = (
        "✅ **АДМИН-ПАНЕЛЬ ЗАКРЫТА**\n\n"
        "Используйте /admin_panel для повторного входа"
    )
    try:
        await query.edit_message_text(text, parse_mode='Markdown')
    except Exception as e:
        if "not modified" not in str(e):
            logger.error(f"Ошибка при закрытии админ-панели: {e}")
        else:
            logger.debug(f"Сообщение не изменилось, пропускаем: {e}")


async def admin_back_to_panel_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Возврат в главное админ-меню."""
    query = update.callback_query
    await safe_callback_answer(query)

    # Возвращаемся в главное админ-меню
    await admin_panel_command(update, context)


# ==================== ВСПОМОГАТЕЛЬНЫЕ CALLBACK HANDLERS ====================

async def admin_add_exercise_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Запускает процесс добавления упражнения через диалог."""
    # Эта функция просто возвращает управление - ConversationHandler перехватит callback_data="admin_add_exercise"
    pass


async def admin_add_challenge_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Запускает процесс добавления челленджа через диалог."""
    # ConversationHandler перехватит callback_data="admin_add_challenge"
    # Эта функция нужна только для предотвращения ошибки "Unknown callback"
    query = update.callback_query
    await safe_callback_answer(query)


async def admin_list_exercises_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показывает список всех упражнений с пагинацией по 7 штук."""
    query = update.callback_query
    await safe_callback_answer(query)

    from database_postgres import get_all_exercises

    # Получаем номер страницы из callback_data или из context
    page = 0
    if query.data and query.data.startswith("admin_list_exercises_page_"):
        page = int(query.data.split("_")[-1])

    exercises = get_all_exercises()

    if not exercises:
        text = "📋 **СПИСОК УПРАЖНЕНИЙ**\n\n❌ Упражнений пока нет"
        keyboard = [[InlineKeyboardButton("◀️ Назад", callback_data="admin_exercises")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        try:
            await query.edit_message_text(text, reply_markup=reply_markup, parse_mode='Markdown')
        except Exception as e:
            if "not modified" not in str(e):
                logger.error(f"Ошибка при редактировании сообщения: {e}")
        return

    # Пагинация по 7 упражнений на страницу
    per_page = 7
    total_pages = (len(exercises) + per_page - 1) // per_page
    start_idx = page * per_page
    end_idx = start_idx + per_page
    page_exercises = exercises[start_idx:end_idx]

    # Формируем компактные кнопки (название + очки + уровень)
    keyboard = []
    for ex in page_exercises:
        ex_id, name, metric, points, week, difficulty = ex

        difficulty_text = 'Новичок' if difficulty == 'newbie' else 'Профи'

        # Компактная кнопка: только название, очки и уровень
        button_text = f"📋 {name} | ⭐{points} | {difficulty_text}"

        keyboard.append([InlineKeyboardButton(button_text, callback_data=f"admin_view_exercise_{ex_id}")])

    # Добавляем навигацию пагинации
    nav_row = []
    if page > 0:
        nav_row.append(InlineKeyboardButton("⬅️ Пред.", callback_data=f"admin_list_exercises_page_{page-1}"))
    if page < total_pages - 1:
        nav_row.append(InlineKeyboardButton("След. ➡️", callback_data=f"admin_list_exercises_page_{page+1}"))

    if nav_row:
        keyboard.append(nav_row)

    keyboard.append([InlineKeyboardButton("◀️ В упражнения", callback_data="admin_exercises")])

    text = f"📋 **СПИСОК УПРАЖНЕНИЙ** (стр. {page + 1}/{total_pages})\n\nВыберите упражнение для просмотра:"

    reply_markup = InlineKeyboardMarkup(keyboard)
    try:
        await query.edit_message_text(text, reply_markup=reply_markup, parse_mode='Markdown')
    except Exception as e:
        if "not modified" not in str(e):
            logger.error(f"Ошибка при редактировании сообщения: {e}")


async def admin_list_challenges_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показывает список всех челленджей с пагинацией по 7 штук."""
    query = update.callback_query
    await safe_callback_answer(query)

    from database_postgres import get_all_challenges

    # Получаем номер страницы из callback_data или из context
    page = 0
    if query.data and query.data.startswith("admin_list_challenges_page_"):
        page = int(query.data.split("_")[-1])

    challenges = get_all_challenges()

    if not challenges:
        text = "📋 **СПИСОК ЧЕЛЛЕНДЖОВ**\n\n❌ Челленджей пока нет"
        keyboard = [[InlineKeyboardButton("◀️ В челленджи", callback_data="admin_challenges")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        try:
            await query.edit_message_text(text, reply_markup=reply_markup, parse_mode='Markdown')
        except Exception as e:
            if "not modified" not in str(e):
                logger.error(f"Ошибка при редактировании сообщения: {e}")
        return

    # Пагинация по 7 челленджей на страницу
    per_page = 7
    total_pages = (len(challenges) + per_page - 1) // per_page
    start_idx = page * per_page
    end_idx = start_idx + per_page
    page_challenges = challenges[start_idx:end_idx]

    # Формируем компактные кнопки
    keyboard = []
    for ch in page_challenges:
        ch_id, name, description, target_type, target_id, metric, target_value, start_date, end_date, bonus_points, status = ch

        start_date_str = start_date.strftime('%d.%m') if start_date else '?'
        end_date_str = end_date.strftime('%d.%m') if end_date else '?'

        # Компактная кнопка: название и даты (без статуса)
        button_text = f"🏆 {name} | {start_date_str}-{end_date_str}"

        keyboard.append([InlineKeyboardButton(button_text, callback_data=f"admin_view_challenge_{ch_id}")])

    # Добавляем навигацию пагинации
    nav_row = []
    if page > 0:
        nav_row.append(InlineKeyboardButton("⬅️ Пред.", callback_data=f"admin_list_challenges_page_{page-1}"))
    if page < total_pages - 1:
        nav_row.append(InlineKeyboardButton("След. ➡️", callback_data=f"admin_list_challenges_page_{page+1}"))

    if nav_row:
        keyboard.append(nav_row)

    keyboard.append([InlineKeyboardButton("◀️ В челленджи", callback_data="admin_challenges")])

    text = f"📋 **СПИСОК ЧЕЛЛЕНДЖОВ** (стр. {page + 1}/{total_pages})\n\nВыберите челлендж для просмотра:"

    reply_markup = InlineKeyboardMarkup(keyboard)
    try:
        await query.edit_message_text(text, reply_markup=reply_markup, parse_mode='Markdown')
    except Exception as e:
        if "not modified" not in str(e):
            logger.error(f"Ошибка при редактировании сообщения: {e}")


async def admin_add_complex_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Начинает диалог создания комплекса."""
    query = update.callback_query
    await safe_callback_answer(query)

    text = "📦 **СОЗДАТЬ КОМПЛЕКС**\n\nВведите название комплекса:"

    keyboard = [[InlineKeyboardButton("❌ Отмена", callback_data="admin_cancel_complex")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.edit_message_text(text, reply_markup=reply_markup, parse_mode='Markdown')

    return COMPLEX_NAME


async def admin_complex_name_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обрабатывает ввод названия комплекса."""
    if not update.message or not update.message.text:
        return COMPLEX_NAME

    name = update.message.text.strip()

    # Валидация длины
    if len(name) < 3:
        keyboard = [[InlineKeyboardButton("❌ Отмена", callback_data="admin_cancel_complex")]]
        await update.message.reply_text("❌ Название должно быть не менее 3 символов. Попробуйте еще раз:", reply_markup=InlineKeyboardMarkup(keyboard))
        return COMPLEX_NAME
    if len(name) > 100:
        keyboard = [[InlineKeyboardButton("❌ Отмена", callback_data="admin_cancel_complex")]]
        await update.message.reply_text("❌ Название должно быть не более 100 символов. Попробуйте еще раз:", reply_markup=InlineKeyboardMarkup(keyboard))
        return COMPLEX_NAME

    # Валидация символов
    is_valid, error_msg = validate_text_input(name, max_length=100)
    if not is_valid:
        keyboard = [[InlineKeyboardButton("❌ Отмена", callback_data="admin_cancel_complex")]]
        await update.message.reply_text(f"❌ {error_msg}", reply_markup=InlineKeyboardMarkup(keyboard))
        return COMPLEX_NAME

    context.user_data['complex_name'] = name

    await update.message.reply_text(
        f"✅ Название: {name}\n\n"
        f"Введите описание комплекса:"
    )
    return COMPLEX_DESC


async def admin_complex_desc_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обрабатывает ввод описания комплекса."""
    if not update.message or not update.message.text:
        return COMPLEX_DESC

    description = update.message.text.strip()

    # Валидация длины
    if len(description) > 500:
        keyboard = [[InlineKeyboardButton("❌ Отмена", callback_data="admin_cancel_complex")]]
        await update.message.reply_text("❌ Описание должно быть не более 500 символов. Попробуйте еще раз:", reply_markup=InlineKeyboardMarkup(keyboard))
        return COMPLEX_DESC

    # Валидация символов
    is_valid, error_msg = validate_text_input(description, max_length=500)
    if not is_valid:
        keyboard = [[InlineKeyboardButton("❌ Отмена", callback_data="admin_cancel_complex")]]
        await update.message.reply_text(f"❌ {error_msg}", reply_markup=InlineKeyboardMarkup(keyboard))
        return COMPLEX_DESC

    context.user_data['complex_description'] = description

    # Показываем варианты типа комплекса
    keyboard = [
        [InlineKeyboardButton("⏱ На время", callback_data="complex_type_for_time")],
        [InlineKeyboardButton("🔢 На количество", callback_data="complex_type_for_reps")],
        [InlineKeyboardButton("❌ Отмена", callback_data="admin_cancel_complex")]
    ]

    await update.message.reply_text(
        f"✅ Описание: {description}\n\n"
        f"Выберите тип комплекса:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
    return COMPLEX_TYPE


async def admin_complex_type_select(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обрабатывает выбор типа комплекса."""
    query = update.callback_query
    await safe_callback_answer(query)

    complex_type = query.data.replace('complex_type_', '')
    context.user_data['complex_type'] = complex_type

    type_names = {
        'for_time': '⏱ На время',
        'for_reps': '🔢 На количество'
    }

    await query.edit_message_text(
        f"✅ Тип: {type_names.get(complex_type, complex_type)}\n\n"
        f"Введите количество очков за выполнение комплекса:"
    )
    return COMPLEX_POINTS


async def admin_complex_points_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обрабатывает ввод очков комплекса."""
    if not update.message or not update.message.text:
        return COMPLEX_POINTS

    points_text = update.message.text.strip()

    try:
        points = int(points_text)
        if points < 1 or points > 1000:
            keyboard = [[InlineKeyboardButton("❌ Отмена", callback_data="admin_cancel_complex")]]
            await update.message.reply_text("❌ Очки должны быть от 1 до 1000", reply_markup=InlineKeyboardMarkup(keyboard))
            return COMPLEX_POINTS
    except ValueError:
        keyboard = [[InlineKeyboardButton("❌ Отмена", callback_data="admin_cancel_complex")]]
        await update.message.reply_text("❌ Введите число от 1 до 1000", reply_markup=InlineKeyboardMarkup(keyboard))
        return COMPLEX_POINTS

    context.user_data['complex_points'] = points

    # Показываем варианты сложности
    keyboard = [
        [InlineKeyboardButton("🙂 Новичок", callback_data="complex_diff_beginner")],
        [InlineKeyboardButton("🤓 Профи", callback_data="complex_diff_pro")]
    ]

    await update.message.reply_text(
        f"✅ Очки: {points}\n\n"
        f"Выберите сложность комплекса:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
    return COMPLEX_DIFFICULTY


async def admin_complex_difficulty_select(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обрабатывает выбор сложности комплекса."""
    query = update.callback_query
    await safe_callback_answer(query)

    difficulty = query.data.replace('complex_diff_', '')
    context.user_data['complex_difficulty'] = difficulty

    difficulty_names = {
        'beginner': '🙂 Новичок',
        'pro': '🤓 Профи'
    }

    # Получаем список упражнений
    from database_postgres import get_exercises
    exercises = get_exercises(active_only=True)

    if not exercises:
        await query.edit_message_text("❌ Нет активных упражнений. Сначала создайте упражнения.")
        return ConversationHandler.END

    # Формируем список упражнений для выбора
    keyboard = []
    for ex in exercises:
        ex_id, name, metric, points, week, diff = ex
        metric_text = "⏱" if metric == "time" else "🔢"
        keyboard.append([InlineKeyboardButton(f"{metric_text} {name}", callback_data=f"complex_ex_{ex_id}")])

    keyboard.append([InlineKeyboardButton("✅ Готово", callback_data="complex_ex_done")])
    keyboard.append([InlineKeyboardButton("❌ Отмена", callback_data="admin_cancel_complex")])

    text = (
        f"✅ Сложность: {difficulty_names.get(difficulty, difficulty)}\n\n"
        f"Выберите упражнения для комплекса (можно несколько):\n"
        f"Нажмите '✅ Готово' когда закончите выбор."
    )

    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard))
    return COMPLEX_EXERCISE_SELECT


async def admin_complex_exercise_toggle(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Добавляет/убирает упражнение из комплекса."""
    query = update.callback_query
    await safe_callback_answer(query)

    # Проверяем, что это не кнопка "Готово"
    if query.data == 'complex_ex_done':
        return await admin_complex_exercise_done(update, context)

    exercise_id = int(query.data.replace('complex_ex_', ''))

    # Инициализируем список выбранных упражнений если его нет
    if 'complex_selected_exercises' not in context.user_data:
        context.user_data['complex_selected_exercises'] = []

    selected_exercises = context.user_data['complex_selected_exercises']

    # Добавляем или убираем упражнение
    if exercise_id in selected_exercises:
        selected_exercises.remove(exercise_id)
    else:
        selected_exercises.append(exercise_id)

    # Обновляем клавиатуру с отмеченными упражнениями
    from database_postgres import get_exercises
    exercises = get_exercises(active_only=True)

    keyboard = []
    for ex in exercises:
        ex_id, name, metric, points, week, diff = ex
        metric_text = "✅ " if ex_id in selected_exercises else "⬜ "
        metric_text += "⏱" if metric == "time" else "🔢"
        keyboard.append([InlineKeyboardButton(f"{metric_text} {name}", callback_data=f"complex_ex_{ex_id}")])

    keyboard.append([InlineKeyboardButton("✅ Готово", callback_data="complex_ex_done")])
    keyboard.append([InlineKeyboardButton("❌ Отмена", callback_data="admin_cancel_complex")])

    text = (
        f"Выбрано упражнений: {len(selected_exercises)}\n\n"
        f"Выберите упражнения для комплекса (можно несколько):\n"
        f"Нажмите '✅ Готово' когда закончите выбор."
    )

    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard))


async def admin_complex_exercise_done(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Завершает выбор упражнений и создает комплекс."""
    query = update.callback_query

    # Гарантированно очищаем данные при любом исходе
    try:
        await safe_callback_answer(query)

        selected_exercises = context.user_data.get('complex_selected_exercises', [])

        if len(selected_exercises) == 0:
            try:
                await query.edit_message_text("❌ Выберите хотя бы одно упражнение!")
            except:
                pass
            return COMPLEX_EXERCISE_SELECT

        # Получаем данные из context
        name = context.user_data.get('complex_name', '')
        description = context.user_data.get('complex_description', '')
        complex_type = context.user_data.get('complex_type', '')
        points = context.user_data.get('complex_points', 0)
        difficulty = context.user_data.get('complex_difficulty', 'beginner')

        # Создаем комплекс
        from database_postgres import add_complex, add_complex_exercise
        complex_id = add_complex(name, description, complex_type, points, difficulty=difficulty)

        if not complex_id:
            error_text = f"❌ Ошибка: комплекс с названием '{name}' уже существует!"
            try:
                await query.edit_message_text(error_text)
            except:
                await update.message.reply_text(error_text)
            return ConversationHandler.END

        # Добавляем упражнения в комплекс
        for order_index, exercise_id in enumerate(selected_exercises):
            add_complex_exercise(complex_id, exercise_id, reps=1, order_index=order_index)

        # Отправляем уведомление в канал
        try:
            complex_data = {
                'id': complex_id,
                'name': name,
                'description': description,
                'difficulty': difficulty
            }
            creator_name = update.effective_user.first_name or "Админ"
            await channel_notifications.notify_new_complex(context.bot, complex_data, creator_name)
        except Exception as e:
            logger.error(f"Ошибка отправки уведомления о комплексе: {e}")

        # Словари для перевода
        type_names = {
            'for_time': '⏱ На время',
            'for_reps': '🔢 На количество'
        }
        difficulty_names = {
            'beginner': '🙂 Новичок',
            'pro': '🤓 Профи'
        }

        # Экранируем спецсимволы для Markdown
        safe_name = escape_markdown(name)
        safe_description = escape_markdown(description)

        text = (
            f"✅ **КОМПЛЕКС СОЗДАН!**\n\n"
            f"📦 **{safe_name}**\n"
            f"📝 {safe_description}\n"
            f"🎯 Тип: {type_names.get(complex_type, complex_type)}\n"
            f"⭐ Очки: {points}\n"
            f"📊 Сложность: {difficulty_names.get(difficulty, difficulty)}\n"
            f"🏋️ Упражнений: {len(selected_exercises)}"
        )

        keyboard = [[InlineKeyboardButton("◀️ В комплексы", callback_data="admin_complexes")]]
        reply_markup = InlineKeyboardMarkup(keyboard)

        try:
            await query.edit_message_text(text, reply_markup=reply_markup, parse_mode='Markdown')
        except Exception as e:
            # Если Markdown сломался, отправляем без форматирования
            logger.error(f"Markdown error: {e}")
            plain_text = (
                f"✅ КОМПЛЕКС СОЗДАН!\n\n"
                f"📦 {name}\n"
                f"📝 {description}\n"
                f"🎯 Тип: {type_names.get(complex_type, complex_type)}\n"
                f"⭐ Очки: {points}\n"
                f"📊 Сложность: {difficulty_names.get(difficulty, difficulty)}\n"
                f"🏋️ Упражнений: {len(selected_exercises)}"
            )
            try:
                await query.edit_message_text(plain_text, reply_markup=reply_markup)
            except:
                await update.message.reply_text(plain_text, reply_markup=reply_markup)

        return ConversationHandler.END

    except Exception as e:
        logger.error(f"Ошибка при создании комплекса: {e}")
        try:
            await update.message.reply_text(f"❌ Произошла ошибка: {str(e)}")
        except:
            pass
        return ConversationHandler.END

    finally:
        # ГАРАНТИРОВАННО очищаем данные в любом случае
        context.user_data.clear()


async def admin_cancel_complex(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Отменяет создание комплекса."""
    try:
        await update.message.reply_text("❌ Создание комплекса отменено")
    except Exception as e:
        logger.error(f"Ошибка при отправке сообщения об отмене: {e}")
    finally:
        # ГАРАНТИРОВАННО очищаем данные
        context.user_data.clear()
    return ConversationHandler.END


async def admin_list_complexes_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показывает список всех комплексов с пагинацией по 7 штук."""
    query = update.callback_query
    await safe_callback_answer(query)

    from database_postgres import get_all_complexes

    # Получаем номер страницы из callback_data
    page = 0
    if query.data and query.data.startswith("admin_list_complexes_page_"):
        page = int(query.data.split("_")[-1])

    complexes = get_all_complexes(active_only=False)

    # Словари для перевода
    type_names = {
        'for_time': '⏱ На время',
        'for_reps': '🔢 На количество'
    }
    difficulty_names = {
        'beginner': '🙂 Новичок',
        'pro': '🤓 Профи'
    }

    if not complexes:
        text = "📋 **СПИСОК КОМПЛЕКСОВ**\n\n❌ Комплексов пока нет"
        keyboard = [[InlineKeyboardButton("◀️ В комплексы", callback_data="admin_complexes")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        try:
            await query.edit_message_text(text, reply_markup=reply_markup, parse_mode='Markdown')
        except Exception as e:
            if "not modified" not in str(e):
                logger.error(f"Ошибка при редактировании сообщения: {e}")
        return

    # Пагинация по 7 комплексов на страницу
    per_page = 7
    total_pages = (len(complexes) + per_page - 1) // per_page
    start_idx = page * per_page
    end_idx = start_idx + per_page
    page_complexes = complexes[start_idx:end_idx]

    # Формируем компактные кнопки
    keyboard = []
    for comp in page_complexes:
        comp_id, name, description, type_, points, difficulty = comp

        type_name = type_names.get(type_, type_)
        difficulty_name = difficulty_names.get(difficulty, difficulty)

        # Компактная кнопка: название, тип, сложность и очки
        button_text = f"📦 {name} | {type_name} | {difficulty_name} | ⭐{points}"

        keyboard.append([InlineKeyboardButton(button_text, callback_data=f"admin_view_complex_{comp_id}")])

    # Добавляем навигацию пагинации
    nav_row = []
    if page > 0:
        nav_row.append(InlineKeyboardButton("⬅️ Пред.", callback_data=f"admin_list_complexes_page_{page-1}"))
    if page < total_pages - 1:
        nav_row.append(InlineKeyboardButton("След. ➡️", callback_data=f"admin_list_complexes_page_{page+1}"))

    if nav_row:
        keyboard.append(nav_row)

    keyboard.append([InlineKeyboardButton("◀️ В комплексы", callback_data="admin_complexes")])

    text = f"📋 **СПИСОК КОМПЛЕКСОВ** (стр. {page + 1}/{total_pages})\n\nВыберите комплекс для просмотра:"

    reply_markup = InlineKeyboardMarkup(keyboard)
    try:
        await query.edit_message_text(text, reply_markup=reply_markup, parse_mode='Markdown')
    except Exception as e:
        if "not modified" not in str(e):
            logger.error(f"Ошибка при редактировании сообщения: {e}")


async def admin_view_complex_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показывает детальную информацию о комплексе."""
    query = update.callback_query
    await safe_callback_answer(query)

    # Получаем complex_id из callback_data
    complex_id = int(query.data.split("_")[-1])

    from database_postgres import get_complex_by_id, get_complex_exercises

    complex_data = get_complex_by_id(complex_id)

    if not complex_data:
        text = "❌ Комплекс не найден"
        keyboard = [[InlineKeyboardButton("◀️ К списку", callback_data="admin_list_complexes")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(text, reply_markup=reply_markup)
        return

    comp_id, name, description, type_, points, difficulty = complex_data

    # Словари для перевода
    type_names = {
        'for_time': '⏱ На время',
        'for_reps': '🔢 На количество'
    }
    difficulty_names = {
        'beginner': '🙂 Новичок',
        'pro': '🤓 Профи'
    }

    type_name = type_names.get(type_, type_)
    difficulty_name = difficulty_names.get(difficulty, difficulty)

    # Получаем упражнения комплекса
    exercises = get_complex_exercises(complex_id)

    # Формируем текст с упражнениями
    exercises_text = ""
    if exercises:
        for idx, ex in enumerate(exercises, 1):
            ce_id, ex_id, ex_name, metric, reps = ex
            metric_icon = "⏱" if metric == "time" else "🔢"
            exercises_text += f"{idx}. {metric_icon} {ex_name}\n"
    else:
        exercises_text = "Упражнений нет"

    # Экранируем спецсимволы для Markdown
    safe_name = escape_markdown(name)
    safe_description = escape_markdown(description)

    text = (
        f"📦 **{safe_name}**\n\n"
        f"📝 **Описание:** {safe_description}\n\n"
        f"🎯 **Тип:** {type_name}\n"
        f"⭐ **Очки:** {points}\n"
        f"📊 **Сложность:** {difficulty_name}\n\n"
        f"🏋️ **Упражнения ({len(exercises)}):**\n{exercises_text}"
    )

    keyboard = [
        [InlineKeyboardButton("🗑 Удалить", callback_data=f"admin_delete_complex_{complex_id}")],
        [InlineKeyboardButton("◀️ К списку", callback_data="admin_list_complexes")]
    ]

    reply_markup = InlineKeyboardMarkup(keyboard)
    try:
        await query.edit_message_text(text, reply_markup=reply_markup, parse_mode='Markdown')
    except Exception as e:
        if "not modified" not in str(e):
            logger.error(f"Ошибка при просмотре комплекса: {e}")
            # Если Markdown сломался, отправляем без форматирования
            try:
                plain_text = (
                    f"📦 {name}\n\n"
                    f"📝 Описание: {description}\n\n"
                    f"🎯 Тип: {type_name}\n"
                    f"⭐ Очки: {points}\n"
                    f"📊 Сложность: {difficulty_name}\n\n"
                    f"🏋️ Упражнения ({len(exercises)}):\n{exercises_text}"
                )
                await query.edit_message_text(plain_text, reply_markup=reply_markup)
            except:
                pass


async def admin_delete_complex_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Удаление комплекса."""
    query = update.callback_query
    await safe_callback_answer(query)

    # Получаем complex_id из callback_data
    complex_id = int(query.data.split("_")[-1])

    from database_postgres import get_complex_by_id

    complex_data = get_complex_by_id(complex_id)

    if not complex_data:
        text = "❌ Комплекс не найден"
        keyboard = [[InlineKeyboardButton("◀️ К списку", callback_data="admin_list_complexes")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(text, reply_markup=reply_markup)
        return

    complex_name = complex_data[1]

    text = f"🗑 **УДАЛЕНИЕ КОМПЛЕКСА**\n\n❓ Вы действительно хотите удалить комплекс **{complex_name}**?\n\n⚠️ Все упражнения комплекса также будут удалены!"

    keyboard = [
        [InlineKeyboardButton("✅ Да, удалить", callback_data=f"admin_confirm_delete_complex_{complex_id}")],
        [InlineKeyboardButton("❌ Отмена", callback_data=f"admin_view_complex_{complex_id}")]
    ]

    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.edit_message_text(text, reply_markup=reply_markup, parse_mode='Markdown')


async def admin_confirm_delete_complex_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Подтверждение удаления комплекса."""
    query = update.callback_query
    await safe_callback_answer(query)

    # Получаем complex_id из callback_data
    complex_id = int(query.data.split("_")[-1])

    from database_postgres import get_complex_by_id, delete_complex

    complex_data = get_complex_by_id(complex_id)

    if not complex_data:
        text = "❌ Комплекс не найден"
        keyboard = [[InlineKeyboardButton("◀️ К списку", callback_data="admin_list_complexes")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(text, reply_markup=reply_markup)
        return

    complex_name = complex_data[1]

    # Удаляем комплекс из БД
    try:
        delete_complex(complex_id)
        text = f"✅ **КОМПЛЕКС УДАЛЕН**\n\nКомплекс **{complex_name}** успешно удален!"
    except Exception as e:
        logger.error(f"Ошибка удаления комплекса: {e}")
        text = f"❌ Ошибка при удалении комплекса: {e}"

    keyboard = [[InlineKeyboardButton("◀️ К списку", callback_data="admin_list_complexes")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.edit_message_text(text, reply_markup=reply_markup, parse_mode='Markdown')



async def admin_view_exercise_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показывает детальную информацию об упражнении."""
    query = update.callback_query
    await safe_callback_answer(query)

    # Получаем exercise_id из callback_data
    exercise_id = int(query.data.split("_")[-1])

    from database_postgres import get_exercise_by_id

    exercise = get_exercise_by_id(exercise_id)

    if not exercise:
        text = "❌ Упражнение не найдено"
        keyboard = [[InlineKeyboardButton("◀️ К списку", callback_data="admin_list_exercises")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(text, reply_markup=reply_markup)
        return

    ex_id, name, description, metric, points, week, difficulty = exercise
    metric_names = {'reps': 'Повторы', 'time': 'Время', 'weight': 'Вес', 'distance': 'Дистанция'}
    metric_text = metric_names.get(metric, metric)
    difficulty_text = 'Новичок' if difficulty == 'newbie' else 'Профи'
    week_text = f"Неделя {week}" if week else "Любая неделя"

    text = (
        f"🏋️ **{name}**\n\n"
        f"📝 **Описание:** {description}\n\n"
        f"📊 **Тип:** {metric_text}\n"
        f"⭐ **Очки:** {points}\n"
        f"🎯 **Сложность:** {difficulty_text}\n"
        f"📅 **Неделя:** {week_text}\n"
    )

    keyboard = [
        [InlineKeyboardButton("✏️ Редактировать", callback_data=f"admin_edit_exercise_{exercise_id}")],
        [InlineKeyboardButton("🗑 Удалить", callback_data=f"admin_delete_exercise_{exercise_id}")],
        [InlineKeyboardButton("◀️ К списку", callback_data="admin_list_exercises")]
    ]

    reply_markup = InlineKeyboardMarkup(keyboard)
    try:
        await query.edit_message_text(text, reply_markup=reply_markup, parse_mode='Markdown')
    except Exception as e:
        if "not modified" not in str(e):
            logger.error(f"Ошибка при просмотре упражнения: {e}")
        else:
            logger.debug(f"Сообщение не изменилось, пропускаем: {e}")


async def admin_edit_exercise_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Начинает процесс редактирования упражнения."""
    query = update.callback_query
    await safe_callback_answer(query)

    # Получаем exercise_id из callback_data
    exercise_id = int(query.data.split("_")[-1])

    # Сохраняем exercise_id в context
    context.user_data['edit_exercise_id'] = exercise_id

    keyboard = [
        [InlineKeyboardButton("📝 Название", callback_data=f"edit_name_{exercise_id}")],
        [InlineKeyboardButton("📝 Описание", callback_data=f"edit_desc_{exercise_id}")],
        [InlineKeyboardButton("📊 Метрика", callback_data=f"edit_metric_{exercise_id}")],
        [InlineKeyboardButton("⭐ Очки", callback_data=f"edit_points_{exercise_id}")],
        [InlineKeyboardButton("🎯 Сложность", callback_data=f"edit_diff_{exercise_id}")],
        [InlineKeyboardButton("❌ Отмена", callback_data=f"admin_cancel_edit_{exercise_id}")]
    ]

    text = "✏️ **РЕДАКТИРОВАНИЕ УПРАЖНЕНИЯ**\n\nВыберите, что хотите изменить:"

    reply_markup = InlineKeyboardMarkup(keyboard)
    try:
        await query.edit_message_text(text, reply_markup=reply_markup, parse_mode='Markdown')
    except Exception as e:
        if "not modified" not in str(e):
            logger.error(f"Ошибка при редактировании сообщения: {e}")


async def admin_edit_exercise_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Редактирует название упражнения."""
    query = update.callback_query
    await safe_callback_answer(query)

    # Извлекаем exercise_id из callback_data
    if query.data and query.data.startswith("edit_name_"):
        exercise_id = int(query.data.split("_")[-1])
        context.user_data['edit_exercise_id'] = exercise_id
    else:
        exercise_id = context.user_data.get('edit_exercise_id')

    keyboard = [[InlineKeyboardButton("❌ Отмена", callback_data=f"admin_cancel_edit_{exercise_id}")]]
    await query.edit_message_text(
        "✏️ **РЕДАКТИРОВАНИЕ НАЗВАНИЯ**\n\nВведите новое название упражнения:",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode='Markdown'
    )

    return EDIT_EXERCISE_NAME


async def admin_edit_exercise_desc(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Редактирует описание упражнения."""
    query = update.callback_query
    await safe_callback_answer(query)

    # Извлекаем exercise_id из callback_data
    if query.data and query.data.startswith("edit_desc_"):
        exercise_id = int(query.data.split("_")[-1])
        context.user_data['edit_exercise_id'] = exercise_id
    else:
        exercise_id = context.user_data.get('edit_exercise_id')

    keyboard = [[InlineKeyboardButton("❌ Отмена", callback_data=f"admin_cancel_edit_{exercise_id}")]]
    await query.edit_message_text(
        "✏️ **РЕДАКТИРОВАНИЕ ОПИСАНИЯ**\n\nВведите новое описание упражнения:",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode='Markdown'
    )

    return EDIT_EXERCISE_DESC


async def admin_edit_exercise_metric(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Редактирует метрику упражнения."""
    query = update.callback_query
    await safe_callback_answer(query)

    # Извлекаем exercise_id из callback_data
    if query.data and query.data.startswith("edit_metric_"):
        exercise_id = int(query.data.split("_")[-1])
        context.user_data['edit_exercise_id'] = exercise_id
    else:
        exercise_id = context.user_data.get('edit_exercise_id')

    keyboard = [
        [
            InlineKeyboardButton("🔢 Повторы", callback_data=f"edit_metric_reps_{exercise_id}"),
            InlineKeyboardButton("⏱ Время (мин)", callback_data=f"edit_metric_time_{exercise_id}")
        ],
        [
            InlineKeyboardButton("🏋 Вес (кг)", callback_data=f"edit_metric_weight_{exercise_id}"),
            InlineKeyboardButton("🏃 Дистанция (км)", callback_data=f"edit_metric_distance_{exercise_id}")
        ],
        [InlineKeyboardButton("❌ Отмена", callback_data=f"admin_cancel_edit_{exercise_id}")]
    ]

    await query.edit_message_text(
        "✏️ **РЕДАКТИРОВАНИЕ МЕТРИКИ**\n\nВыберите новый тип метрики:",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode='Markdown'
    )

    return EDIT_EXERCISE_METRIC


async def admin_edit_exercise_points(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Редактирует очки упражнения."""
    query = update.callback_query
    await safe_callback_answer(query)

    # Извлекаем exercise_id из callback_data
    if query.data and query.data.startswith("edit_points_"):
        exercise_id = int(query.data.split("_")[-1])
        context.user_data['edit_exercise_id'] = exercise_id
    else:
        exercise_id = context.user_data.get('edit_exercise_id')

    keyboard = [[InlineKeyboardButton("❌ Отмена", callback_data=f"admin_cancel_edit_{exercise_id}")]]
    await query.edit_message_text(
        "✏️ **РЕДАКТИРОВАНИЕ ОЧКОВ**\n\nВведите новое количество очков:",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode='Markdown'
    )

    return EDIT_EXERCISE_POINTS


async def admin_edit_exercise_diff(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Редактирует сложность упражнения."""
    query = update.callback_query
    await safe_callback_answer(query)

    # Извлекаем exercise_id из callback_data
    if query.data and query.data.startswith("edit_diff_"):
        exercise_id = int(query.data.split("_")[-1])
        context.user_data['edit_exercise_id'] = exercise_id
    else:
        exercise_id = context.user_data.get('edit_exercise_id')

    keyboard = [
        [
            InlineKeyboardButton("🙂 Новичок", callback_data=f"edit_diff_beginner_{exercise_id}"),
            InlineKeyboardButton("🤓 Профи", callback_data=f"edit_diff_pro_{exercise_id}")
        ],
        [InlineKeyboardButton("❌ Отмена", callback_data=f"admin_cancel_edit_{exercise_id}")]
    ]

    await query.edit_message_text(
        "✏️ **РЕДАКТИРОВАНИЕ СЛОЖНОСТИ**\n\nВыберите новый уровень сложности:",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode='Markdown'
    )

    return EDIT_EXERCISE_DIFF


async def admin_delete_exercise_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Удаление упражнения."""
    query = update.callback_query
    await safe_callback_answer(query)

    # Получаем exercise_id из callback_data
    exercise_id = int(query.data.split("_")[-1])

    from database_postgres import get_exercise_by_id

    exercise = get_exercise_by_id(exercise_id)

    if not exercise:
        text = "❌ Упражнение не найдено"
        keyboard = [[InlineKeyboardButton("◀️ К списку", callback_data="admin_list_exercises")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(text, reply_markup=reply_markup)
        return

    exercise_name = exercise[1]

    text = f"🗑 **УДАЛЕНИЕ УПРАЖНЕНИЯ**\n\n❓ Вы действительно хотите удалить упражнение **{exercise_name}**?"

    keyboard = [
        [InlineKeyboardButton("✅ Да, удалить", callback_data=f"admin_confirm_delete_exercise_{exercise_id}")],
        [InlineKeyboardButton("❌ Отмена", callback_data=f"admin_view_exercise_{exercise_id}")]
    ]

    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.edit_message_text(text, reply_markup=reply_markup, parse_mode='Markdown')


async def admin_confirm_delete_exercise_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Подтверждение удаления упражнения."""
    query = update.callback_query
    await safe_callback_answer(query)

    # Получаем exercise_id из callback_data
    exercise_id = int(query.data.split("_")[-1])

    from database_postgres import get_exercise_by_id, delete_exercise

    exercise = get_exercise_by_id(exercise_id)

    if not exercise:
        text = "❌ Упражнение не найдено"
        keyboard = [[InlineKeyboardButton("◀️ К списку", callback_data="admin_list_exercises")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(text, reply_markup=reply_markup)
        return

    exercise_name = exercise[1]

    # Удаляем упражнение из БД
    try:
        delete_exercise(exercise_id)
        text = f"✅ **УПРАЖНЕНИЕ УДАЛЕНО**\n\nУпражнение **{exercise_name}** успешно удалено!"
    except Exception as e:
        logger.error(f"Ошибка удаления упражнения: {e}")
        text = f"❌ Ошибка при удалении упражнения: {e}"

    keyboard = [[InlineKeyboardButton("◀️ К списку", callback_data="admin_list_exercises")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.edit_message_text(text, reply_markup=reply_markup, parse_mode='Markdown')


# ==================== ФУНКЦИИ РЕДАКТИРОВАНИЯ УПРАЖНЕНИЙ ====================

async def admin_edit_exercise_name_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обрабатывает ввод нового названия упражнения."""
    if not update.message or not update.message.text:
        return EDIT_EXERCISE_NAME

    new_name = update.message.text.strip()

    if len(new_name) > 100:
        await update.message.reply_text("❌ Слишком длинное название (макс. 100 символов)")
        return EDIT_EXERCISE_NAME

    if len(new_name) == 0:
        await update.message.reply_text("❌ Название не может быть пустым")
        return EDIT_EXERCISE_NAME

    exercise_id = context.user_data.get('edit_exercise_id')
    if not exercise_id:
        await update.message.reply_text("❌ Ошибка: упражнение не выбрано")
        return ConversationHandler.END

    from database_postgres import update_exercise

    try:
        update_exercise(exercise_id, name=new_name)
        await update.message.reply_text(f"✅ Название изменено на: {new_name}")
    except Exception as e:
        logger.error(f"Ошибка обновления названия: {e}")
        await update.message.reply_text(f"❌ Ошибка при обновлении: {e}")

    context.user_data.clear()
    return ConversationHandler.END


async def admin_edit_exercise_desc_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обрабатывает ввод нового описания упражнения."""
    if not update.message or not update.message.text:
        return EDIT_EXERCISE_DESC

    new_desc = update.message.text.strip()

    if len(new_desc) > 500:
        await update.message.reply_text("❌ Слишком длинное описание (макс. 500 символов)")
        return EDIT_EXERCISE_DESC

    exercise_id = context.user_data.get('edit_exercise_id')
    if not exercise_id:
        await update.message.reply_text("❌ Ошибка: упражнение не выбрано")
        return ConversationHandler.END

    from database_postgres import update_exercise

    try:
        update_exercise(exercise_id, description=new_desc)
        await update.message.reply_text("✅ Описание обновлено")
    except Exception as e:
        logger.error(f"Ошибка обновления описания: {e}")
        await update.message.reply_text(f"❌ Ошибка при обновлении: {e}")

    context.user_data.clear()
    return ConversationHandler.END


async def admin_edit_exercise_metric_select(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обрабатывает выбор новой метрики упражнения."""
    query = update.callback_query
    await safe_callback_answer(query)

    # Извлекаем metric и exercise_id из callback_data (формат: edit_metric_reps_123)
    parts = query.data.split('_')
    metric = parts[-2] if len(parts) >= 3 else parts[-1]  # reps, time, weight, distance
    exercise_id = int(parts[-1]) if len(parts) >= 3 else context.user_data.get('edit_exercise_id')

    if not exercise_id:
        await query.edit_message_text("❌ Ошибка: упражнение не выбрано")
        return ConversationHandler.END

    from database_postgres import update_exercise

    try:
        update_exercise(exercise_id, metric=metric)

        metric_names = {
            'reps': 'Повторы',
            'time': 'Время (мин)',
            'weight': 'Вес (кг)',
            'distance': 'Дистанция (км)'
        }

        await query.edit_message_text(
            f"✅ Метрика изменена на: {metric_names.get(metric, metric)}"
        )
    except Exception as e:
        logger.error(f"Ошибка обновления метрики: {e}")
        await query.edit_message_text(f"❌ Ошибка при обновлении: {e}")

    context.user_data.clear()
    return ConversationHandler.END


async def admin_edit_exercise_points_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обрабатывает ввод новых очков упражнения."""
    if not update.message or not update.message.text:
        return EDIT_EXERCISE_POINTS

    points_text = update.message.text.strip()

    try:
        points = int(points_text)
        if points < 1 or points > 1000:
            await update.message.reply_text("❌ Очки должны быть от 1 до 1000")
            return EDIT_EXERCISE_POINTS
    except ValueError:
        await update.message.reply_text("❌ Введите число от 1 до 1000")
        return EDIT_EXERCISE_POINTS

    exercise_id = context.user_data.get('edit_exercise_id')
    if not exercise_id:
        await update.message.reply_text("❌ Ошибка: упражнение не выбрано")
        return ConversationHandler.END

    from database_postgres import update_exercise

    try:
        update_exercise(exercise_id, points=points)
        await update.message.reply_text(f"✅ Очки изменены на: {points}")
    except Exception as e:
        logger.error(f"Ошибка обновления очков: {e}")
        await update.message.reply_text(f"❌ Ошибка при обновлении: {e}")

    context.user_data.clear()
    return ConversationHandler.END


async def admin_edit_exercise_diff_select(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обрабатывает выбор новой сложности упражнения."""
    query = update.callback_query
    await safe_callback_answer(query)

    # Извлекаем diff и exercise_id из callback_data (формат: edit_diff_beginner_123)
    parts = query.data.split('_')
    diff = parts[-2] if len(parts) >= 3 else parts[-1]  # beginner, pro
    exercise_id = int(parts[-1]) if len(parts) >= 3 else context.user_data.get('edit_exercise_id')

    if not exercise_id:
        await query.edit_message_text("❌ Ошибка: упражнение не выбрано")
        return ConversationHandler.END

    diff_map = {'beginner': 'newbie', 'pro': 'pro'}
    difficulty = diff_map.get(diff, 'newbie')

    from database_postgres import update_exercise

    try:
        update_exercise(exercise_id, difficulty=difficulty)

        difficulty_text = 'Новичок' if difficulty == 'newbie' else 'Профи'
        await query.edit_message_text(
            f"✅ Сложность изменена на: {difficulty_text}"
        )
    except Exception as e:
        logger.error(f"Ошибка обновления сложности: {e}")
        await query.edit_message_text(f"❌ Ошибка при обновлении: {e}")

    context.user_data.clear()
    return ConversationHandler.END


async def admin_cancel_edit_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Отменяет редактирование упражнения."""
    query = update.callback_query
    await safe_callback_answer(query)

    exercise_id = context.user_data.get('edit_exercise_id')

    context.user_data.clear()

    keyboard = [[InlineKeyboardButton("◀️ К списку", callback_data="admin_list_exercises")]]

    try:
        await query.edit_message_text(
            "❌ Редактирование отменено",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
    except Exception as e:
        if "not modified" not in str(e):
            logger.error(f"Ошибка при отмене редактирования: {e}")

    return ConversationHandler.END


# ==================== CONVERSATION HANDLERS ====================
# Создаём в конце файла, чтобы все функции были определены

# Создаём ConversationHandler для добавления упражнений
admin_exercise_add_conversation = ConversationHandler(
    entry_points=[CallbackQueryHandler(admin_exercise_add_start, pattern='^admin_add_exercise$')],
    states={
        EXERCISE_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, admin_exercise_add_name)],
        EXERCISE_DESC: [MessageHandler(filters.TEXT & ~filters.COMMAND, admin_exercise_add_desc)],
        EXERCISE_METRIC: [CallbackQueryHandler(admin_exercise_add_metric, pattern='^ex_metric_')],
        EXERCISE_POINTS: [MessageHandler(filters.TEXT & ~filters.COMMAND, admin_exercise_add_points)],
        EXERCISE_DIFF: [CallbackQueryHandler(admin_exercise_add_diff, pattern='^ex_diff_')],
    },
    fallbacks=[
        CommandHandler('cancel', admin_cancel),
        CallbackQueryHandler(admin_cancel, pattern='^admin_cancel_exercise$')
    ],
)

# Создаём ConversationHandler для редактирования упражнений
admin_exercise_edit_conversation = ConversationHandler(
    entry_points=[
        CallbackQueryHandler(admin_edit_exercise_callback, pattern='^admin_edit_exercise_'),
        CallbackQueryHandler(admin_edit_exercise_name, pattern='^edit_name_'),
        CallbackQueryHandler(admin_edit_exercise_desc, pattern='^edit_desc_'),
        CallbackQueryHandler(admin_edit_exercise_metric, pattern='^edit_metric_'),
        CallbackQueryHandler(admin_edit_exercise_points, pattern='^edit_points_'),
        CallbackQueryHandler(admin_edit_exercise_diff, pattern='^edit_diff_'),
    ],
    states={
        EDIT_EXERCISE_NAME: [
            MessageHandler(filters.TEXT & ~filters.COMMAND, admin_edit_exercise_name_input),
            CallbackQueryHandler(admin_cancel_edit_callback, pattern='^admin_cancel_edit_')
        ],
        EDIT_EXERCISE_DESC: [
            MessageHandler(filters.TEXT & ~filters.COMMAND, admin_edit_exercise_desc_input),
            CallbackQueryHandler(admin_cancel_edit_callback, pattern='^admin_cancel_edit_')
        ],
        EDIT_EXERCISE_METRIC: [
            CallbackQueryHandler(admin_edit_exercise_metric_select, pattern='^edit_metric_'),
            CallbackQueryHandler(admin_cancel_edit_callback, pattern='^admin_cancel_edit_')
        ],
        EDIT_EXERCISE_POINTS: [
            MessageHandler(filters.TEXT & ~filters.COMMAND, admin_edit_exercise_points_input),
            CallbackQueryHandler(admin_cancel_edit_callback, pattern='^admin_cancel_edit_')
        ],
        EDIT_EXERCISE_DIFF: [
            CallbackQueryHandler(admin_edit_exercise_diff_select, pattern='^edit_diff_'),
            CallbackQueryHandler(admin_cancel_edit_callback, pattern='^admin_cancel_edit_')
        ],
    },
    fallbacks=[
        CommandHandler('cancel', admin_cancel_edit_callback),
        CallbackQueryHandler(admin_cancel_edit_callback, pattern='^admin_cancel_edit_')
    ],
)

# Создаём ConversationHandler для добавления челленджев
admin_challenge_add_conversation = ConversationHandler(
    entry_points=[CallbackQueryHandler(admin_challenge_add_start, pattern='^admin_add_challenge$')],
    states={
        CHALLENGE_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, admin_challenge_add_name)],
        CHALLENGE_DESC: [MessageHandler(filters.TEXT & ~filters.COMMAND, admin_challenge_add_desc)],
        CHALLENGE_MULTI_EXERCISE_SELECT: [
            CallbackQueryHandler(admin_challenge_multi_exercise_select, pattern='^ch_multi_ex_')
        ],
        CHALLENGE_METRIC: [CallbackQueryHandler(admin_challenge_add_metric, pattern='^ch_metric_')],
        CHALLENGE_TARGET_VALUE: [MessageHandler(filters.TEXT & ~filters.COMMAND, admin_challenge_add_target_value)],
        CHALLENGE_START_DATE: [MessageHandler(filters.TEXT & ~filters.COMMAND, admin_challenge_add_start_date)],
        CHALLENGE_END_DATE: [MessageHandler(filters.TEXT & ~filters.COMMAND, admin_challenge_add_end_date)],
        CHALLENGE_BONUS_POINTS: [MessageHandler(filters.TEXT & ~filters.COMMAND, admin_challenge_add_bonus_points)],
    },
    fallbacks=[
        CommandHandler('cancel', admin_challenge_cancel),
        CallbackQueryHandler(admin_challenge_cancel, pattern='^admin_cancel_challenge$')
    ],
)

# ==================== CONVERSATION HANDLER ДЛЯ КОМПЛЕКСОВ ====================

admin_complex_add_conversation = ConversationHandler(
    entry_points=[CallbackQueryHandler(admin_add_complex_callback, pattern='^admin_add_complex$')],
    states={
        COMPLEX_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, admin_complex_name_input)],
        COMPLEX_DESC: [MessageHandler(filters.TEXT & ~filters.COMMAND, admin_complex_desc_input)],
        COMPLEX_TYPE: [CallbackQueryHandler(admin_complex_type_select, pattern='^complex_type_')],
        COMPLEX_POINTS: [MessageHandler(filters.TEXT & ~filters.COMMAND, admin_complex_points_input)],
        COMPLEX_DIFFICULTY: [CallbackQueryHandler(admin_complex_difficulty_select, pattern='^complex_diff_')],
        COMPLEX_EXERCISE_SELECT: [
            CallbackQueryHandler(admin_complex_exercise_toggle, pattern='^complex_ex_'),
            CallbackQueryHandler(admin_complex_exercise_done, pattern='^complex_ex_done')
        ],
    },
    fallbacks=[
        CommandHandler('cancel', admin_cancel_complex),
        CallbackQueryHandler(admin_cancel_complex, pattern='^admin_cancel_complex')
    ],
)
