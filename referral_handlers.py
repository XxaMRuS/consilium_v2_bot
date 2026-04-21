#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Реферальная система с админ-панелью
"""

import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, CommandHandler, CallbackQueryHandler
from datetime import datetime

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

ADMIN_ID = 173705485

# Callback данные
REFERRAL_STATS_CALLBACK = "referral_stats"
REFERRAL_CHANGE_BONUS_CALLBACK = "referral_change_bonus"
REFERRAL_EDIT_TEXTS_CALLBACK = "referral_edit_texts"
REFERRAL_LOGS_CALLBACK = "referral_logs"
REFERRAL_RESET_TEXTS_CALLBACK = "referral_reset_texts"
REFERRAL_BACK_CALLBACK = "referral_back"

# Опции бонусов
BONUS_OPTIONS = [30, 50, 100, 150]

# ==================== ФУНКЦИИ ====================

from database_postgres import (
    get_referral_code, get_referral_info, get_referral_count,
    process_referral, get_referral_stats, get_referral_logs,
    get_referral_settings, update_referral_setting, reset_referral_texts,
    get_user_info, get_setting, set_setting,
    get_db_connection
)


# ==================== КОМАНДЫ ====================

async def referral_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда /referral - показывает реферальную информацию"""
    user_id = update.effective_user.id

    # Проверяем реферальную информацию
    info = get_referral_info(user_id)

    # Получаем реферальный код
    referral_code = get_referral_code(user_id)

    # Получаем количество приглашенных
    referral_count = get_referral_count(user_id)

    # Получаем настройки бонусов
    settings = get_referral_settings()
    bonus = settings['referral_bonus']

    # Формируем текст сообщения
    text = f"🔗 **ТВОЯ РЕФЕРАЛЬНАЯ ССЫЛКА**\n\n"
    text += "━━━━━━━━━━━━━━━━━━━━━\n\n"
    text += f"📎 **Твой код:** `{referral_code}`\n\n"
    text += f"👥 **Пригласил:** {referral_count} человек\n"
    text += f"💰 **Бонус за приглашение:** {bonus} очков\n\n"
    text += f"📋 **Получено бонусов:** {'Да' if info and info[2] else 'Нет'}\n\n"
    text += "━━━━━━━━━━━━━━━━━━━━━\n\n"
    text += f"🔗 **Ссылка:** `t.me/consilium_fitness_bot?start={referral_code}`"

    # Добавляем кнопку поделиться
    keyboard = [[InlineKeyboardButton("📤 Поделиться", switch_inline_query=True)]]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.message.reply_text(text, reply_markup=reply_markup)


