# -*- coding: utf-8 -*-
# Обработчики панели собственника

import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.error import BadRequest
from telegram.ext import ContextTypes, ConversationHandler, MessageHandler, filters
from database_postgres import get_db_connection, release_db_connection, is_owner

logger = logging.getLogger(__name__)

OWNER_MENU = "owner_menu"
OWNER_STATS = "owner_stats"
OWNER_BALANCES = "owner_balances"
OWNER_CHAMPIONS = "owner_champions"
OWNER_CHAMPIONS_HISTORY = "owner_champions_history"
OWNER_CHAMPIONS_MENU = "owner_champions_menu"
OWNER_CHAMPIONS_CALCULATE = "owner_champions_calculate"
OWNER_CHAMPIONS_CALCULATE_CURRENT = "owner_champions_calculate_current"
OWNER_CHAMPIONS_CONFIRM = "owner_champions_confirm"
OWNER_COMPETITIONS = "owner_competitions"
OWNER_COMPETITIONS_TOGGLE = "owner_competitions_toggle"
OWNER_COMPETITIONS_ENABLE_ALL = "owner_competitions_enable_all"
OWNER_COMPETITIONS_DISABLE_ALL = "owner_competitions_disable_all"
OWNER_COMPETITIONS_ENABLE_BEGINNERS = "owner_competitions_enable_beginners"
OWNER_FF_INFO = "owner_ff_info"
OWNER_FF_TRANSFER = "owner_ff_transfer"
OWNER_FF_TRANSFER_CANCEL = "owner_ff_transfer_cancel"
OWNER_FF_TRANSFER_CONFIRM_YES = "owner_ff_transfer_confirm_yes"
OWNER_BACK = "owner_back"

# PvP настройки
OWNER_PVP_SETTINGS = "owner_pvp_settings"
OWNER_PVP_EXERCISE = "owner_pvp_exercise"
OWNER_PVP_COMPLEX = "owner_pvp_complex"
OWNER_PVP_CHALLENGE = "owner_pvp_challenge"

# PvP перевод очков (аналогично FF)
OWNER_PVP_TRANSFER = "owner_pvp_transfer"
OWNER_PVP_TRANSFER_CANCEL = "owner_pvp_transfer_cancel"
OWNER_PVP_TRANSFER_CONFIRM_YES = "owner_pvp_transfer_confirm_yes"

# Каналы
OWNER_CHANNEL_CHECK = "owner_channel_check"
OWNER_CHANNEL_RECONNECT = "owner_channel_reconnect"
OWNER_CHANNEL_MESSAGE = "owner_channel_message"
OWNER_CHANNEL_CANCEL = "owner_channel_cancel"

# Состояния для ConversationHandler перевода FF
WAITING_FF_TRANSFER_USER, WAITING_FF_TRANSFER_AMOUNT, WAITING_FF_TRANSFER_CONFIRM = range(3)

# Состояния для ConversationHandler перевода PvP (аналогично FF)
WAITING_PVP_TRANSFER_USER, WAITING_PVP_TRANSFER_AMOUNT, WAITING_PVP_TRANSFER_CONFIRM = range(20, 23)

# Состояния для ConversationHandler ввода своего процента PvP
WAITING_PVP_CUSTOM_INPUT = range(10, 11)

# Состояния для ConversationHandler отправки сообщения в канал
WAITING_CHANNEL_MESSAGE = range(30, 31)


def escape_markdown(text):
    """Экранирует спецсимволы для Markdown."""
    if not text:
        return ""

    # Экранируем спецсимволы Markdown
    special_chars = ['_', '*', '[', ']', '(', ')', '~', '`', '>', '#', '+', '-', '=', '|', '{', '}', '.', '!']
    result = str(text)

    for char in special_chars:
        result = result.replace(char, '\\' + char)

    return result


# Декоратор для проверки доступа
def owner_only(func):
    """Декоратор для проверки, что пользователь является владельцем."""
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = update.effective_user.id

        if not is_owner(user_id):
            try:
                if update.callback_query:
                    await update.callback_query.answer("❌ Доступ только для собственника", show_alert=True)
                elif update.message:
                    await update.message.reply_text("❌ Доступ только для собственника")
            except:
                pass
            return

        return await func(update, context)
    return wrapper


@owner_only
async def owner_menu_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показывает главное меню собственника."""
    query = update.callback_query

    try:
        await query.answer()
    except:
        pass

    text = "🔧 **ПАНЕЛЬ СОБСТВЕННИКА**\n\n"
    text += "Выберите раздел:"

    keyboard = [
        [
            InlineKeyboardButton("📊 Статистика", callback_data=OWNER_STATS),
            InlineKeyboardButton("💰 Балансы FF", callback_data=OWNER_BALANCES),
        ],
        [
            InlineKeyboardButton("⚡ Соревнования", callback_data=OWNER_COMPETITIONS),
            InlineKeyboardButton("🏆 Чемпионы", callback_data=OWNER_CHAMPIONS),
        ],
        [
            InlineKeyboardButton("💸 Перевести FF", callback_data=OWNER_FF_TRANSFER),
            InlineKeyboardButton("🏆 Перевести FruNStatus", callback_data=OWNER_PVP_TRANSFER),
        ],
        [
            InlineKeyboardButton("📢 Каналы", callback_data=OWNER_CHANNEL_CHECK),
            InlineKeyboardButton("⚔️ PvP настройки", callback_data=OWNER_PVP_SETTINGS),
        ],
        [
            InlineKeyboardButton("ℹ️ FF Информация", callback_data=OWNER_FF_INFO),
            InlineKeyboardButton("◀️ В главное меню", callback_data="back_to_main"),
        ],
    ]

    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")


@owner_only
async def owner_stats_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показывает общую статистику."""
    query = update.callback_query

    try:
        await query.answer()
    except:
        pass

    conn = get_db_connection()
    cur = conn.cursor()

    try:
        # Общая статистика
        cur.execute("SELECT COUNT(*) FROM users")
        total_users = cur.fetchone()[0]

        cur.execute("SELECT COUNT(*) FROM exercises WHERE is_speed_competition = TRUE")
        active_competitions = cur.fetchone()[0]

        cur.execute("SELECT SUM(fun_fuel_balance) FROM users WHERE fun_fuel_balance IS NOT NULL")
        total_ff = cur.fetchone()[0] or 0

        cur.execute("SELECT COUNT(*) FROM workouts")
        total_workouts = cur.fetchone()[0]

        text = "📊 **СТАТИСТИКА БОТА**\n\n"
        text += f"👤 Пользователей: {total_users}\n"
        text += f"⚡ Соревнований: {active_competitions}\n"
        text += f"💰 Всего FFCoin в системе: {total_ff}\n"
        text += f"💪 Тренировок выполнено: {total_workouts}\n"

        keyboard = [[InlineKeyboardButton("◀️ В меню", callback_data=OWNER_MENU)]]
        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")

    except Exception as e:
        logger.error(f"Ошибка получения статистики: {e}")
        text = f"❌ Ошибка получения статистики: {e}"
        keyboard = [[InlineKeyboardButton("◀️ В меню", callback_data=OWNER_MENU)]]
        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard))
    finally:
        release_db_connection(conn)


@owner_only
async def owner_balances_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показывает балансы FF пользователей."""
    query = update.callback_query

    try:
        await query.answer()
    except:
        pass

    conn = get_db_connection()
    cur = conn.cursor()

    try:
        cur.execute("""
            SELECT telegram_id, first_name, username, fun_fuel_balance
            FROM users
            WHERE fun_fuel_balance IS NOT NULL
            ORDER BY fun_fuel_balance DESC
            LIMIT 20
        """)

        users = cur.fetchall()

        if not users:
            text = "💰 **БАЛАНСЫ FFCoin**\n\n"
            text += "Пока нет данных"
        else:
            text = "💰 **БАЛАНСЫ FFCoin (ТОП-20)**\n\n"
            text += "💡 Нажми на кнопку чтобы скопировать ID\n\n"

            # Создаём список с кнопками для каждого пользователя
            keyboard = []

            for user in users:
                telegram_id, first_name, username, balance = user
                username_str = f"@{username}" if username else "(нет username)"
                # Экранируем спецсимволы
                safe_first_name = escape_markdown(first_name)
                safe_username = escape_markdown(username_str)
                text += f"💎 {safe_first_name} {safe_username}: {balance} FFCoin\n"

                # Добавляем кнопку с ID
                button_text = f"📋 {telegram_id}"
                keyboard.append([InlineKeyboardButton(button_text, callback_data=f"copy_id:{telegram_id}")])

            keyboard.append([InlineKeyboardButton("◀️ В меню", callback_data=OWNER_MENU)])
            await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")

    except Exception as e:
        logger.error(f"Ошибка получения балансов: {e}")
        text = f"❌ Ошибка получения балансов: {e}"
        keyboard = [[InlineKeyboardButton("◀️ В меню", callback_data=OWNER_MENU)]]
        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard))
    finally:
        release_db_connection(conn)


@owner_only
async def owner_copy_id_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показывает ID пользователя для копирования."""
    query = update.callback_query

    try:
        await query.answer()
    except:
        pass

    # Извлекаем ID из callback_data
    callback_data = query.data
    if not callback_data.startswith("copy_id:"):
        return

    try:
        user_id = callback_data.split(":")[1]

        text = f"📋 **ID ПОЛЬЗОВАТЕЛЯ**\n\n"
        text += f"```\n{user_id}\n```\n\n"
        text += "💡 Длительно нажми на ID чтобы скопировать"

        keyboard = [[InlineKeyboardButton("◀️ Вернуться к балансам", callback_data=OWNER_BALANCES)]]

        try:
            await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")
        except Exception as e:
            if "not modified" not in str(e):
                logger.error(f"Ошибка отображения: {e}")
                raise

    except Exception as e:
        logger.error(f"Ошибка копирования ID: {e}")


@owner_only
async def owner_champions_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показывает историю чемпионов."""
    query = update.callback_query

    try:
        await query.answer()
    except:
        pass

    from champions_system import get_monthly_champions
    from datetime import datetime

    # Получаем чемпионов за прошлый месяц
    today = datetime.now()
    if today.month == 1:
        year = today.year - 1
        month = 12
    else:
        year = today.year
        month = today.month - 1

    champions = get_monthly_champions(year, month)

    if not champions:
        text = f"🏆 **ЧЕМПИОНЫ ЗА {month}.{year}**\n\n"
        text += "Чемпионов пока нет. Убедитесь, что:\n"
        text += "• Упражнения включены в соревнования\n"
        text += "• Есть результаты за период"
    else:
        text = f"🏆 **ЧЕМПИОНЫ ЗА {month}.{year}**\n\n"

        # Группируем по упражнениям
        from collections import defaultdict
        exercises_champions = defaultdict(list)

        for champ in champions:
            exercise_id = champ[3]  # target_id
            exercises_champions[exercise_id].append(champ)

        for exercise_id, champs in exercises_champions.items():
            exercise_name = champs[0][13] or f"Упражнение #{exercise_id}"
            safe_exercise_name = escape_markdown(exercise_name)

            text += f"🥇 **{safe_exercise_name}**\n"

            for champ in champs:
                position = champ[6]
                first_name = champ[14] or "Пользователь"
                username = champ[15]
                wins_score = champ[7]

                if position == 1:
                    emoji = "🥇"
                elif position == 2:
                    emoji = "🥈"
                else:
                    emoji = "🥉"

                username_str = f"@{username}" if username else "(нет username)"
                safe_first_name = escape_markdown(first_name)
                safe_username = escape_markdown(username_str)

                text += f"{emoji} {safe_first_name} {safe_username} - {wins_score} очков\n"

            text += "\n"

    keyboard = [
        [
            InlineKeyboardButton("🔄 Рассчитать", callback_data=OWNER_CHAMPIONS_CALCULATE),
            InlineKeyboardButton("◀️ В меню чемпионы", callback_data=OWNER_MENU),
        ],
    ]

    try:
        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")
    except Exception as e:
        if "not modified" not in str(e):
            logger.error(f"Ошибка отображения истории чемпионов: {e}")
            raise


@owner_only
async def owner_champions_menu_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показывает меню чемпионов с кнопкой расчёта."""
    query = update.callback_query

    try:
        await query.answer()
    except:
        pass

    text = "🏆 **ЧЕМПИОНЫ**\n\n"
    text += "Выберите действие:"

    keyboard = [
        [
            InlineKeyboardButton("🔄 Рассчитать прошлый месяц", callback_data=OWNER_CHAMPIONS_CALCULATE),
            InlineKeyboardButton("📊 История чемпионов", callback_data=OWNER_CHAMPIONS_HISTORY),
        ],
        [
            InlineKeyboardButton("📈 Рассчитать текущий месяц", callback_data=OWNER_CHAMPIONS_CALCULATE_CURRENT),
            InlineKeyboardButton("📈 Статистика системы", callback_data=OWNER_STATS),
        ],
        [
            InlineKeyboardButton("◀️ В меню", callback_data=OWNER_MENU),
        ],
    ]

    try:
        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")
    except Exception as e:
        # Если сообщение не изменилось, просто игнорируем
        if "not modified" not in str(e):
            logger.error(f"Ошибка отображения меню чемпионов: {e}")
            raise


