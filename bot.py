import os
import telebot
import sqlite3
import logging
from datetime import datetime

# 1. SETUP LOGGING
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# 2. CONFIGURATION
TOKEN = os.getenv("BOT_TOKEN")
DB_PATH = "/app/data/prices.db" 

bot = telebot.TeleBot(TOKEN)

# 3. DATABASE INITIALIZATION & MIGRATION
def init_db():
    try:
        if not os.path.exists("/app/data"):
            os.makedirs("/app/data")
            
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        # Create table if it doesn't exist
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS price_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                item TEXT NOT NULL,
                price REAL NOT NULL,
                currency TEXT DEFAULT 'SGD',
                store TEXT NOT NULL,
                date TEXT NOT NULL
            )
        ''')
        
        # Migration: Check if 'currency' column exists (for older databases)
        cursor.execute("PRAGMA table_info(price_log)")
        columns = [column[1] for column in cursor.fetchall()]
        if 'currency' not in columns:
            cursor.execute("ALTER TABLE price_log ADD COLUMN currency TEXT DEFAULT 'SGD'")
            logger.info("Migrated database: Added currency column.")
            
        conn.commit()
        conn.close()
        logger.info("✅ Database initialized successfully.")
    except Exception as e:
        logger.error(f"❌ Database error: {e}")

# 4. BOT COMMANDS

@bot.message_handler(commands=['start', 'help'])
def send_welcome(message):
    welcome_text = (
        "🛒 **Multi-Currency Price Tracker**\n\n"
        "**Commands:**\n"
        "• `/add [item] [price] [currency] [store]`\n"
        "  _Ex: /add Milk 2.50 SGD NTUC_\n"
        "  _Ex: /add Eggs 15 MYR Giant_\n\n"
        "• `/compare [item]` — See prices by currency\n"
        "• `/delete [item]` — Remove last entry\n"
        "• `/backup` — Get your database file"
    )
    bot.reply_to(message, welcome_text, parse_mode="Markdown")

@bot.message_handler(commands=['add'])
def add_price(message):
    try:
        # Expected: /add Bread 3.50 SGD ColdStorage
        parts = message.text.split(maxsplit=4)
        if len(parts) < 5:
            bot.reply_to(message, "⚠️ Usage: `/add Milk 2.50 SGD NTUC`")
            return
        
        item = parts[1].lower()
        price = float(parts[2])
        currency = parts[3].upper()
        store = parts[4].upper()
        date_today = datetime.now().strftime("%Y-%m-%d")

        conn = sqlite3.connect(DB_PATH)
        conn.execute("INSERT INTO price_log (item, price, currency, store, date) VALUES (?, ?, ?, ?, ?)",
                     (item, price, currency, store, date_today))
        conn.commit()
        conn.close()
        
        bot.reply_to(message, f"✅ Recorded: **{item}**\n💰 **{price:.2f} {currency}** at {store}")
    except ValueError:
        bot.reply_to(message, "❌ Invalid price. Use a number (e.g. 2.50).")
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
        # Grouping by currency and sorting by price
        cursor = conn.execute("SELECT price, currency, store, date FROM price_log WHERE item=? ORDER BY currency ASC, price ASC", (item,))
        rows = cursor.fetchall()
        conn.close()
        
        if rows:
            response = f"📊 **Price history for {item.capitalize()}:**\n\n"
            for r in rows:
                response += f"• **{r[0]:.2f} {r[1]}** — {r[2]} ({r[3]})\n"
            bot.reply_to(message, response, parse_mode="Markdown")
        else:
            bot.reply_to(message, f"❓ No records for '{item}'.")
    except Exception as e:
        logger.error(f"Compare error: {e}")

@bot.message_handler(commands=['delete'])
def delete_price(message):
    try:
        parts = message.text.split()
        if len(parts) < 2:
            bot.reply_to(message, "⚠️ Usage: `/delete Milk`")
            return
            
        item = parts[1].lower()
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("SELECT id, price, currency FROM price_log WHERE item=? ORDER BY id DESC LIMIT 1", (item,))
        row = cursor.fetchone()
        
        if row:
            cursor.execute("DELETE FROM price_log WHERE id=?", (row[0],))
            conn.commit()
            bot.reply_to(message, f"🗑️ Deleted last entry for **{item}** ({row[1]} {row[2]}).")
        else:
            bot.reply_to(message, f"❓ Item '{item}' not found.")
        conn.close()
    except Exception as e:
        logger.error(f"Delete error: {e}")

@bot.message_handler(commands=['backup'])
def backup_db(message):
    try:
        with open(DB_PATH, 'rb') as f:
            bot.send_document(message.chat.id, f)
    except Exception:
        bot.reply_to(message, "❌ Backup failed.")

# 5. START POLLING
if __name__ == "__main__":
    init_db()
    logger.info("Bot is starting...")
    bot.infinity_polling(timeout=10, long_polling_timeout=5)
