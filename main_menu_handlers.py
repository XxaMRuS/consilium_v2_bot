from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes


async def show_main_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Показать главное меню с inline-кнопками"""
    from database_postgres import get_user_coin_balance, get_user_scoreboard_total, is_admin, is_owner

    user_id = update.effective_user.id
    user_first_name = update.effective_user.first_name or "Друг"

    text = f"👋 Привет, **{user_first_name}**! Добро пожаловать в фитнес-бот!\n\n"

    # Получаем баланс FRuN монет
    try:
        frun_balance = get_user_coin_balance(user_id)
        text += f"💎 **FRuN монеты:** {frun_balance}\n"
        text += f"💡 Валюта бота (покупки, награды)\n\n"
    except Exception as e:
        text += f"💎 **FRuN монеты:** Н/Д\n"
        text += f"💡 Валюта бота (покупки, награды)\n\n"

    # Получаем спортивные очки для PvP
    try:
        pvp_points = get_user_scoreboard_total(user_id)
        text += f"⚡ **Спортивные очки:** {pvp_points}\n"
        text += f"💡 Зарабатываются тренировками, используются для PvP\n\n"
    except Exception as e:
        text += f"⚡ **Спортивные очки:** Н/Д\n"
        text += f"💡 Зарабатываются тренировками, используются для PvP\n\n"

    # Добавляем информацию об очках на Горе
    text += f"⭐ **Очки на Горе:** Рейтинговая система\n"
    text += f"💡 Отдельная система рейтинга"

    text += "\n\n━━━━━━━━━━━━━━━━━━━━━━\n"
    text += "🎯 **Выбери раздел:**"

    keyboard = [
        [
            InlineKeyboardButton("⛰️ Гора Успеха", callback_data="mountain"),
            InlineKeyboardButton("🏋️ Спорт", callback_data="sport"),
        ],
        [
            InlineKeyboardButton("🔥 PvP вызовы", callback_data="pvp"),
            InlineKeyboardButton("🏆 Зал славы", callback_data="hall_of_fame"),
        ],
        [
            InlineKeyboardButton("👤 Профиль", callback_data="profile"),
        ],
    ]

    # Добавляем админ-кнопку для админов
    try:
        if is_admin(user_id):
            keyboard.append([
                InlineKeyboardButton("⚙️ Админ", callback_data="admin"),
            ])
    except:
        pass

    # Добавляем кнопку собственника
    try:
        if is_owner(user_id):
            keyboard.append([
                InlineKeyboardButton("🔧 Панель", callback_data="owner_menu"),
            ])
    except:
        pass

    reply_markup = InlineKeyboardMarkup(keyboard)

    if update.message:
        await update.message.reply_text(text, reply_markup=reply_markup, parse_mode='Markdown')
    elif update.callback_query:
        await update.callback_query.edit_message_text(text, reply_markup=reply_markup, parse_mode='Markdown')
        await update.callback_query.answer()