# -*- coding: utf-8 -*-
# Функции форматирования для отображения данных


def format_number(value):
    """Форматирует число для отображения, убирая .0 для целых чисел.

    Args:
        value: Число (int, float) или другое значение

    Returns:
        str: Отформатированная строка числа

    Examples:
        50.0 → "50"
        50.5 → "50.5"
        50 → "50"
        None → "0"
    """
    if value is None:
        return "0"
    if isinstance(value, (int, float)):
        # Если число целое, возвращаем без десятичных знаков
        if value == int(value):
            return str(int(value))
        else:
            return str(value)
    return str(value)
