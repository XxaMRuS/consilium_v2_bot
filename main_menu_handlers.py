from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes


async def show_main_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Показать главное меню с inline-кнопками"""
    from database_postgres import get_user_coin_balance, get_user_scoreboard_total, is_admin, is_owner

    user_id = update.effective_user.id
    user_first_name = update.effective_user.first_name or "Друг"

    text = f"👋 Привет, **{user_first_name}**! Добро пожаловать в фитнес-бот!\n\n"

    # Получаем баланс FFCoin
    try:
        frun_balance = get_user_coin_balance(user_id)
        text += f"💰 **FFCoin:** {frun_balance}\n"
        text += f"💡 Валюта для ставок\n\n"
    except Exception as e:
        text += f"💰 **FFCoin:** Н/Д\n"
        text += f"💡 Валюта для ставок\n\n"

    # Получаем FruNStatus
    try:
        pvp_points = get_user_scoreboard_total(user_id)
        text += f"🏆 **FruNStatus:** {pvp_points}\n"
        text += f"💡 Твой ранг (каждые 100 = медаль!)\n\n"
    except Exception as e:
        text += f"🏆 **FruNStatus:** Н/Д\n"
        text += f"💡 Твой ранг (каждые 100 = медаль!)\n\n"

    # Добавляем информацию об FruNFuel
    text += f"⛽ **FruNFuel:** Очки на Горе Успеха\n"
    text += f"💡 Рейтинговая система"

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
            InlineKeyboardButton("🤖 AI Тренер", callback_data="ai_menu"),
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