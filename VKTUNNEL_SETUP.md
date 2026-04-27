# 🚀 VK Mini App - Локальная разработка

## 📋 Что нужно установить

### 1. Python зависимости
```bash
pip install fastapi uvicorn python-dotenv
```

### 2. VK Tunnel
```bash
npm install -g @vkontakte/vk-tunnel
```

---

## 🏗️ Настройка проекта

### Шаг 1: Подготовка базы данных

**ВАРИАНТ А: Использовать существующую базу**
```bash
# Используй ту же DATABASE_URL что в проде
# Nothing to change!
```

**ВАРИАНТ Б: Локальная база данных**
```bash
# Установить PostgreSQL
# Создать базу данных
createdb fitness_bot_local

# Обновить .env.local
DATABASE_URL=postgresql://user@localhost:5432/fitness_bot_local
```

### Шаг 2: Активировать локальное окружение

**Linux/Mac:**
```bash
cp .env.local .env
source venv/bin/activate  # если используешь venv
```

**Windows:**
```cmd
copy .env.local .env
venv\Scripts\activate.bat  # если используешь venv
```

---

## 🎯 Запуск локального сервера

### Вариант А: Автоматический (рекомендуется)

**Linux/Mac:**
```bash
chmod +x run_local.sh
./run_local.sh
```

**Windows:**
```cmd
run_local.bat
```

### Вариант Б: Прямой запуск
```bash
python api_main.py
```

**Сервер запустится на:** http://127.0.0.1:8000

---

## 🌐 Запуск VK Tunnel

### Шаг 1: Генерация SSL сертификатов

```bash
mkdir certs
openssl req -x509 -newkey rsa:4096 -keyout certs/key.pem -out certs/cert.pem -days 365 -nodes
```

### Шаг 2: Запуск VK Tunnel

**Базовый запуск:**
```bash
vk-tunnel --mode=local --http-port=8000 --https-port=6001
```

**С конфигом:**
```bash
vk-tunnel --config=vk-tunnel-config.json
```

**VK Tunnel создаст туннель:**
- Локальный: http://127.0.0.1:8000
- Внешний: https://<random>.vk-tunnel.app
- Порт: 6001

### Шаг 3: Получить URL туннеля

VK Tunnel покажет что-то вроде:
```
✔ Local server: http://localhost:8000
✔ Tunnel URL: https://abc123.vk-tunnel.app
```

---

## ⚙️ Настройка VK Mini App

### Обнови настройки в VK:

1. Открой: https://vk.com/editapp?id=54567668
2. Перейди в "Настройки"
3. Измени "Адрес" на URL туннеля:
   ```
   https://abc123.vk-tunnel.app
   ```
4. Сохрани

---

## 🧪 Тестирование

### 1. Проверь локальный сервер
Открой в браузере:
```
http://127.0.0.1:8000
```

Должен увидеть: "Fitness Bot"

### 2. Проверь туннель
Открой в браузере:
```
https://abc123.vk-tunnel.app
```

Должен увидеть то же самое

### 3. Открой VK Mini App
```
https://vk.com/app54567668
```

---

## 🛠️ Фронтенд разработка

### Структура проекта:
```
consilium_bot_v2/
├── api_main.py          # FastAPI сервер
├── index.html           # Главный экран
├── test.html            # Тестовая страница
├── static/              # Статические файлы
│   └── vk-bridge.min.js
└── frontend/            # Фронтенд код (опционально)
    ├── src/
    ├── public/
    └── package.json
```

### Редактирование HTML:

1. Открой `index.html`
2. Внеси изменения
3. Обнови страницу в браузере (F5)
4. Мгновенно видишь результат!

---

## 🔧 Горячие клавиши

### FastAPI (автоперезагрузка):
- Измени код → Сервер перезагружается автоматически
- Логи в консоли показывают перезагрузку

### VK Tunnel:
- `Ctrl+C` — остановить туннель
- Повторный запуск — новый URL

---

## 📱 Полный цикл разработки

### 1. Запусти локальный сервер:
```bash
python api_main.py
```

### 2. Запусти VK Tunnel (в новом терминале):
```bash
vk-tunnel --mode=local --http-port=8000
```

### 3. Открой VK Mini App:
```
https://vk.com/app54567668
```

### 4. Вноси изменения:
- Измени `index.html`
- Сохрани файл
- Обнови VK Mini App (F5)
- Результат мгновенно!

---

## 🚨 Распространенные проблемы

### Проблема 1: "Port 8000 already in use"
**Решение:**
```bash
# Windows
netstat -ano | findstr :8000
taskkill /PID <PID> /F

# Linux/Mac
lsof -ti:8000 | xargs kill -9
```

### Проблема 2: "VK Tunnel не запускается"
**Решение:**
```bash
# Переустанови VK Tunnel
npm uninstall -g @vkontakte/vk-tunnel
npm install -g @vkontakte/vk-tunnel
```

### Проблема 3: "База данных не подключается"
**Решение:**
- Проверь `DATABASE_URL` в `.env.local`
- Убедись что PostgreSQL запущен
- Проверь подключение:
  ```bash
  psql -h localhost -U user -d fitness_bot
  ```

### Проблема 4: "VK Mini App показывает старую версию"
**Решение:**
- Очисти кэш VK Mini App
- Закрой и открой приложение
- Используй `Ctrl+Shift+R` для жесткого обновления

---

## 📚 Полезные ресурсы

- **VK Tunnel Docs:** https://github.com/VKCOM/vk-tunnel
- **VK Bridge Docs:** https://dev.vk.com/bridge/overview
- **FastAPI Docs:** https://fastapi.tiangolo.com/
- **VK Mini Apps:** https://dev.vk.com/mini-apps/overview

---

## 🎯 Советы по разработке

### 1. Используй автоперезагрузку
FastAPI автоматически перезагружается при изменениях файлов

### 2. Держи оба терминала открытыми
- Терминал 1: FastAPI сервер
- Терминал 2: VK Tunnel

### 3. Используй console.log
```javascript
console.log('🐛 Debug:', data);
```

### 4. Проверяй локально сначала
```
localhost → VK Tunnel → VK Mini App
```

### 5. Коммить часто
```bash
git add .
git commit -m "feat: добавлена фича"
git push
```

---

## 🚀 Деплой на Render (когда готово)

### 1. Запуш изменения в main:
```bash
git checkout main
git merge feature/vk_mini_app
git push origin main
```

### 2. Render автоматически задеплоит!

### 3. Обнови URL в VK Mini App настройках:
```
https://fitness-bot-api-6k0i.onrender.com
```

---

## ✅ Чек-лист перед стартом

- [ ] Python установлен
- [ ] FastAPI и зависимости установлены
- [ ] VK Tunnel установлен
- [ ] База данных доступна
- [ ] `.env.local` создан и настроен
- [ ] Локальный сервер запускается (`python api_main.py`)
- [ ] VK Tunnel запускается (`vk-tunnel --mode=local`)
- [ ] VK Mini App обновлён с URL туннеля

---

**🎉 ГОТОВО! Разрабатывай локально, деплой на Render когда готово!**
