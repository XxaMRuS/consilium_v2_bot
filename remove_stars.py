#!/usr/bin/env python3
import re

files_to_fix = [
    'sport_handlers.py',
    'sport_challenge_handlers.py'
]

for file_path in files_to_fix:
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()

        # Убираем **текст** (жирный шрифт) и заменяем на просто текст
        content = re.sub(r'\*\*([^*]+)\*\*', r'\1', content)

        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(content)

        print(f'✅ Исправлен файл: {file_path}')
    except Exception as e:
        print(f'❌ Ошибка в {file_path}: {e}')
