# -*- coding: utf-8 -*-
# Обработчики панели собственника

import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler
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

# Состояния для ConversationHandler перевода FF
WAITING_FF_TRANSFER_USER, WAITING_FF_TRANSFER_AMOUNT, WAITING_FF_TRANSFER_CONFIRM = range(3)


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
            InlineKeyboardButton("ℹ️ FF Информация", callback_data=OWNER_FF_INFO),
        ],
        [
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
        text += f"💰 Всего FF в системе: {total_ff}\n"
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
            text = "💰 **БАЛАНСЫ FF**\n\n"
            text += "Пока нет данных"
        else:
            text = "💰 **БАЛАНСЫ FF (ТОП-20)**\n\n"
            text += "💡 Нажми на кнопку чтобы скопировать ID\n\n"

            # Создаём список с кнопками для каждого пользователя
            keyboard = []

            for user in users:
                telegram_id, first_name, username, balance = user
                username_str = f"@{username}" if username else "(нет username)"
                # Экранируем спецсимволы
                safe_first_name = escape_markdown(first_name)
                safe_username = escape_markdown(username_str)
                text += f"💎 {safe_first_name} {safe_username}: {balance} FF\n"

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
        text += f"💰 Всего FF в системе: {total_ff}\n"
        text += f"👤 Пользователей с FF: {users_with_ff}\n\n"

        text += "💡 **Как управлять FF:**\n\n"
        text += "📝 **Для перевода FF пользователю:**\n"
        text += "Используйте скрипт manage_ff.py\n"
        text += "Команда: python manage_ff.py add ID СУММА\n\n"

        text += "⚠️ **Важно:**\n"
        text += "• FF используется для PvP ставок (10% комиссия)\n"
        text += "• Победитель получает 90% от банка\n"
        text += "• FF также начисляется за достижения\n\n"

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

        text = "💸 **ПЕРЕВОД FF**\n\n"
        text += "📝 Выберите пользователя из списка или введите ID/username вручную"

        keyboard = []

        # Добавляем кнопки для каждого пользователя
        for user in users:
            telegram_id, first_name, username, ff_balance = user
            username_part = f" @{username}" if username else ""
            ff_part = f" ({ff_balance}FF)" if ff_balance else ""

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
        text += f"💰 Текущий баланс: {current_ff} FF\n\n"
        text += "📝 Выберите сумму:"

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
        text += f"💰 Текущий баланс: {current_ff} FF\n\n"
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

    # Проверяем, что это положительное число
    try:
        amount = int(amount_input)
        if amount <= 0:
            raise ValueError("Amount must be positive")
    except ValueError:
        text = "❌ **Неверная сумма!**\n\n"
        text += "Сумма должна быть положительным числом.\n"
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
            notification_text = f"🎁 **ТЫ ПОЛУЧИЛ FF!**\n\n"
            notification_text += f"💰 Ты получил: {amount} FF\n"
            notification_text += f"📊 Твой баланс: {new_balance} FF\n\n"
            notification_text += f"💡 Используй FF для PvP ставок и покупок!"

            await bot.send_message(
                chat_id=target_user['telegram_id'],
                text=notification_text,
                parse_mode="Markdown"
            )
            notification_sent = True
            logger.info(f"📬 Уведомление отправлено пользователю {target_user['telegram_id']}")
        except Exception as e:
            notification_error = str(e)
            logger.warning(f"Не удалось отправить уведомление пользователю {target_user['telegram_id']}: {e}")

        safe_first_name = escape_markdown(target_user['first_name'])
        username_str = f"@{target_user['username']}" if target_user['username'] else "(нет username)"
        safe_username = escape_markdown(username_str)

        text = "✅ **ПЕРЕВОД ВЫПОЛНЕН!**\n\n"
        text += f"👤 Получатель: {safe_first_name} {safe_username}\n"
        text += f"💰 Переведено: {amount} FF\n"
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
            await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")
        except Exception as e:
            if "not modified" not in str(e):
                logger.error(f"Ошибка отображения: {e}")
                raise

        # Лируем перевод
        logger.info(f"💸 FF TRANSFER: {amount} FF -> {target_user['telegram_id']} ({safe_first_name})")

    except Exception as e:
        logger.error(f"Ошибка перевода FF: {e}")
        text = f"❌ **ОШИБКА ПЕРЕВОДА**\n\n"
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