@owner_only
async def owner_champions_history_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показывает историю чемпионов."""
    query = update.callback_query

    try:
        await query.answer()
    except:
        pass

    from champions_system import get_monthly_champions
    from datetime import datetime

    # Получаем чемпионов за прошлый месяц
    today = datetime.now()
    if today.month == 1:
        year = today.year - 1
        month = 12
    else:
        year = today.year
        month = today.month - 1

    champions = get_monthly_champions(year, month)

    if not champions:
        text = f"🏆 **ЧЕМПИОНЫ ЗА {month}.{year}**\n\n"
        text += "Чемпионов пока нет. Убедитесь, что:\n"
        text += "• Упражнения включены в соревнования\n"
        text += "• Есть результаты за период"
    else:
        text = f"🏆 **ЧЕМПИОНЫ ЗА {month}.{year}**\n\n"

        # Группируем по упражнениям
        from collections import defaultdict
        exercises_champions = defaultdict(list)

        for champ in champions:
            exercise_id = champ[3]  # target_id
            exercises_champions[exercise_id].append(champ)

        for exercise_id, champs in exercises_champions.items():
            exercise_name = champs[0][13] or f"Упражнение #{exercise_id}"
            safe_exercise_name = escape_markdown(exercise_name)

            text += f"🥇 **{safe_exercise_name}**\n"

            for champ in champs:
                position = champ[6]
                first_name = champ[14] or "Пользователь"
                username = champ[15]
                wins_score = champ[7]

                if position == 1:
                    emoji = "🥇"
                elif position == 2:
                    emoji = "🥈"
                else:
                    emoji = "🥉"

                username_str = f"@{username}" if username else "(нет username)"
                safe_first_name = escape_markdown(first_name)
                safe_username = escape_markdown(username_str)

                text += f"{emoji} {safe_first_name} {safe_username} - {wins_score} очков\n"

            text += "\n"

    keyboard = [
        [
            InlineKeyboardButton("🔄 Рассчитать", callback_data=OWNER_CHAMPIONS_CALCULATE),
            InlineKeyboardButton("◀️ В меню чемпионы", callback_data=OWNER_CHAMPIONS_MENU),
        ],
    ]

    try:
        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")
    except Exception as e:
        if "not modified" not in str(e):
            logger.error(f"Ошибка отображения истории чемпионов: {e}")
            raise


@owner_only
async def owner_champions_calculate_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показывает меню расчёта чемпионов."""
    query = update.callback_query

    try:
        await query.answer()
    except:
        pass

    from datetime import datetime
    today = datetime.now()

    # Определяем прошлый месяц
    if today.month == 1:
        year = today.year - 1
        month = 12
    else:
        year = today.year
        month = today.month - 1

    text = f"🏆 **РАСЧЁТ ЧЕМПИОНОВ**\n\n"
    text += f"Будут рассчитаны чемпионы за: {month}.{year}\n\n"
    text += "⚠️ **ВНИМАНИЕ:**\n"
    text += "Это начислит мега-бонусы:\n"
    text += "• 1 место: 50% банка очков\n"
    text += "• 2 место: 30% банка очков\n"
    text += "• 3 место: 20% банка очков\n\n"
    text += "Вы уверены?"

    keyboard = [
        [
            InlineKeyboardButton("✅ ДА, Рассчитать", callback_data=OWNER_CHAMPIONS_CONFIRM),
            InlineKeyboardButton("❌ Отмена", callback_data=OWNER_CHAMPIONS_MENU),
        ],
        [InlineKeyboardButton("◀️ В меню", callback_data=OWNER_MENU)],
    ]

    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")


@owner_only
async def owner_champions_calculate_current_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Рассчитывает чемпионов за текущий месяц."""
    query = update.callback_query

    try:
        await query.answer()
    except:
        pass

    from datetime import datetime
    today = datetime.now()
    year = today.year
    month = today.month

    text = f"📈 **РАСЧЁТ ЧЕМПИОНОВ**\n\n"
    text += f"Будут рассчитаны чемпионы за: {month}.{year}\n\n"
    text += "⚠️ **ВНИМАНИЕ:**\n"
    text += "Это расчёт за ТЕКУЩИЙ месяц (пока идёт).\n"
    text += "Используйте для тестирования!\n\n"
    text += "Вы уверены?"

    keyboard = [
        [
            InlineKeyboardButton("✅ ДА, Рассчитать", callback_data=OWNER_CHAMPIONS_CONFIRM),
            InlineKeyboardButton("❌ Отмена", callback_data=OWNER_CHAMPIONS_MENU),
        ],
        [InlineKeyboardButton("◀️ В меню", callback_data=OWNER_MENU)],
    ]

    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")


@owner_only
async def owner_champions_confirm_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Выполняет расчёт чемпионов."""
    query = update.callback_query

    try:
        await query.answer()
    except:
        pass

    # Показываем сообщение о процессе
    text = "⏳ **РАСЧЁТ ЧЕМПИОНОВ**\n\n"
    text += "Пожалуйста, подождите...\n"
    text += "Это может занять несколько минут."

    keyboard = [[InlineKeyboardButton("◀️ В меню", callback_data=OWNER_MENU)]]

    try:
        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")
    except Exception as e:
        if "not modified" not in str(e):
            logger.error(f"Ошибка отображения: {e}")
            raise

    # Выполняем расчёт с уведомлениями
    try:
        from champions_system import calculate_and_notify_champions

        results = await calculate_and_notify_champions(context)

        if not results:
            text = "❌ **РАСЧЁТ ЗАВЕРШЁН**\n\n"
            text += "Нет данных для расчёта чемпионов.\n\n"
            text += "💡 Убедитесь, что:\n"
            text += "• Упражнения включены в соревнования\n"
            text += "• Есть результаты за период\n"
            text += "• Этот период ещё не рассчитывался"
        else:
            notified_count = sum(len(champs) for champs in results.values())
            text = "✅ **РАСЧЁТ ЧЕМПИОНОВ ЗАВЕРШЁН**\n\n"
            text += f"🏆 Обработано упражнений: {len(results)}\n"
            text += f"📬 Уведомлений отправлено: {notified_count}\n\n"
            text += "💰 Мега-бонусы начислены!\n"
            text += "🎉 Чемпионы уведомлены!"

        keyboard = [[InlineKeyboardButton("🔙 Вернуться в чемпионы", callback_data=OWNER_CHAMPIONS_MENU)]]
        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")

    except Exception as e:
        logger.error(f"Ошибка расчёта чемпионов: {e}")
        text = f"❌ **ОШИБКА РАСЧЁТА**\n\n"
        text += f"Произошла ошибка:\n{str(e)}\n\n"
        text += "Проверьте логи для деталей."

        keyboard = [[InlineKeyboardButton("◀️ В меню", callback_data=OWNER_MENU)]]
        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")


@owner_only
async def owner_competitions_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показывает список упражнений для управления соревнованиями."""
    query = update.callback_query

    try:
        await query.answer()
    except:
        pass

    conn = get_db_connection()
    cur = conn.cursor()

    try:
        # Получаем все упражнения
        cur.execute("""
            SELECT id, name, is_speed_competition
            FROM exercises
            ORDER BY is_speed_competition DESC, name
        """)

        exercises = cur.fetchall()

        if not exercises:
            text = "⚡ **УПРАВЛЕНИЕ СОРЕВНОВАНИЯМИ**\n\n"
            text += "Упражнений пока нет"
            keyboard = [[InlineKeyboardButton("◀️ В меню", callback_data=OWNER_MENU)]]
        else:
            text = "⚡ **УПРАВЛЕНИЕ СОРЕВНОВАНИЯМИ**\n\n"

            active_count = 0
            inactive_count = 0

            for ex in exercises:
                ex_id, name, is_active = ex
                if is_active:
                    active_count += 1
                else:
                    inactive_count += 1

            text += f"📊 Всего: {len(exercises)} | 🟢 Активно: {active_count} | 🔴 Неактивно: {inactive_count}\n\n"
            text += "Выберите действие:"

            # Массовые действия
            keyboard = [
                [
                    InlineKeyboardButton("🟢 Включить все", callback_data=OWNER_COMPETITIONS_ENABLE_ALL),
                    InlineKeyboardButton("🔴 Выключить все", callback_data=OWNER_COMPETITIONS_DISABLE_ALL),
                ],
                [
                    InlineKeyboardButton("🟡 Включить новичковые", callback_data=OWNER_COMPETITIONS_ENABLE_BEGINNERS),
                    InlineKeyboardButton("⏬ Список упражнений", callback_data=OWNER_COMPETITIONS),
                ],
                [
                    InlineKeyboardButton("◀️ В меню", callback_data=OWNER_MENU),
                ],
            ]

        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")

    except Exception as e:
        logger.error(f"Ошибка получения упражнений: {e}")
        text = f"❌ Ошибка получения упражнений: {e}"
        keyboard = [[InlineKeyboardButton("◀️ В меню", callback_data=OWNER_MENU)]]
        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard))
    finally:
        release_db_connection(conn)


@owner_only
async def owner_competitions_toggle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Переключает статус соревнования для упражнения."""
    query = update.callback_query

    try:
        await query.answer()
    except:
        pass

    # Извлекаем exercise_id из callback_data
    callback_data = query.data
    if not callback_data.startswith(OWNER_COMPETITIONS_TOGGLE + ":"):
        logger.error(f"Неверный формат callback_data: {callback_data}")
        return

    try:
        exercise_id = int(callback_data.split(":")[1])
    except (IndexError, ValueError):
        logger.error(f"Не удалось извлечь exercise_id из: {callback_data}")
        return

    conn = get_db_connection()
    cur = conn.cursor()

    try:
        # Получаем текущий статус
        cur.execute("""
            SELECT name, is_speed_competition
            FROM exercises
            WHERE id = %s
        """, (exercise_id,))

        result = cur.fetchone()
        if not result:
            text = "❌ Упражнение не найдено"
            keyboard = [[InlineKeyboardButton("◀️ В меню", callback_data=OWNER_MENU)]]
            await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard))
            return

        name, current_status = result
        new_status = not current_status

        # Обновляем статус
        cur.execute("""
            UPDATE exercises
            SET is_speed_competition = %s
            WHERE id = %s
            RETURNING name
        """, (new_status, exercise_id))

        conn.commit()

        status_text = "✅ ВКЛЮЧЕНО" if new_status else "❌ ВЫКЛЮЧЕНО"
        safe_name = escape_markdown(name)

        text = f"⚡ **УПРАВЛЕНИЕ СОРЕВНОВАНИЯМИ**\n\n"
        text += f"Статус изменён:\n"
        text += f"📝 {safe_name}\n"
        text += f"🔄 {status_text}\n\n"
        text += "Нажмите кнопку ниже для возврата в меню"

        keyboard = [
            [InlineKeyboardButton("🔄 Вернуться к списку", callback_data=OWNER_COMPETITIONS)],
            [InlineKeyboardButton("◀️ В главное меню", callback_data=OWNER_MENU)],
        ]

        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")

    except Exception as e:
        logger.error(f"Ошибка переключения статуса: {e}")
        text = f"❌ Ошибка переключения статуса: {e}"
        keyboard = [[InlineKeyboardButton("◀️ В меню", callback_data=OWNER_MENU)]]
        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard))
    finally:
        release_db_connection(conn)