async def admin_referral_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Админ-панель реферальной системы"""
    user_id = update.effective_user.id

    # Проверка админки
    if user_id != ADMIN_ID:
        await update.message.reply_text("⛔ У вас нет прав для выполнения этой команды.")
        return

    keyboard = [
        [
            InlineKeyboardButton("📈 Статистика", callback_data=REFERRAL_STATS_CALLBACK),
            InlineKeyboardButton("⚙️ Изменить бонус", callback_data=REFERRAL_CHANGE_BONUS_CALLBACK),
        ],
        [
            InlineKeyboardButton("✏️ Текст приглашения", callback_data=REFERRAL_EDIT_TEXTS_CALLBACK),
            InlineKeyboardButton("📜 Логи", callback_data=REFERRAL_LOGS_CALLBACK),
        ],
        [
            InlineKeyboardButton("🔄 Сбросить тексты", callback_data=REFERRAL_RESET_TEXTS_CALLBACK),
            InlineKeyboardButton("◀️ Назад", callback_data=REFERRAL_BACK_CALLBACK),
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.message.reply_text(
        "⚙️ **АДМИН-ПАНЕЛЬ РЕФЕРАЛЬНОЙ СИСТЕМЫ**\n\n"
        "━━━━━━━━━━━━━━━━━━━━━\n\n"
        "Выберите действие:",
        reply_markup=reply_markup
    )


# ==================== CALLBACK HANDLERS ====================

async def referral_stats_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показывает статистику реферальной системы"""
    query = update.callback_query
    await safe_callback_answer(query)

    stats = get_referral_stats()

    text = "📈 **СТАТИСТИКА РЕФЕРАЛЬНОЙ СИСТЕМЫ**\n\n"
    text += "━━━━━━━━━━━━━━━━━━━━━\n\n"
    text += f"👥 **Всего с кодом:** {stats['total_with_code']}\n"
    text += f"🎯 **Всего приглашённых:** {stats['total_referred']}\n"
    text += f"💰 **Общая сумма бонусов:** {stats['total_bonus']} очков\n\n"

    if stats['top_referrers']:
        text += "━━━━━━━━━━━━━━━━━━━━━\n\n"
        text += "🏆 **ТОП-10 ПРИГЛАСИВШИХ:**\n"
        for i, ref in enumerate(stats['top_referrers'], 1):
            telegram_id, first_name, username, score, referral_count = ref
            username_display = f"(@{username})" if username else ""
            text += f"{i}. {first_name} {username_display} — {referral_count} приглашений, {score} очков\n"

    keyboard = [[InlineKeyboardButton("🎮 Назад", callback_data=REFERRAL_BACK_CALLBACK)]]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await query.edit_message_text(text, reply_markup=reply_markup)


async def referral_change_bonus_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Изменяет размер бонуса за приглашение"""
    query = update.callback_query
    await safe_callback_answer(query)

    # Получаем текущий бонус
    current_bonus = int(get_setting('referral_bonus') or 50)

    # Создаём клавиатуру с вариантами бонусов
    keyboard = []
    row = []
    for bonus in BONUS_OPTIONS:
        label = f"{bonus} очков" if bonus == current_bonus else f"{bonus} очков ✅"
        row.append(InlineKeyboardButton(label, callback_data=f"bonus_{bonus}"))
    keyboard.append(row)

    keyboard.append([InlineKeyboardButton("◀️ Назад", callback_data=REFERRAL_BACK_CALLBACK)])
    reply_markup = InlineKeyboardMarkup(keyboard)

    text = f"⚙️ **ИЗМЕНИТЬ БОНУС ЗА ПРИГЛАШЕНИЕ**\n\n"
    text += f"💰 **Текущий бонус:** {current_bonus} очков\n\n"
    text += "Выберите новый размер бонуса:"

    await query.edit_message_text(text, reply_markup=reply_markup)


async def referral_process_bonus_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обрабатывает выбор бонуса"""
    query = update.callback_query
    await safe_callback_answer(query)

    bonus = int(query.data.split('_')[1])

    # Обновляем настройку
    update_referral_setting('referral_bonus', str(bonus))

    text = f"✅ Бонус обновлен!\n\n"
    text += f"💰 **Новый размер бонуса:** {bonus} очков"

    keyboard = [[InlineKeyboardButton("◀️ Назад", callback_data=REFERRAL_BACK_CALLBACK)]]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await query.edit_message_text(text, reply_markup=reply_markup)


async def referral_edit_texts_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Редактирует тексты приглашений"""
    query = update.callback_query
    await safe_callback_answer(query)

    settings = get_referral_settings()

    text = "✏️ **ТЕКСТЫ ПРИГЛАШЕНИЙ**\n\n"
    text += "📝 **Текст для приглашающего:**\n"
    text += f"{settings['referral_success_text']}\n\n"
    text += "📝 **Текст для нового пользователя:**\n"
    text += f"{settings['referral_welcome_text']}"

    keyboard = [
        [
            InlineKeyboardButton("Изменить текст приглашающего", callback_data="edit_success_text"),
            InlineKeyboardButton("Изменить текст нового", callback_data="edit_welcome_text"),
        ],
        [
            InlineKeyboardButton("◀️ Назад", callback_data=REFERRAL_BACK_CALLBACK)
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await query.edit_message_text(text, reply_markup=reply_markup)


async def referral_edit_success_text_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Редактирует текст для приглашающего"""
    query = update.callback_query
    await safe_callback_answer(query)

    await query.edit_message_text(
        "📝 Введите новый текст для приглашающего.\n\n"
        "Доступные переменные:\n"
        "• {inviter} - имя пригласившего\n"
        "• {new_user} - имя нового пользователя\n"
        "• {bonus} - количество очков\n\n"
        "Отправьте /cancel для отмены."
    )

    # Устанавливаем состояние ожидания текста
    context.user_data['waiting_for'] = "edit_success_text"


