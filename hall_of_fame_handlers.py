# -*- coding: utf-8 -*-
# Обработчики Зала славы

import logging
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from champions_system import get_monthly_champions

logger = logging.getLogger(__name__)

HALL_OF_FAME_MENU = "hall_of_fame_menu"
HALL_OF_FAME_MONTH = "hall_of_fame_month"
HALL_OF_FAME_BACK = "hall_of_fame_back"

async def hall_of_fame_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показывает Зал славы."""
    query = update.callback_query

    try:
        await query.answer()
    except:
        pass

    # Получаем чемпионов за предыдущий месяц
    today = datetime.now()
    if today.month == 1:
        year = today.year - 1
        month = 12
    else:
        year = today.year
        month = today.month - 1

    champions = get_monthly_champions(year, month)

    if not champions:
        text = "🏆 **ЗАЛ СЛАВЫ**\n\n"
        text += f"Пока нет чемпионов за {month}.{year}\n\n"
        text += "💪 Выполняйте упражнения competitively на скорости,\n"
        text += "чтобы стать чемпионом!"

        keyboard = [[InlineKeyboardButton("◀️ В меню", callback_data="back_to_main")]]
        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")
        return

    # Группируем по упражнениям
    from collections import defaultdict
    exercises_champions = defaultdict(list)

    for champ in champions:
        exercise_id = champ[3]  # target_id
        exercises_champions[exercise_id].append(champ)

    # Формируем текст
    text = f"🏆 **ЗАЛ СЛАВЫ**\n"
    text += f"📊 {month}.{year}\n\n"

    for exercise_id, champs in exercises_champions.items():
        exercise_name = champs[0][13] or f"Упражнение #{exercise_id}"

        text += f"🥇 **{exercise_name}**\n"

        for champ in champs:
            position = champ[6]
            first_name = champ[14] or "Пользователь"
            username = champ[15]
            wins_score = champ[7]
            first_place_count = champ[8]
            second_place_count = champ[9]
            third_place_count = champ[10]

            if position == 1:
                emoji = "🥇"
            elif position == 2:
                emoji = "🥈"
            else:
                emoji = "🥉"

            username_str = f"@{username}" if username else "Нет username"
            text += f"{emoji} {first_name} ({username_str}) - {wins_score} победных очков\n"
            text += f"   ️🥇: {first_place_count}x, 🥈: {second_place_count}x, 🥉: {third_place_count}x\n"

        text += "\n"

    text += "💪 **Статистика побед:**\n"
    text += "🥇 1 место = 3 очка\n"
    text += "🥈 2 место = 2 очка\n"
    text += "🥉 3 место = 1 очко\n\n"

    text += "💡 Выполняйте упражнения на скорости,\n"
    text += "чтобы стать чемпионом!"

    keyboard = [[InlineKeyboardButton("◀️ В меню", callback_data="back_to_main")]]
    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")
