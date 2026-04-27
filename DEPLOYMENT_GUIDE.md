# 🚀 РУКОВОДСТВО ПО ДЕПЛОЮ API НА RENDER.COM

## 📋 ПОДГОТОВКА

### ✅ Что уже готово:
- [x] REST API создан (`api_main.py`)
- [x] HTML тестовый интерфейс (`api_test.html`)
- [x] Requirements обновлён (`requirements.txt`)
- [x] Render конфигурация (`render.yaml`)
- [x] Скрипт запуска (`start_api.sh`)

---

## 🚀 ДЕПЛОЙ ЗА 5 МИНУТ

### Шаг 1: Создать аккаунт Render (если нет)
1. Перейти на https://render.com
2. Зарегистрироваться через GitHub/GitLab/Bitbucket
3. Подтвердить email

### Шаг 2: Создать New Web Service
1. В Dashboard нажать **"New +"** → **"Web Service"**
2. Выбрать репозиторий с вашим проектом
3. Если не видите - нажать **"Connect Account"** и дать доступ к GitHub

### Шаг 3: Настроить сервис
**Basic Settings:**
- **Name**: `fitness-bot-api` (или любое)
- **Region**: Singapore (ближе к России) или Frankfurt
- **Branch**: `feature/vk_mini_app`
- **Root Directory**: `.` (корень проекта)
- **Runtime**: `Python 3` → `Python 3.12`

**Build & Deploy:**
- **Build Command**: `pip install -r requirements.txt`
- **Start Command**: `python api_main.py`

### Шаг 4: Переменные окружения (Environment Variables)
Добавить в **"Environment"** раздел:

```
PYTHON_VERSION=3.12
RUN_API_SERVER=true
DATABASE_URL=ваша_база_данных
```

**Для DATABASE_URL:**
1. Создать PostgreSQL базу в Render: **"New +"** → **"PostgreSQL"**
2. Скопировать **"Internal Database URL"**
3. Вставить в переменные окружения API

### Шаг 5: Деплой
1. Нажать **"Create Web Service"**
2. Подождать 2-3 минуты (сборка и запуск)
3. Видите зелёный статус **"Live"**? ✅ Готово!

---

## 🌐 ПОЛУЧИТЬ URL АПИ

После деплоя Render выдаст URL вида:
```
https://fitness-bot-api.onrender.com
```

**Проверить работу:**
```
https://fitness-bot-api.onrender.com/
https://fitness-bot-api.onrender.com/docs (Swagger)
```

---

## ⚙️ НАСТРОЙКА CORS (если нужно)

Если API будут вызывать с фронтенда, добавить в `api_main.py`:

```python
from fastapi.middleware.cors import CORSMiddleware

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # или конкретные домены
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

---

## 📊 МОНИТОРИНГ

В Render Dashboard доступны:
- **Logs** - логи приложения в реальном времени
- **Metrics** - метрики (CPU, RAM, запросы)
- **Events** - события деплоя

---

## 🔧 TROUBLESHOOTING

### API не отвечает:
1. Проверить логи в Render Dashboard (Logs)
2. Убедиться что порт правильный (Render использует свои порты)
3. Проверить переменные окружения

### Ошибка базы данных:
1. Проверить что DATABASE_URL правильный
2. Убедиться что база PostgreSQL создана
3. Проверить что база в том же регионе что API

### Медленный запуск:
1. Первые 2-3 минуты могут быть медленными (холодный старт)
2. Последующие запросы будут быстрыми

---

## 💰 СТОИМОСТЬ

**Бесплатный план Render:**
- 750 часов/месяц (хватает для тестов)
- Автоматически "спит" при неактивности
- Просыпается за ~30 секунд при первом запросе

**Платные планы:**
- От $7/месяц за постоянную работу
- Быстрый запуск и стабильная работа

---

## 🎯 СЛЕДУЮЩИЕ ШАГИ ПОСЛЕ ДЕПЛОЯ

1. ✅ Получить URL задеплоенного API
2. ✅ Протестировать все endpoint'ы
3. ✅ Создать VK Mini App
4. ✅ Подключить VK SDK к API
5. ✅ Протестировать интеграцию

---

**Готово! Ваш API будет доступен из интернета!** 🚀
