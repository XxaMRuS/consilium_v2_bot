# ⚡ VK Mini App - Быстрый старт

## 🚀 Одна команда для всего

### Полная установка и запуск:
```bash
make setup
```

## 📱 Быстрый запуск

### 1. Запуск сервера (Терминал 1):
```bash
make run
# или
python api_main.py
```

### 2. Запуск туннеля (Терминал 2):
```bash
make tunnel
# или
vk-tunnel --mode=local --http-port=8000
```

### 3. Открыть приложение:
```
https://vk.com/app54567668
```

## 🛠️ Основные команды

| Команда | Описание |
|---------|----------|
| `make run` | Запустить сервер |
| `make dev` | Запустить с автоперезагрузкой |
| `make tunnel` | Запустить VK Tunnel |
| `make clean` | Очистить временные файлы |
| `make test-api` | Тест API |

## 📝 Редактирование

1. Открой `index.html`
2. Внеси изменения
3. Сохрани файл
4. Обнови страницу (F5)
5. Готово! ✅

## 🔗 Ссылки

- **Локальный сервер:** http://127.0.0.1:8000
- **VK Tunnel:** https://<random>.vk-tunnel.app
- **VK Mini App:** https://vk.com/app54567668
- **API Docs:** http://127.0.0.1:8000/docs

## 🆘 Проблемы?

**Порт занят?**
```bash
# Windows
netstat -ano | findstr :8000
taskkill /PID <PID> /F

# Linux/Mac
lsof -ti:8000 | xargs kill -9
```

**База данных?**
- Проверь `.env.local`
- Убедись что PostgreSQL запущен

**VK Tunnel не работает?**
```bash
npm reinstall -g @vkontakte/vk-tunnel
```

## 📚 Полная документация

Смотри `VKTUNNEL_SETUP.md`

---

**💡 Разрабатывай локально → деплой на Render когда готово!**
