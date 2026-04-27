#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Обработчики для Горы Успеха (Mountain of Success)
"""

import logging
import os
import asyncio
import random
from validation_utils import safe_int_convert
import colorsys
from datetime import datetime, timedelta
from functools import wraps
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, InputMediaPhoto
from telegram.ext import ContextTypes
from PIL import Image, ImageDraw, ImageFont
import io

# ==================== ДЕБАГ-РЕЖИМ ====================
from debug_utils import debug_print, log_call, log_user_data, DEBUG_MODE

# ==================== НАСТРОЙКА ЛОГИРОВАНИЯ ====================
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
MOUNTAIN_CACHE_DIR = "mountain_cache"
MOUNTAIN_CACHE_MINUTES = 30  # Кэширование на 30 минут

# Цвета для гор
COLOR_GOLDEN = (255, 215, 0)      # Золотой для новичков
COLOR_BRONZE = (205, 127, 50)     # Бронзовый для профи
COLOR_MOUNTAIN = (139, 69, 19)    # Коричневый гора
COLOR_SKY = (135, 206, 235)       # Небесный
COLOR_WHITE = (255, 255, 255)
COLOR_BLACK = (0, 0, 0)

# Callback данные
MOUNTAIN_MENU_CALLBACK = "mountain_menu"
MOUNTAIN_BEGINNERS_CALLBACK = "mountain_beginners"
MOUNTAIN_PROS_CALLBACK = "mountain_pros"
MOUNTAIN_TOP20_CALLBACK = "mountain_top20"
MOUNTAIN_TOP50_CALLBACK = "mountain_top50"
MOUNTAIN_TOP100_CALLBACK = "mountain_top100"
MOUNTAIN_TOP200_CALLBACK = "mountain_top200"
MOUNTAIN_SEARCH_CALLBACK = "mountain_search"
MOUNTAIN_BACK_CALLBACK = "mountain_back"
MOUNTAIN_REFRESH_CALLBACK = "mountain_refresh"


# ==================== ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ====================

def ensure_cache_dir():
    """Создаёт директорию для кэша, если её нет."""
    if not os.path.exists(MOUNTAIN_CACHE_DIR):
        os.makedirs(MOUNTAIN_CACHE_DIR)
        debug_print(f"📁 Создана директория кэша: {MOUNTAIN_CACHE_DIR}")


def get_cache_file_path(group, limit, search_query=None):
    """Возвращает путь к файлу кэша."""
    if search_query:
        filename = f"mountain_{group}_{limit}_{search_query}.png"
    else:
        filename = f"mountain_{group}_{limit}.png"
    return os.path.join(MOUNTAIN_CACHE_DIR, filename)


def is_cache_valid(file_path):
    """Проверяет, актуален ли кэш."""
    if not os.path.exists(file_path):
        return False

    # Проверяем возраст файла
    file_time = datetime.fromtimestamp(os.path.getmtime(file_path))
    age = datetime.now() - file_time
    return age < timedelta(minutes=MOUNTAIN_CACHE_MINUTES)


def generate_mountain_image(users, group, search_query=None):
    """Генерирует изображение пирамиды из адаптивных кирпичиков.

    Args:
        users: Список кортежей (telegram_id, first_name, username, score, position, total)
        group: Группа ('newbie' или 'pro')
        search_query: Поисковый запрос (если есть)

    Returns:
        bytes: Изображение в формате PNG
    """
    debug_print(f"🏔️ Генерация адаптивной пирамиды: group={group}, users={len(users)}")

    # Размеры изображения
    width = 1400
    height = 900

    # Создаём изображение с серым фоном (как календарь)
    img = Image.new('RGB', (width, height), (240, 240, 240))
    draw = ImageDraw.Draw(img)

    # Определяем цветовую схему
    group_name = "Новички" if group == 'newbie' else "Эксперты"

    # Добавляем шрифты
    try:
        font_title = ImageFont.truetype("arial.ttf", 28)
        font_nick = ImageFont.truetype("arial.ttf", 13)
        font_score = ImageFont.truetype("arial.ttf", 11)
        font_small = ImageFont.truetype("arial.ttf", 10)
    except Exception as e:
        logger.warning(f"Не удалось загрузить шрифты, используем default: {e}")
        font_title = ImageFont.load_default()
        font_nick = ImageFont.load_default()
        font_score = ImageFont.load_default()
        font_small = ImageFont.load_default()

    # Заголовок
    title = f"⛰️ Пирамида Чемпионов — {group_name}"
    if search_query:
        title += f" (Поиск: {search_query})"

    draw.text((width // 2 - 200, 15), title, fill=(50, 50, 50), font=font_title)

    # Построение пирамиды из кирпичиков
    if users:
        y_position = 80
        center_x = width // 2

        # Пирамида: каждый ряд шире предыдущего
        user_idx = 0
        row_number = 1

        while user_idx < len(users):
            # Количество людей в ряду = номер ряда
            people_in_row = row_number

            # Берем пользователей для этого ряда
            row_users = users[user_idx:user_idx + people_in_row]

            if not row_users:
                break

            # Сначала вычисляем ширину каждого кирпичика в этом ряду
            brick_widths = []
            for user in row_users:
                telegram_id, first_name, username, score, position, total = user

                # Формируем никнейм для расчета ширины
                if username:
                    display_name = f"@{username}"
                elif first_name:
                    filtered_name = ''.join(c for c in first_name if c.isalnum() or c.isspace())
                    display_name = filtered_name
                else:
                    display_name = f"User{telegram_id}"

                # Вычисляем реальную ширину текста через шрифт
                try:
                    # Для никнейма
                    nick_bbox = font_nick.getbbox(display_name)
                    nick_width = nick_bbox[2] - nick_bbox[0]

                    # Для очков
                    score_bbox = font_score.getbbox(str(score))
                    score_width = score_bbox[2] - score_bbox[0]

                    # Общая ширина текста + отступы
                    text_width = max(nick_width, score_width) + 20  # 20px отступы

                    # Вычисляем ширину кирпичика (минимум 90px, максимум 160px)
                    brick_width = max(90, min(160, text_width))
                except Exception as e:
                    logger.debug(f"Не удалось вычислить точную ширину, используем фолбэк: {e}")
                    # Фолбэк на приблизительный расчет
                    text_width = len(display_name) * 9  # 9px на символ (более точно)
                    brick_width = max(90, min(160, text_width))

                brick_widths.append(brick_width)

            # Вычисляем X позицию для ряда (центрируем)
            total_row_width = sum(brick_widths) + (len(brick_widths) - 1) * 5  # 5px отступ между кирпичиками
            row_start_x = center_x - total_row_width // 2

            # Рисуем ряд кирпичиков
            for i, user in enumerate(row_users):
                telegram_id, first_name, username, score, position, total = user

                brick_width = brick_widths[i]
                brick_height = 50  # Высота кирпичика (как раньше)
                brick_padding = 3

                # Позиция кирпичика
                x_pos = row_start_x + sum(brick_widths[:i]) + i * 5

                # Уникальный цвет для каждого участника (разные оттенки)
                # Используем позицию для генерации уникального цвета
                import random
                random.seed(position)  # Фиксированный seed для позиции
                hue = (position * 37) % 360  # Разные оттенки

                # Конвертируем HSL в RGB
                import colorsys
                rgb = colorsys.hsv_to_rgb(hue / 360, 0.7, 0.8)
                brick_color = (int(rgb[0] * 255), int(rgb[1] * 255), int(rgb[2] * 255))

                # Особые цвета для топ-3
                if position == 1:
                    brick_color = (255, 215, 0)  # Золотой
                elif position == 2:
                    brick_color = (192, 192, 192)  # Серебряный
                elif position == 3:
                    brick_color = (205, 127, 50)  # Бронзовый

                # Рисуем кирпичик
                draw.rectangle([
                    x_pos, y_position,
                    x_pos + brick_width, y_position + brick_height
                ], fill=brick_color, outline=(80, 80, 80), width=2)

                # Формируем никнейм (БЕЗ обрезания!)
                if username:
                    display_name = f"@{username}"
                elif first_name:
                    filtered_name = ''.join(c for c in first_name if c.isalnum() or c.isspace())
                    display_name = filtered_name
                else:
                    display_name = f"User{telegram_id}"

                # Рисуем никнейм (адаптивно - переносим если длинный)
                if len(display_name) <= 10:
                    # Короткий ник - одна строка, очки по центру
                    nick_width = font_nick.getbbox(display_name)[2] - font_nick.getbbox(display_name)[0]
                    score_width = font_score.getbbox(str(score))[2] - font_score.getbbox(str(score))[0]

                    # Центрируем никнейм по горизонтали
                    nick_x = x_pos + (brick_width - nick_width) // 2
                    score_x = x_pos + (brick_width - score_width) // 2

                    draw.text((nick_x, y_position + 8), display_name, fill=(255, 255, 255), font=font_nick)
                    draw.text((score_x, y_position + 28), f"{score}", fill=(255, 255, 255), font=font_score)
                else:
                    # Длинный ник - две строки, очки по центру
                    first_part = display_name[:10]
                    second_part = display_name[10:]

                    first_width = font_small.getbbox(first_part)[2] - font_small.getbbox(first_part)[0]
                    second_width = font_small.getbbox(second_part)[2] - font_small.getbbox(second_part)[0]
                    score_width = font_score.getbbox(str(score))[2] - font_score.getbbox(str(score))[0]

                    # Центрируем каждую строку
                    first_x = x_pos + (brick_width - first_width) // 2
                    second_x = x_pos + (brick_width - second_width) // 2
                    score_x = x_pos + (brick_width - score_width) // 2

                    draw.text((first_x, y_position + 5), first_part, fill=(255, 255, 255), font=font_small)
                    draw.text((second_x, y_position + 18), second_part, fill=(255, 255, 255), font=font_small)
                    draw.text((score_x, y_position + 35), f"{score}", fill=(255, 255, 255), font=font_small)

            # Переходим к следующему ряду (фиксированное расстояние как раньше)
            y_position += brick_height + 5  # 5px между рядами
            user_idx += people_in_row
            row_number += 1

            # Ограничиваем количество рядов чтобы не вышло за границы
            if y_position > height - 50:
                break

    # Сохраняем в байты
    img_bytes = io.BytesIO()
    img.save(img_bytes, format='PNG')
    img_bytes.seek(0)

    debug_print(f"🏔️ Изображение сгенерировано: {len(img_bytes.getvalue())} байт")
    return img_bytes.getvalue()


def get_ranking_data(group, limit=20, search_query=None):
    """Получает данные рейтинга из базы данных.

    Args:
        group: Группа ('newbie' или 'pro')
        limit: Лимит участников
        search_query: Поисковый запрос (опционально)

    Returns:
        list: Список кортежей (telegram_id, first_name, username, score, position, total)
    """
    from database_postgres import get_mountain_ranking, get_mountain_total_users

    try:
        # Получаем пользователей из базы
        users = get_mountain_ranking(group, limit, search_query)

        # Получаем общее количество участников в группе
        total = get_mountain_total_users(group)

        # Добавляем позицию к каждому пользователю
        result = []
        for i, user in enumerate(users, 1):
            result.append(user + (i, total))

        return result

    except Exception as e:
        logger.error(f"Ошибка получения рейтинга: {e}")
        return []


# ==================== ОБРАБОТЧИКИ КОМАНД ====================

@log_call
async def mountain_menu_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Главное меню Горы Успеха."""
    log_user_data(update, context, "mountain_menu_command")
    debug_print(f"🏔️ mountain_menu_command: ВЫЗВАНА")

    keyboard = [
        [InlineKeyboardButton("😊 Гора Новичков", callback_data=MOUNTAIN_BEGINNERS_CALLBACK)],
        [InlineKeyboardButton("😎 Гора Экспертов", callback_data=MOUNTAIN_PROS_CALLBACK)],
        [InlineKeyboardButton("🔍 Поиск по имени", callback_data=MOUNTAIN_SEARCH_CALLBACK)],
        [InlineKeyboardButton("◀️ Назад", callback_data='back_to_main')]
    ]

    reply_markup = InlineKeyboardMarkup(keyboard)

    text = (
        "⛰️ **ГОРА УСПЕХА**\n\n"
        "Добро пожаловать на Гору Успеха! Здесь ты можешь:\n\n"
        "😊 **Новички** — рейтинг для начинающих атлетов\n"
        "😎 **Эксперты** — рейтинг для опытных атлетов\n"
        "🔍 **Поиск** — найти своих друзей по имени или username\n\n"
        "Выбери гору для восхождения!"
    )

    anchor = update.message if update.message else update.callback_query.message
    await anchor.reply_text(text, reply_markup=reply_markup, parse_mode='Markdown')
    debug_print(f"🏔️ mountain_menu_command: ВОЗВРАТ")


