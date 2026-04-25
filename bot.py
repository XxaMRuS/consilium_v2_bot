import os
import logging
from datetime import datetime
from dotenv import load_dotenv
from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ConversationHandler

# Загружаем переменные окружения из .env файла
load_dotenv()

# Отключаем PTBUserWarning
logging.getLogger('telegram.ext').setLevel(logging.ERROR)

# Импортируем веб-сервер для Render health check
try:
    from web_server import start_web_server
    WEB_SERVER_AVAILABLE = True
except ImportError:
    WEB_SERVER_AVAILABLE = False
    logging.warning("⚠️ Веб-сервер не доступен")

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
    owner_pvp_settings_callback, owner_pvp_exercise_callback, owner_pvp_complex_callback, owner_pvp_challenge_callback,
    owner_pvp_set_percent_callback, owner_pvp_custom_percent_callback, owner_pvp_custom_input,
    owner_pvp_transfer_callback, owner_pvp_select_user_callback, owner_pvp_manual_input_callback,
    owner_pvp_transfer_user_input, owner_pvp_transfer_amount_input, owner_pvp_amount_callback, owner_pvp_custom_amount_callback,
    owner_pvp_transfer_confirm_callback, owner_pvp_transfer_cancel_callback,
    owner_channel_check_callback, owner_channel_change_id_callback, owner_channel_reconnect_callback,
    owner_channel_message_callback, owner_channel_message_send, owner_channel_message_cancel,
    WAITING_FF_TRANSFER_USER, WAITING_FF_TRANSFER_AMOUNT, WAITING_FF_TRANSFER_CONFIRM, WAITING_PVP_CUSTOM_INPUT,
    WAITING_PVP_TRANSFER_USER, WAITING_PVP_TRANSFER_AMOUNT, WAITING_PVP_TRANSFER_CONFIRM,
    WAITING_CHANNEL_MESSAGE,
    OWNER_MENU, OWNER_STATS, OWNER_BALANCES, OWNER_CHAMPIONS, OWNER_CHAMPIONS_HISTORY, OWNER_CHAMPIONS_MENU, OWNER_CHAMPIONS_CALCULATE, OWNER_CHAMPIONS_CALCULATE_CURRENT, OWNER_CHAMPIONS_CONFIRM,
    OWNER_COMPETITIONS, OWNER_COMPETITIONS_TOGGLE, OWNER_COMPETITIONS_ENABLE_ALL, OWNER_COMPETITIONS_DISABLE_ALL, OWNER_COMPETITIONS_ENABLE_BEGINNERS,
    OWNER_FF_INFO, OWNER_FF_TRANSFER, OWNER_FF_TRANSFER_CANCEL, OWNER_FF_TRANSFER_CONFIRM_YES,
    OWNER_PVP_SETTINGS, OWNER_PVP_EXERCISE, OWNER_PVP_COMPLEX, OWNER_PVP_CHALLENGE,
    OWNER_PVP_TRANSFER, OWNER_PVP_TRANSFER_CANCEL, OWNER_PVP_TRANSFER_CONFIRM_YES,
    OWNER_CHANNEL_CHECK, OWNER_CHANNEL_RECONNECT, OWNER_CHANNEL_MESSAGE
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
    sport_menu, exercises_list, challenges_list, complexes_list, show_complex_info, start_complex_execution, set_complex_mode,
    sport_ratings, sport_top_workouts, sport_top_challenges, sport_top_complexes, sport_my_stats,
    start_workout, handle_complex_exercise_result, handle_complex_media,
    SPORT_MENU, SPORT_EXERCISES, SPORT_CHALLENGES, SPORT_COMPLEXES, SPORT_RATINGS, SPORT_MY_STATS,
    SPORT_TOP_WORKOUTS, SPORT_TOP_CHALLENGES, SPORT_TOP_COMPLEXES, SPORT_BACK_TO_MAIN,
    SPORT_WORKOUT_START, SPORT_CHALLENGE_JOIN, SPORT_COMPLEX_START, SPORT_COMPLEX_DO,
    SPORT_COMPLEX_MODE_SEPARATE, SPORT_COMPLEX_MODE_SINGLE,
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

