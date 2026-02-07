import os
import telebot
# ... rest of your code ...
TOKEN = os.getenv("BOT_TOKEN") # Railway will provide this

bot = telebot.TeleBot(TOKEN)
# Important: Use the same path you set in the Railway Mount Path
db_path = "/app/data/prices.db"
conn = sqlite3.connect(db_path)
