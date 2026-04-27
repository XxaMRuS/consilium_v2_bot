# 🚀 НОВЫЙ СЕРВИС НА RENDER

## ИНСТРУКЦИЯ ПО СОЗДАНИЮ НОВОГО СЕРВИСА:

### 1. УДАЛИ СТАРЫЙ СЕРВИС:
- Открой Render Dashboard
- Найди `fitness-bot-api`
- Нажми "Delete" (если есть важные данные - экспортируй сначала)

### 2. СОЗДАЙ НОВЫЙ:
- "New +" → "Web Service"
- Подключи GitHub
- Выбери репозиторий: `consilium_v2_bot`
- Выбери ветку: `main`
- Введи имя: `fitness-bot-api-v2`

### 3. КОНФИГУРАЦИЯ:
- Runtime: `Python 3` → `Python 3.12`
- Build Command: `pip install -r requirements.txt`
- Start Command: `python api_main.py`

### 4. ПЕРЕМЕННЫЕ ОКРУЖЕНИЯ:
- `PYTHON_VERSION` = `3.12`
- `PORT` = (автоматически)

### 5. СОЗДАЙ БАЗУ ДАННЫХ (если нужно):
- "New +" → "PostgreSQL"
- Скопируй `DATABASE_URL`
- Добавь в переменные сервиса

### 6. РЕЗУЛЬТАТ:
- Получишь НОВЫЙ URL: `https://fitness-bot-api-v2.onrender.com`
- С точно последней версией кода
- С VK Bridge и отладкой
