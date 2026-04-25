# -*- coding: utf-8 -*-
"""
Календарь тренировок пользователя с кнопками
Интерактивный календарь с циферками
"""
import logging
from datetime import datetime, timedelta
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, CallbackQueryHandler
from database_postgres import get_user_workouts

logger = logging.getLogger(__name__)

# Константы для callback_data
CALENDAR = "calendar"
CALENDAR_PREV = "calendar_prev"
CALENDAR_NEXT = "calendar_next"
CALENDAR_BACK = "calendar_back"
CALENDAR_DAY = "calendar_day"


async def calendar_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показывает интерактивный календарь тренировок за текущий месяц"""
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
        # Получаем тренировки за месяц
        workouts = get_user_workouts(user_id, limit=1000)

        # Фильтруем тренировки за нужный месяц
        month_workouts = []
        for workout in workouts:
            if len(workout) > 4 and workout[4]:  # проверяем дату
                workout_date = workout[4]
                if workout_date.year == year and workout_date.month == month:
                    month_workouts.append(workout)

        # Создаем календарь с кнопками
        text = format_calendar_text(year, month, month_workouts)
        keyboard = create_calendar_keyboard(year, month, month_workouts)

        reply_markup = InlineKeyboardMarkup(keyboard)

        if query.message:
            await query.edit_message_text(text, reply_markup=reply_markup, parse_mode="Markdown")
        else:
            await update.message.reply_text(text, reply_markup=reply_markup, parse_mode="Markdown")

    except Exception as e:
        logger.error(f"Ошибка при показе календаря: {e}")
        error_text = "❌ Не удалось загрузить календарь. Попробуйте позже."

        keyboard = [[InlineKeyboardButton("◀️ В спорт", callback_data="sport")]]
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
        # Получаем тренировки за месяц
        workouts = get_user_workouts(user_id, limit=1000)

        # Фильтруем тренировки за нужный месяц
        month_workouts = []
        for workout in workouts:
            if len(workout) > 4 and workout[4]:  # проверяем дату
                workout_date = workout[4]
                if workout_date.year == current_year and workout_date.month == current_month:
                    month_workouts.append(workout)

        text = format_calendar_text(current_year, current_month, month_workouts)
        keyboard = create_calendar_keyboard(current_year, current_month, month_workouts)
        reply_markup = InlineKeyboardMarkup(keyboard)

        await query.edit_message_text(text, reply_markup=reply_markup, parse_mode="Markdown")

    except Exception as e:
        logger.error(f"Ошибка навигации календаря: {e}")
        await query.edit_message_text("❌ Ошибка. Попробуйте позже.")


async def calendar_day_click(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обрабатывает нажатие на конкретный день"""
    query = update.callback_query
    await query.answer()

    # Получаем день из callback_data
    day_str = query.data.replace(f"{CALENDAR_DAY}_", "")
    try:
        day = int(day_str)
    except ValueError:
        return

    user_id = update.effective_user.id
    year = context.user_data.get('calendar_year', datetime.now().year)
    month = context.user_data.get('calendar_month', datetime.now().month)

    try:
        # Получаем тренировки за выбранный день
        workouts = get_user_workouts(user_id, limit=1000)

        # Фильтруем тренировки за конкретный день
        day_workouts = []
        for workout in workouts:
            if len(workout) > 4 and workout[4]:  # проверяем дату
                workout_date = workout[4]
                if workout_date.year == year and workout_date.month == month and workout_date.day == day:
                    day_workouts.append(workout)

        # Формируем сообщение с деталями дня
        month_names = {
            1: "января", 2: "февраля", 3: "марта", 4: "апреля",
            5: "мая", 6: "июня", 7: "июля", 8: "августа",
            9: "сентября", 10: "октября", 11: "ноября", 12: "декабря"
        }

        text = f"📅 **{day} {month_names.get(month, 'месяца')} {year}**\n\n"

        if day_workouts:
            text += f"🏋️ **Тренировок: {len(day_workouts)}**\n\n"

            for i, workout in enumerate(day_workouts, 1):
                # workout = (id, name, result_value, video_link, date, is_best, type, comment)
                exercise_name = workout[1] if len(workout) > 1 else "Неизвестное упражнение"
                result_value = str(workout[2]) if len(workout) > 2 else "-"
                is_best = workout[5] if len(workout) > 5 else False
                workout_type = workout[6] if len(workout) > 6 else "упражнение"

                # Определяем иконку типа
                type_icons = {
                    'упражнение': '🏋️',
                    'комплекс': '📦',
                    'челлендж': '🎯'
                }
                type_icon = type_icons.get(workout_type, '🏋️')

                best_mark = " 🏆" if is_best else ""
                text += f"{i}. {type_icon} *{exercise_name}*{best_mark}\n"
                text += f"   Тип: {workout_type}\n"
                text += f"   Результат: {result_value}\n\n"
        else:
            text += "😴 В этот день тренировок не было\n\n"
            text += "Но это не повод отчаиваться! Завтра — новый день для побед! 💪"

        # Добавляем кнопку назад
        keyboard = [[InlineKeyboardButton("◀️ Назад в календарь", callback_data=CALENDAR)]]
        reply_markup = InlineKeyboardMarkup(keyboard)

        await query.edit_message_text(text, reply_markup=reply_markup, parse_mode="Markdown")

    except Exception as e:
        logger.error(f"Ошибка при показе деталей дня: {e}")
        await query.edit_message_text("❌ Ошибка. Попробуйте позже.")