@log_call
async def mountain_beginners_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показывает гору новичков (Top-20)."""
    log_user_data(update, context, "mountain_beginners_callback")
    debug_print(f"🏔️ mountain_beginners_callback: ВЫЗВАНА")

    await show_mountain(update, context, group='newbie', limit=20)
    debug_print(f"🏔️ mountain_beginners_callback: ВОЗВРАТ")


@log_call
async def mountain_pros_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показывает гору профи (Top-20)."""
    log_user_data(update, context, "mountain_pros_callback: ВЫЗВАНА")

    await show_mountain(update, context, group='pro', limit=20)
    debug_print(f"🏔️ mountain_pros_callback: ВОЗВРАТ")


async def show_mountain(update: Update, context: ContextTypes.DEFAULT_TYPE, group, limit=20, search_query=None):
    """Показывает гору с изображением-пирамидой и кнопками управления."""
    debug_print(f"🏔️ show_mountain: group={group}, limit={limit}, search={search_query}")

    ensure_cache_dir()

    # Проверяем кэш
    cache_file = get_cache_file_path(group, limit, search_query)

    if is_cache_valid(cache_file):
        debug_print(f"🏔️ Используем кэш: {cache_file}")
        with open(cache_file, 'rb') as f:
            photo_bytes = f.read()
    else:
        debug_print(f"🏔️ Генерируем новое изображение")
        # Получаем данные рейтинга
        users = get_ranking_data(group, limit, search_query)

        # Генерируем изображение
        photo_bytes = generate_mountain_image(users, group, search_query)

        # Сохраняем в кэш
        with open(cache_file, 'wb') as f:
            f.write(photo_bytes)
        debug_print(f"🏔️ Изображение сохранено в кэш: {cache_file}")

    # Создаём клавиатуру
    group_name = "Новички" if group == 'newbie' else "Профи"

    # Кнопки выбора количества
    keyboard = []
    limit_buttons = []
    if limit != 20:
        limit_buttons.append(InlineKeyboardButton("📊 Top 20", callback_data=f"{MOUNTAIN_TOP20_CALLBACK}_{group}"))
    if limit != 50:
        limit_buttons.append(InlineKeyboardButton("📊 Top 50", callback_data=f"{MOUNTAIN_TOP50_CALLBACK}_{group}"))
    if limit != 100:
        limit_buttons.append(InlineKeyboardButton("📊 Top 100", callback_data=f"{MOUNTAIN_TOP100_CALLBACK}_{group}"))

    if limit_buttons:
        keyboard.append(limit_buttons)

    # Кнопки управления
    keyboard.append([
        InlineKeyboardButton("🔄 Обновить", callback_data=f"{MOUNTAIN_REFRESH_CALLBACK}_{group}_{limit}"),
        InlineKeyboardButton("🔍 Поиск", callback_data=MOUNTAIN_SEARCH_CALLBACK)
    ])

    # Кнопка "Назад"
    keyboard.append([InlineKeyboardButton("◀️ В меню горы", callback_data=MOUNTAIN_BACK_CALLBACK)])

    reply_markup = InlineKeyboardMarkup(keyboard)

    # Заголовок с информацией
    title = f"⛰️ Гора Успеха — {group_name}"
    if search_query:
        title += f" (🔍 {search_query})"

    # Добавляем информацию о топ-10 в caption
    users = get_ranking_data(group, min(limit, 10), search_query)
    if users:
        title += "\n\n🏆 ТОП-10 ЛИДЕРОВ:\n"
        for i, user in enumerate(users[:10], 1):
            telegram_id, first_name, username, score, position, total = user

            # Формируем красивое отображение имени
            name_parts = []
            if first_name:
                filtered_name = ''.join(c for c in first_name if c.isalnum() or c.isspace() or c in '._-')
                if filtered_name:
                    name_parts.append(filtered_name[:20])
            if username:
                name_parts.append(f"@{username}")

            if name_parts:
                display_name = " | ".join(name_parts)
            else:
                display_name = f"User{telegram_id}"

            # Медали для топ-3
            medal = "🥇" if i == 1 else "🥈" if i == 2 else "🥉" if i == 3 else "🏅"
            title += f"{medal} #{position} {display_name}\n   └ {score} очков\n\n"

    # Проверяем, есть ли callback_query
    if update.callback_query:
        query = update.callback_query
        await safe_callback_answer(query)

        # Отправляем новое сообщение с фото
        await query.message.reply_photo(
            photo=photo_bytes,
            caption=title,
            reply_markup=reply_markup
        )
    else:
        # Режим 2: Нет callback_query (вызов из handle_search_input)
        await update.effective_chat.send_photo(
            photo=photo_bytes,
            caption=title,
            reply_markup=reply_markup
        )

    debug_print(f"🏔️ show_mountain: ВОЗВРАТ")