@owner_only
async def owner_ff_info_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показывает информацию о системе FF и инструкцию по управлению."""
    query = update.callback_query

    try:
        await query.answer()
    except:
        pass

    conn = get_db_connection()
    cur = conn.cursor()

    try:
        # Получаем общую статистику FF
        cur.execute("SELECT SUM(fun_fuel_balance) FROM users WHERE fun_fuel_balance IS NOT NULL")
        total_ff = cur.fetchone()[0] or 0

        cur.execute("SELECT COUNT(*) FROM users WHERE fun_fuel_balance > 0")
        users_with_ff = cur.fetchone()[0]

        text = "💸 **УПРАВЛЕНИЕ FRUN FUEL**\n\n"

        text += "📊 **Статистика системы:**\n"
        text += f"💰 Всего FFCoin в системе: {total_ff}\n"
        text += f"👤 Пользователей с FFCoin: {users_with_ff}\n\n"

        text += "💡 **Как управлять FFCoin:**\n\n"
        text += "📝 **Для перевода FFCoin пользователю:**\n"
        text += "Используйте скрипт manage_ff.py\n"
        text += "Команда: python manage_ff.py add ID СУММА\n\n"

        text += "⚠️ **Важно:**\n"
        text += "• FFCoin используется для PvP ставок (10% комиссия)\n"
        text += "• Победитель получает 90% от банка\n"
        text += "• FFCoin также начисляется за достижения\n\n"

        text += "🔧 **Доступные команды:**\n"
        text += "• python manage_ff.py list - все пользователи\n"
        text += "• python manage_ff.py balance ID - баланс\n"
        text += "• python manage_ff.py add ID СУММА - начислить\n"
        text += "• python manage_ff.py stats - статистика"

        keyboard = [
            [InlineKeyboardButton("💰 Балансы FF", callback_data=OWNER_BALANCES)],
            [InlineKeyboardButton("◀️ В меню", callback_data=OWNER_MENU)],
        ]

        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")

    except Exception as e:
        logger.error(f"Ошибка получения информации о FF: {e}")
        text = f"❌ Ошибка получения информации: {e}"
        keyboard = [[InlineKeyboardButton("◀️ В меню", callback_data=OWNER_MENU)]]
        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard))
    finally:
        release_db_connection(conn)


@owner_only
async def owner_ff_transfer_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Начинает процесс перевода FF с выбором пользователя из списка."""
    query = update.callback_query

    try:
        await query.answer()
    except:
        pass

    conn = get_db_connection()
    cur = conn.cursor()

    try:
        # Получаем топ-20 пользователей по FF
        cur.execute("""
            SELECT telegram_id, first_name, username, fun_fuel_balance
            FROM users
            WHERE fun_fuel_balance IS NOT NULL
            ORDER BY fun_fuel_balance DESC NULLS LAST
            LIMIT 20
        """)

        users = cur.fetchall()

        text = "💸 **ПЕРЕВОД FFCoin**\n\n"
        text += "📝 Выберите пользователя из списка или введите ID/username вручную"

        keyboard = []

        # Добавляем кнопки для каждого пользователя
        for user in users:
            telegram_id, first_name, username, ff_balance = user
            username_part = f" @{username}" if username else ""
            ff_part = f" ({ff_balance} FFCoin)" if ff_balance else ""

            # Обрезаем длинные имена
            display_name = escape_markdown(first_name[:15])
            button_text = f"👤 {display_name}{username_part}{ff_part}"

            # Используем формат select_user:USER_ID
            keyboard.append([InlineKeyboardButton(button_text, callback_data=f"ff_select_user:{telegram_id}")])

        # Добавляем кнопку ручного ввода и отмены
        keyboard.append([InlineKeyboardButton("⌨️ Ввести ID/username вручную", callback_data="ff_manual_input")])
        keyboard.append([InlineKeyboardButton("❌ Отмена", callback_data=OWNER_FF_TRANSFER_CANCEL)])

        try:
            await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")
        except Exception as e:
            if "not modified" not in str(e):
                logger.error(f"Ошибка отображения: {e}")
                raise

        context.user_data['ff_transfer_state'] = WAITING_FF_TRANSFER_USER
        return WAITING_FF_TRANSFER_USER

    except Exception as e:
        logger.error(f"Ошибка получения списка пользователей: {e}")
        text = "❌ Ошибка получения списка пользователей"
        keyboard = [[InlineKeyboardButton("❌ Отмена", callback_data=OWNER_FF_TRANSFER_CANCEL)]]

        try:
            await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard))
        except:
            pass

        return ConversationHandler.END

    finally:
        release_db_connection(conn)


@owner_only
async def owner_ff_select_user_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обрабатывает выбор пользователя из списка."""
    query = update.callback_query

    try:
        await query.answer()
    except:
        pass

    # Извлекаем user_id из callback_data
    callback_data = query.data
    if not callback_data.startswith("ff_select_user:"):
        logger.error(f"Неверный формат callback_data: {callback_data}")
        return

    try:
        target_user_id = int(callback_data.split(":")[1])
    except (IndexError, ValueError):
        logger.error(f"Не удалось извлечь user_id из: {callback_data}")
        return

    # Получаем данные о пользователе
    conn = get_db_connection()
    cur = conn.cursor()

    try:
        cur.execute("""
            SELECT telegram_id, first_name, username, fun_fuel_balance
            FROM users
            WHERE telegram_id = %s
        """, (target_user_id,))

        user = cur.fetchone()

        if not user:
            text = "❌ Пользователь не найден"
            keyboard = [[InlineKeyboardButton("◀️ Назад", callback_data=OWNER_FF_TRANSFER)]]

            try:
                await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard))
            except:
                pass
            return

        # Показываем быстрые суммы
        telegram_id, first_name, username, ff_balance = user
        username_str = f"@{username}" if username else "(нет username)"
        safe_first_name = escape_markdown(first_name)
        safe_username = escape_markdown(username_str)
        current_ff = ff_balance or 0

        # Сохраняем данные о пользователе
        context.user_data['ff_transfer_target'] = {
            'telegram_id': telegram_id,
            'first_name': first_name,
            'username': username,
            'current_ff': current_ff
        }

        text = f"💸 **ПЕРЕВОД FF**\n\n"
        text += f"👤 {safe_first_name} {safe_username}\n"
        text += f"🆔 ID: {telegram_id}\n"
        text += f"💰 Текущий баланс: {current_ff} FFCoin\n\n"
        text += "📝 Выберите сумму (положительную для начисления, отрицательную для списания):\n\n"
        text += "⚠️ Для СПИСАНИЯ используй кнопку ниже или введи -100, -500 и т.д."

        # Быстрые суммы
        keyboard = [
            [
                InlineKeyboardButton("10 FF", callback_data="ff_amount:10"),
                InlineKeyboardButton("50 FF", callback_data="ff_amount:50"),
            ],
            [
                InlineKeyboardButton("100 FF", callback_data="ff_amount:100"),
                InlineKeyboardButton("500 FF", callback_data="ff_amount:500"),
            ],
            [
                InlineKeyboardButton("1000 FF", callback_data="ff_amount:1000"),
                InlineKeyboardButton("⌨️ Своя сумма", callback_data="ff_custom_amount"),
            ],
            [
                InlineKeyboardButton("❌ Списать 100", callback_data="ff_amount:-100"),
                InlineKeyboardButton("❌ Списать 500", callback_data="ff_amount:-500"),
            ],
            [
                InlineKeyboardButton("◀️ Назад", callback_data=OWNER_FF_TRANSFER),
                InlineKeyboardButton("❌ Отмена", callback_data=OWNER_FF_TRANSFER_CANCEL),
            ],
        ]

        try:
            await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")
        except Exception as e:
            if "not modified" not in str(e):
                logger.error(f"Ошибка отображения: {e}")
                raise

        context.user_data['ff_transfer_state'] = WAITING_FF_TRANSFER_AMOUNT
        return WAITING_FF_TRANSFER_AMOUNT

    finally:
        release_db_connection(conn)


@owner_only
async def owner_ff_manual_input_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показывает подсказку для ручного ввода ID/username."""
    query = update.callback_query

    try:
        await query.answer()
    except:
        pass

    text = "💸 **ПЕРЕВОД FF**\n\n"
    text += "📝 Введите:\n"
    text += "• Telegram ID (число)\n"
    text += "• @username (например, @username)\n"
    text += "• username без @\n\n"
    text += "💡 Используйте /id чтобы узнать свой ID"

    keyboard = [
        [InlineKeyboardButton("◀️ Вернуться к списку", callback_data=OWNER_FF_TRANSFER)],
        [InlineKeyboardButton("❌ Отмена", callback_data=OWNER_FF_TRANSFER_CANCEL)],
    ]

    try:
        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")
    except Exception as e:
        if "not modified" not in str(e):
            logger.error(f"Ошибка отображения: {e}")
            raise