async def referral_edit_welcome_text_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Редактирует текст для нового пользователя"""
    query = update.callback_query
    await safe_callback_answer(query)

    await query.edit_message_text(
        "📝 Введите новый текст для нового пользователя.\n\n"
        "Доступные переменные:\n"
        "• {inviter} - имя пригласившего\n"
        "• {new_user} - имя нового пользователя\n"
        "• {bonus} - количество очков\n\n"
        "Отправьте /cancel для отмены."
    )

    # Устанавливаем состояние ожидания текста
    context.user_data['waiting_for'] = "edit_welcome_text"


async def referral_logs_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показывает логи регистраций"""
    query = update.callback_query
    await safe_callback_answer(query)

    logs = get_referral_logs()

    if not logs:
        text = "📜 **ЛОГИ РЕГИСТРАЦИЙ**\n\nПока нет регистраций через реферальные коды."
    else:
        text = "📜 **ПОСЛЕДНИЕ 20 РЕГИСТРАЦИЙ**\n\n"
        for log in logs:
            new_user_id, new_user_name, new_user_username, referrer_id, referrer_name, referrer_username, registered_at = log

            new_username_display = f"(@{new_user_username})" if new_user_username else new_user_name
            referrer_username_display = f"(@{referrer_username})" if referrer_username else referrer_name if referrer_name else "Система"

            text += f"👤 {new_user_username_display} → {referrer_username_display}\n"
            text += f"📅 {registered_at.strftime('%Y-%m-%d %H:%M')}\n\n"

    keyboard = [[InlineKeyboardButton("◀️ Назад", callback_data=REFERRAL_BACK_CALLBACK)]]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await query.edit_message_text(text, reply_markup=reply_markup)


async def referral_reset_texts_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Сбрасывает тексты на стандартные"""
    query = update.callback_query
    await safe_callback_answer(query)

    # Сбрасываем тексты
    texts = reset_referral_texts()

    text = "🔄 **ТЕКСТЫ СБРОШЕНЫ НА СТАНДАРТНЫЕ**\n\n"
    text += "✅ Текст для приглашающего:\n"
    text += f"{texts['referral_success_text']}\n\n"
    text += "✅ Текст для нового пользователя:\n"
    text += f"{texts['referral_welcome_text']}"

    keyboard = [[InlineKeyboardButton("◀️ Назад", callback_data=REFERRAL_BACK_CALLBACK)]]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await query.edit_message_text(text, reply_markup=reply_markup)


async def referral_back_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Возврат в админ-панель"""
    query = update.callback_query
    await safe_callback_answer(query)

    # Возвращаемся к админ-панели
    await admin_referral_command(update, context)


# =================️ ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ====================