@log_call
async def mountain_top_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обрабатывает кнопки Top 20/50/100/200."""
    log_user_data(update, context, "mountain_top_callback")
    debug_print(f"🏔️ mountain_top_callback: ВЫЗВАНА")

    query = update.callback_query
    data = query.data.split('_')

    if len(data) >= 3:
        # Извлекаем число из 'top50', 'top100' и т.д.
        top_str = data[1]  # 'top50', 'top100' и т.д.
        limit = int(top_str.replace('top', ''))  # 50, 100 и т.д.
        group = data[2]  # 'newbie' или 'pro'

        await show_mountain(update, context, group=group, limit=limit)

    debug_print(f"🏔️ mountain_top_callback: ВОЗВРАТ")


@log_call
async def mountain_refresh_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обновляет гору (очищает кэш)."""
    log_user_data(update, context, "mountain_refresh_callback")
    debug_print(f"🏔️ mountain_refresh_callback: ВЫЗВАНА")

    query = update.callback_query
    data = query.data.split('_')

    if len(data) >= 3:
        group = data[2]
        limit = int(data[3]) if len(data) > 3 else 20

        # Очищаем весь кэш горы для получения новой версии
        try:
            import glob
            cache_files = glob.glob(os.path.join(MOUNTAIN_CACHE_DIR, "mountain_*.png"))
            for cache_file in cache_files:
                if os.path.exists(cache_file):
                    os.remove(cache_file)
            debug_print(f"🏔️ Удалено {len(cache_files)} файлов кэша")
        except Exception as e:
            logger.error(f"Ошибка очистки кэша: {e}")

        await show_mountain(update, context, group=group, limit=limit)

    debug_print(f"🏔️ mountain_refresh_callback: ВОЗВРАТ")


