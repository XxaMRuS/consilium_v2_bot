# -*- coding: utf-8 -*-
"""
Скрипт для массового исправления небезопасных int() преобразований
"""

import re
import os

# Файлы для исправления
FILES_TO_FIX = [
    'admin_handlers.py',
    'owner_handlers.py',
    'pvp_handlers.py',
    'mountain_handlers.py'
]

# Паттерны для поиска и замены
PATTERNS = [
    # Паттерн 1: exercise_id = int(query.data.split("_")[-1])
    (
        r'(\s+)(\w+) = int\(query\.data\.split\("_"\)\[-1\]\)',
        r'\1success, \2, error = safe_int_convert(\n\1    query.data.split("_")[-1] if query.data else "",\n\1    "\2",\n\1    min_value=1\n\1)\n\1if not success:\n\1    await query.answer(f"❌ {error}", show_alert=True)\n\1    return'
    ),
    # Паттерн 2: exercise_id = int(callback_data.split("_")[-1])
    (
        r'(\s+)(\w+) = int\(callback_data\.split\("_"\)\[-1\]\)',
        r'\1success, \2, error = safe_int_convert(\n\1    callback_data.split("_")[-1] if callback_data else "",\n\1    "\2",\n\1    min_value=1\n\1)\n\1if not success:\n\1    await query.answer(f"❌ {error}", show_alert=True)\n\1    return'
    ),
    # Паттерн 3: page = int(query.data.split("_")[-1])
    (
        r'(\s+)(page) = int\(query\.data\.split\("_"\)\[-1\]\)',
        r'\1success, \2, error = safe_int_convert(\n\1    query.data.split("_")[-1] if query.data else "",\n\1    "\2",\n\1    min_value=0\n\1)\n\1if not success:\n\1    await query.answer(f"❌ {error}", show_alert=True)\n\1    return'
    ),
    # Паттерн 4: complex_id = int(callback_data.split(f"{PREFIX}_")[1])
    (
        r'(\s+)(complex_id) = int\(callback_data\.split\(f"\{(\w+)\}_"}\)\[1\]\)',
        r'\1try:\n\1    complex_part = callback_data.split(f"\2_")[1] if callback_data else ""\n\1    success, \2, error = safe_int_convert(complex_part, "\2", min_value=1)\n\1    if not success:\n\1        await query.answer(f"❌ {error}", show_alert=True)\n\1        return\n\1except (IndexError, AttributeError) as e:\n\1    logging.error(f"Некорректный callback_data: {callback_data}")\n\1    await query.answer("❌ Некорректные данные", show_alert=True)\n\1    return'
    ),
]

def fix_file(filepath):
    """Исправляет файл с небезопасными int() преобразованиями"""
    print(f"🔧 Обработка файла: {filepath}")

    if not os.path.exists(filepath):
        print(f"❌ Файл не найден: {filepath}")
        return False

    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()

    original_content = content
    fixes_count = 0

    for pattern, replacement in PATTERNS:
        matches = re.findall(pattern, content)
        if matches:
            print(f"  📝 Найдено {len(matches)} мест для паттерна")
            content = re.sub(pattern, replacement, content)
            fixes_count += len(matches)

    if content != original_content:
        # Создаем backup
        backup_path = filepath + '.backup'
        with open(backup_path, 'w', encoding='utf-8') as f:
            f.write(original_content)
        print(f"  💾 Backup создан: {backup_path}")

        # Записываем исправленный файл
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(content)

        print(f"  ✅ Исправлено {fixs_count} мест")
        return True
    else:
        print(f"  ℹ️ Не найдено мест для исправления")
        return False


def main():
    """Главная функция"""
    print("🚀 Начинаю массовое исправление int() преобразований...")

    total_fixed = 0
    for filename in FILES_TO_FIX:
        filepath = f"C:\\Users\\LL\\PycharmProjects\\consilium_bot_v2\\{filename}"
        if fix_file(filepath):
            total_fixed += 1

    print(f"\n🎯 Готово! Обработано файлов: {total_fixed}/{len(FILES_TO_FIX)}")


if __name__ == "__main__":
    main()