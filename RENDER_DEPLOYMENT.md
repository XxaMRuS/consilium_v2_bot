# 🚀 FITNESS BOT - Render Deployment Guide

## 📋 Requirements for Render

- PostgreSQL database
- Python 3.12.0 (ТОЛЬКО эта версия!)
- BOT_TOKEN environment variable
- DATABASE_URL environment variable

**⚠️ ВАЖНО:** Используйте Python 3.12.0, НЕ используйте Python 3.14+ (есть проблемы с asyncio)

## 🔧 Environment Variables (ВАЖНО!)

### ⚠️ ОШИБКА InvalidToken?

Если вы видите ошибку `InvalidToken`, значит переменные окружения не настроены!

### 📝 Шаги для настройки Environment Variables на Render:

#### 1. Откройте Render Dashboard:
- Перейдите на https://dashboard.render.com
- Выберите ваш Web Service бота

#### 2. Перейдите в Environment Variables:
- Слева в меню выберите **"Environment"**
- Нажмите **"Add Environment Variable"**

#### 3. Добавьте переменные:

**Переменная 1: BOT_TOKEN**
- **Key:** `BOT_TOKEN`
- **Value:** `8660617089:AAErjnmbqZfrX_CMqkA0jisEn3xL5-koWkc`
- Нажмите **"Save"**

**Переменная 2: DATABASE_URL**
- **Key:** `DATABASE_URL`
- **Value:** `postgresql://consilium_bot_db_user:SABK9whZ2uQUDKtBfTgBZameKa0jzWR9@dpg-d75aj2h5pdvs73ci216g-a.oregon-postgres.render.com/consilium_bot_db`
- Нажмите **"Save"**

#### 4. Перезапустите сервис:
- Нажмите **"Manual Deploy"** → **"Clear build cache & deploy"**
- Или просто закоммитьте изменения в GitHub для автодеплоя

### 🔍 Проверка переменных окружения:

В логах Render должно быть:
```
✅ Переменные окружения загружены успешно
```

Если видите ошибку:
```
❌ BOT_TOKEN не найден в переменных окружения!
```

Значите переменная не добавлена в Render!

## 📝 Important Notes

1. **JobQueue**: The bot uses JobQueue for scheduled tasks:
   - Daily ranking updates at 12:00
   - Monthly champions calculation on the 1st at 00:01

2. **Database**: PostgreSQL is required for connection pooling

3. **Logging**: All logs are sent to stdout for Render monitoring

4. **Workers**: If using worker processes, set `WEB_CONCURRENCY=1`

5. **Environment Variables**: CRITICAL! .env file doesn't work on Render!

## 🏃 Starting the Bot

The bot starts automatically with:
```bash
python bot.py
```

## 🔍 Monitoring

Check Render logs for:
- "✅ Переменные окружения загружены успешно" - environment OK
- "Бот запущен..." - bot started successfully
- "Application started" - Telegram connection OK
- Job execution logs
- Any ERROR messages

## ⚠️ Troubleshooting

1. **InvalidToken Error**:
   - ✅ Добавьте BOT_TOKEN в Environment Variables в Render
   - ✅ Перезапустите сервис
   - ❌ НЕ используйте .env файл на Render

2. **Bot doesn't respond**: Check BOT_TOKEN is correct
3. **Database errors**: Verify DATABASE_URL format
4. **JobQueue not working**: Check if worker is enabled
5. **Memory issues**: May need to upgrade Render plan

## 📊 Scheduled Tasks

- `daily_ranking_update` - Updates rankings daily at 12:00
- `monthly_champions_calculation` - Calculates champions on 1st at 00:01

Both tasks run automatically and send notifications to users!

## 🎯 Owner Panel Access

After deployment, set owner with:
```bash
python set_owner.py TELEGRAM_ID
```

## 🔄 Updates

Push to GitHub → Render auto-deploys from main branch

---

**Status**: ✅ Ready for production
**Version**: 2.0 with automatic champions calculation
**Last Updated**: 21.04.2026 - Added Environment Variables setup guide