@log_call
async def mountain_search_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Начинает поиск по имени."""
    log_user_data(update, context, "mountain_search_callback")
    debug_print(f"🏔️ mountain_search_callback: ВЫЗВАНА")

    query = update.callback_query
    await safe_callback_answer(query)

    search_text = (
        "🔍 **Поиск на Горе Успеха**\n\n"
        "Введи имя или username для поиска:\n\n"
        "Примеры:\n"
        "• Иван\n"
        "• @username\n"
        "• ivan"
    )

    # Создаём инлайн-клавиатуру с кнопкой "Назад"
    keyboard = [
        [InlineKeyboardButton("◀️ Назад", callback_data=MOUNTAIN_BACK_CALLBACK)]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    # Отправляем новое сообщение
    await query.message.reply_text(search_text, reply_markup=reply_markup, parse_mode='Markdown')

    # Устанавливаем состояние ожидания ввода
    context.user_data['waiting_for_search'] = True

    debug_print(f"🏔️ mountain_search_callback: ВОЗВРАТ")


async def handle_search_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обрабатывает поисковый запрос."""
    debug_print(f"🏔️ handle_search_input: ВЫЗВАНА")

    if not context.user_data.get('waiting_for_search'):
        return

    search_query = update.message.text.strip()
    debug_print(f"🏔️ Поисковый запрос: {search_query}")

    # Убираем @ из username если есть
    if search_query.startswith('@'):
        search_query = search_query[1:]

    # Очищаем состояние
    context.user_data.pop('waiting_for_search', None)

    # Показываем результат поиска для новичков
    await show_mountain(update, context, group='newbie', limit=20, search_query=search_query)

    debug_print(f"🏔️ handle_search_input: ВОЗВРАТ")


