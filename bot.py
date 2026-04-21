import os
import logging
from datetime import datetime
from dotenv import load_dotenv
from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ConversationHandler
from main_menu_handlers import show_main_menu
from hall_of_fame_handlers import hall_of_fame_callback, HALL_OF_FAME_MENU
from owner_handlers import (
    owner_menu_callback, owner_stats_callback, owner_balances_callback,
    owner_champions_history_callback, owner_champions_menu_callback, owner_champions_calculate_callback, owner_champions_calculate_current_callback, owner_champions_confirm_callback,
    owner_competitions_callback, owner_competitions_toggle_callback, owner_competitions_enable_all_callback,
    owner_competitions_disable_all_callback, owner_competitions_enable_beginners_callback,
    owner_ff_info_callback, owner_copy_id_callback,
    owner_ff_transfer_callback, owner_ff_select_user_callback, owner_ff_manual_input_callback,
    owner_ff_transfer_user_input, owner_ff_transfer_amount_input, owner_ff_amount_callback, owner_ff_custom_amount_callback,
    owner_ff_transfer_confirm_callback, owner_ff_transfer_cancel_callback,
    WAITING_FF_TRANSFER_USER, WAITING_FF_TRANSFER_AMOUNT, WAITING_FF_TRANSFER_CONFIRM,
    OWNER_MENU, OWNER_STATS, OWNER_BALANCES, OWNER_CHAMPIONS, OWNER_CHAMPIONS_HISTORY, OWNER_CHAMPIONS_MENU, OWNER_CHAMPIONS_CALCULATE, OWNER_CHAMPIONS_CALCULATE_CURRENT, OWNER_CHAMPIONS_CONFIRM,
    OWNER_COMPETITIONS, OWNER_COMPETITIONS_TOGGLE, OWNER_COMPETITIONS_ENABLE_ALL, OWNER_COMPETITIONS_DISABLE_ALL, OWNER_COMPETITIONS_ENABLE_BEGINNERS,
    OWNER_FF_INFO, OWNER_FF_TRANSFER, OWNER_FF_TRANSFER_CANCEL, OWNER_FF_TRANSFER_CONFIRM_YES
)

# Импорты модулей
from mountain_handlers import (
    mountain_menu_command, mountain_beginners_callback, mountain_pros_callback,
    mountain_top_callback, mountain_search_callback, mountain_refresh_callback,
    mountain_back_callback, handle_search_input, MOUNTAIN_MENU_CALLBACK,
    MOUNTAIN_BEGINNERS_CALLBACK, MOUNTAIN_PROS_CALLBACK, MOUNTAIN_SEARCH_CALLBACK,
    MOUNTAIN_TOP20_CALLBACK, MOUNTAIN_TOP50_CALLBACK, MOUNTAIN_TOP100_CALLBACK,
    MOUNTAIN_TOP200_CALLBACK, MOUNTAIN_REFRESH_CALLBACK, MOUNTAIN_BACK_CALLBACK
)
from pvp_handlers import (
    pvp_main_menu, pvp_show_challenge_candidates, pvp_select_bet,
    pvp_send_challenge_with_bet, pvp_accept_challenge, pvp_reject_challenge,
    pvp_my_challenges, pvp_show_history, pvp_show_stats, pvp_cancel_challenge,
    PVP_MENU_CALLBACK, PVP_NEW_CHALLENGE_CALLBACK, PVP_MY_CHALLENGES_CALLBACK,
    PVP_HISTORY_CALLBACK, PVP_STATS_CALLBACK, PVP_COINS_CALLBACK,
    PVP_LEADERBOARD_CALLBACK, PVP_CHALLENGE_USER_PREFIX, PVP_BET_PREFIX,
    PVP_ACCEPT_PREFIX, PVP_REJECT_PREFIX, PVP_CANCEL_PREFIX
)
from referral_handlers import (
    referral_command, show_referral_link, handle_referral_start
)
from admin_handlers import admin_menu, admin_exercise_add_conversation, admin_exercise_edit_conversation, admin_challenge_add_conversation, admin_complex_add_conversation, admin_add_conversation
from sport_handlers import (
    sport_menu, exercises_list, challenges_list, complexes_list,
    sport_ratings, sport_top_workouts, sport_top_challenges, sport_top_complexes, sport_my_stats,
    start_workout,
    SPORT_MENU, SPORT_EXERCISES, SPORT_CHALLENGES, SPORT_COMPLEXES, SPORT_RATINGS, SPORT_MY_STATS,
    SPORT_TOP_WORKOUTS, SPORT_TOP_CHALLENGES, SPORT_TOP_COMPLEXES, SPORT_BACK_TO_MAIN,
    SPORT_WORKOUT_START, SPORT_CHALLENGE_JOIN, SPORT_COMPLEX_START,
    workout_conversation
)
from sport_challenge_handlers import (
    challenges_list as sport_challenges_list,
    my_challenges_list, show_challenge_info, show_challenge_exercises,
    start_challenge_exercise, join_challenge_callback, show_challenge_progress,
    challenge_exercise_conversation
)
from ranking_notifications import init_ranking_notifications_table, update_rankings_and_notify
from champions_system import calculate_and_notify_champions

