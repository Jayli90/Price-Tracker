import os
import telebot
import sqlite3
import logging
from datetime import datetime

# 1. SETUP LOGGING
# This allows you to see bot activity in the Railway "Deployments > Logs" tab
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# 2. CONFIGURATION
# TOKEN must be set in the Railway "Variables" tab
TOKEN = os.getenv("BOT_TOKEN")
# DB_PATH must match your Railway Volume Mount Path
DB_PATH = "/app/data/prices.db" 

bot = telebot.TeleBot(TOKEN)

# 3. DATABASE INITIALIZATION
def init_db():
    try:
        if not os.path.exists("/app/data"):
            os.makedirs("/app/data")
            
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS price_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                item TEXT NOT NULL,
                price REAL NOT NULL,
                store TEXT NOT NULL,
                date TEXT NOT NULL
            )
        ''')
        conn.commit()
        conn.close()
        logger.info("✅ Database initialized successfully.")
    except Exception as e:
        logger.error(f"❌ Database error: {e}")

# 4. BOT COMMANDS

@bot.message_handler(commands=['start', 'help'])
def send_welcome(message):
    welcome_text = (
        "🛒 **Price Tracker Bot is Online!**\n\n"
        "Commands:\n"
        "• `/add [item] [price] [store]` — Save a price\n"
        "• `/compare [item]` — Find the cheapest price\n"
        "• `/backup` — Download your database file"
    )
    bot.reply_to(message, welcome_text, parse_mode="Markdown")

@bot.message_handler(commands=['add'])
def add_price(message):
    try:
        # Split into: /add, item, price, store
        parts = message.text.split(maxsplit=3)
        if len(parts) < 4:
            bot.reply_to(message, "⚠️ Usage: `/add Milk 2.50 NTUC`")
            return
        
        item = parts[1].lower()
        price = float(parts[2])
        store = parts[3].upper()
        date_today = datetime.now().strftime("%Y-%m-%d")

        conn = sqlite3.connect(DB_PATH)
        conn.execute("INSERT INTO price_log (item, price, store, date) VALUES (?, ?, ?, ?)",
                     (item, price, store, date_today))
        conn.commit()
        conn.close()
        
        bot.reply_to(message, f"✅ Recorded: **{item}** at **${price:.2f}** ({store})")
        logger.info(f"New Entry: {item} - ${price}")
    except ValueError:
        bot.reply_to(message, "❌ Invalid price. Please use a number (e.g., 2.50).")
    except Exception as e:
        logger.error(f"Add error: {e}")

@bot.message_handler(commands=['compare', 'check'])
def compare_prices(message):
    try:
        parts = message.text.split()
        if len(parts) < 2:
            bot.reply_to(message, "⚠️ Usage: `/compare Milk`")
            return
            
        item = parts[1].lower()
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.execute("SELECT price, store, date FROM price_log WHERE item=? ORDER BY price ASC", (item,))
        rows = cursor.fetchall()
        conn.close()
        
        if rows:
            response = f"📊 **Price history for {item.capitalize()}:**\n\n"
            for r in rows:
                response += f"• **${r[0]:.2f}** — {r[1]} ({r[2]})\n"
            bot.reply_to(message, response, parse_mode="Markdown")
        else:
            bot.reply_to(message, f"❓ No data found for '{item}'.")
    except Exception as e:
        logger.error(f"Compare error: {e}")

@bot.message_handler(commands=['backup'])
def backup_db(message):
    try:
        with open(DB_PATH, 'rb') as f:
            bot.send_document(message.chat.id, f, caption="📂 Here is your prices.db file.")
    except Exception as e:
        bot.reply_to(message, "❌ Could not retrieve backup.")

# 5. START POLLING
if __name__ == "__main__":
    init_db()
    logger.info("Bot is starting...")
    # infinity_polling keeps the bot running even if it hits network hiccups
    bot.infinity_polling(timeout=10, long_polling_timeout=5)

import cv2
from pyzbar.pyzbar import decode
import numpy as np

@bot.message_handler(content_types=['photo'])
def handle_barcode(message):
    try:
        # 1. Download the photo from Telegram
        file_info = bot.get_file(message.photo[-1].file_id)
        downloaded_file = bot.download_file(file_info.file_path)
        
        # 2. Convert to a format OpenCV can read
        nparr = np.frombuffer(downloaded_file, np.uint8)
        img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        
        # 3. Decode the barcode
        barcodes = decode(img)
        
        if barcodes:
            # Extract the first barcode found
            barcode_data = barcodes[0].data.decode('utf-8')
            bot.reply_to(message, f"🔍 Scanned Barcode: `{barcode_data}`\n\n"
                                  f"Now send: `/add {barcode_data} [price] [store]`", 
                                  parse_mode="Markdown")
        else:
            bot.reply_to(message, "❌ No barcode detected. Try a clearer photo!")
            
    except Exception as e:
        logger.error(f"Barcode error: {e}")
        bot.reply_to(message, "⚠️ Error processing the image.")

