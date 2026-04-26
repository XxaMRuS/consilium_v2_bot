# -*- coding: utf-8 -*-
"""
Утилиты для безопасной валидации и обработки данных
Защищают от крашей при некорректных пользовательских данных
"""

import logging
from typing import Optional, Tuple

logger = logging.getLogger(__name__)


def safe_int_convert(value: str, field_name: str = "value",
                    min_value: Optional[int] = None,
                    max_value: Optional[int] = None) -> Tuple[bool, Optional[int], str]:
    """
    Безопасное преобразование строки в integer с валидацией

    Args:
        value: Строка для преобразования
        field_name: Имя поля (для логов)
        min_value: Минимальное допустимое значение
        max_value: Максимальное допустимое значение

    Returns:
        (success, converted_value, error_message)

    Examples:
        >>> safe_int_convert("123", "user_id")
        (True, 123, "")

        >>> safe_int_convert("abc", "user_id")
        (False, None, "user_id должен быть числом")

        >>> safe_int_convert("-5", "exercise_id", min_value=1)
        (False, None, "exercise_id должен быть >= 1")
    """
    if value is None:
        return False, None, f"{field_name} не указан"

    if not isinstance(value, (str, int, float)):
        return False, None, f"{field_name} имеет неверный тип"

    try:
        converted = int(value)
    except (ValueError, TypeError) as e:
        logger.warning(f"Не удалось конвертировать {field_name}={value}: {e}")
        return False, None, f"{field_name} должен быть числом"

    # Проверка диапазонов
    if min_value is not None and converted < min_value:
        return False, None, f"{field_name} должен быть >= {min_value}"

    if max_value is not None and converted > max_value:
        return False, None, f"{field_name} должен быть <= {max_value}"

    return True, converted, ""


def safe_callback_data_parse(callback_data: str, separator: str = "_",
                             expected_parts: int = 2,
                             convert_to_int: list = None) -> Tuple[bool, list, str]:
    """
    Безопасный разбор callback_data с валидацией

    Args:
        callback_data: Строка callback_data
        separator: Разделитель
        expected_parts: Ожидаемое количество частей
        convert_to_int: Индексы частей, которые нужно конвертировать в int

    Returns:
        (success, parts_list, error_message)

    Examples:
        >>> safe_callback_data_parse("sport_menu_123", "_", 3, [2])
        (True, ["sport", "menu", 123], "")

        >>> safe_callback_data_parse("invalid", "_", 3)
        (False, [], "Некорректный формат данных")
    """
    if not callback_data:
        return False, [], "Пустые данные"

    try:
        parts = callback_data.split(separator)

        if len(parts) != expected_parts:
            return False, [], f"Некорректный формат: ожидалось {expected_parts} частей"

        # Конвертация указанных частей в int
        if convert_to_int:
            for idx in convert_to_int:
                if idx < len(parts):
                    success, converted, error = safe_int_convert(parts[idx], f"part_{idx}")
                    if not success:
                        return False, [], error
                    parts[idx] = converted

        return True, parts, ""

    except Exception as e:
        logger.error(f"Ошибка разбора callback_data: {e}")
        return False, [], "Ошибка обработки данных"


def safe_float_convert(value: str, field_name: str = "value",
                      min_value: Optional[float] = None,
                      max_value: Optional[float] = None) -> Tuple[bool, Optional[float], str]:
    """
    Безопасное преобразование строки в float с валидацией
    """
    if value is None:
        return False, None, f"{field_name} не указан"

    try:
        converted = float(value)
    except (ValueError, TypeError) as e:
        logger.warning(f"Не удалось конвертировать {field_name}={value}: {e}")
        return False, None, f"{field_name} должен быть числом"

    if min_value is not None and converted < min_value:
        return False, None, f"{field_name} должен быть >= {min_value}"

    if max_value is not None and converted > max_value:
        return False, None, f"{field_name} должен быть <= {max_value}"

    return True, converted, ""


def validate_user_id(user_id: int) -> Tuple[bool, str]:
    """
    Валидация user_id для Telegram/VK

    Args:
        user_id: ID пользователя

    Returns:
        (is_valid, error_message)
    """
    if not isinstance(user_id, int):
        try:
            user_id = int(user_id)
        except (ValueError, TypeError):
            return False, "user_id должен быть числом"

    # Telegram user_id обычно в диапазоне 1..2^31-1
    # VK может быть больше
    if user_id < 1:
        return False, "user_id должен быть положительным числом"

    if user_id > 10**10:  # Защита от явно неверных значений
        return False, "user_id слишком большой"

    return True, ""


