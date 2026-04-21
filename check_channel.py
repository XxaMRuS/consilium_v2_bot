import telebot

BOT_TOKEN = "ТВОЙ_ТОКЕН_СЮДА"
CHANNEL_ID = "@MDFruN_Sports_Channel"  # или числовой ID

bot = telebot.TeleBot(BOT_TOKEN)

try:
    chat = bot.get_chat(CHANNEL_ID)
    print(f"✅ Найден канал: {chat.title} (ID: {chat.id})")
except Exception as e:
    print(f"❌ Бот не видит канал: {e}")