async def show_referral_link(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показывает реферальную ссылку (из /start)"""
    referral_code = context.args[0] if context.args else None

    if not referral_code:
        return

    user_id = update.effective_user.id

    # Проверяем, существует ли код
    from database_postgres import get_db_connection
    conn = get_db_connection()
    cur = conn.cursor()

    try:
        cur.execute("SELECT telegram_id FROM users WHERE referral_code = %s", (referral_code,))
        result = cur.fetchone()
        cur.close()

        if not result:
            await update.message.reply_text(
                "❌ Реферальный код не найден.\n\n"
                "Проверьте правильность кода или используйте команду /referral для получения вашего кода."
            )
            return

        referrer_id = result[0]

        if referrer_id == user_id:
            await update.message.reply_text(
                "❌ Нельзя использовать свой собственный реферальный код.\n\n"
                "Для получения бонусов приглашайте новых пользователей!"
            )
            return

        # Обрабатываем реферальный код
        success, message = process_referral(user_id, referral_code)

        await update.message.reply_text(message)

    except Exception as e:
        logger.error(f"Ошибка при обработке реферального кода: {e}")
        await update.message.reply_text(f"❌ Ошибка при обработке кода: {e}")


async def send_referral_log_to_channel(new_user_id, referrer_id, bonus, context: ContextTypes.DEFAULT_TYPE):
    """Отправляет лог реферальной регистрации в канал"""
    try:
        from database_postgres import get_user_info
        from config import CHANNEL_ID

        # Получаем информацию о пользователях
        new_user = get_user_info(new_user_id)
        referrer = get_user_info(referrer_id) if referrer_id else None

        if new_user and referrer:
            # Формируем сообщение
            new_username = f"@{new_user[2]}" if new_user[2] else new_user[3] if new_user[3] else "Пользователь"
            referrer_username = f"@{referrer[2]}" if referrer[2] else referrer[3] if referrer[3] else "Пользователь"

            message = (
                f"🎉 **Новый реферал!**\n\n"
                f"👤 Пригласивший: {referrer_username} (ID: {referrer_id})\n"
                f"🆕 Новый: {new_username} (ID: {new_user_id})\n"
                f"💰 Бонус: {bonus} очков каждому"
            )

            # Отправляем в канал через бота
            await context.bot.send_message(
                chat_id=CHANNEL_ID,
                text=message,
                parse_mode='Markdown'
            )
            logger.info(f"Реферальный лог отправлен в канал")

    except Exception as e:
        logger.error(f"Ошибка отправки реферального лога: {e}")


# =================️ РЕГИСТРАЦИЯ ПОЛЬЗОВАТЕЛЯ С РЕФЕРАЛЬНЫМ КОДОМ ====================

async def handle_referral_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обрабатывает /start с реферальным кодом"""
    if not context.args or not len(context.args):
        return

    referral_code = context.args[0].upper()

    user_id = update.effective_user.id
    user_first_name = update.effective_user.first_name
    user_last_name = update.effective_user.last_name
    user_username = update.effective_user.username

    # Сначала регистрируем пользователя
    from database_postgres import register_user
    register_user(user_id, user_first_name, user_username, user_last_name)

    # Проверяем, существует ли код
    from database_postgres import get_db_connection
    conn = get_db_connection()
    cur = conn.cursor()

    try:
        cur.execute("SELECT telegram_id FROM users WHERE referral_code = %s", (referral_code,))
        result = cur.fetchone()
        cur.close()

        if not result:
            await update.message.reply_text(
                "❌ Реферальный код не найден.\n\n"
                "Проверьте правильность кода или используйте команду /referral для получения вашего кода."
            )
            return

        referrer_id = result[0]

        if referrer_id == user_id:
            await update.message.reply_text(
                "❌ Нельзя использовать свой собственный реферальный код.\n\n"
                "Для получения бонусов приглашайте новых пользователей!"
            )
            return

        # Обрабатываем реферальный код
        success, message = process_referral(user_id, referral_code)

        await update.message.reply_text(message)

        # Если успешная обработка, отправляем лог в канал
        if success:
            bonus = int(get_setting('referral_bonus') or 50)
            await send_referral_log_to_channel(user_id, referrer_id, bonus, context)

    except Exception as e:
        logger.error(f"Ошибка при обработке реферального кода в /start: {e}")
        await update.message.reply_text(f"❌ Ошибка при обработке кода: {e}")