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
        
        # Create table with currency support
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
        
        # Migration: Ensure 'currency' column exists for existing DBs
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
        "🛒 **Price Tracker Pro**\n\n"
        "**Commands:**\n"
        "• `/add [item] [price] [curr] [store]` — Save a price\n"
        "• `/compare [item]` — View price history\n"
        "• `/list` — See all items you've tracked\n"
        "• `/edit [item] [new_price] [new_curr] [new_store]`\n"
        "• `/delete [item]` — Remove last entry\n"
        "• `/backup` — Download your database file"
    )
    bot.reply_