# Загрузка переменных окружения
load_dotenv()

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

BOT_TOKEN = os.getenv('BOT_TOKEN')
DATABASE_URL = os.getenv('DATABASE_URL')

# Проверка наличия обязательных переменных окружения
if not BOT_TOKEN:
    logger.error("❌ BOT_TOKEN не найден в переменных окружения!")
    logger.error("Установите BOT_TOKEN в настройках Render (Environment Variables)")
    raise ValueError("BOT_TOKEN is required but not set")

if not DATABASE_URL:
    logger.error("❌ DATABASE_URL не найден в переменных окружения!")
    logger.error("Установите DATABASE_URL в настройках Render (Environment Variables)")
    raise ValueError("DATABASE_URL is required but not set")

logger.info("✅ Переменные окружения загружены успешно")


async def show_user_id(update: Update, context) -> None:
    """Показывает пользователю его Telegram ID и информацию"""
    from database_postgres import get_user_info, get_fun_fuel_balance, get_user_scoreboard_total

    user_id = update.effective_user.id
    first_name = update.effective_user.first_name or "Друг"
    username = update.effective_user.username

    # Получаем информацию о пользователе
    user_info = get_user_info(user_id)

    text = f"👋 Привет, **{first_name}**!\n\n"
    text += f"🆔 **Твой Telegram ID:** `{user_id}`\n\n"

    if username:
        text += f"👤 Username: @{username}\n"

    text += "\n💡 **Эта информация нужна для:**\n"
    text += "• Получения FF от собственника\n"
    text += "• Поддержки и решения проблем\n\n"

    # Добавляем балансы если пользователь зарегистрирован
    if user_info:
        try:
            ff_balance = get_fun_fuel_balance(user_id)
            score = get_user_scoreboard_total(user_id)

            text += "💰 **Твои балансы:**\n"
            text += f"• FruN Fuel: {ff_balance} FF\n"
            text += f"• Спортивные очки: {score}\n"
        except:
            pass

    if update.message:
        await update.message.reply_text(text, parse_mode="Markdown")


async def start(update: Update, context) -> None:
    """Обработчик команды /start"""
    from database_postgres import register_user

    # Регистрируем пользователя
    user_id = update.effective_user.id
    first_name = update.effective_user.first_name
    username = update.effective_user.username
    last_name = update.effective_user.last_name

    register_user(user_id, first_name, username, last_name)

    # Создаём Reply-клавиатуру с эмодзи
    keyboard = [["🏠 Меню", "❌ Отмена"]]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

    # Проверяем, есть ли реферальный параметр
    if context.args and len(context.args) > 0:
        # Есть реферальная ссылка
        await handle_referral_start(update, context)
    else:
        # Обычный старт
        await update.message.reply_text(
            "Добро пожаловать! 👋\n\n"
            "Используйте кнопки меню для навигации:",
            reply_markup=reply_markup
        )


async def menu(update: Update, context) -> None:
    """Обработчик команды /menu"""
    await show_main_menu(update, context)


async def cancel(update: Update, context) -> None:
    """Обработчик команды /cancel"""
    await update.message.reply_text("❌ Действие отменено.")

    # Очищаем user_data если есть
    if context.user_data:
        context.user_data.clear()


async def handle_menu_button(update: Update, context) -> None:
    """Обработчик кнопки 🏠 Меню"""
    await show_main_menu(update, context)


async def handle_cancel_button(update: Update, context) -> None:
    """Обработчик кнопки ❌ Отмена"""
    await update.message.reply_text("❌ Действие отменено.")

    # Очищаем user_data если есть
    if context.user_data:
        context.user_data.clear()


async def handle_search_input_if_waiting(update: Update, context) -> None:
    """Проверяет, ожидаем ли мы ввод для какой-то системы."""
    # Проверяем, нет ли активного conversation (админка создает упражнения)
    if any(key in context.user_data for key in ['exercise_name', 'exercise_desc', 'exercise_metric', 'exercise_points']):
        # Есть активный conversation для создания упражнения, не обрабатываем здесь
        logger.info(f"⏸️ Пропускаем сообщение, активен conversation (keys: {list(context.user_data.keys())})")
        return

    # Проверяем разные состояния ожидания
    if context.user_data and context.user_data.get('waiting_for_search'):
        await handle_search_input(update, context)