def validate_text_length(text: str, max_length: int = 4096,
                         field_name: str = "text") -> Tuple[bool, str]:
    """
    Валидация длины текстового поля
    """
    if text is None:
        return False, f"{field_name} не может быть пустым"

    if len(text) > max_length:
        return False, f"{field_name} слишком длинный (макс {max_length} символов)"

    if len(text.strip()) == 0:
        return False, f"{field_name} не может быть пустым"

    return True, ""


def safe_list_index(lst: list, index: int, default=None):
    """
    Безопасное получение элемента списка по индексу
    """
    try:
        return lst[index] if 0 <= index < len(lst) else default
    except (TypeError, IndexError):
        return default


# ==================== ДЕКОРАТОРЫ ДЛЯ БЕЗОПАСНОСТИ ====================

def safe_handler(default_response=None):
    """
    Декоратор для безопасной обработки ошибок в handlers

    Args:
        default_response: Ответ при ошибке (если None, пробрасывает исключение)

    Usage:
        @safe_handler(default_response="Произошла ошибка")
        async def my_handler(update, context):
            # Код который может упасть
            pass
    """
    def decorator(func):
        async def wrapper(*args, **kwargs):
            try:
                return await func(*args, **kwargs)
            except Exception as e:
                logger.error(f"Ошибка в {func.__name__}: {e}", exc_info=True)

                if default_response is not None:
                    # Пытаемся отправить ответ пользователю
                    try:
                        update = args[0]
                        if hasattr(update, 'message'):
                            await update.message.reply_text(default_response)
                        elif hasattr(update, 'callback_query'):
                            await update.callback_query.answer(default_response, show_alert=True)
                    except Exception as send_error:
                        logger.error(f"Не удалось отправить ошибку пользователю: {send_error}")
                    return None
                else:
                    raise  # Пробрасываем исключение дальше
        return wrapper
    return decorator


def log_execution_time(func):
    """Декоратор для логирования времени выполнения"""
    async def wrapper(*args, **kwargs):
        import time
        start_time = time.time()

        try:
            result = await func(*args, **kwargs)
            execution_time = time.time() - start_time

            if execution_time > 1.0:  # Логируем только медленные функции
                logger.warning(f"⚠️ Медленная функция {func.__name__}: {execution_time:.2f}s")
            elif execution_time > 0.1:
                logger.info(f"⏱️ {func.__name__}: {execution_time:.3f}s")

            return result
        except Exception as e:
            execution_time = time.time() - start_time
            logger.error(f"❌ Ошибка в {func.__name__} ({execution_time:.2f}s): {e}")
            raise

    return wrapper


# ==================== УТИЛИТЫ ДЛЯ РЕТЕЯ ЛОГИКИ ====================

class RetryLogic:
    """Класс для retry логики с экспоненциальной задержкой"""

    def __init__(self, max_retries=3, base_delay=1.0):
        self.max_retries = max_retries
        self.base_delay = base_delay

    async def retry(self, func, *args, **kwargs):
        """
        Повторяет функцию при неудаче с экспоненциальной задержкой

        Args:
            func: Функция для повтора
            *args, **kwargs: Аргументы функции

        Returns:
            Результат функции или последний exception

        Raises:
            Последний exception если все попытки неудачны
        """
        import asyncio

        last_exception = None

        for attempt in range(self.max_retries):
            try:
                return await func(*args, **kwargs)
            except Exception as e:
                last_exception = e
                if attempt < self.max_retries - 1:
                    delay = self.base_delay * (2 ** attempt)
                    logger.warning(f"Попытка {attempt + 1} не удалась, retry через {delay}s...")
                    await asyncio.sleep(delay)
                else:
                    logger.error(f"Все {self.max_retries} попыток не удались")

        raise last_exception


# ==================== УТИЛИТЫ ДЛЯ ВАЛИДАЦИИ ДАННЫХ ====================

def sanitize_string(text: str, max_length: int = 1000,
                    remove_html: bool = True,
                    allowed_tags: list = None) -> str:
    """
    Очистка строки от потенциально опасного контента

    Args:
        text: Исходная строка
        max_length: Максимальная длина
        remove_html: Удалить HTML теги
        allowed_tags: Разрешенные HTML теги

    Returns:
        Очищенная строка
    """
    if not text:
        return ""

    # Обрезка по длине
    text = text[:max_length]

    # Удаление опасных символов
    dangerous_chars = ['<', '>', '"', "'", '\\']
    for char in dangerous_chars:
        text = text.replace(char, '')

    # Удаление лишних пробелов
    text = ' '.join(text.split())

    return text.strip()