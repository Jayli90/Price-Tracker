import os
import telebot
import sqlite3
import logging
import cv2
import numpy as np
from pyzbar.pyzbar import decode
from datetime import datetime

# 1. SETUP LOGGING
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# 2. CONFIGURATION
TOKEN = os.getenv("BOT_TOKEN")
DB_PATH = "/app/data/prices.db" # Matches Railway Volume Mount Path

bot = telebot.TeleBot(TOKEN)

# 3. DATABASE INITIALIZATION
def init_db():
    if not os.path.exists("/app/data"):
        os.makedirs("/app/data")
    conn = sqlite3.connect(DB_PATH)
    conn.execute('''CREATE TABLE IF NOT EXISTS price_log 
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, 
                 item TEXT, price REAL, store TEXT, date TEXT)''')
    conn.commit()
    conn.close()
    logger.info("Database Ready.")

# --- COMMANDS ---

@bot.message_handler(commands=['start', 'help'])
def send_welcome(message):
    bot.reply_to(message, "🛒 **Price Tracker Pro**\n\n"
                          "• `/add [item] [price] [store]`\n"
                          "• `/compare [item]`\n"
                          "• `/delete [item]` (Removes last entry)\n"
                          "• `/backup` - Get DB file\n"
                          "• **Send a Photo** of a barcode to scan it!", parse_mode="Markdown")

@bot.message_handler(commands=['add'])
def add_price(message):
    try:
        _, item, price, store = message.text.split(maxsplit=3)
        conn = sqlite3.connect(DB_PATH)
        conn.execute("INSERT INTO price_log (item, price, store, date) VALUES (?, ?, ?, ?)",
                     (item.lower(), float(price), store.upper(), datetime.now().strftime("%Y-%m-%d")))
        conn.commit()
        conn.close()
        bot.reply_to(message, f"✅ Added **{item}** at **${float(price):.2f}** ({store.upper()})")
    except:
        bot.reply_to(message, "❌ Use: `/add Milk 2.50 NTUC` or `/add [barcode] 2.50 NTUC`")

@bot.message_handler(commands=['compare', 'check'])
def compare_prices(message):
    try:
        item = message.text.split()[1].lower()
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.execute("SELECT price, store, date FROM price_log WHERE item=? ORDER BY price ASC", (item,))
        rows = cursor.fetchall()
        conn.close()
        
        if rows:
            res = f"📊 **Prices for {item.capitalize()}:**\n" + "\n".join([f"• **${r[0]:.2f}** @ {r[1]} ({r[2]})" for r in rows])
            bot.reply_to(message, res, parse_mode="Markdown")
        else:
            bot.reply_to(message, "❓ No data yet.")
    except:
        bot.reply_to(message, "❌ Use: `/compare Milk` or `/compare [barcode]`")

@bot.message_handler(commands=['delete'])
def delete_price(message):
    try:
        item = message.text.split()[1].lower()
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("SELECT id FROM price_log WHERE item=? ORDER BY id DESC LIMIT 1", (item,))
        row = cursor.fetchone()
        if row:
            cursor.execute("DELETE FROM price_log WHERE id=?", (row[0],))
            conn.commit()
            bot.reply_to(message, f"🗑️ Deleted last entry for {item}.")
        else:
            bot.reply_to(message, "Item not found.")
        conn.close()
    except:
        bot.reply_to(message, "❌ Use: `/delete Milk`")

@bot.message_handler(commands=['backup'])
def backup_db(message):
    try:
        with open(DB_PATH, 'rb') as f:
            bot.send_document(message.chat.id, f)
    except:
        bot.reply_to(message, "Backup failed.")

# --- BARCODE SCANNING ---

@bot.message_handler(content_types=['photo'])
def handle_photo(message):
    try:
        file_info = bot.get_file(message.photo[-1].file_id)
        downloaded_file = bot.download_file(file_info.file_path)
        nparr = np.frombuffer(downloaded_file, np.uint8)
        img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        
        barcodes = decode(img)
        if barcodes:
            code = barcodes[0].data.decode('utf-8')
            bot.reply_to(message, f"🔍 **Barcode Detected:** `{code}`\n\nCopy and use:\n`/add {code} [price] [store]`", parse_mode="Markdown")
        else:
            bot.reply_to(message, "❌ Could not find a barcode. Try a closer, clearer photo!")
    except Exception as e:
        logger.error(f"Image error: {e}")

# --- START ---
if __name__ == "__main__":
    init_db()
    logger.info("Bot is polling...")
    bot.infinity_polling()