@owner_only
async def owner_ff_transfer_user_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обрабатывает ввод Telegram ID или username пользователя."""
    if not update.message:
        return

    user_input = update.message.text.strip()

    conn = get_db_connection()
    cur = conn.cursor()

    try:
        # Проверяем, что это ID (число) или username (текст)
        target_user = None

        # Сначала пробуем как ID
        try:
            target_user_id = int(user_input)
            cur.execute("""
                SELECT telegram_id, first_name, username, fun_fuel_balance
                FROM users
                WHERE telegram_id = %s
            """, (target_user_id,))
            target_user = cur.fetchone()
        except ValueError:
            # Не число - значит username
            # Убираем @ если есть
            username = user_input.lstrip('@')
            cur.execute("""
                SELECT telegram_id, first_name, username, fun_fuel_balance
                FROM users
                WHERE username = %s
            """, (username,))
            target_user = cur.fetchone()

        if not target_user:
            text = "❌ **Пользователь не найден!**\n\n"
            text += f"Пользователь не найден в системе.\n"
            text += "📝 Попробуйте другой ID/@username или нажмите Отмена:"

            keyboard = [[InlineKeyboardButton("❌ Отмена", callback_data=OWNER_FF_TRANSFER_CANCEL)]]

            if update.message:
                await update.message.reply_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")
            return

        # Пользователь найден - показываем информацию и просим сумму
        telegram_id, first_name, username, ff_balance = target_user
        username_str = f"@{username}" if username else "(нет username)"
        safe_first_name = escape_markdown(first_name)
        safe_username = escape_markdown(username_str)
        current_ff = ff_balance or 0

        # Сохраняем данные о пользователе
        context.user_data['ff_transfer_target'] = {
            'telegram_id': telegram_id,
            'first_name': first_name,
            'username': username,
            'current_ff': current_ff
        }

        text = f"💸 **ПЕРЕВОД FF**\n\n"
        text += f"👤 Пользователь: {safe_first_name} {safe_username}\n"
        text += f"🆔 ID: {telegram_id}\n"
        text += f"💰 Текущий баланс: {current_ff} FFCoin\n\n"
        text += "📝 Введите сумму для перевода:"

        keyboard = [[InlineKeyboardButton("❌ Отмена", callback_data=OWNER_FF_TRANSFER_CANCEL)]]

        if update.message:
            sent_message = await update.message.reply_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")
            # Сохраняем message_id для последующего редактирования
            context.user_data['ff_transfer_message_id'] = sent_message.message_id

        context.user_data['ff_transfer_state'] = WAITING_FF_TRANSFER_AMOUNT
        return WAITING_FF_TRANSFER_AMOUNT

    finally:
        release_db_connection(conn)


@owner_only
async def owner_ff_amount_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обрабатывает выбор быстрой суммы."""
    query = update.callback_query

    try:
        await query.answer()
    except:
        pass

    # Извлекаем сумму из callback_data
    callback_data = query.data
    if not callback_data.startswith("ff_amount:"):
        logger.error(f"Неверный формат callback_data: {callback_data}")
        return

    try:
        amount = int(callback_data.split(":")[1])
    except (IndexError, ValueError):
        logger.error(f"Не удалось извлечь сумму из: {callback_data}")
        return

    # Получаем данные о пользователе
    target_user = context.user_data.get('ff_transfer_target')
    if not target_user:
        text = "❌ Ошибка сеанса. Попробуйте снова."
        keyboard = [[InlineKeyboardButton("◀️ В меню", callback_data=OWNER_MENU)]]

        try:
            await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard))
        except:
            pass

        context.user_data.pop('ff_transfer_target', None)
        context.user_data.pop('ff_transfer_state', None)
        return ConversationHandler.END

    # Сохраняем сумму и показываем подтверждение
    context.user_data['ff_transfer_amount'] = amount

    safe_first_name = escape_markdown(target_user['first_name'])
    username_str = f"@{target_user['username']}" if target_user['username'] else "(нет username)"
    safe_username = escape_markdown(username_str)
    new_balance = target_user['current_ff'] + amount

    text = "✅ **ПОДТВЕРЖДЕНИЕ ПЕРЕВОДА**\n\n"
    text += f"👤 Получатель: {safe_first_name} {safe_username}\n"
    text += f"🆔 ID: {target_user['telegram_id']}\n"
    text += f"💰 Сумма: {amount} FF\n"
    text += f"📊 Текущий баланс: {target_user['current_ff']} FF\n"
    text += f"📊 Новый баланс: {new_balance} FF\n\n"
    text += "✅ Подтвердите перевод:"

    keyboard = [
        [
            InlineKeyboardButton("✅ Да, перевести", callback_data=OWNER_FF_TRANSFER_CONFIRM_YES),
            InlineKeyboardButton("❌ Отмена", callback_data=OWNER_FF_TRANSFER_CANCEL),
        ],
    ]

    try:
        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")
    except Exception as e:
        if "not modified" not in str(e):
            logger.error(f"Ошибка отображения: {e}")
            raise

    context.user_data['ff_transfer_state'] = WAITING_FF_TRANSFER_CONFIRM
    return WAITING_FF_TRANSFER_CONFIRM


@owner_only
async def owner_ff_custom_amount_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показывает подсказку для ввода своей суммы."""
    query = update.callback_query

    try:
        await query.answer()
    except:
        pass

    text = "💸 **ПЕРЕВОД FF**\n\n"
    text += "📝 Введите сумму для перевода:"

    keyboard = [
        [InlineKeyboardButton("◀️ Вернуться к суммам", callback_data=OWNER_FF_TRANSFER)],
        [InlineKeyboardButton("❌ Отмена", callback_data=OWNER_FF_TRANSFER_CANCEL)],
    ]

    try:
        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")
    except Exception as e:
        if "not modified" not in str(e):
            logger.error(f"Ошибка отображения: {e}")
            raise


@owner_only
async def owner_ff_transfer_amount_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обрабатывает ввод суммы и показывает подтверждение."""
    if not update.message:
        return

    amount_input = update.message.text.strip()

    # Проверяем, что это число
    try:
        amount = int(amount_input)
    except ValueError:
        text = "❌ **Неверная сумма!**\n\n"
        text += "Введите число (положительное для начисления, отрицательное для списания).\n"
        text += "📝 Попробуйте снова или нажмите Отмена:"

        keyboard = [[InlineKeyboardButton("❌ Отмена", callback_data=OWNER_FF_TRANSFER_CANCEL)]]

        if update.message:
            await update.message.reply_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")
        return

    # Получаем данные о пользователе
    target_user = context.user_data.get('ff_transfer_target')
    if not target_user:
        text = "❌ Ошибка сеанса. Начните заново."
        keyboard = [[InlineKeyboardButton("◀️ В меню", callback_data=OWNER_MENU)]]

        if update.message:
            await update.message.reply_text(text, reply_markup=InlineKeyboardMarkup(keyboard))
        return ConversationHandler.END

    # Сохраняем сумму
    context.user_data['ff_transfer_amount'] = amount

    # Показываем подтверждение
    safe_first_name = escape_markdown(target_user['first_name'])
    username_str = f"@{target_user['username']}" if target_user['username'] else "(нет username)"
    safe_username = escape_markdown(username_str)
    new_balance = target_user['current_ff'] + amount

    text = "💸 **ПОДТВЕРЖДЕНИЕ ПЕРЕВОДА**\n\n"
    text += f"👤 Получатель: {safe_first_name} {safe_username}\n"
    text += f"🆔 ID: {target_user['telegram_id']}\n"
    text += f"💰 Сумма: {amount} FF\n"
    text += f"📊 Текущий баланс: {target_user['current_ff']} FF\n"
    text += f"📊 Новый баланс: {new_balance} FF\n\n"
    text += "✅ Подтвердите перевод:"

    keyboard = [
        [
            InlineKeyboardButton("✅ Да, перевести", callback_data=OWNER_FF_TRANSFER_CONFIRM_YES),
            InlineKeyboardButton("❌ Отмена", callback_data=OWNER_FF_TRANSFER_CANCEL),
        ],
    ]

    if update.message:
        await update.message.reply_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")

    context.user_data['ff_transfer_state'] = WAITING_FF_TRANSFER_CONFIRM
    return WAITING_FF_TRANSFER_CONFIRM


@owner_only
async def owner_ff_transfer_confirm_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Выполняет подтверждённый перевод."""
    query = update.callback_query

    try:
        await query.answer()
    except:
        pass

    # Получаем данные перевода
    target_user = context.user_data.get('ff_transfer_target')
    amount = context.user_data.get('ff_transfer_amount')

    if not target_user or amount is None:
        text = "❌ Ошибка сеанса. Попробуйте снова."
        keyboard = [[InlineKeyboardButton("◀️ В меню", callback_data=OWNER_MENU)]]

        try:
            await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard))
        except Exception as e:
            if "not modified" not in str(e):
                logger.error(f"Ошибка отображения: {e}")
                raise

        # Очищаем данные
        context.user_data.pop('ff_transfer_target', None)
        context.user_data.pop('ff_transfer_amount', None)
        context.user_data.pop('ff_transfer_state', None)
        return ConversationHandler.END

    try:
        # Выполняем перевод
        from database_postgres import add_fun_fuel, get_fun_fuel_balance

        add_fun_fuel(target_user['telegram_id'], amount, f"Перевод от собственника")

        # Проверяем новый баланс
        new_balance = get_fun_fuel_balance(target_user['telegram_id'])

        # Отправляем уведомление пользователю (показываем результат)
        notification_sent = False
        notification_error = None

        try:
            from telegram import Bot
            bot = context.bot
            notification_text = f"🎁 ТЫ ПОЛУЧИЛ FFCoin!\n\n"
            notification_text += f"💰 Ты получил: {amount} FFCoin\n"
            notification_text += f"📊 Твой баланс: {new_balance} FFCoin\n\n"
            notification_text += f"💡 Используй FFCoin для PvP ставок!"

            logger.info(f"📤 Попытка отправить уведомление о FF пользователю {target_user['telegram_id']}...")

            await bot.send_message(
                chat_id=target_user['telegram_id'],
                text=notification_text
            )
            notification_sent = True
            logger.info(f"✅ Уведомление об FF успешно отправлено пользователю {target_user['telegram_id']}")
        except Exception as e:
            notification_error = str(e)
            logger.error(f"❌ Ошибка отправки уведомления об FF пользователю {target_user['telegram_id']}: {e}")
            logger.error(f"Тип ошибки: {type(e).__name__}")

        # Формируем имя получателя
        username_str = f"@{target_user['username']}" if target_user['username'] else "(нет username)"

        text = "✅ ПЕРЕВОД ВЫПОЛНЕН!\n\n"
        text += f"👤 Получатель: {target_user['first_name']} {username_str}\n"
        text += f"💰 Переведено: {amount} FFCoin\n"
        text += f"📊 Новый баланс: {new_balance} FF\n\n"

        # Добавляем информацию об уведомлении
        if notification_sent:
            text += "📬 Уведомление отправлено"
        elif notification_error:
            text += "⚠️ Уведомление не отправлено\n"
            if "bot was blocked" in notification_error.lower():
                text += "Причина: Пользователь заблокировал бота"
            elif "user is deactivated" in notification_error.lower():
                text += "Причина: Пользователь деактивирован"
            elif "chat not found" in notification_error.lower():
                text += "Причина: Чат не найден"
            else:
                text += f"Ошибка: {notification_error[:80]}..."
        else:
            text += "⏳ Уведомление отправляется..."

        keyboard = [
            [InlineKeyboardButton("💸 Ещё перевод", callback_data=OWNER_FF_TRANSFER)],
            [InlineKeyboardButton("◀️ В меню", callback_data=OWNER_MENU)],
        ]

        try:
            await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard))
        except Exception as e:
            if "not modified" not in str(e):
                logger.error(f"Ошибка отображения: {e}")
                raise

        # Логируем перевод
        logger.info(f"💸 FF TRANSFER: {amount} FF -> {target_user['telegram_id']} ({target_user['first_name']})")

    except Exception as e:
        logger.error(f"Ошибка перевода FF: {e}")
        text = f"❌ ОШИБКА ПЕРЕВОДА\n\n"
        text += f"Произошла ошибка: {str(e)}"

        keyboard = [[InlineKeyboardButton("◀️ В меню", callback_data=OWNER_MENU)]]

        try:
            await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard))
        except Exception as e2:
            logger.error(f"Ошибка отображения ошибки: {e2}")

    finally:
        # Очищаем данные
        context.user_data.pop('ff_transfer_target', None)
        context.user_data.pop('ff_transfer_amount', None)
        context.user_data.pop('ff_transfer_state', None)
        context.user_data.pop('ff_transfer_message_id', None)

    return ConversationHandler.END


@owner_only
async def owner_ff_transfer_cancel_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Отменяет процесс перевода."""
    query = update.callback_query

    try:
        await query.answer()
    except:
        pass

    text = "❌ **ПЕРЕВОД ОТМЕНЁН**"

    keyboard = [[InlineKeyboardButton("◀️ В меню", callback_data=OWNER_MENU)]]

    try:
        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")
    except Exception as e:
        if "not modified" not in str(e):
            logger.error(f"Ошибка отмены: {e}")
            raise

    # Очищаем данные
    context.user_data.pop('ff_transfer_target', None)
    context.user_data.pop('ff_transfer_amount', None)
    context.user_data.pop('ff_transfer_state', None)
    context.user_data.pop('ff_transfer_message_id', None)

    return ConversationHandler.END