@log_call
async def mountain_back_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Возвращается в главное меню горы."""
    log_user_data(update, context, "mountain_back_callback")
    debug_print(f"🏔️ mountain_back_callback: ВЫЗВАНА")

    await mountain_menu_command(update, context)
    debug_print(f"🏔️ mountain_back_callback: ВОЗВРАТ")


@log_call
async def mountain_profile_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показывает профиль пользователя при нажатии на никнейм в горе."""
    log_user_data(update, context, "mountain_profile_callback")
    debug_print(f"🏔️ mountain_profile_callback: ВЫЗВАНА")

    query = update.callback_query
    await safe_callback_answer(query)

    # Получаем user_id из callback_data
    callback_data = query.data

    success, target_user_id, error = safe_int_convert(
        callback_data.split("_")[-1] if callback_data else "",
        "target_user_id",
        min_value=1
    )

    if not success:
        await query.answer(f"❌ {error}", show_alert=True)
        return

    # Получаем статистику пользователя
    from database_postgres import get_user_mountain_stats, get_fun_fuel_balance, get_user_coin_balance, get_user_pvp_stats

    stats = get_user_mountain_stats(target_user_id)

    if not stats:
        await query.edit_message_text("❌ Профиль не найден")
        return

    # Получаем валюты
    try:
        frun_balance = get_user_coin_balance(target_user_id)
    except Exception as e:
        logger.warning(f"Не удалось получить frun_balance: {e}")
        frun_balance = 0

    try:
        fun_fuel = get_fun_fuel_balance(target_user_id)
    except Exception as e:
        logger.warning(f"Не удалось получить fun_fuel: {e}")
        fun_fuel = 0

    # Получаем PvP статистику
    try:
        pvp_stats = get_user_pvp_stats(target_user_id)
    except Exception as e:
        logger.warning(f"Не удалось получить PvP статистику: {e}")
        pvp_stats = {'total': 0, 'wins': 0, 'losses': 0, 'draws': 0, 'coins_won': 0, 'coins_lost': 0}

    # Получаем очки лидера для расчета разрыва
    from database_postgres import get_mountain_ranking
    try:
        top_users = get_mountain_ranking(stats['user_group'], limit=1)
        leader_score = top_users[0][3] if top_users else 0
        user_score = stats['score']
        score_gap = leader_score - user_score if leader_score > user_score else 0

        if score_gap > 0:
            gap_text = f"📈 До вершины: {score_gap:,} очков".replace(',', ' ')
        else:
            gap_text = "👑 На вершине!"
    except Exception as e:
        logger.warning(f"Не удалось рассчитать позицию до вершины: {e}")
        gap_text = "📈 До вершины: рассчитываем..."

    group_emoji = "😊 Новичок" if stats['user_group'] == 'newbie' else "😎 Эксперт"
    username_text = f"@{stats['username']}" if stats['username'] else "(нет username)"

    # FruNStatus - медали
    training_score = stats['score']
    frun_status_medals = training_score // 100

    # Формируем текст профиля
    text = f"👤 ПРОФИЛЬ УЧАСТНИКА\n\n"
    text += f"👤 Имя: {stats['first_name']}\n"
    text += f"📝 Username: {username_text}\n"
    text += f"📊 Группа: {group_emoji}\n\n"
    text += f"💎 FFCoin: {frun_balance}\n"
    text += f"💡 Валюта для ставок\n\n"
    text += f"⛽ FruNFuel: {fun_fuel}\n"
    text += f"💡 Очки на Горе Успеха\n\n"
    text += f"🏆 Тренировочные очки: {training_score}\n"
    text += f"💡 Очки за выполнение упражнений\n\n"
    text += f"🏅 FruNStatus: {frun_status_medals} медалей\n"
    text += f"💡 Твой ранг (каждые 100 очков = медаль!)\n\n"
    text += f"⛰️ ПОЗИЦИЯ НА ГОРЕ\n"
    text += f"📍 Место: {stats['position']} из {stats['total']}\n"
    text += f"{gap_text}\n\n"
    text += f"🏋️ ТРЕНИРОВКИ\n"
    text += f"💪 Всего: {stats['workout_count']}\n\n"
    text += f"🏆 PvP СТАТИСТИКА\n"
    text += f"🎯 Всего вызовов: {pvp_stats['total']}\n"
    text += f"🏆 Побед: {pvp_stats['wins']}\n"
    text += f"😢 Поражений: {pvp_stats['losses']}\n"
    text += f"🤝 Ничьих: {pvp_stats['draws']}\n"

    # Кнопка "Назад"
    keyboard = [[InlineKeyboardButton("◀️ Назад к горе", callback_data=MOUNTAIN_BACK_CALLBACK)]]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await query.edit_message_text(text, reply_markup=reply_markup)
    debug_print(f"🏔️ mountain_profile_callback: ВОЗВРАТ")