# AI-модули
from ai_handlers import (
    ai_menu_command,
    ai_advice_conversation,
    ai_photo_conversation,
    ai_recommend,
    ai_progress,
    AI_MENU, AI_ADVICE, AI_PHOTO, AI_RECOMMEND, AI_PROGRESS
)
# Календарь тренировок
from calendar_handlers import (
    calendar_menu,
    calendar_navigation,
    calendar_day_click,
    CALENDAR, CALENDAR_PREV, CALENDAR_NEXT, CALENDAR_BACK, CALENDAR_DAY
)

# Загрузка переменных окружения
load_dotenv()

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Проверка загрузки API ключей
logger.info("🔍 Проверка API ключей...")
api_keys_status = {
    'YANDEX_API_KEY': bool(os.getenv('YANDEX_API_KEY')),
    'GROQ_API_KEY': bool(os.getenv('GROQ_API_KEY')),
    'GEMINI_API_KEY': bool(os.getenv('GEMINI_API_KEY')),
    'OPENROUTER_API_KEY': bool(os.getenv('OPENROUTER_API_KEY')),
    'DEEPSEEK_API_KEY': bool(os.getenv('DEEPSEEK_API_KEY')),
    'OPENAI_API_KEY': bool(os.getenv('OPENAI_API_KEY'))
}