async def handle_main_menu(update: Update, context) -> None:
    """Обработчик inline-кнопок главного меню"""
    query = update.callback_query
    callback_data = query.data

    # Не обрабатываем callbacks для редактирования упражнений и админки - их должен обрабатывать ConversationHandler или другие обработчики
    if (callback_data.startswith("admin_edit_exercise_") or
        callback_data.startswith("edit_name_") or
        callback_data.startswith("edit_desc_") or
        callback_data.startswith("edit_metric_") or
        callback_data.startswith("edit_points_") or
        callback_data.startswith("edit_diff_") or
        callback_data.startswith("admin_cancel_edit_") or
        callback_data.startswith("ch_metric_") or
        callback_data.startswith("ch_multi_ex_") or
        callback_data == "admin_add_challenge" or
        callback_data == "admin_add" or
        callback_data == "admin_cancel_add" or
        callback_data == "admin_add_cancel" or
        callback_data == "admin_admins_menu" or
        callback_data == "admin_list" or
        callback_data == "admin_remove" or
        callback_data.startswith("admin_remove_confirm_") or
        callback_data.startswith("admin_add_level_") or
        callback_data == "admin_stats"):
        return

    await query.answer()

    # Маршрутизация на основе callback_data
    if callback_data == "mountain":
        # Гора Успеха
        await mountain_menu_command(update, context)
    elif callback_data == "sport":
        # Спорт
        await sport_menu(update, context)
    elif callback_data == "pvp":
        # PvP вызовы
        await pvp_main_menu(update, context)
    elif callback_data == "hall_of_fame":
        # Зал славы
        await hall_of_fame_callback(update, context)
    elif callback_data == OWNER_MENU:
        # Меню собственника
        await owner_menu_callback(update, context)
    elif callback_data == OWNER_STATS:
        # Статистика
        await owner_stats_callback(update, context)
    elif callback_data == OWNER_BALANCES:
        # Балансы FF
        await owner_balances_callback(update, context)
    elif callback_data == OWNER_CHAMPIONS:
        # Чемпионы меню
        await owner_champions_menu_callback(update, context)
    elif callback_data == OWNER_CHAMPIONS_HISTORY:
        # История чемпионов
        await owner_champions_history_callback(update, context)
    elif callback_data == OWNER_CHAMPIONS_MENU:
        # Меню чемпионов
        await owner_champions_menu_callback(update, context)
    elif callback_data == OWNER_CHAMPIONS_CALCULATE:
        # Расчёт чемпионов
        await owner_champions_calculate_callback(update, context)
    elif callback_data == OWNER_CHAMPIONS_CONFIRM:
        # Подтверждение расчёта
        await owner_champions_confirm_callback(update, context)
    elif callback_data == OWNER_COMPETITIONS:
        # Соревнования
        await owner_competitions_callback(update, context)
    elif callback_data.startswith(OWNER_COMPETITIONS_TOGGLE + ":"):
        # Переключение соревнования
        await owner_competitions_toggle_callback(update, context)
    elif callback_data == OWNER_FF_INFO:
        # Информация о FF
        await owner_ff_info_callback(update, context)
    elif callback_data == "profile":
        # Профиль (показываем базовую информацию)
        from database_postgres import get_user_mountain_stats, get_user_coin_balance, get_user_scoreboard_total, get_user_pvp_stats

        user_id = update.effective_user.id
        stats = get_user_mountain_stats(user_id)

        if not stats:
            await query.edit_message_text("❌ Профиль не найден. Используй /start")
            return

        from telegram import InlineKeyboardButton, InlineKeyboardMarkup

        group_emoji = "🙂 Новичок" if stats['user_group'] == 'newbie' else "🤓 Профи"
        percent_text = f"{stats['percent_from_top']:.1f}%" if stats['percent_from_top'] is not None else "N/A"
        username_text = f"@{stats['username']}" if stats['username'] else "(нет username)"

        # Экранируем имя пользователя
        safe_first_name = stats['first_name'].replace('_', '\\_').replace('*', '\\*').replace('[', '\\[').replace(']', '\\]')

        # Получаем FRuN монеты
        try:
            frun_balance = get_user_coin_balance(user_id)
        except:
            frun_balance = 0

        # Получаем спортивные очки для PvP
        try:
            pvp_points = get_user_scoreboard_total(user_id)
        except:
            pvp_points = 0

        # Получаем PvP-статистику
        try:
            pvp_stats = get_user_pvp_stats(user_id)
        except:
            pvp_stats = {'total': 0, 'wins': 0, 'losses': 0, 'draws': 0, 'coins_won': 0, 'coins_lost': 0}

        text = (
            f"👤 **ТВОЙ ПРОФИЛЬ**\n\n"
            f"👤 Имя: {safe_first_name}\n"
            f"📝 Username: {username_text}\n"
            f"📊 Группа: {group_emoji}\n\n"
            f"💎 **FRuN монеты:** {frun_balance}\n"
            f"💡 Валюта бота (покупки, награды)\n\n"
            f"⚡ **Спортивные очки (PvP):** {pvp_points}\n"
            f"💡 Зарабатываются тренировками\n\n"
            f"⛰️ **ПОЗИЦИЯ НА ГОРЕ**\n"
            f"📍 Место: {stats['position']} из {stats['total']}\n"
            f"📈 От вершины: {percent_text}\n\n"
            f"🏋️ **ТРЕНИРОВКИ**\n"
            f"💪 Всего: {stats['workout_count']}\n\n"
            f"🏆 **PvP СТАТИСТИКА**\n"
            f"🎯 Всего вызовов: {pvp_stats['total']}\n"
            f"🏆 Побед: {pvp_stats['wins']}\n"
            f"😢 Поражений: {pvp_stats['losses']}\n"
            f"🤝 Ничьих: {pvp_stats['draws']}\n"
            f"💰 Выиграно очков: +{pvp_stats['coins_won']}\n"
            f"💸 Проиграно очков: {pvp_stats['coins_lost']}\n"
        )

        keyboard = [
            [InlineKeyboardButton("◀️ В главное меню", callback_data="back_to_main")]
        ]

        reply_markup = InlineKeyboardMarkup(keyboard)
        try:
            await query.edit_message_text(text, reply_markup=reply_markup, parse_mode='Markdown')
        except Exception as e:
            # Если Markdown сломался, отправляем без форматирования
            plain_text = (
                f"👤 ТВОЙ ПРОФИЛЬ\n\n"
                f"👤 Имя: {stats['first_name']}\n"
                f"📝 Username: {username_text}\n"
                f"📊 Группа: {group_emoji}\n\n"
                f"💎 FRuN монеты: {frun_balance}\n"
                f"💡 Валюта бота (покупки, награды)\n\n"
                f"⚡ Спортивные очки (PvP): {pvp_points}\n"
                f"💡 Зарабатываются тренировками\n\n"
                f"⛰️ ПОЗИЦИЯ НА ГОРЕ\n"
                f"📍 Место: {stats['position']} из {stats['total']}\n"
                f"📈 От вершины: {percent_text}\n\n"
                f"🏋️ ТРЕНИРОВКИ\n"
                f"💪 Всего: {stats['workout_count']}\n\n"
                f"🏆 PvP СТАТИСТИКА\n"
                f"🎯 Всего вызовов: {pvp_stats['total']}\n"
                f"🏆 Побед: {pvp_stats['wins']}\n"
                f"😢 Поражений: {pvp_stats['losses']}\n"
                f"🤝 Ничьих: {pvp_stats['draws']}\n"
                f"💰 Выиграно очков: +{pvp_stats['coins_won']}\n"
                f"💸 Проиграно очков: {pvp_stats['coins_lost']}\n"
            )
            try:
                await query.edit_message_text(plain_text, reply_markup=reply_markup)
            except:
                pass
    elif callback_data == "admin":
        # Админ-панель
        await admin_menu(update, context)
    elif callback_data == "back_to_mountain":
        # Возврат в меню горы
        await mountain_menu_command(update, context)
    elif callback_data == "back_to_main":
        # Возврат в главное меню
        await show_main_menu(update, context)


