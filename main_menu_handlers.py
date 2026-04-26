from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes


async def show_main_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Показать главное меню с inline-кнопками"""
    from database_postgres import async_get_user_coin_balance, async_get_fun_fuel_balance, get_user_mountain_stats, is_admin, is_owner

    user_id = update.effective_user.id
    user_first_name = update.effective_user.first_name or "Друг"

    text = f"👋 Привет, **{user_first_name}**! Добро пожаловать в фитнес-бот!\n\n"

    # Получаем баланс FFCoin (АСИНХРОННО!)
    try:
        frun_balance = await async_get_user_coin_balance(user_id)
        text += f"💰 **FFCoin:** {frun_balance}\n"
        text += f"💡 Валюта для ставок\n\n"
    except Exception as e:
        text += f"💰 **FFCoin:** Н/Д\n"
        text += f"💡 Валюта для ставок\n\n"

    # Получаем тренировочные очки
    try:
        stats = get_user_mountain_stats(user_id)
        if stats:
            training_score = stats.get('score', 0)
            text += f"🏆 **Тренировочные очки:** {training_score}\n"
            text += f"💡 Очки за выполнение упражнений\n\n"
        else:
            text += f"🏆 **Тренировочные очки:** Н/Д\n"
            text += f"💡 Очки за выполнение упражнений\n\n"
    except Exception as e:
        text += f"🏆 **Тренировочные очки:** Н/Д\n"
        text += f"💡 Очки за выполнение упражнений\n\n"

    # Получаем FruNFuel (АСИНХРОННО!)
    try:
        fun_fuel = await async_get_fun_fuel_balance(user_id)
        text += f"⛽ **FruNFuel:** {fun_fuel}\n"
        text += f"💡 Очки на Горе Успеха"
    except Exception as e:
        text += f"⛽ **FruNFuel:** Н/Д\n"
        text += f"💡 Очки на Горе Успеха"

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