@owner_only
async def owner_competitions_enable_all_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Включает все упражнения в соревнования."""
    query = update.callback_query

    try:
        await query.answer()
    except:
        pass

    conn = get_db_connection()
    cur = conn.cursor()

    try:
        # Включаем все упражнения
        cur.execute("""
            UPDATE exercises
            SET is_speed_competition = TRUE
            RETURNING COUNT(*) as total,
                   COUNT(*) FILTER (WHERE is_speed_competition = TRUE) as already_active
        """)

        result = cur.fetchone()
        total, already_active = result
        newly_enabled = total - already_active

        conn.commit()

        text = "🟢 **ВКЛЮЧИТЬ ВСЕ УПРАЖНЕНИЯ**\n\n"
        text += f"✅ Готово!\n\n"
        text += f"📊 Всего упражнений: {total}\n"
        text += f"🟢 Были активны: {already_active}\n"
        text += f"🆕 Включено: {newly_enabled}\n\n"
        text += "⚡ Все упражнения теперь участвуют в соревнованиях!"

        keyboard = [
            [InlineKeyboardButton("⏬ Список упражнений", callback_data=OWNER_COMPETITIONS)],
            [InlineKeyboardButton("◀️ В меню", callback_data=OWNER_MENU)],
        ]

        try:
            await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")
        except Exception as e:
            if "not modified" not in str(e):
                logger.error(f"Ошибка отображения: {e}")
                raise

        logger.info(f"✅ Включены все упражнения: {newly_enabled} новых")

    except Exception as e:
        logger.error(f"Ошибка включения всех упражнений: {e}")
        text = f"❌ Ошибка включения: {e}"
        keyboard = [[InlineKeyboardButton("◀️ В меню", callback_data=OWNER_MENU)]]
        try:
            await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard))
        except:
            pass
    finally:
        release_db_connection(conn)


@owner_only
async def owner_competitions_disable_all_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Выключает все упражнения из соревнований."""
    query = update.callback_query

    try:
        await query.answer()
    except:
        pass

    conn = get_db_connection()
    cur = conn.cursor()

    try:
        # Выключаем все упражнения
        cur.execute("""
            UPDATE exercises
            SET is_speed_competition = FALSE
            RETURNING COUNT(*) as total,
                   COUNT(*) FILTER (WHERE is_speed_competition = FALSE) as already_inactive
        """)

        result = cur.fetchone()
        total, already_inactive = result
        newly_disabled = total - already_inactive

        conn.commit()

        text = "🔴 **ВЫКЛЮЧИТЬ ВСЕ УПРАЖНЕНИЯ**\n\n"
        text += f"✅ Готово!\n\n"
        text += f"📊 Всего упражнений: {total}\n"
        text += f"🔴 Были неактивны: {already_inactive}\n"
        text += f"🆕 Выключено: {newly_disabled}\n\n"
        text += "⚠️ Соревнования暂停 для всех упражнений!"

        keyboard = [
            [InlineKeyboardButton("⏬ Список упражнений", callback_data=OWNER_COMPETITIONS)],
            [InlineKeyboardButton("◀️ В меню", callback_data=OWNER_MENU)],
        ]

        try:
            await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")
        except Exception as e:
            if "not modified" not in str(e):
                logger.error(f"Ошибка отображения: {e}")
                raise

        logger.info(f"✅ Выключены все упражнения: {newly_disabled} новых")

    except Exception as e:
        logger.error(f"Ошибка выключения всех упражнений: {e}")
        text = f"❌ Ошибка выключения: {e}"
        keyboard = [[InlineKeyboardButton("◀️ В меню", callback_data=OWNER_MENU)]]
        try:
            await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard))
        except:
            pass
    finally:
        release_db_connection(conn)


@owner_only
async def owner_competitions_enable_beginners_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Включает только упражнения для новичков."""
    query = update.callback_query

    try:
        await query.answer()
    except:
        pass

    conn = get_db_connection()
    cur = conn.cursor()

    try:
        # Выключаем все упражнения
        cur.execute("UPDATE exercises SET is_speed_competition = FALSE")

        # Включаем только новичковые
        cur.execute("""
            UPDATE exercises
            SET is_speed_competition = TRUE
            WHERE difficulty = 'beginner'
            RETURNING COUNT(*) as enabled
        """)

        enabled_count = cur.fetchone()[0]
        conn.commit()

        # Получаем статистику
        cur.execute("""
            SELECT COUNT(*) as total,
                   COUNT(*) FILTER (WHERE difficulty = 'beginner') as beginner_total
            FROM exercises
        """)
        total_stats = cur.fetchone()
        total_exercises = total_stats[0]
        total_beginners = total_stats[1]

        text = "🟡 **ВКЛЮЧИТЬ НОВИЧКОВЫЕ**\n\n"
        text += f"✅ Готово!\n\n"
        text += f"📊 Всего упражнений: {total_exercises}\n"
        text += f"👶 Новичковых: {total_beginners}\n"
        text += f"🟢 Включено: {enabled_count}\n\n"
        text += "⚡ Только новички соревнуются!"

        keyboard = [
            [InlineKeyboardButton("🟢 Включить все", callback_data=OWNER_COMPETITIONS_ENABLE_ALL)],
            [InlineKeyboardButton("⏬ Список упражнений", callback_data=OWNER_COMPETITIONS)],
            [InlineKeyboardButton("◀️ В меню", callback_data=OWNER_MENU)],
        ]

        try:
            await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")
        except Exception as e:
            if "not modified" not in str(e):
                logger.error(f"Ошибка отображения: {e}")
                raise

        logger.info(f"✅ Включены новичковые упражнения: {enabled_count}")

    except Exception as e:
        logger.error(f"Ошибка включения новичковых: {e}")
        text = f"❌ Ошибка включения: {e}"
        keyboard = [[InlineKeyboardButton("◀️ В меню", callback_data=OWNER_MENU)]]
        try:
            await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard))
        except:
            pass
    finally:
        release_db_connection(conn)


@owner_only
async def owner_pvp_settings_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показывает и позволяет редактировать настройки PvP конвертации."""
    query = update.callback_query

    try:
        await query.answer()
    except:
        pass

    from database_postgres import get_all_pvp_settings

    # Получаем текущие настройки
    settings = get_all_pvp_settings()
    exercise_percent = settings.get('exercise_pvp_percent', 7)
    complex_percent = settings.get('complex_pvp_percent', 15)
    challenge_percent = settings.get('challenge_pvp_percent', 20)

    text = "⚔️ **НАСТРОЙКИ PvP КОНВЕРТАЦИИ**\n\n"
    text += "💡 Процент очков, конвертируемых в PvP Рейтинг:\n\n"

    text += f"🏋️ Упражнения: {exercise_percent}%\n"
    text += f"📦 Комплексы: {complex_percent}%\n"
    text += f"🏆 Челленджи: {challenge_percent}%\n\n"

    text += "💡 Пример: При 100 очках за упражнение и 7% конвертации\n"
    text += f"пользователь получит +7 к PvP Рейтингу\n\n"

    text += "📝 Выберите что изменить:"

    keyboard = [
        [
            InlineKeyboardButton(f"🏋️ Упражнения ({exercise_percent}%)", callback_data=OWNER_PVP_EXERCISE),
            InlineKeyboardButton(f"📦 Комплексы ({complex_percent}%)", callback_data=OWNER_PVP_COMPLEX),
        ],
        [
            InlineKeyboardButton(f"🏆 Челленджи ({challenge_percent}%)", callback_data=OWNER_PVP_CHALLENGE),
            InlineKeyboardButton("ℹ️ Информация", callback_data=OWNER_FF_INFO),
        ],
        [
            InlineKeyboardButton("◀️ В меню", callback_data=OWNER_MENU),
        ],
    ]

    try:
        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")
    except Exception as e:
        if "not modified" not in str(e):
            logger.error(f"Ошибка отображения настроек PvP: {e}")
            raise


@owner_only
async def owner_pvp_exercise_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Изменяет процент конвертации для упражнений."""
    query = update.callback_query

    try:
        await query.answer()
    except:
        pass

    from database_postgres import get_pvp_setting

    current_percent = get_pvp_setting('exercise_pvp_percent')

    text = f"🏋️ **КОНВЕРТАЦИЯ УПРАЖНЕНИЙ**\n\n"
    text += f"Текущий процент: {current_percent}%\n\n"
    text += "💡 Этот процент от очков за упражнение\n"
    text += "конвертируется в PvP Рейтинг\n\n"
    text += "📝 Выберите новый процент:"

    # Быстрые варианты
    percents = [0, 5, 7, 10, 15, 20, 25, 50]
    keyboard = []

    for i in range(0, len(percents), 2):
        row = []
        row.append(InlineKeyboardButton(f"{percents[i]}%", callback_data=f"pvp_exercise_set:{percents[i]}"))
        if i + 1 < len(percents):
            row.append(InlineKeyboardButton(f"{percents[i+1]}%", callback_data=f"pvp_exercise_set:{percents[i+1]}"))
        keyboard.append(row)

    keyboard.append([
        InlineKeyboardButton("⌨️ Свой %", callback_data="pvp_exercise_custom"),
        InlineKeyboardButton("◀️ Назад", callback_data=OWNER_PVP_SETTINGS),
    ])

    try:
        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")
    except Exception as e:
        if "not modified" not in str(e):
            logger.error(f"Ошибка отображения: {e}")
            raise


@owner_only
async def owner_pvp_complex_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Изменяет процент конвертации для комплексов."""
    query = update.callback_query

    try:
        await query.answer()
    except:
        pass

    from database_postgres import get_pvp_setting

    current_percent = get_pvp_setting('complex_pvp_percent')

    text = f"📦 **КОНВЕРТАЦИЯ КОМПЛЕКСОВ**\n\n"
    text += f"Текущий процент: {current_percent}%\n\n"
    text += "💡 Этот процент от очков за комплекс\n"
    text += "конвертируется в PvP Рейтинг\n\n"
    text += "📝 Выберите новый процент:"

    # Быстрые варианты
    percents = [0, 10, 15, 20, 25, 30, 50, 75]
    keyboard = []

    for i in range(0, len(percents), 2):
        row = []
        row.append(InlineKeyboardButton(f"{percents[i]}%", callback_data=f"pvp_complex_set:{percents[i]}"))
        if i + 1 < len(percents):
            row.append(InlineKeyboardButton(f"{percents[i+1]}%", callback_data=f"pvp_complex_set:{percents[i+1]}"))
        keyboard.append(row)

    keyboard.append([
        InlineKeyboardButton("⌨️ Свой %", callback_data="pvp_complex_custom"),
        InlineKeyboardButton("◀️ Назад", callback_data=OWNER_PVP_SETTINGS),
    ])

    try:
        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")
    except Exception as e:
        if "not modified" not in str(e):
            logger.error(f"Ошибка отображения: {e}")
            raise