async def handle_callback_query(update: Update, context) -> None:
    """Универсальный обработчик для всех callback-запросов"""
    query = update.callback_query

    callback_data = query.data

    # Не обрабатываем эти callbacks - их должен обрабатывать ConversationHandler
    if (callback_data == "admin_add_challenge" or
        callback_data.startswith("ch_multi_ex_") or
        callback_data.startswith("ch_metric_") or
        callback_data.startswith("sport_challenge_do_exercise_") or
        callback_data == "admin_add_complex" or
        callback_data.startswith("complex_type_") or
        callback_data.startswith("complex_diff_") or
        callback_data.startswith("complex_ex_") or
        callback_data == "admin_cancel_complex" or
        callback_data.startswith("admin_edit_exercise_") or
        callback_data.startswith("edit_name_") or
        callback_data.startswith("edit_desc_") or
        callback_data.startswith("edit_metric_") or
        callback_data.startswith("edit_points_") or
        callback_data.startswith("edit_diff_") or
        callback_data.startswith("admin_cancel_edit_") or
        callback_data.startswith("admin_add_level_") or
        callback_data == "admin_add" or
        callback_data == "admin_cancel_add" or
        callback_data == "admin_add_cancel"):
        return

    logger.info(f"🔍 handle_callback_query получил: {callback_data}")

    try:
        # ==================== ГORA УСПЕХА ====================
        if callback_data == MOUNTAIN_BEGINNERS_CALLBACK:
            await mountain_beginners_callback(update, context)
        elif callback_data == MOUNTAIN_PROS_CALLBACK:
            await mountain_pros_callback(update, context)
        elif callback_data == MOUNTAIN_SEARCH_CALLBACK:
            await mountain_search_callback(update, context)
        elif callback_data.startswith(MOUNTAIN_TOP20_CALLBACK):
            await mountain_top_callback(update, context)
        elif callback_data.startswith(MOUNTAIN_TOP50_CALLBACK):
            await mountain_top_callback(update, context)
        elif callback_data.startswith(MOUNTAIN_TOP100_CALLBACK):
            await mountain_top_callback(update, context)
        elif callback_data.startswith(MOUNTAIN_TOP200_CALLBACK):
            await mountain_top_callback(update, context)
        elif callback_data.startswith(MOUNTAIN_REFRESH_CALLBACK):
            await mountain_refresh_callback(update, context)
        elif callback_data == MOUNTAIN_BACK_CALLBACK:
            await mountain_back_callback(update, context)
        elif callback_data == MOUNTAIN_MENU_CALLBACK:
            await mountain_menu_command(update, context)

        # ==================== PvP ВЫЗОВЫ ====================
        elif callback_data == PVP_MENU_CALLBACK:
            await pvp_main_menu(update, context)
        elif callback_data == PVP_NEW_CHALLENGE_CALLBACK:
            await pvp_show_challenge_candidates(update, context)
        elif callback_data == PVP_MY_CHALLENGES_CALLBACK:
            await pvp_my_challenges(update, context)
        elif callback_data == PVP_HISTORY_CALLBACK:
            await pvp_show_history(update, context)
        elif callback_data == PVP_STATS_CALLBACK:
            await pvp_show_stats(update, context)
        elif callback_data.startswith(PVP_CHALLENGE_USER_PREFIX):
            # Выбор пользователя для вызова - функция сама обработает callback_data
            await pvp_select_bet(update, context)
        elif callback_data.startswith(PVP_BET_PREFIX):
            # Выбор ставки - данные уже сохранены в pvp_select_bet
            await pvp_send_challenge_with_bet(update, context)
        elif callback_data.startswith(PVP_ACCEPT_PREFIX):
            # Принятие вызова - функция сама обработает callback_data
            await pvp_accept_challenge(update, context)
        elif callback_data.startswith(PVP_REJECT_PREFIX):
            # Отклонение вызова - функция сама обработает callback_data
            await pvp_reject_challenge(update, context)
        elif callback_data.startswith(PVP_CANCEL_PREFIX):
            # Отмена вызова
            challenge_id = int(callback_data.replace(PVP_CANCEL_PREFIX, ""))
            await pvp_cancel_challenge(update, context)

        # ==================== СПОРТ ====================
        elif callback_data == SPORT_EXERCISES:
            await exercises_list(update, context)
        elif callback_data == SPORT_CHALLENGES:
            await sport_challenges_list(update, context)
        elif callback_data == SPORT_COMPLEXES:
            await complexes_list(update, context)
        elif callback_data == SPORT_RATINGS:
            await sport_ratings(update, context)
        elif callback_data == SPORT_MY_STATS:
            await sport_my_stats(update, context)
        elif callback_data == SPORT_TOP_WORKOUTS:
            await sport_top_workouts(update, context)
        elif callback_data == SPORT_TOP_CHALLENGES:
            await sport_top_challenges(update, context)
        elif callback_data == SPORT_TOP_COMPLEXES:
            await sport_top_complexes(update, context)
        elif callback_data == SPORT_MENU:
            await sport_menu(update, context)
        elif callback_data == SPORT_BACK_TO_MAIN:
            await show_main_menu(update, context)
        elif callback_data.startswith(SPORT_WORKOUT_START):
            # Вызов упражнения - используем ConversationHandler
            await start_workout(update, context)
        elif callback_data.startswith(SPORT_CHALLENGE_JOIN):
            # Присоединение к челленджу - используем реальную функцию
            await join_challenge_callback(update, context)
        elif callback_data.startswith(SPORT_COMPLEX_START):
            # Выполнение комплекса
            from telegram import InlineKeyboardButton, InlineKeyboardMarkup
            keyboard = [[InlineKeyboardButton("◀️ В комплексы", callback_data=SPORT_COMPLEXES)]]
            await query.edit_message_text("🔨 **В разработке**\n\nВыполнение комплексов появится в следующем обновлении!", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")

        # ==================== АДМИНКА ====================
        elif callback_data == "admin" or callback_data == "admin_back_to_panel" or callback_data == "admin_panel":
            from admin_handlers import admin_panel_command
            await admin_panel_command(update, context)
        elif callback_data == "admin_close":
            # Закрыть админ-панель и вернуться в главное меню
            await show_main_menu(update, context)
        elif callback_data == "admin_exercises":
            from admin_handlers import admin_exercises_callback
            await admin_exercises_callback(update, context)
        elif callback_data == "admin_challenges":
            from admin_handlers import admin_challenges_callback
            await admin_challenges_callback(update, context)
        elif callback_data == "admin_complexes":
            from admin_handlers import admin_complexes_callback
            await admin_complexes_callback(update, context)
        elif callback_data == "admin_list_exercises":
            from admin_handlers import admin_list_exercises_callback
            await admin_list_exercises_callback(update, context)
        # admin_add_challenge обрабатывается ConversationHandler'ом в admin_handlers.py
        elif callback_data == "admin_list_challenges" or callback_data.startswith("admin_list_challenges_page_"):
            from admin_handlers import admin_list_challenges_callback
            await admin_list_challenges_callback(update, context)
        elif callback_data == "admin_list_complexes":
            from admin_handlers import admin_list_complexes_callback
            await admin_list_complexes_callback(update, context)
        elif callback_data == "admin_list_exercises" or callback_data.startswith("admin_list_exercises_page_"):
            from admin_handlers import admin_list_exercises_callback
            await admin_list_exercises_callback(update, context)
        elif callback_data.startswith("admin_view_exercise_"):
            from admin_handlers import admin_view_exercise_callback
            logger.info(f"✅ Вызываем admin_view_exercise_callback для: {callback_data}")
            await admin_view_exercise_callback(update, context)
        elif callback_data.startswith("admin_view_challenge_"):
            from admin_handlers import admin_view_challenge_callback
            logger.info(f"✅ Вызываем admin_view_challenge_callback для: {callback_data}")
            await admin_view_challenge_callback(update, context)
        # admin_edit_exercise_*, edit_*, admin_cancel_edit_* обрабатываются в admin_handlers.py ConversationHandler
        elif callback_data.startswith("admin_delete_exercise_"):
            from admin_handlers import admin_delete_exercise_callback
            await admin_delete_exercise_callback(update, context)
        elif callback_data.startswith("admin_confirm_delete_exercise_"):
            from admin_handlers import admin_confirm_delete_exercise_callback
            await admin_confirm_delete_exercise_callback(update, context)
        elif callback_data.startswith("admin_delete_challenge_"):
            from admin_handlers import admin_delete_challenge_callback
            await admin_delete_challenge_callback(update, context)
        elif callback_data.startswith("admin_confirm_delete_challenge_"):
            from admin_handlers import admin_confirm_delete_challenge_callback
            await admin_confirm_delete_challenge_callback(update, context)
        elif callback_data.startswith("admin_view_complex_"):
            from admin_handlers import admin_view_complex_callback
            await admin_view_complex_callback(update, context)
        elif callback_data.startswith("admin_delete_complex_"):
            from admin_handlers import admin_delete_complex_callback
            await admin_delete_complex_callback(update, context)
        elif callback_data.startswith("admin_confirm_delete_complex_"):
            from admin_handlers import admin_confirm_delete_complex_callback
            await admin_confirm_delete_complex_callback(update, context)
        elif callback_data.startswith("admin_list_complexes_page_"):
            from admin_handlers import admin_list_complexes_callback
            await admin_list_complexes_callback(update, context)

        # ==================== СОБСТВЕННИК ====================
        elif callback_data == OWNER_MENU:
            # Меню собственника
            await owner_menu_callback(update, context)
        elif callback_data == OWNER_STATS:
            # Статистика
            await owner_stats_callback(update, context)
        elif callback_data == OWNER_BALANCES:
            # Балансы FF
            await owner_balances_callback(update, context)
        elif callback_data == OWNER_CHAMPIONS:
            # Чемпионы меню
            await owner_champions_menu_callback(update, context)
        elif callback_data == OWNER_CHAMPIONS_HISTORY:
            # История чемпионов
            await owner_champions_history_callback(update, context)
        elif callback_data == OWNER_CHAMPIONS_MENU:
            # Меню чемпионов
            await owner_champions_menu_callback(update, context)
        elif callback_data == OWNER_CHAMPIONS_CALCULATE:
            # Расчёт чемпионов
            await owner_champions_calculate_callback(update, context)
        elif callback_data == OWNER_CHAMPIONS_CALCULATE_CURRENT:
            # Расчёт чемпионов за текущий месяц
            await owner_champions_calculate_current_callback(update, context)
        elif callback_data == OWNER_CHAMPIONS_CONFIRM:
            # Подтверждение расчёта
            await owner_champions_confirm_callback(update, context)
        elif callback_data == OWNER_COMPETITIONS:
            # Соревнования
            await owner_competitions_callback(update, context)
        elif callback_data.startswith(OWNER_COMPETITIONS_TOGGLE + ":"):
            # Переключение соревнования
            await owner_competitions_toggle_callback(update, context)
        elif callback_data == OWNER_COMPETITIONS_ENABLE_ALL:
            # Включить все упражнения
            await owner_competitions_enable_all_callback(update, context)
        elif callback_data == OWNER_COMPETITIONS_DISABLE_ALL:
            # Выключить все упражнения
            await owner_competitions_disable_all_callback(update, context)
        elif callback_data == OWNER_COMPETITIONS_ENABLE_BEGINNERS:
            # Включить новичковые упражнения
            await owner_competitions_enable_beginners_callback(update, context)
        elif callback_data == OWNER_FF_INFO:
            # Информация о FF
            await owner_ff_info_callback(update, context)
        elif callback_data.startswith("copy_id:"):
            # Копирование ID пользователя
            await owner_copy_id_callback(update, context)

        # ==================== АДМИНЫ ====================
        elif callback_data == "admin_admins_menu":
            from admin_handlers import admin_admins_menu_callback
            await admin_admins_menu_callback(update, context)
        elif callback_data == "admin_list":
            from admin_handlers import admin_list_callback
            await admin_list_callback(update, context)
        elif callback_data == "admin_remove":
            from admin_handlers import admin_remove_callback
            await admin_remove_callback(update, context)
        elif callback_data.startswith("admin_remove_confirm_"):
            from admin_handlers import admin_remove_confirm
            await admin_remove_confirm(update, context)
        elif callback_data == "admin_stats":
            from admin_handlers import admin_stats_callback
            await admin_stats_callback(update, context)
        # admin_add и admin_add_level_* обрабатываются ConversationHandler'ом

        # ==================== SPORT CHALLENGES ====================
        elif callback_data == "sport_challenges":
            await sport_challenges_list(update, context)
        elif callback_data == "sport_my_challenges":
            await my_challenges_list(update, context)
        elif callback_data.startswith("sport_challenge_") and callback_data.count("_") == 2:
            # sport_challenge_CHALLENGE_ID - просмотр челленджа
            await show_challenge_info(update, context)
        elif callback_data.startswith("sport_my_challenge_"):
            # sport_my_challenge_CHALLENGE_ID - просмотр своего челленджа
            await show_challenge_info(update, context)
        elif callback_data.startswith("sport_challenge_join_"):
            await join_challenge_callback(update, context)
        elif callback_data.startswith("sport_challenge_exercises_"):
            await show_challenge_exercises(update, context)
        elif callback_data.startswith("sport_challenge_progress_"):
            await show_challenge_progress(update, context)
        elif callback_data == "sport_my_challenges":
            await my_challenges_list(update, context)
        elif callback_data == "sport_back" or callback_data == "sport_cancel":
            await sport_menu(update, context)

        # ==================== ОБЩИЕ CALLBACK ====================
        elif callback_data == "back_to_main":
            await show_main_menu(update, context)
        else:
            # Неизвестный callback
            logger.warning(f"Неизвестный callback: {callback_data}")
            await query.edit_message_text(f"❌ Неизвестная команда: {callback_data}")

    except Exception as e:
        logger.error(f"Ошибка при обработке callback {callback_data}: {e}", exc_info=True)
        try:
            await query.edit_message_text(f"❌ Произошла ошибка: {str(e)}")
        except:
            await query.message.reply_text(f"❌ Произошла ошибка: {str(e)}")
    finally:
        # Безопасный ответ на callback, если еще не был отправлен
        try:
            if not query.answered:
                await query.answer()
        except:
            pass  # Игнорируем ошибки ответа


def main() -> None:
    """Главная функция для запуска бота"""
    # Создаём приложение
    application = Application.builder().token(BOT_TOKEN).build()

    # Регистрируем обработчики команд
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("menu", menu))
    application.add_handler(CommandHandler("cancel", cancel))
    application.add_handler(CommandHandler("id", show_user_id))

    # Регистрируем обработчики для Reply-кнопок с эмодзи
    application.add_handler(MessageHandler(filters.Regex(r'^🏠 Меню$'), handle_menu_button))
    application.add_handler(MessageHandler(filters.Regex(r'^❌ Отмена$'), handle_cancel_button))

    # Регистрируем ConversationHandler для админки (упражнения, челленджи, комплексы) - ДО общих обработчиков!
    application.add_handler(admin_exercise_add_conversation)
    application.add_handler(admin_exercise_edit_conversation)
    application.add_handler(admin_challenge_add_conversation)

    # Регистрируем ConversationHandler для выполнения упражнений в челленджах
    application.add_handler(challenge_exercise_conversation)

    # Регистрируем ConversationHandler для выполнения обычных упражнений
    application.add_handler(workout_conversation)

    # Регистрируем ConversationHandler для создания комплексов
    application.add_handler(admin_complex_add_conversation)

    # Регистрируем ConversationHandler для добавления админов
    application.add_handler(admin_add_conversation)

    # Создаём ConversationHandler для перевода FF
    owner_ff_transfer_conversation = ConversationHandler(
        entry_points=[CallbackQueryHandler(owner_ff_transfer_callback, pattern=f'^{OWNER_FF_TRANSFER}$')],
        states={
            WAITING_FF_TRANSFER_USER: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, owner_ff_transfer_user_input),
                CallbackQueryHandler(owner_ff_select_user_callback, pattern=r'^ff_select_user:\d+$'),
                CallbackQueryHandler(owner_ff_manual_input_callback, pattern='^ff_manual_input$'),
                CallbackQueryHandler(owner_ff_transfer_cancel_callback, pattern=f'^{OWNER_FF_TRANSFER_CANCEL}$')
            ],
            WAITING_FF_TRANSFER_AMOUNT: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, owner_ff_transfer_amount_input),
                CallbackQueryHandler(owner_ff_amount_callback, pattern=r'^ff_amount:\d+$'),
                CallbackQueryHandler(owner_ff_custom_amount_callback, pattern='^ff_custom_amount$'),
                CallbackQueryHandler(owner_ff_transfer_cancel_callback, pattern=f'^{OWNER_FF_TRANSFER_CANCEL}$')
            ],
            WAITING_FF_TRANSFER_CONFIRM: [
                CallbackQueryHandler(owner_ff_transfer_confirm_callback, pattern=f'^{OWNER_FF_TRANSFER_CONFIRM_YES}$'),
                CallbackQueryHandler(owner_ff_transfer_cancel_callback, pattern=f'^{OWNER_FF_TRANSFER_CANCEL}$')
            ],
        },
        fallbacks=[CallbackQueryHandler(owner_ff_transfer_cancel_callback, pattern=f'^{OWNER_FF_TRANSFER_CANCEL}$')],
    )

    # Регистрируем ConversationHandler для перевода FF
    application.add_handler(owner_ff_transfer_conversation)

    # Регистрируем обработчик callback-запросов для главного меню
    application.add_handler(CallbackQueryHandler(handle_main_menu, pattern=r'^(mountain|sport|pvp|hall_of_fame|profile|admin|owner_menu|owner_stats|owner_balances|owner_champions|owner_champions_history|owner_champions_menu|owner_champions_calculate|owner_champions_confirm|back_to_main)$'))

    # Регистрируем обработчики для кнопок Топ Горы Успеха
    application.add_handler(CallbackQueryHandler(mountain_top_callback, pattern=f'^{MOUNTAIN_TOP20_CALLBACK}_'))
    application.add_handler(CallbackQueryHandler(mountain_top_callback, pattern=f'^{MOUNTAIN_TOP50_CALLBACK}_'))
    application.add_handler(CallbackQueryHandler(mountain_top_callback, pattern=f'^{MOUNTAIN_TOP100_CALLBACK}_'))
    application.add_handler(CallbackQueryHandler(mountain_top_callback, pattern=f'^{MOUNTAIN_TOP200_CALLBACK}_'))

    # Регистрируем обработчик для поискового ввода (должен быть последним)
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_search_input_if_waiting))

    # Регистрируем универсальный обработчик для всех остальных callback
    application.add_handler(CallbackQueryHandler(handle_callback_query))

    # Инициализируем таблицу для уведомлений о рейтинге
    logger.info("🔔 Инициализация системы уведомлений о рейтинге...")
    init_ranking_notifications_table()

    # Добавляем ежедневную задачу на 12:00
    job_queue = application.job_queue
    if job_queue:
        # Запускаем обновление рейтинга каждый день в 12:00
        job_queue.run_daily(
            callback=update_rankings_and_notify,
            time=datetime.now().replace(hour=12, minute=0, second=0, microsecond=0),
            data=BOT_TOKEN,
            name='daily_ranking_update'
        )
        logger.info("✅ Ежедневное обновление рейтинга запланировано на 12:00")

        # Запускаем расчёт чемпионов 1-го числа каждого месяца в 00:01
        async def monthly_champions_job(context):
            """Фоновая задача для расчёта чемпионов месяца с уведомлениями."""
            try:
                result = calculate_and_notify_champions(context)
                if result:
                    logger.info("✅ Расчёт чемпионов месяца завершён и уведомления отправлены")
                else:
                    logger.info("ℹ️ Расчёт чемпионов не был выполнен (возможно, уже был рассчитан)")
            except Exception as e:
                logger.error(f"❌ Ошибка расчёта чемпионов: {e}")

        job_queue.run_monthly(
            callback=monthly_champions_job,
            day=1,  # 1-го числа
            time=datetime.now().replace(hour=0, minute=1, second=0, microsecond=0),
            name='monthly_champions_calculation'
        )
        logger.info("✅ Автоматический расчёт чемпионов запланирован на 1-е число 00:01")
        logger.info("✅ Ежемесячный расчёт чемпионов запланирован на 1-е число в 00:01")
    else:
        logger.warning("⚠️ JobQueue не доступен, автоматические задачи не будут выполняться")

    # Запускаем бота
    logger.info("Бот запущен...")
    logger.info("🏠 Готов к работе! Модули: Гора Успеха ✅, PvP ✅, Спорт ✅, Рефералы ✅, Админ ✅")
    logger.info("🔔 Уведомления о рейтинге: каждый день в 12:00")
    logger.info("📱 Reply-кнопки: 🏠 Меню, ❌ Отмена - активированы")
    application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == '__main__':
    main()