for key, status in api_keys_status.items():
    if status:
        logger.info(f"✅ {key}: загружен")
    else:
        logger.warning(f"⚠️ {key}: не найден")

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
    elif callback_data == AI_MENU:
        # AI Тренер
        await ai_menu_command(update, context)
    elif callback_data == CALENDAR:
        # Календарь тренировок
        await calendar_menu(update, context)
    elif callback_data == "profile":
        # Профиль (показываем базовую информацию)
        from database_postgres import get_user_mountain_stats, get_user_coin_balance, get_user_scoreboard_total, get_user_pvp_stats

        user_id = update.effective_user.id
        stats = get_user_mountain_stats(user_id)

        if not stats:
            await query.edit_message_text("❌ Профиль не найден. Используй /start")
            return

        from telegram import InlineKeyboardButton, InlineKeyboardMarkup

        group_emoji = "😊 Новичок" if stats['user_group'] == 'newbie' else "😎 Эксперт"
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
            f"💎 **FFCoin:** {frun_balance}\n"
            f"💡 Валюта для ставок\n\n"
            f"🏆 **FruNStatus:** {pvp_points}\n"
            f"💡 Твой ранг (каждые 100 = медаль!)\n\n"
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
                f"💎 FFCoin: {frun_balance}\n"
                f"💡 Валюта для ставок\n\n"
                f"🏆 FruNStatus: {pvp_points}\n"
                f"💡 Твой ранг (каждые 100 = медаль!)\n\n"
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
            # Показ информации о комплексе
            await show_complex_info(update, context)
        elif callback_data.startswith(SPORT_COMPLEX_DO):
            # Начать выполнение комплекса
            await start_complex_execution(update, context)
        elif callback_data.startswith(SPORT_COMPLEX_MODE_SEPARATE) or callback_data.startswith(SPORT_COMPLEX_MODE_SINGLE):
            # Установка режима выполнения комплекса
            await set_complex_mode(update, context)

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
        elif callback_data == OWNER_PVP_SETTINGS:
            # Настройки PvP конвертации
            await owner_pvp_settings_callback(update, context)
        elif callback_data == OWNER_PVP_EXERCISE:
            # Настройка конвертации упражнений
            await owner_pvp_exercise_callback(update, context)
        elif callback_data == OWNER_PVP_COMPLEX:
            # Настройка конвертации комплексов
            await owner_pvp_complex_callback(update, context)
        elif callback_data == OWNER_PVP_CHALLENGE:
            # Настройка конвертации челленджей
            await owner_pvp_challenge_callback(update, context)
        elif callback_data == OWNER_CHANNEL_CHECK:
            # Проверка каналов
            await owner_channel_check_callback(update, context)
        elif callback_data == OWNER_CHANNEL_RECONNECT:
            # Переподключение к каналу
            await owner_channel_reconnect_callback(update, context)
        elif callback_data == OWNER_CHANNEL_MESSAGE:
            # Сообщение в канал от собственника
            await owner_channel_message_callback(update, context)
        elif callback_data == "owner_channel_change_id":
            # Изменение ID канала
            await owner_channel_change_id_callback(update, context)
        elif callback_data.startswith(("pvp_exercise_set:", "pvp_complex_set:", "pvp_challenge_set:")):
            # Установка выбранного процента
            await owner_pvp_set_percent_callback(update, context)
        elif callback_data.startswith(("pvp_exercise_custom", "pvp_complex_custom", "pvp_challenge_custom")):
            # Ввод своего процента
            await owner_pvp_custom_percent_callback(update, context)

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
        elif callback_data == AI_MENU:
            await ai_menu_command(update, context)
        elif callback_data == AI_RECOMMEND:
            await ai_recommend(update, context)
        elif callback_data == AI_PROGRESS:
            await ai_progress(update, context)
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
    # Инициализируем базу данных
    from database_postgres import init_db, init_connection_pool
    from cache_manager import start_cache_cleanup

    init_db()

    # Инициализируем connection pool для ускорения
    init_connection_pool(minconn=3, maxconn=20)

    # Запускаем автоматическую очистку кэша
    start_cache_cleanup(interval=300)  # Каждые 5 минут
    logger.info("✅ Кэширование и connection pool запущены")

    # Создаём приложение (JobQueue не поддерживается в этой версии)
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

    # Создаём ConversationHandler для перевода PvP
    owner_pvp_transfer_conversation = ConversationHandler(
        entry_points=[CallbackQueryHandler(owner_pvp_transfer_callback, pattern=f'^{OWNER_PVP_TRANSFER}$')],
        states={
            WAITING_PVP_TRANSFER_USER: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, owner_pvp_transfer_user_input),
                CallbackQueryHandler(owner_pvp_select_user_callback, pattern=r'^pvp_select_user:\d+$'),
                CallbackQueryHandler(owner_pvp_manual_input_callback, pattern='^pvp_manual_input$'),
                CallbackQueryHandler(owner_pvp_transfer_cancel_callback, pattern=f'^{OWNER_PVP_TRANSFER_CANCEL}$')
            ],
            WAITING_PVP_TRANSFER_AMOUNT: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, owner_pvp_transfer_amount_input),
                CallbackQueryHandler(owner_pvp_amount_callback, pattern=r'^pvp_amount:\d+$'),
                CallbackQueryHandler(owner_pvp_custom_amount_callback, pattern='^pvp_custom_amount$'),
                CallbackQueryHandler(owner_pvp_transfer_cancel_callback, pattern=f'^{OWNER_PVP_TRANSFER_CANCEL}$')
            ],
            WAITING_PVP_TRANSFER_CONFIRM: [
                CallbackQueryHandler(owner_pvp_transfer_confirm_callback, pattern=f'^{OWNER_PVP_TRANSFER_CONFIRM_YES}$'),
                CallbackQueryHandler(owner_pvp_transfer_cancel_callback, pattern=f'^{OWNER_PVP_TRANSFER_CANCEL}$')
            ],
        },
        fallbacks=[CallbackQueryHandler(owner_pvp_transfer_cancel_callback, pattern=f'^{OWNER_PVP_TRANSFER_CANCEL}$')],
    )

    # Регистрируем ConversationHandler для перевода PvP
    application.add_handler(owner_pvp_transfer_conversation)

    # Создаём ConversationHandler для ввода своего процента PvP
    from owner_handlers import WAITING_PVP_CUSTOM_INPUT
    owner_pvp_custom_conversation = ConversationHandler(
        entry_points=[
            CallbackQueryHandler(owner_pvp_custom_percent_callback, pattern=r'^pvp_(exercise|complex|challenge)_custom$')
        ],
        states={
            WAITING_PVP_CUSTOM_INPUT: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, owner_pvp_custom_input),
                CallbackQueryHandler(owner_pvp_settings_callback, pattern=f'^{OWNER_PVP_SETTINGS}$')
            ],
        },
        fallbacks=[CallbackQueryHandler(owner_pvp_settings_callback, pattern=f'^{OWNER_PVP_SETTINGS}$')],
        per_message=True  # Отслеживать CallbackQueryHandler для каждого сообщения
    )

    # Регистрируем ConversationHandler для ввода своего процента PvP
    application.add_handler(owner_pvp_custom_conversation)

    # Создаём ConversationHandler для отправки сообщения в канал
    owner_channel_message_conversation = ConversationHandler(
        entry_points=[
            CallbackQueryHandler(owner_channel_message_callback, pattern=f'^{OWNER_CHANNEL_MESSAGE}$')
        ],
        states={
            WAITING_CHANNEL_MESSAGE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, owner_channel_message_send),
                CommandHandler("cancel", owner_channel_message_cancel),
            ],
        },
        fallbacks=[
            CommandHandler("cancel", owner_channel_message_cancel),
            CallbackQueryHandler(owner_channel_check_callback, pattern=f'^{OWNER_CHANNEL_CHECK}$')
        ],
        per_message=False
    )

    # Регистрируем ConversationHandler для отправки сообщения в канал
    application.add_handler(owner_channel_message_conversation)

    # Регистрируем AI-обработчики
    application.add_handler(ai_advice_conversation)
    application.add_handler(ai_photo_conversation)

    # Регистрируем обработчик callback-запросов для главного меню
    application.add_handler(CallbackQueryHandler(handle_main_menu, pattern=r'^(mountain|sport|pvp|hall_of_fame|profile|admin|owner_menu|owner_stats|owner_balances|owner_champions|owner_champions_history|owner_champions_menu|owner_champions_calculate|owner_champions_confirm|back_to_main|ai_menu|calendar)$'))

    # Регистрируем обработчики для кнопок Топ Горы Успеха
    application.add_handler(CallbackQueryHandler(mountain_top_callback, pattern=f'^{MOUNTAIN_TOP20_CALLBACK}_'))
    application.add_handler(CallbackQueryHandler(mountain_top_callback, pattern=f'^{MOUNTAIN_TOP50_CALLBACK}_'))
    application.add_handler(CallbackQueryHandler(mountain_top_callback, pattern=f'^{MOUNTAIN_TOP100_CALLBACK}_'))
    application.add_handler(CallbackQueryHandler(mountain_top_callback, pattern=f'^{MOUNTAIN_TOP200_CALLBACK}_'))

    # Регистрируем обработчики календаря тренировок
    application.add_handler(CallbackQueryHandler(calendar_navigation, pattern=f'^{CALENDAR_PREV}$'))
    application.add_handler(CallbackQueryHandler(calendar_navigation, pattern=f'^{CALENDAR_NEXT}$'))
    application.add_handler(CallbackQueryHandler(calendar_navigation, pattern=f'^{CALENDAR_BACK}$'))
    application.add_handler(CallbackQueryHandler(calendar_day_click, pattern=f'^{CALENDAR_DAY}_'))

    # Регистрируем обработчик для поискового ввода (должен быть последним)
    application.add_handler(MessageHandler(filters.PHOTO | filters.VIDEO | filters.Document.ALL, handle_complex_media))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_complex_exercise_result))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_search_input_if_waiting))

    # Регистрируем универсальный обработчик для всех остальных callback
    application.add_handler(CallbackQueryHandler(handle_callback_query))

    # Инициализируем таблицу для уведомлений о рейтинге
    logger.info("🔔 Инициализация системы уведомлений о рейтинге...")
    init_ranking_notifications_table()

    # JobQueue не поддерживается в этой версии
    logger.info("ℹ️ Автоматические задачи через JobQueue не поддерживаются")

    # Запускаем веб-сервер для Render health check
    if WEB_SERVER_AVAILABLE:
        try:
            start_web_server()
            logger.info("✅ Веб-сервер для health check запущен")
        except Exception as e:
            logger.warning(f"⚠️ Не удалось запустить веб-сервер: {e}")

    # Запускаем бота
    logger.info("Бот запущен...")
    logger.info("🏠 Готов к работе! Модули: Гора Успеха ✅, PvP ✅, Спорт ✅, Рефералы ✅, Админ ✅")
    logger.info("ℹ️ JobQueue отключен - автоматические задачи не работают")
    logger.info("📱 Reply-кнопки: 🏠 Меню, ❌ Отмена - активированы")

    # Запуск с поддержкой Python 3.14+
    import asyncio
    import sys

    if sys.version_info >= (3, 14):
        # Для Python 3.14+ создаём event loop вручную
        logger.info("🔄 Python 3.14+ обнаружен, используем специальный запуск")

        async def run_bot():
            async with application:
                await application.initialize()
                await application.start()
                await application.updater.start_polling()
                # Держим бота запущенным
                stop_event = asyncio.Event()
                await stop_event.wait()

        try:
            asyncio.run(run_bot())
        except KeyboardInterrupt:
            logger.info("Бот остановлен")
    else:
        # Для Python 3.12 и ниже стандартный запуск
        application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == '__main__':
    main()