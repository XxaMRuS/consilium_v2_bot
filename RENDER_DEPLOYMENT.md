# 🚀 FITNESS BOT - Render Deployment Guide

## 📋 Requirements for Render

- PostgreSQL database
- Python 3.12+
- BOT_TOKEN environment variable
- DATABASE_URL environment variable

## 🔧 Environment Variables

Add these in Render Dashboard:

```
BOT_TOKEN=your_telegram_bot_token
DATABASE_URL=postgresql://user:password@host:port/database
PYTHON_VERSION=3.12
```

## 📝 Important Notes

1. **JobQueue**: The bot uses JobQueue for scheduled tasks:
   - Daily ranking updates at 12:00
   - Monthly champions calculation on the 1st at 00:01

2. **Database**: PostgreSQL is required for connection pooling

3. **Logging**: All logs are sent to stdout for Render monitoring

4. **Workers**: If using worker processes, set `WEB_CONCURRENCY=1`

## 🏃 Starting the Bot

The bot starts automatically with:
```bash
python bot.py
```

## 🔍 Monitoring

Check Render logs for:
- "Бот запущен..." - bot started successfully
- "Application started" - Telegram connection OK
- Job execution logs
- Any ERROR messages

## ⚠️ Troubleshooting

1. **Bot doesn't respond**: Check BOT_TOKEN is correct
2. **Database errors**: Verify DATABASE_URL format
3. **JobQueue not working**: Check if worker is enabled
4. **Memory issues**: May need to upgrade Render plan

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
