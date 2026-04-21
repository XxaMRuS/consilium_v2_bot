#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Обработчики для Горы Успеха (Mountain of Success)
"""

import logging
import os
import asyncio
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
    """Генерирует изображение горы с пользователями.

    Args:
        users: Список кортежей (telegram_id, first_name, username, score, position, total)
        group: Группа ('newbie' или 'pro')
        search_query: Поисковый запрос (если есть)

    Returns:
        bytes: Изображение в формате PNG
    """
    debug_print(f"🏔️ Генерация изображения горы: group={group}, users={len(users)}")

    # Размеры изображения
    width = 800
    height = 600

    # Создаём изображение
    img = Image.new('RGB', (width, height), COLOR_SKY)
    draw = ImageDraw.Draw(img)

    # Определяем цветовую схему
    primary_color = COLOR_GOLDEN if group == 'newbie' else COLOR_BRONZE
    group_name = "🙂 Новички" if group == 'newbie' else "🤓 Профи"

    # Рисуем гору
    mountain_points = [
        (width // 2, 50),      # Вершина
        (100, height - 50),    # Левый низ
        (width - 100, height - 50)  # Правый низ
    ]
    draw.polygon(mountain_points, fill=COLOR_MOUNTAIN, outline=primary_color, width=3)

    # Добавляем заголовок
    try:
        # Пытаемся использовать шрифт, иначе используем стандартный
        font_large = ImageFont.truetype("arial.ttf", 24)
        font_medium = ImageFont.truetype("arial.ttf", 18)
        font_small = ImageFont.truetype("arial.ttf", 14)
    except:
        font_large = ImageFont.load_default()
        font_medium = ImageFont.load_default()
        font_small = ImageFont.load_default()

    # Заголовок
    title = f"⛰️ ГОРА УСПЕХА — {group_name}"
    if search_query:
        title += f" (🔍 {search_query})"

    draw.text((10, 10), title, fill=COLOR_BLACK, font=font_large)

    # Рисуем пользователей на горе
    if users:
        for user in users[:20]:  # Показываем максимум 20 на изображении
            telegram_id, first_name, username, score, position, total = user

            # Вычисляем позицию на горе (0-100% от вершины)
            if total > 0:
                percent_from_top = (position - 1) / total * 100
            else:
                percent_from_top = 0

            # Преобразуем в координаты на горе
            # Чем выше позиция (меньше position), тем ближе к вершине
            progress = (position - 1) / max(len(users), 1)

            # Координаты на треугольнике горы
            base_y = height - 50
            top_y = 50
            current_y = top_y + (base_y - top_y) * progress

            # Ширина горы на текущей высоте
            mountain_width_at_height = (current_y - top_y) / (base_y - top_y) * (width - 200)
            center_x = width // 2
            current_x = center_x + (mountain_width_at_height // 2) * (1 if position % 2 == 0 else -1)

            # Рисуем человечка
            emoji = "🤠"
            draw.text((current_x, current_y), emoji, fill=COLOR_BLACK, font=font_medium)

            # Добавляем имя и позицию
            display_name = first_name[:10] if first_name else f"User{telegram_id}"
            percent_text = f"{percent_from_top:.1f}%"

            # Текст под человечком
            info_text = f"{position}. {display_name} ({score}★) - {percent_text}"
            draw.text((current_x - 20, current_y + 20), info_text, fill=COLOR_BLACK, font=font_small)

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
        [InlineKeyboardButton("🟢 Гора Новичков", callback_data=MOUNTAIN_BEGINNERS_CALLBACK)],
        [InlineKeyboardButton("🔴 Гора Профи", callback_data=MOUNTAIN_PROS_CALLBACK)],
        [InlineKeyboardButton("🔍 Поиск по имени", callback_data=MOUNTAIN_SEARCH_CALLBACK)],
        [InlineKeyboardButton("◀️ Назад", callback_data='back_to_main')]
    ]

    reply_markup = InlineKeyboardMarkup(keyboard)

    text = (
        "⛰️ **ГОРА УСПЕХА**\n\n"
        "Добро пожаловать на Гору Успеха! Здесь ты можешь:\n\n"
        "🟢 **Новички** — рейтинг для начинающих атлетов\n"
        "🔴 **Профи** — рейтинг для опытных атлетов\n"
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
    """Показывает гору с изображением и кнопками навигации."""
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
    keyboard = []

    # Кнопки количества участников
    limit_buttons = []
    if limit != 20:
        limit_buttons.append(InlineKeyboardButton("📊 Top 20", callback_data=f"{MOUNTAIN_TOP20_CALLBACK}_{group}"))
    if limit != 50:
        limit_buttons.append(InlineKeyboardButton("📊 Top 50", callback_data=f"{MOUNTAIN_TOP50_CALLBACK}_{group}"))
    if limit != 100:
        limit_buttons.append(InlineKeyboardButton("📊 Top 100", callback_data=f"{MOUNTAIN_TOP100_CALLBACK}_{group}"))
    if limit != 200:
        limit_buttons.append(InlineKeyboardButton("📊 Top 200", callback_data=f"{MOUNTAIN_TOP200_CALLBACK}_{group}"))

    if limit_buttons:
        keyboard.append(limit_buttons)

    # Кнопки навигации
    nav_buttons = []
    nav_buttons.append(InlineKeyboardButton("🔄 Обновить", callback_data=f"{MOUNTAIN_REFRESH_CALLBACK}_{group}_{limit}"))
    nav_buttons.append(InlineKeyboardButton("🔍 Поиск", callback_data=MOUNTAIN_SEARCH_CALLBACK))
    keyboard.append(nav_buttons)

    # Кнопка "Назад"
    keyboard.append([InlineKeyboardButton("◀️ В меню горы", callback_data=MOUNTAIN_BACK_CALLBACK)])

    reply_markup = InlineKeyboardMarkup(keyboard)

    # Заголовок
    title = f"⛰️ Гора Успеха — {group_name}"
    if search_query:
        title += f" (🔍 {search_query})"

    # Проверяем, есть ли callback_query
    if update.callback_query:
        # Режим 1: Есть callback_query (нажатие кнопки)
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
        # Отправляем новое сообщение напрямую в чат
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

        # Удаляем кэш
        cache_file = get_cache_file_path(group, limit)
        if os.path.exists(cache_file):
            os.remove(cache_file)
            debug_print(f"🏔️ Кэш удалён: {cache_file}")

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
async def profile_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показывает профиль пользователя с полной статистикой."""
    log_user_data(update, context, "profile_command")
    debug_print(f"🏔️ profile_command: ВЫЗВАНА")

    from database_postgres import get_user_mountain_stats

    user_id = update.effective_user.id
    stats = get_user_mountain_stats(user_id)

    if not stats:
        await update.message.reply_text("❌ Профиль не найден. Пожалуйста,先用 /start зарегистрироваться.")
        debug_print(f"🏔️ profile_command: ВОЗВРАТ (профиль не найден)")
        return

    # Формируем текст профиля
    group_emoji = "🟢 Новичок" if stats['user_group'] == 'newbie' else "🤓 Профи"
    percent_text = f"{stats['percent_from_top']:.1f}%" if stats['percent_from_top'] is not None else "N/A"

    username_text = f"📝 Username: @{stats['username']}\n" if stats['username'] else "📝 Username: (нет)\n"

    text = (
        f"👤 **ПРОФИЛЬ**\n\n"
        f"👤 Имя: {stats['first_name']}\n"
        f"{username_text}"
        f"📊 Группа: {group_emoji}\n"
        f"⭐ Очки: {stats['score']}\n\n"
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