@owner_only
async def owner_pvp_challenge_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Изменяет процент конвертации для челленджей."""
    query = update.callback_query

    try:
        await query.answer()
    except:
        pass

    from database_postgres import get_pvp_setting

    current_percent = get_pvp_setting('challenge_pvp_percent')

    text = f"🏆 **КОНВЕРТАЦИЯ ЧЕЛЛЕНДЖЕЙ**\n\n"
    text += f"Текущий процент: {current_percent}%\n\n"
    text += "💡 Этот процент от очков за челлендж\n"
    text += "конвертируется в PvP Рейтинг\n\n"
    text += "📝 Выберите новый процент:"

    # Быстрые варианты
    percents = [0, 10, 20, 25, 30, 50, 75, 100]
    keyboard = []

    for i in range(0, len(percents), 2):
        row = []
        row.append(InlineKeyboardButton(f"{percents[i]}%", callback_data=f"pvp_challenge_set:{percents[i]}"))
        if i + 1 < len(percents):
            row.append(InlineKeyboardButton(f"{percents[i+1]}%", callback_data=f"pvp_challenge_set:{percents[i+1]}"))
        keyboard.append(row)

    keyboard.append([
        InlineKeyboardButton("⌨️ Свой %", callback_data="pvp_challenge_custom"),
        InlineKeyboardButton("◀️ Назад", callback_data=OWNER_PVP_SETTINGS),
    ])

    try:
        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")
    except Exception as e:
        if "not modified" not in str(e):
            logger.error(f"Ошибка отображения: {e}")
            raise


@owner_only
async def owner_pvp_set_percent_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Устанавливает выбранный процент конвертации."""
    query = update.callback_query

    try:
        await query.answer()
    except:
        pass

    # Извлекаем тип и процент из callback_data
    callback_data = query.data
    if not callback_data.startswith(("pvp_exercise_set:", "pvp_complex_set:", "pvp_challenge_set:")):
        logger.error(f"Неверный формат callback_data: {callback_data}")
        return

    try:
        parts = callback_data.split(":")
        pvp_type = parts[0].replace("_set", "")  # exercise, complex, challenge
        percent = int(parts[1])
    except (IndexError, ValueError):
        logger.error(f"Не удалось извлечь данные из: {callback_data}")
        return

    # Определяем ключ для базы данных
    key_mapping = {
        'pvp_exercise': 'exercise_pvp_percent',
        'pvp_complex': 'complex_pvp_percent',
        'pvp_challenge': 'challenge_pvp_percent'
    }

    key = key_mapping.get(pvp_type)
    if not key:
        logger.error(f"Неизвестный тип PvP: {pvp_type}")
        return

    try:
        from database_postgres import set_pvp_setting

        # Устанавливаем новый процент
        set_pvp_setting(key, percent)

        # Формируем название типа для отображения
        type_names = {
            'exercise': 'упражнений',
            'complex': 'комплексов',
            'challenge': 'челленджей'
        }
        type_name = type_names.get(pvp_type.replace("pvp_", ""), "")

        text = f"✅ **НАСТРОЙКА ИЗМЕНЕНА**\n\n"
        text += f"📊 Конвертация {type_name}\n"
        text += f"🔄 Новый процент: {percent}%\n\n"
        text += "💡 Изменения применены немедленно!"

        keyboard = [
            [InlineKeyboardButton("⚔️ Вернуться к настройкам", callback_data=OWNER_PVP_SETTINGS)],
            [InlineKeyboardButton("◀️ В меню", callback_data=OWNER_MENU)],
        ]

        try:
            await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")
        except Exception as e:
            if "not modified" not in str(e):
                logger.error(f"Ошибка отображения: {e}")
                raise

        logger.info(f"✅ Изменён процент конвертации {type_name}: {percent}%")

    except Exception as e:
        logger.error(f"Ошибка установки процента: {e}")
        text = f"❌ Ошибка установки: {e}"
        keyboard = [[InlineKeyboardButton("◀️ В меню", callback_data=OWNER_MENU)]]
        try:
            await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard))
        except:
            pass


@owner_only
async def owner_pvp_custom_percent_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показывает подсказку для ввода своего процента."""
    query = update.callback_query

    try:
        await query.answer()
    except:
        pass

    callback_data = query.data

    # Определяем тип на основе callback_data
    if "exercise" in callback_data:
        pvp_type = "exercise"
        type_name = "упражнений"
        back_callback = OWNER_PVP_EXERCISE
    elif "complex" in callback_data:
        pvp_type = "complex"
        type_name = "комплексов"
        back_callback = OWNER_PVP_COMPLEX
    elif "challenge" in callback_data:
        pvp_type = "challenge"
        type_name = "челленджей"
        back_callback = OWNER_PVP_CHALLENGE
    else:
        logger.error(f"Неизвестный тип в callback_data: {callback_data}")
        return

    text = f"📝 **СВОЙ ПРОЦЕНТ**\n\n"
    text += f"Введите процент конвертации для {type_name}\n\n"
    text += "💡 Введите число от 0 до 100"

    keyboard = [
        [InlineKeyboardButton("◀️ Назад", callback_data=back_callback)],
        [InlineKeyboardButton("◀️ В меню", callback_data=OWNER_MENU)],
    ]

    try:
        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")

        # Сохраняем состояние для ввода
        context.user_data['pvp_custom_type'] = pvp_type

    except Exception as e:
        if "not modified" not in str(e):
            logger.error(f"Ошибка отображения: {e}")
            raise


@owner_only
async def owner_pvp_custom_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обрабатывает ввод своего процента."""
    if not update.message:
        return ConversationHandler.END

    pvp_type = context.user_data.get('pvp_custom_type')
    if not pvp_type:
        text = "❌ Ошибка сеанса. Попробуйте снова."
        keyboard = [[InlineKeyboardButton("◀️ В меню", callback_data=OWNER_MENU)]]
        await update.message.reply_text(text, reply_markup=InlineKeyboardMarkup(keyboard))
        return ConversationHandler.END

    user_input = update.message.text.strip()

    try:
        percent = int(user_input)
        if not (0 <= percent <= 100):
            raise ValueError("Процент должен быть от 0 до 100")
    except ValueError:
        text = "❌ **НЕВЕРНЫЙ ПРОЦЕНТ!**\n\n"
        text += "Процент должен быть числом от 0 до 100\n\n"
        text += "📝 Попробуйте снова или нажмите Отмена:"
        keyboard = [[InlineKeyboardButton("❌ Отмена", callback_data=OWNER_PVP_SETTINGS)]]
        await update.message.reply_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")
        return WAITING_PVP_CUSTOM_INPUT

    try:
        from database_postgres import set_pvp_setting

        # Определяем ключ
        key_mapping = {
            'exercise': 'exercise_pvp_percent',
            'complex': 'complex_pvp_percent',
            'challenge': 'challenge_pvp_percent'
        }

        key = key_mapping.get(pvp_type)
        if not key:
            text = "❌ Ошибка типа"
            keyboard = [[InlineKeyboardButton("◀️ В меню", callback_data=OWNER_MENU)]]
            await update.message.reply_text(text, reply_markup=InlineKeyboardMarkup(keyboard))
            return ConversationHandler.END

        # Устанавливаем процент
        set_pvp_setting(key, percent)

        # Формируем название
        type_names = {
            'exercise': 'упражнений',
            'complex': 'комплексов',
            'challenge': 'челленджей'
        }
        type_name = type_names.get(pvp_type, "")

        text = f"✅ **НАСТРОЙКА ИЗМЕНЕНА**\n\n"
        text += f"📊 Конвертация {type_name}\n"
        text += f"🔄 Новый процент: {percent}%\n\n"
        text += "💡 Изменения применены немедленно!"

        keyboard = [
            [InlineKeyboardButton("⚔️ Вернуться к настройкам", callback_data=OWNER_PVP_SETTINGS)],
            [InlineKeyboardButton("◀️ В меню", callback_data=OWNER_MENU)],
        ]

        await update.message.reply_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")
        logger.info(f"✅ Установлен свой процент {type_name}: {percent}%")

    except Exception as e:
        logger.error(f"Ошибка установки процента: {e}")
        text = f"❌ Ошибка: {e}"
        keyboard = [[InlineKeyboardButton("◀️ В меню", callback_data=OWNER_MENU)]]
        await update.message.reply_text(text, reply_markup=InlineKeyboardMarkup(keyboard))

    finally:
        context.user_data.pop('pvp_custom_type', None)

    return ConversationHandler.END


# ========== PvP ПЕРЕВОД ОЧКОВ ==========


@owner_only
async def owner_pvp_transfer_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Начинает процесс перевода PvP Рейтинга."""
    query = update.callback_query

    try:
        await query.answer()

        # Получаем список пользователей
        from database_postgres import get_all_users, get_user_pvp_stats
        users = get_all_users(limit=20)

        if not users:
            await query.edit_message_text("❌ Нет пользователей для перевода.")
            return ConversationHandler.END

        # Формируем клавиатуру с пользователями
        keyboard = []
        for user in users:
            user_id = user[0]
            first_name = user[1] or "Пользователь"
            last_name = user[2] or ""
            username = user[3] or ""

            # Получаем PvP Рейтинг пользователя
            try:
                pvp_stats = get_user_pvp_stats(user_id)
                pvp_points = pvp_stats.get('total_points', 0) if pvp_stats else 0
            except Exception as e:
                logger.warning(f"Не удалось получить PvP для {user_id}: {e}")
                pvp_points = 0

            # Показываем Имя + Никнейм (если есть) + PvP Рейтинг
            if username:
                display_name = f"{first_name} (@{username})"
            else:
                display_name = f"{first_name} {last_name}".strip()

            # Добавляем PvP Рейтинг
            button_text = f"{display_name} - {pvp_points} PvP"

            if len(button_text) > 50:
                # Если слишком длинно, обрезаем имя, но оставляем PvP
                if len(display_name) > 35:
                    display_name = display_name[:32] + "..."
                button_text = f"{display_name} - {pvp_points} PvP"

            keyboard.append([InlineKeyboardButton(
                button_text,
                callback_data=f"pvp_select_user:{user_id}"
            )])

        keyboard.extend([
            [InlineKeyboardButton("⌨️ Ввести ID вручную", callback_data="pvp_manual_input")],
            [InlineKeyboardButton("❌ Отмена", callback_data="owner_pvp_transfer_cancel")]
        ])

        reply_markup = InlineKeyboardMarkup(keyboard)

        text = "💎 **ПЕРЕВОД PvP ОЧКОВ**\n\n"
        text += "Выбери пользователя для перевода:\n\n"
        text += "💡 Или введи Telegram ID вручную"

        await query.edit_message_text(text, reply_markup=reply_markup, parse_mode="Markdown")

        context.user_data['pvp_transfer_state'] = WAITING_PVP_TRANSFER_USER
        return WAITING_PVP_TRANSFER_USER

    except Exception as e:
        logger.error(f"Ошибка в pvp_transfer: {e}")
        await query.edit_message_text(f"❌ Ошибка: {e}")


@owner_only
async def owner_pvp_select_user_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обрабатывает выбор пользователя из списка."""
    query = update.callback_query
    await query.answer()

    user_id = int(query.data.split(":")[1])
    context.user_data['pvp_target_user_id'] = user_id

    await show_pvp_amount_menu(update, user_id)

    context.user_data['pvp_transfer_state'] = WAITING_PVP_TRANSFER_AMOUNT
    return WAITING_PVP_TRANSFER_AMOUNT


@owner_only
async def owner_pvp_manual_input_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показывает сообщение для ручного ввода Telegram ID."""
    query = update.callback_query
    await query.answer()

    keyboard = [[InlineKeyboardButton("❌ Отмена", callback_data="owner_pvp_transfer_cancel")]]
    reply_markup = InlineKeyboardMarkup(keyboard)

    text = "⌨️ **ВВОД Telegram ID**\n\n"
    text += "Введи Telegram ID или @username пользователя:"

    await query.edit_message_text(text, reply_markup=reply_markup, parse_mode="Markdown")

    context.user_data['pvp_transfer_state'] = WAITING_PVP_TRANSFER_USER
    return WAITING_PVP_TRANSFER_USER


@owner_only
async def owner_pvp_transfer_user_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обрабатывает ввод Telegram ID."""
    if not update.message:
        return ConversationHandler.END

    user_input = update.message.text.strip()

    try:
        from database_postgres import get_user_info, get_user_by_username
        user_id = None

        if user_input.isdigit():
            user_id = int(user_input)
            user_info = get_user_info(user_id)
            if not user_info:
                await update.message.reply_text("❌ Пользователь не найден. Попробуй еще раз:")
                return WAITING_PVP_TRANSFER_USER
        else:
            if user_input.startswith("@"):
                user_input = user_input[1:]

            user_info = get_user_by_username(user_input)
            if not user_info:
                await update.message.reply_text("❌ Пользователь не найден. Попробуй еще раз:")
                return WAITING_PVP_TRANSFER_USER

            user_id = user_info[0]

        context.user_data['pvp_target_user_id'] = user_id
        await show_pvp_amount_menu(update, user_id, message=True)

        context.user_data['pvp_transfer_state'] = WAITING_PVP_TRANSFER_AMOUNT
        return WAITING_PVP_TRANSFER_AMOUNT

    except Exception as e:
        logger.error(f"Ошибка обработки ввода: {e}")
        await update.message.reply_text(f"❌ Ошибка: {e}")
        return ConversationHandler.END