def format_calendar_text(year, month, workouts):
    """Формирует текст календаря со статистикой"""
    month_names = {
        1: "Январь", 2: "Февраль", 3: "Март", 4: "Апрель",
        5: "Май", 6: "Июнь", 7: "Июль", 8: "Август",
        9: "Сентябрь", 10: "Октябрь", 11: "Ноябрь", 12: "Декабрь"
    }

    month_name = month_names.get(month, "Месяц")

    text = f"📅 **КАЛЕНДАРЬ ТРЕНИРОВОК**\n\n"
    text += f"📆 {month_name} {year}\n\n"

    # Подсчитываем статистику
    total_workouts = len(workouts)

    # Подсчитываем активные дни
    active_days = set()
    for workout in workouts:
        if len(workout) > 4 and workout[4]:
            active_days.add(workout[4].day)

    text += f"📊 **Всего тренировок:** {total_workouts}\n"
    text += f"📈 **Активных дней:** {len(active_days)}\n\n"

    # Легенда индикаторов
    text += "**🎯 Активность:**\n"
    text += "🔥 3+ тренировок  💪 2 тренировки  ✅ 1 тренировка  ❌ Нет тренировок\n\n"
    text += "**📋 Типы тренировок:**\n"
    text += "🏋️ Упражнение  🎯 Челлендж  📦 Комплекс\n\n"
    text += "👆 **Нажми на день,** чтобы увидеть детали"

    return text


def create_calendar_keyboard(year, month, workouts):
    """Создает интерактивную клавиатуру календаря с кнопками-днями"""
    month_names = {
        1: "ЯНВАРЬ", 2: "ФЕВРАЛЬ", 3: "МАРТ", 4: "АПРЕЛЬ",
        5: "МАЙ", 6: "ИЮНЬ", 7: "ИЮЛЬ", 8: "АВГУСТ",
        9: "СЕНТЯБРЬ", 10: "ОКТЯБРЬ", 11: "НОЯБРЬ", 12: "ДЕКАБРЬ"
    }

    month_name = month_names.get(month, "МЕСЯЦ")

    # Создаем словарь тренировок по дням
    workouts_by_day = {}
    for workout in workouts:
        if len(workout) > 4 and workout[4]:
            day = workout[4].day
            if day not in workouts_by_day:
                workouts_by_day[day] = []
            workouts_by_day[day].append(workout)

    # Определяем количество дней в месяце
    if month == 12:
        days_in_month = 31
    else:
        next_month = datetime(year, month + 1, 1) - timedelta(days=1)
        days_in_month = next_month.day

    # Определяем день недели первого числа
    first_day = datetime(year, month, 1)
    start_weekday = first_day.weekday()  # 0=понедельник, 6=воскресенье

    keyboard = []

    # Заголовок с названием месяца и навигацией
    header_row = [
        InlineKeyboardButton("⬅️", callback_data=CALENDAR_PREV),
        InlineKeyboardButton(f"📆 {month_name}", callback_data="ignore"),
        InlineKeyboardButton("➡️", callback_data=CALENDAR_NEXT)
    ]
    keyboard.append(header_row)

    # Дни недели
    weekday_row = [
        InlineKeyboardButton("Пн", callback_data="ignore"),
        InlineKeyboardButton("Вт", callback_data="ignore"),
        InlineKeyboardButton("Ср", callback_data="ignore"),
        InlineKeyboardButton("Чт", callback_data="ignore"),
        InlineKeyboardButton("Пт", callback_data="ignore"),
        InlineKeyboardButton("Сб", callback_data="ignore"),
        InlineKeyboardButton("Вс", callback_data="ignore")
    ]
    keyboard.append(weekday_row)

    # Пустые ячейки до первого числа
    week_row = []
    for i in range(start_weekday):
        week_row.append(InlineKeyboardButton(" ", callback_data="ignore"))

    # Заполняем дни
    for day in range(1, days_in_month + 1):
        # Формируем кнопку дня
        if day in workouts_by_day:
            workout_count = len(workouts_by_day[day])
            if workout_count >= 3:
                day_label = f"🔥{day}"  # Много тренировок
            elif workout_count >= 2:
                day_label = f"💪{day}"  # Несколько тренировок
            else:
                day_label = f"✅{day}"  # Одна тренировка
        else:
            day_label = f"❌{day}"  # Нет тренировок

        day_button = InlineKeyboardButton(day_label, callback_data=f"{CALENDAR_DAY}_{day}")
        week_row.append(day_button)

        # Если воскресенье или конец недели - добавляем строку
        if (start_weekday + day - 1) % 7 == 6:
            keyboard.append(week_row)
            week_row = []

    # Добавляем последнюю неделю если не полная
    if week_row:
        # Дополняем пустыми кнопками до 7
        while len(week_row) < 7:
            week_row.append(InlineKeyboardButton(" ", callback_data="ignore"))
        keyboard.append(week_row)

    # Кнопка "В спорт"
    footer_row = [
        InlineKeyboardButton("◀️ В спорт", callback_data="sport")
    ]
    keyboard.append(footer_row)

    return keyboard
