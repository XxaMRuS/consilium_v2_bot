# 🌐 VK Mini App - Локальная разработка с Ngrok

**VK Tunnel не работает? Используй ngrok!**

---

## 🚀 БЫСТРЫЙ СТАРТ С NGROK

### 1. Установка Ngrok

#### Windows:
1. Скачай: https://ngrok.com/download
2. Распакуй архив
3. Добавь в PATH или используй напрямую

#### Linux/Mac:
```bash
brew install ngrok
```

#### Или через Chocolatey (Windows):
```powershell
choco install ngrok
```

### 2. Регистрация

1. Зарегистрируйся: https://ngrok.com/signup
2. Получи автотокен в dashboard
3. Авторизуйся:
```powershell
ngrok config add-authtoken YOUR_TOKEN
```

### 3. Запуск

**Терминал 1: Локальный сервер**
```powershell
python api_main.py
```

**Терминал 2: Ngrok**
```powershell
ngrok http 8000
```

**Или используй скрипты:**
```powershell
# Windows
start_ngrok.bat

# Linux/Mac
chmod +x start_ngrok.sh
./start_ngrok.sh
```

### 4. Получи URL

Ngrok покажет:
```
Session Status                online
Forwarding                    https://abc123.ngrok.io -> http://localhost:8000
                              ^^^^^^^^^^^^^^^^^^^^
                              Скопируй этот URL!
```

### 5. Обнови VK Mini App

1. Открой: https://vk.com/editapp?id=54567668
2. Измени "Адрес" на: `https://abc123.ngrok.io`
3. Сохрани

### 6. Открой приложение
```
https://vk.com/app54567668
```

---

## 📋 ПОЛНЫЙ ЦИКЛ РАЗРАБОТКИ

### Запуск:
```powershell
# Терминал 1
python api_main.py

# Терминал 2
ngrok http 8000
```

### Редактирование:
1. Открой `index.html`
2. Внеси изменения
3. Сохрани файл
4. Обнови VK Mini App (F5)

### Результат:
- ✅ Мгновенное отображение изменений
- ✅ Не нужно ждать деплоя на Render
- ✅ Удобная отладка в консоли

---

## 🎯 ПРЕИМУЩЕСТВА NGROK

| Преимущество | Описание |
|--------------|----------|
| ✅ **Быстрый** | Мгновенный запуск |
| ✅ **Простой** | Одна команда |
| ✅ **Стабильный** | Работает всегда |
| ✅ **Бесплатный** | Достаточно для разработки |
| ✅ **HTTPS** | Автоматически создаёт |
| ✅ **Логи** | Видны все запросы |

---

## 🛠️ ДОПОЛНИТЕЛЬНЫЕ ВОЗМОЖНОСТИ NGROK

### Просмотр логов в реальном времени:

Ngrok показывает все запросы:
```
HTTP Requests
-------------

GET /api/users/123          200 OK
GET /static/vk-bridge.min.js 200 OK
```

### Фиксированный поддомен (платно):

```powershell
ngrok http 8000 --domain=my-app.ngrok.io
```

### Настраиваемый субдомен:

Зарегистрируйся на https://ngrok.com и получи фиксированный домен.

---

## 🔄 ОБНОВЛЕНИЕ URL

При каждом перезапуске ngrok создаёт новый URL:
- Было: `https://abc123.ngrok.io`
- Стало: `https://xyz789.ngrok.io`

**Решение:**
1. Используй фиксированный домен (платно)
2. Или обновляй URL в VK Mini App каждый раз

---

## 🚨 РАСПРОСТРАНЕННЫЕ ПРОБЛЕМЫ

### Проблема 1: "ngrok not found"
**Решение:**
```powershell
# Добавь в PATH или используй полный путь
C:\path\to\ngrok.exe http 8000
```

### Проблема 2: "Authtoken required"
**Решение:**
```powershell
# Зарегистрируйся на ngrok.com и получи токен
ngrok config add-authtoken YOUR_TOKEN
```

### Проблема 3: "Port 8000 already in use"
**Решение:**
```powershell
# Windows
netstat -ano | findstr :8000
taskkill /PID <PID> /F

# Linux/Mac
lsof -ti:8000 | xargs kill -9
```

### Проблема 4: VK Mini App не обновляется
**Решение:**
- Очисти кэш: `Ctrl+Shift+R`
- Закрой и открой приложение
- Обнови URL в настройках VK

---

## 💡 СОВЕТЫ

### 1. Используй 2 терминала
- Терминал 1: `python api_main.py`
- Терминал 2: `ngrok http 8000`

### 2. Держи ngrok запущенным
Перезапускай только локальный сервер

### 3. Используй автоперезагрузку
FastAPI автоматически перезагружается при изменениях

### 4. Следи за логами ngrok
Показывает все запросы и ошибки

---

## 📚 АЛЬТЕРНАТИВЫ NGROK

### Cloudflare Tunnel
```bash
cloudflared tunnel --url http://localhost:8000
```

### Localtunnel
```bash
npx localtunnel --port 8000
```

### VK Tunnel (если работает)
```bash
vk-tunnel --app-id=54567668 --http-port=8000
```

---

## 🎯 ЧЕК-ЛИСТ

- [ ] Ngrok установлен
- [ ] Автотокен настроен
- [ ] Локальный сервер запущен (`python api_main.py`)
- [ ] Ngrok запущен (`ngrok http 8000`)
- [ ] URL скопирован
- [ ] VK Mini App обновлён с новым URL
- [ ] Приложение открыто и работает

---

## 🚀 ДЕПЛОЙ НА RENDER

Когда всё готово:

```bash
git checkout main
git add .
git commit -m "feat: новая функция"
git push origin main
```

Render автоматически задеплоит!

---

**🎉 ГОТОВО! Разрабатывай локально с ngrok!**