async def show_pvp_amount_menu(update, user_id, message=False):
    """Показывает меню выбора суммы PvP."""
    from database_postgres import get_user_info, get_user_pvp_stats
    user_info = get_user_info(user_id)

    if not user_info:
        text = "❌ Пользователь не найден"
    else:
        first_name = user_info[1] or "Пользователь"
        username = user_info[3] or ""
        # Показываем Имя + Никнейм (если есть)
        if username:
            display_user = f"{first_name} (@{username})"
        else:
            display_user = first_name

        pvp_stats = get_user_pvp_stats(user_id)
        current_pvp = pvp_stats.get('total_points', 0) if pvp_stats else 0

        text = f"🏆 **ПЕРЕВОД FruNStatus**\n\n"
        text += f"👤 Пользователь: {display_user}\n"
        text += f"🎯 Текущий FruNStatus: {current_pvp}\n\n"
        text += "Выбери сумму (положительная = начисление, отрицательная = списание):\n\n"
        text += "⚠️ Для СПИСАНИЯ используй кнопки ниже или введи -100, -500"

    keyboard = [
        [InlineKeyboardButton("🏆 +10", callback_data="pvp_amount:10")],
        [InlineKeyboardButton("🏆 +50", callback_data="pvp_amount:50")],
        [InlineKeyboardButton("🏆 +100", callback_data="pvp_amount:100")],
        [InlineKeyboardButton("🏆 +200", callback_data="pvp_amount:200")],
        [InlineKeyboardButton("🏆 +500", callback_data="pvp_amount:500")],
        [InlineKeyboardButton("🏆 +1000", callback_data="pvp_amount:1000")],
        [InlineKeyboardButton("⌨️ Своя сумма", callback_data="pvp_custom_amount")],
        [InlineKeyboardButton("❌ -100", callback_data="pvp_amount:-100")],
        [InlineKeyboardButton("❌ -500", callback_data="pvp_amount:-500")],
        [InlineKeyboardButton("◀️ Отмена", callback_data="owner_pvp_transfer_cancel")]
    ]

    reply_markup = InlineKeyboardMarkup(keyboard)

    if message:
        await update.message.reply_text(text, reply_markup=reply_markup, parse_mode="Markdown")
    else:
        query = update.callback_query
        await query.edit_message_text(text, reply_markup=reply_markup, parse_mode="Markdown")


@owner_only
async def owner_pvp_amount_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обрабатывает выбор суммы."""
    query = update.callback_query
    await query.answer()

    amount = int(query.data.split(":")[1])
    context.user_data['pvp_amount'] = amount

    await show_pvp_confirm(update, context)

    context.user_data['pvp_transfer_state'] = WAITING_PVP_TRANSFER_CONFIRM
    return WAITING_PVP_TRANSFER_CONFIRM


@owner_only
async def owner_pvp_custom_amount_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показывает сообщение для ввода своей суммы."""
    query = update.callback_query
    await query.answer()

    keyboard = [[InlineKeyboardButton("❌ Отмена", callback_data="owner_pvp_transfer_cancel")]]
    reply_markup = InlineKeyboardMarkup(keyboard)

    text = "⌨️ **СВОЯ СУММА**\n\n"
    text += "Введи количество PvP Рейтинга:"

    await query.edit_message_text(text, reply_markup=reply_markup, parse_mode="Markdown")


@owner_only
async def owner_pvp_transfer_amount_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обрабатывает ввод своей суммы."""
    if not update.message:
        return ConversationHandler.END

    amount_input = update.message.text.strip()

    try:
        amount = int(amount_input)

        context.user_data['pvp_amount'] = amount
        await show_pvp_confirm(update, context, message=True)

        context.user_data['pvp_transfer_state'] = WAITING_PVP_TRANSFER_CONFIRM
        return WAITING_PVP_TRANSFER_CONFIRM

    except ValueError:
        await update.message.reply_text("❌ Введи число. Попробуй еще раз:")
        return WAITING_PVP_TRANSFER_AMOUNT
    except Exception as e:
        logger.error(f"Ошибка ввода суммы: {e}")
        await update.message.reply_text(f"❌ Ошибка: {e}")
        return ConversationHandler.END


async def show_pvp_confirm(update, context, message=False):
    """Показывает подтверждение перевода."""
    user_id = context.user_data.get('pvp_target_user_id')
    amount = context.user_data.get('pvp_amount', 0)

    from database_postgres import get_user_info
    user_info = get_user_info(user_id)

    if user_info:
        first_name = user_info[1] or "Пользователь"
        username = user_info[3] or ""
        # Показываем Имя + Никнейм (если есть)
        if username:
            display_user = f"{first_name} (@{username})"
        else:
            display_user = first_name

        text = f"🏆 **ПОДТВЕРЖДЕНИЕ ПЕРЕВОДА**\n\n"
        text += f"👤 Получатель: {display_user}\n"

        if amount >= 0:
            text += f"🎯 Начислить: +{amount} FruNStatus\n\n"
        else:
            text += f"❌ Списать: {amount} FruNStatus\n\n"

        text += "Подтвердишь?"
    else:
        text = "❌ Ошибка получения данных пользователя"

    keyboard = [
        [InlineKeyboardButton("✅ Подтвердить", callback_data="owner_pvp_transfer_confirm_yes")],
        [InlineKeyboardButton("❌ Отмена", callback_data="owner_pvp_transfer_cancel")]
    ]

    reply_markup = InlineKeyboardMarkup(keyboard)

    if message:
        await update.message.reply_text(text, reply_markup=reply_markup, parse_mode="Markdown")
    else:
        query = update.callback_query
        await query.edit_message_text(text, reply_markup=reply_markup, parse_mode="Markdown")


@owner_only
async def owner_pvp_transfer_confirm_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Выполняет подтверждённый перевод."""
    query = update.callback_query

    try:
        await query.answer()

        user_id = context.user_data.get('pvp_target_user_id')
        amount = context.user_data.get('pvp_amount', 0)
        admin_id = update.effective_user.id

        from database_postgres import add_pvp_points_admin, get_user_info
        success = add_pvp_points_admin(user_id, amount, "Админский перевод", admin_id)

        if success:
            user_info = get_user_info(user_id)

            # Отправляем уведомление пользователю
            notification_sent = False
            notification_error = None

            try:
                from database_postgres import get_user_pvp_stats
                bot = context.bot

                # Получаем новый баланс PvP
                pvp_stats = get_user_pvp_stats(user_id)
                new_pvp_balance = pvp_stats.get('total_points', 0) if pvp_stats else 0

                if user_info:
                    first_name_user = user_info[1] or "Пользователь"
                    notification_text = f"🎁 ТЫ ПОЛУЧИЛ FruNStatus!\n\n"
                    notification_text += f"🏆 Ты получил: +{amount} к FruNStatus\n"
                    notification_text += f"💎 Твой FruNStatus: {new_pvp_balance}\n\n"
                    notification_text += f"💡 Каждые 100 FruNStatus = медаль!"

                    logger.info(f"📤 Попытка отправить уведомление о PvP пользователю {user_id}...")

                    await bot.send_message(
                        chat_id=user_id,
                        text=notification_text
                    )
                    notification_sent = True
                    logger.info(f"✅ Уведомление о PvP успешно отправлено пользователю {user_id}")
            except Exception as e:
                notification_error = str(e)
                logger.error(f"❌ Ошибка отправки уведомления о PvP пользователю {user_id}: {e}")
                logger.error(f"Тип ошибки: {type(e).__name__}")

            # Показываем результат собственнику
            if user_info:
                first_name = user_info[1] or "Пользователь"
                username = user_info[3] or ""
                # Показываем Имя + Никнейм (если есть)
                if username:
                    display_user = f"{first_name} (@{username})"
                else:
                    display_user = first_name

                text = f"✅ ПЕРЕВОД ВЫПОЛНЕН\n\n"
                text += f"👤 {display_user}\n"
                text += f"🎯 Начислено: {amount} FruNStatus\n"

                # Добавляем информацию об уведомлении
                if notification_sent:
                    text += "📬 Уведомление отправлено"
                elif notification_error:
                    text += "⚠️ Уведомление не отправлено\n"
                    if "bot was blocked" in notification_error.lower():
                        text += "Причина: Пользователь заблокировал бота"
                    elif "user is deactivated" in notification_error.lower():
                        text += "Причина: Пользователь деактивирован"
                    elif "chat not found" in notification_error.lower():
                        text += "Причина: Чат не найден"
                    else:
                        text += f"Ошибка: {notification_error[:80]}..."
                else:
                    text += "💡 Пользователь теперь может вызывать на дуэли!"
            else:
                text = f"✅ Начислено {amount} FruNStatus"

            keyboard = [[InlineKeyboardButton("◀️ В меню", callback_data=OWNER_MENU)]]
            reply_markup = InlineKeyboardMarkup(keyboard)

            await query.edit_message_text(text, reply_markup=reply_markup)
        else:
            await query.edit_message_text("❌ Ошибка выполнения перевода")

    except Exception as e:
        logger.error(f"Ошибка выполнения перевода PvP: {e}")
        await query.edit_message_text(f"❌ Ошибка: {e}")

    context.user_data.pop('pvp_target_user_id', None)
    context.user_data.pop('pvp_amount', None)
    context.user_data.pop('pvp_transfer_state', None)

    return ConversationHandler.END


