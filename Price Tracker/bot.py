import os
import telebot
# ... rest of your code ...
TOKEN = os.getenv("BOT_TOKEN") # Railway will provide this
bot = telebot.TeleBot(TOKEN)