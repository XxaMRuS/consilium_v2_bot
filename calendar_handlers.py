# -*- coding: utf-8 -*-
"""
Календарь тренировок пользователя
Показывает активность по дням месяца
"""
import logging
from datetime import datetime, timedelta
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, CallbackQueryHandler
from database_postgres import get_user_activity_calendar

logger = logging.getLogger(__name__)

# Константы для callback_data
CALENDAR = "calendar"
CALENDAR_PREV = "calendar_prev"
CALENDAR_NEXT = "calendar_next"
CALENDAR_BACK = "calendar_back"


async def calendar_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показывает календарь тренировок за текущий месяц"""
    query = update.callback_query if update.callback_query else update.message

    user_id = update.effective_user.id

    # Получаем текущий месяц и год
    now = datetime.now()
    year = context.user_data.get('calendar_year', now.year)
    month = context.user_data.get('calendar_month', now.month)

    # Сохраняем текущий месяц
    context.user_data['calendar_year'] = year
    context.user_data['calendar_month'] = month

    try:
        # Получаем данные календаря
        calendar_data = get_user_activity_calendar(user_id, year, month)

        # Формируем текст календаря
        text = format_calendar_text(year, month, calendar_data)

        # Создаем навигацию
        keyboard = create_calendar_navigation(year, month)

        reply_markup = InlineKeyboardMarkup(keyboard)

        if query.message:
            await query.edit_message_text(text, reply_markup=reply_markup, parse_mode="Markdown")
        else:
            await update.message.reply_text(text, reply_markup=reply_markup, parse_mode="Markdown")

    except Exception as e:
        logger.error(f"Ошибка при показе календаря: {e}")
        error_text = "❌ Не удалось загрузить календарь. Попробуйте позже."

        keyboard = [[InlineKeyboardButton("◀️ В меню", callback_data="sport")]]
        reply_markup = InlineKeyboardMarkup(keyboard)

        if query.message:
            await query.edit_message_text(error_text, reply_markup=reply_markup)
        else:
            await update.message.reply_text(error_text, reply_markup=reply_markup)


async def calendar_navigation(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обрабатывает навигацию по календарю"""
    query = update.callback_query
    await query.answer()

    action = query.data

    now = datetime.now()
    current_year = context.user_data.get('calendar_year', now.year)
    current_month = context.user_data.get('calendar_month', now.month)

    # Обрабатываем действие
    if action == CALENDAR_PREV:
        # Месяц назад
        current_month -= 1
        if current_month == 0:
            current_month = 12
            current_year -= 1
    elif action == CALENDAR_NEXT:
        # Месяц вперед
        current_month += 1
        if current_month == 13:
            current_month = 1
            current_year += 1
    elif action == CALENDAR_BACK:
        # Вернуться в спорт меню
        from sport_handlers import sport_menu
        await sport_menu(update, context)
        return

    # Ограничиваем диапазон (не даем уйти слишком далеко)
    max_year = now.year + 1
    min_year = now.year - 2

    if current_year > max_year:
        current_year = max_year
        current_month = now.month
    elif current_year < min_year:
        current_year = min_year
        current_month = 1

    # Сохраняем новые значения
    context.user_data['calendar_year'] = current_year
    context.user_data['calendar_month'] = current_month

    # Показываем календарь
    user_id = update.effective_user.id

    try:
        calendar_data = get_user_activity_calendar(user_id, current_year, current_month)
        text = format_calendar_text(current_year, current_month, calendar_data)
        keyboard = create_calendar_navigation(current_year, current_month)
        reply_markup = InlineKeyboardMarkup(keyboard)

        await query.edit_message_text(text, reply_markup=reply_markup, parse_mode="Markdown")

    except Exception as e:
        logger.error(f"Ошибка навигации календаря: {e}")
        await query.edit_message_text("❌ Ошибка. Попробуйте позже.")


def format_calendar_text(year, month, calendar_data):
    """Форматирует текст календаря"""
    month_names = {
        1: "Январь", 2: "Февраль", 3: "Март", 4: "Апрель",
        5: "Май", 6: "Июнь", 7: "Июль", 8: "Август",
        9: "Сентябрь", 10: "Октябрь", 11: "Ноябрь", 12: "Декабрь"
    }

    month_name = month_names.get(month, "Месяц")

    text = f"📅 **КАЛЕНДАРЬ ТРЕНИРОВОК**\n\n"
    text += f"📆 {month_name} {year}\n\n"

    # Подсчитываем статистику
    total_workouts = sum(day['workout_count'] for day in calendar_data)
    total_volume = sum(day.get('total_volume', 0) for day in calendar_data)
    active_days = len(calendar_data)

    text += f"📊 **Статистика:**\n"
    text += f"• Тренировок: {total_workouts}\n"
    text += f"• Активных дней: {active_days}\n"
    text += f"• Общий объем: {int(total_volume)} кг/повторов\n\n"

    # Формируем визуальное отображение дней
    text += "🗓 **Активность по дням:**\n\n"

    # Создаем словарь для быстрого доступа
    activity_map = {day['day'].day: day for day in calendar_data}

    # Определяем количество дней в месяце
    if month == 12:
        days_in_month = 31
    else:
        next_month = datetime(year, month + 1, 1) - timedelta(days=1)
        days_in_month = next_month.day

    # Разбиваем по неделям
    text += "Пн Вт Ср Чт Пт Сб Вс\n"
    text += "────────────────────\n"

    # Определяем день недели первого числа
    first_day = datetime(year, month, 1)
    start_weekday = first_day.weekday()  # 0=понедельник, 6=воскресенье

    # Добавляем пустые ячейки до первого числа
    week_line = ""
    for i in range(start_weekday):
        week_line += "   "

    # Заполняем дни
    for day in range(1, days_in_month + 1):
        if day < 10:
            day_str = f" {day}"
        else:
            day_str = str(day)

        # Проверяем активность
        if day in activity_map:
            workout_count = activity_map[day]['workout_count']
            if workout_count >= 3:
                day_str = f"🔥{day_str}"  # Много тренировок
            elif workout_count >= 2:
                day_str = f"💪{day_str}"  # Несколько тренировок
            else:
                day_str = f"✅{day_str}"  # Одна тренировка
        else:
            day_str = f"⚪{day_str}"  # Нет тренировок

        week_line += day_str + " "

        # Если воскресенье - перенос строки
        if (start_weekday + day - 1) % 7 == 6:
            text += week_line + "\n"
            week_line = ""

    # Добавляем последнюю неделю если не полная
    if week_line:
        text += week_line + "\n"

    text += "\n"
    text += "🔥 3+ тренировок  💪 2 тренировки  ✅ 1 тренировка  ⚪ Нет\n"

    return text


def create_calendar_navigation(year, month):
    """Создает кнопки навигации"""
    keyboard = [
        [
            InlineKeyboardButton("⬅️", callback_data=CALENDAR_PREV),
            InlineKeyboardButton("🔄 Сегодня", callback_data=CALENDAR_BACK),
            InlineKeyboardButton("➡️", callback_data=CALENDAR_NEXT),
        ],
        [InlineKeyboardButton("◀️ В спорт", callback_data="sport")]
    ]
    return keyboard