@owner_only
async def owner_pvp_transfer_cancel_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Отменяет процесс перевода."""
    query = update.callback_query

    try:
        await query.answer()

        context.user_data.pop('pvp_target_user_id', None)
        context.user_data.pop('pvp_amount', None)
        context.user_data.pop('pvp_transfer_state', None)

        text = "❌ Перевод PvP Рейтинга отменен"

        keyboard = [[InlineKeyboardButton("◀️ В меню", callback_data=OWNER_MENU)]]
        reply_markup = InlineKeyboardMarkup(keyboard)

        await query.edit_message_text(text, reply_markup=reply_markup)

    except Exception as e:
        logger.error(f"Ошибка отмены: {e}")

    return ConversationHandler.END

# -*- coding: utf-8 -*-
"""
Функции для управления каналами - добавь этот код в конец owner_handlers.py
"""

# ========== УПРАВЛЕНИЕ КАНАЛАМИ ==========


@owner_only
async def owner_channel_check_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показывает информацию о каналах и их статусе."""
    query = update.callback_query

    try:
        await query.answer()

        text = "📢 **ПРОВЕРКА КАНАЛОВ**\n\n"
        text += "Проверка подключения бота к каналам:\n\n"

        keyboard = []

        # Проверяем канал уведомлений из переменных окружения
        import os
        from dotenv import load_dotenv
        load_dotenv()

        notification_channel = os.getenv('NOTIFICATION_CHANNEL_ID')

        if notification_channel:
            try:
                # Проверяем доступ бота к каналу
                bot = context.bot
                chat_member = await bot.get_chat_member(notification_channel, bot.id)

                if chat_member:
                    status_emoji = "✅"
                    status_text = "Подключен"

                    # Проверяем права бота
                    can_post_messages = chat_member.can_post_messages if hasattr(chat_member, 'can_post_messages') else False

                    text += f"📢 **Канал уведомлений:**\n"
                    text += f"🆔 ID: `{notification_channel}`\n"
                    text += f"📊 Статус: {status_emoji} {status_text}\n"
                    text += f"📝 Права: {'✅ Может писать' if can_post_messages else '❌ Ограничены'}\n\n"

                    keyboard.append([
                        InlineKeyboardButton("🔄 Переподключить канал", callback_data=OWNER_CHANNEL_RECONNECT),
                        InlineKeyboardButton("📝 Изменить ID канала", callback_data="owner_channel_change_id")
                    ])

            except Exception as e:
                error_msg = str(e)
                text += f"📢 **Канал уведомлений:**\n"
                text += f"🆔 ID: `{notification_channel}`\n"
                text += f"❌ Ошибка подключения: {error_msg[:50]}...\n\n"

                keyboard.append([
                    InlineKeyboardButton("🔄 Переподключить канал", callback_data=OWNER_CHANNEL_RECONNECT),
                    InlineKeyboardButton("📝 Изменить ID канала", callback_data="owner_channel_change_id")
                ])
        else:
            text += "📢 **Канал уведомлений:**\n"
            text += "❌ Не настроен в переменных окружения\n\n"

            keyboard.append([
                InlineKeyboardButton("📝 Добавить канал", callback_data="owner_channel_change_id")
            ])

        keyboard.append([InlineKeyboardButton("◀️ В меню", callback_data=OWNER_MENU)])
        keyboard.append([InlineKeyboardButton("📢 Сообщение собственника", callback_data=OWNER_CHANNEL_MESSAGE)])

        reply_markup = InlineKeyboardMarkup(keyboard)

        try:
            await query.edit_message_text(text, reply_markup=reply_markup, parse_mode="Markdown")
        except BadRequest as e:
            if "Message is not modified" in str(e):
                # Игнорируем ошибку, если сообщение не изменилось
                pass
            else:
                raise

    except Exception as e:
        logger.error(f"Ошибка проверки каналов: {e}")
        text = f"❌ Ошибка проверки каналов: {e}"
        keyboard = [[InlineKeyboardButton("◀️ В меню", callback_data=OWNER_MENU)]]
        try:
            await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard))
        except:
            pass


@owner_only


async def owner_channel_change_id_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показывает инструкции для изменения ID канала."""
    query = update.callback_query

    try:
        await query.answer()

        text = "📝 ИЗМЕНЕНИЕ ID КАНАЛА\n\n"
        text += "📋 ИНСТРУКЦИЯ:\n\n"
        text += "1. Добавь бота в канал как администратор\n"
        text += "2. Узнай ID канала через @getmyid_bot\n"
        text += "3. Измени в .env: NOTIFICATION_CHANNEL_ID\n"
        text += "4. Или в Render - Environment Variables\n"
        text += "5. Перезапусти бота после изменения"

        keyboard = [
            [InlineKeyboardButton("🔄 Проверить подключение", callback_data=OWNER_CHANNEL_CHECK)],
            [InlineKeyboardButton("◀️ В меню", callback_data=OWNER_MENU)]
        ]

        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard))

    except Exception as e:
        logger.error(f"Ошибка отображения инструкций: {e}")


@owner_only
async def owner_channel_reconnect_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Переподключается к каналу и показывает подробную информацию."""
    query = update.callback_query

    try:
        await query.answer("🔄 Переподключение...")

        import os
        from dotenv import load_dotenv
        load_dotenv()

        notification_channel = os.getenv('NOTIFICATION_CHANNEL_ID')

        if not notification_channel:
            text = "❌ КАНАЛ НЕ НАСТРОЕН\n\n"
            text += "Канал уведомлений не указан в переменных окружения.\n\n"
            text += "📝 Добавь в .env:\n"
            text += "NOTIFICATION_CHANNEL_ID=-100XXXXXXXXX\n\n"
            text += "Или введи новый ID:"
        else:
            try:
                bot = context.bot

                # Получаем информацию о канале
                chat = await bot.get_chat(notification_channel)

                text = "✅ ПОДКЛЮЧЕНИЕ К КАНАЛУ\n\n"

                # Информация о канале
                chat_title = chat.title if hasattr(chat, 'title') else "Канал"
                chat_type = chat.type if hasattr(chat, 'type') else "unknown"

                text += f"📢 Название: {chat_title}\n"
                text += f"🆔 ID: {notification_channel}\n"
                text += f"📋 Тип: {chat_type}\n\n"

                # Проверяем права бота
                try:
                    chat_member = await bot.get_chat_member(notification_channel, bot.id)

                    if chat_member:
                        status = chat_member.status
                        text += f"👤 Статус бота: {status}\n"

                        # Проверяем различные права
                        can_post_messages = chat_member.can_post_messages if hasattr(chat_member, 'can_post_messages') else False

                        text += f"📝 Может писать: {'Да' if can_post_messages else 'Нет'}\n\n"

                        if status == 'administrator':
                            text += "✅ Бот является администратором канала\n\n"
                        elif status == 'member':
                            text += "⚠️ Бот является участником канала\n"
                            text += "💡 Рекомендация: Сделай бота администратором\n\n"
                        else:
                            text += f"⚠️ Статус: {status}\n\n"

                except Exception as e:
                    text += f"❌ Не удалось проверить права: {str(e)[:50]}...\n\n"

                # Пробуем отправить тестовое сообщение
                try:
                    test_msg = await bot.send_message(
                        chat_id=notification_channel,
                        text="🔄 Тестовое сообщение от администратора\n\n✅ Подключение к каналу работает!"
                    )
                    text += "📬 Тестовое сообщение: ✅ Отправлено успешно\n\n"
                except Exception as e:
                    error_msg = str(e)
                    text += f"📬 Тестовое сообщение: ❌ Ошибка\n"
                    text += f"Причина: {error_msg[:80]}...\n\n"

                    if "bot was blocked" in error_msg.lower():
                        text += "💡 Решение: Проверь, не заблокирован ли бот\n\n"
                    elif "not enough rights" in error_msg.lower():
                        text += "💡 Решение: Выдай боту права администратора\n\n"
                    elif "chat not found" in error_msg.lower():
                        text += "💡 Решение: Проверь правильность ID канала\n\n"

                text += "💡 Если есть проблемы:\n"
                text += "1. Убедись, что бот добавлен в канал\n"
                text += "2. Выдай боту права администратора\n"
                text += "3. Проверь правильность ID канала"

                keyboard = [
                    [InlineKeyboardButton("🔄 Обновить", callback_data=OWNER_CHANNEL_RECONNECT)],
                    [InlineKeyboardButton("📝 Изменить ID", callback_data="owner_channel_change_id")],
                    [InlineKeyboardButton("◀️ В меню", callback_data=OWNER_MENU)]
                ]

                try:
                    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard))
                except BadRequest as e:
                    if "Message is not modified" in str(e):
                        pass  # Игнорируем, если сообщение не изменилось
                    else:
                        raise
                return

            except Exception as e:
                text = f"❌ ОШИБКА ПОДКЛЮЧЕНИЯ\n\n"
                text += f"Не удалось подключиться к каналу:\n"
                text += f"{notification_channel}\n\n"
                text += f"Ошибка: {str(e)[:100]}"

                keyboard = [
                    [InlineKeyboardButton("🔄 Попробовать снова", callback_data=OWNER_CHANNEL_RECONNECT)],
                    [InlineKeyboardButton("📝 Изменить ID", callback_data="owner_channel_change_id")],
                    [InlineKeyboardButton("◀️ В меню", callback_data=OWNER_MENU)]
                ]

                try:
                    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard))
                except BadRequest as e:
                    if "Message is not modified" in str(e):
                        pass  # Игнорируем, если сообщение не изменилось
                    else:
                        raise
                return

        # Если канал не настроен
        keyboard = [
            [InlineKeyboardButton("📝 Изменить ID", callback_data="owner_channel_change_id")],
            [InlineKeyboardButton("◀️ В меню", callback_data=OWNER_MENU)]
        ]

        try:
            await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard))
        except BadRequest as e:
            if "Message is not modified" in str(e):
                pass  # Игнорируем, если сообщение не изменилось
            else:
                raise

    except Exception as e:
        logger.error(f"Ошибка переподключения канала: {e}")


@owner_only
async def owner_channel_message_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Начинает процесс отправки сообщения в канал."""
    query = update.callback_query

    try:
        await query.answer()

        # Проверяем, настроен ли канал
        import os
        from dotenv import load_dotenv
        load_dotenv()

        notification_channel = os.getenv('NOTIFICATION_CHANNEL_ID')

        if not notification_channel:
            text = "❌ КАНАЛ НЕ НАСТРОЕН\n\n"
            text += "Канал уведомлений не указан в переменных окружения.\n\n"
            text += "📝 Сначала настрой канал в кнопке 'Изменить ID канала'"

            keyboard = [[InlineKeyboardButton("◀️ В меню", callback_data=OWNER_MENU)]]

            try:
                await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard))
            except BadRequest as e:
                if "Message is not modified" not in str(e):
                    raise
            return

        text = "📢 СООБЩЕНИЕ В КАНАЛ\n\n"
        text += "✍️ Напиши сообщение, которое нужно отправить в канал.\n\n"
        text += "💡 Можно использовать:\n"
        text += "• Объявления о розыгрышах\n"
        text += "• Информация о соревнованиях\n"
        text += "• Важные оповещения\n"
        text += "• Любые другие уведомления\n\n"
        text += "⏰ Отправь сообщение сейчас (или /cancel для отмены):"

        keyboard = [[InlineKeyboardButton("◀️ Отмена", callback_data=OWNER_CHANNEL_CHECK)]]

        try:
            await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard))
        except BadRequest as e:
            if "Message is not modified" not in str(e):
                raise

        # Устанавливаем состояние ожидания сообщения
        return WAITING_CHANNEL_MESSAGE

    except Exception as e:
        logger.error(f"Ошибка начала отправки сообщения: {e}")


@owner_only
async def owner_channel_message_send(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Отправляет сообщение в канал."""
    try:
        message_text = update.message.text

        if not message_text:
            await update.message.reply_text("❌ Сообщение не может быть пустым. Попробуй еще раз или /cancel")
            return WAITING_CHANNEL_MESSAGE

        # Получаем ID канала
        import os
        from dotenv import load_dotenv
        load_dotenv()

        notification_channel = os.getenv('NOTIFICATION_CHANNEL_ID')

        if not notification_channel:
            await update.message.reply_text("❌ Канал не настроен. Настрой канал в меню собственника.")
            return ConversationHandler.END

        # Отправляем сообщение в канал
        try:
            bot = context.bot
            await bot.send_message(
                chat_id=notification_channel,
                text=f"📢 **СООБЩЕНИЕ ОТ ОРГАНИЗАТОРА**\n\n{message_text}",
                parse_mode="Markdown"
            )

            await update.message.reply_text(
                f"✅ Сообщение успешно отправлено в канал!\n\n"
                f"📝 Текст сообщения:\n{message_text}"
            )

            logger.info(f"Собственник отправил сообщение в канал: {message_text[:100]}...")

        except Exception as e:
            error_msg = str(e)
            await update.message.reply_text(
                f"❌ Ошибка отправки сообщения в канал:\n"
                f"{error_msg[:100]}\n\n"
                f"💡 Проверь:\n"
                f"• Бот добавлен в канал\n"
                f"• Бот имеет права администратора\n"
                f"• ID канала указан верно"
            )
            logger.error(f"Ошибка отправки сообщения в канал: {e}")

        return ConversationHandler.END

    except Exception as e:
        logger.error(f"Ошибка отправки сообщения: {e}")
        return ConversationHandler.END


@owner_only
async def owner_channel_message_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Отменяет отправку сообщения."""
    await update.message.reply_text("❌ Отправка сообщения отменена")
    return ConversationHandler.END