@log_call
async def profile_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показывает профиль пользователя с полной статистикой."""
    log_user_data(update, context, "profile_command")
    debug_print(f"🏔️ profile_command: ВЫЗВАНА")

    from database_postgres import get_user_mountain_stats, get_user_scoreboard_total, get_fun_fuel_balance

    user_id = update.effective_user.id
    stats = get_user_mountain_stats(user_id)

    if not stats:
        await update.message.reply_text("❌ Профиль не найден. Пожалуйста,先用 /start зарегистрироваться.")
        debug_print(f"🏔️ profile_command: ВОЗВРАТ (профиль не найден)")
        return

    # Получаем FruNStatus и FFCoin
    funstatus = get_user_scoreboard_total(user_id) or 0
    ffcoin = get_fun_fuel_balance(user_id) or 0

    # Формируем текст профиля
    group_emoji = "😊 Новичок" if stats['user_group'] == 'newbie' else "😎 Эксперт"
    percent_text = f"{stats['percent_from_top']:.1f}%" if stats['percent_from_top'] is not None else "N/A"

    username_text = f"📝 Username: @{stats['username']}\n" if stats['username'] else "📝 Username: (нет)\n"

    text = (
        f"👤 ПРОФИЛЬ\n\n"
        f"👤 Имя: {stats['first_name']}\n"
        f"{username_text}"
        f"📊 Группа: {group_emoji}\n\n"
        f"🏆 Тренировочные очки: {stats['score']}\n"
        f"💎 FruNStatus: {stats['score'] // 100} (медалей: {stats['score'] // 100})\n"
        f"💰 FFCoin: {ffcoin}\n\n"
        f"⛰️ **ПОЗИЦИЯ НА ГОРЕ**\n"
        f"📍 Место: {stats['position']} из {stats['total']}\n"
        f"📈 От вершины: {percent_text}\n\n"
        f"🏋️ **ТРЕНИРОВКИ**\n"
        f"💪 Всего тренировок: {stats['workout_count']}\n"
        f"👥 Приглашено друзей: {stats['referral_count']}\n"
        f"📅 Регистрация: {stats['registered_at'].strftime('%d.%m.%Y')}\n\n"
        f"💡 Используй /mountain чтобы увидеть Гору Успеха!"
    )

    keyboard = [
        [InlineKeyboardButton("⛰️ Гора Успеха", callback_data=MOUNTAIN_MENU_CALLBACK)],
        [InlineKeyboardButton("◀️ Назад", callback_data='back_to_main')]
    ]

    reply_markup = InlineKeyboardMarkup(keyboard)

    anchor = update.message if update.message else update.callback_query.message
    await anchor.reply_text(text, reply_markup=reply_markup, parse_mode='Markdown')


# ==================== ЕЖЕНЕДЕЛЬНЫЕ НАГРАДЫ НА ГОРЕ УСПЕХА ====================

async def distribute_weekly_mountain_rewards(context: ContextTypes.DEFAULT_TYPE):
    """
    Еженедельное распределение наград на Горе Успеха.

    Начисляет FruN Fuel:
    - +50 FF для топ-10 в каждой категории
    - +20 FF для топ-50 в каждой категории
    """
    debug_print(f"🏔️ Распределение еженедельных наград на Горе Успеха: НАЧИНАЕТСЯ")

    try:
        from database_postgres import get_db_connection, add_coins, get_ranking_data

        conn = get_db_connection()
        cur = conn.cursor()

        # Обрабатываем обе категории: новички и профи
        categories = ['newbie', 'pro']
        total_distributed = 0
        total_users = 0

        for category in categories:
            try:
                # Получаем топ-100 для категории
                users = get_ranking_data(category, limit=100, search_query=None)

                if not users:
                    logger.warning(f"Нет пользователей в категории {category}")
                    continue

                category_name = "Новички" if category == 'newbie' else "Профи"

                # Начисляем награды топ-10 (+50 FF)
                top_10 = users[:10]
                for i, user in enumerate(top_10, 1):
                    user_id = user['telegram_id']
                    try:
                        add_coins(user_id, 50, 'mountain_top_10', f'👑 {i}-е место на Горе Успеха ({category_name}, топ-10)')
                        logger.info(f"Начислено +50 FF пользователю {user_id} за {i}-е место на Горе ({category_name}, топ-10)")
                        total_distributed += 50
                        total_users += 1
                    except Exception as e:
                        logger.error(f"Ошибка начисления {user_id} (топ-10): {e}")

                # Начисляем награды топ-11-50 (+20 FF)
                if len(users) > 10:
                    top_50 = users[10:50]
                    for user in top_50:
                        user_id = user['telegram_id']
                        try:
                            add_coins(user_id, 20, 'mountain_top_50', f'🥈 Топ-50 на Горе Успеха ({category_name})')
                            logger.info(f"Начислено +20 FF пользователю {user_id} за топ-50 на Горе ({category_name})")
                            total_distributed += 20
                            total_users += 1
                        except Exception as e:
                            logger.error(f"Ошибка начисления {user_id} (топ-50): {e}")

            except Exception as e:
                logger.error(f"Ошибка обработки категории {category}: {e}")

        cur.close()
        conn.close()

        debug_print(f"🏔️ Распределение еженедельных наград: ЗАВЕРШЕНО")
        debug_print(f"👥 Пользователей: {total_users}, 📊 Распределено FF: {total_distributed}")

        # Отправляем отчёт админу (опционально)
        try:
            from database_postgres import get_all_admins
            admins = get_all_admins()

            if admins:
                report_text = (
                    f"⛰️ **ЕЖЕНЕДЕЛЬНЫЕ НАГРАДЫ НА ГОРЕ**\n\n"
                    f"👅 Пользователей: {total_users}\n"
                    f"💰 Распределено FF: {total_distributed}\n"
                    f"📅 Дата: {datetime.now().strftime('%d.%m.%Y %H:%M')}\n\n"
                    f"✅ Распределение успешно завершено!"
                )

                for admin_id in admins:
                    try:
                        await context.bot.send_message(
                            chat_id=admin_id,
                            text=report_text,
                            parse_mode='Markdown'
                        )
                    except Exception as e:
                        logger.error(f"Ошибка отправки отчёта админу {admin_id}: {e}")

        except Exception as e:
            logger.error(f"Ошибка отправки отчёта админам: {e}")

    except Exception as e:
        logger.error(f"Критическая ошибка при распределении наград: {e}")
        debug_print(f"🔴 КРИТИЧЕСКАЯ ОШИБКА: {e}")


async def weekly_mountain_rewards_job(context: ContextTypes.DEFAULT_TYPE):
    """
    Job-функция для планировщика. Вызывает distribute_weekly_mountain_rewards.
    """
    await distribute_weekly_mountain_rewards(context)
    debug_print(f"🏔️ profile_command: ВОЗВРАТ")


@log_call
async def clear_mountain_cache_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Очищает весь кэш горы успеха (для применения обновлений)."""
    debug_print(f"🏔️ clear_mountain_cache_command: ВЫЗВАНА")

    try:
        import glob
        cache_files = glob.glob(os.path.join(MOUNTAIN_CACHE_DIR, "mountain_*.png"))

        removed_count = 0
        for cache_file in cache_files:
            try:
                if os.path.exists(cache_file):
                    os.remove(cache_file)
                    removed_count += 1
            except Exception as e:
                logger.error(f"Ошибка удаления файла {cache_file}: {e}")

        await update.message.reply_text(
            f"✅ Кэш горы очищен!\n\n"
            f"🗑️ Удалено файлов: {removed_count}\n\n"
            f"💡 Теперь откройте гору снова — появится обновлённая версия!"
        )
        debug_print(f"🏔️ Удалено {removed_count} файлов кэша")

    except Exception as e:
        logger.error(f"Ошибка очистки кэша: {e}")
        await update.message.reply_text(f"❌ Ошибка очистки кэша: {e}")
        debug_print(f"🏔️ Ошибка очистки кэша: {e}")

    debug_print(f"🏔️ clear_mountain_cache_command: ВОЗВРАТ")
