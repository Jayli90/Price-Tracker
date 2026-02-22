import os
import telebot
import sqlite3
import logging
from telebot import types
from datetime import datetime

# 1. SETUP LOGGING
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# 2. CONFIGURATION
TOKEN = os.getenv("BOT_TOKEN")
DB_PATH = "/app/data/prices.db" # Volume path for Railway

bot = telebot.TeleBot(TOKEN)

# 3. DATABASE INITIALIZATION & AUTO-MIGRATION
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
        logger.info("✅ Database ready.")
    except Exception as e:
        logger.error(f"❌ Database error: {e}")

# 4. BOT COMMANDS

@bot.message_handler(commands=['start', 'help'])
def send_welcome(message):
    welcome_text = (
        "🛒 **Price Tracker Pro**\n\n"
        "**Main Commands:**\n"
        "• `/add [item] [price] [curr] [store]` — Save a price\n"
        "• `/list` — View tracked items (Buttons)\n"
        "• `/compare [item]` — Quick history check\n\n"
        "**Management:**\n"
        "• `/edit [item] [price] [curr] [store]` — Update last entry\n"
        "• `/delete [item]` — Remove last entry\n"
        "• `/backup` — Get your database file"
    )
    bot.reply_to(message, welcome_text, parse_mode="Markdown")

@bot.message_handler(commands=['add'])
def add_price(message):
    try:
        parts = message.text.split(maxsplit=4)
        if len(parts) < 5:
            bot.reply_to(message, "⚠️ Usage: `/add Milk 2.50 SGD NTUC`")
            return
        
        item, price, currency, store = parts[1].lower(), float(parts[2]), parts[3].upper(), parts[4].upper()
        
        conn = sqlite3.connect(DB_PATH)
        conn.execute("INSERT INTO price_log (item, price, currency, store, date) VALUES (?, ?, ?, ?, ?)",
                     (item, price, currency, store, datetime.now().strftime("%Y-%m-%d")))
        conn.commit()
        conn.close()
        bot.reply_to(message, f"✅ Saved: **{item}** at **{price:.2f} {currency}** ({store})")
    except Exception:
        bot.reply_to(message, "❌ Error. Format: `/add Milk 2.50 SGD NTUC`")

@bot.message_handler(commands=['list'])
def list_items_buttons(message):
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("SELECT DISTINCT item FROM price_log ORDER BY item ASC")
        rows = cursor.fetchall()
        conn.close()

        if rows:
            markup = types.InlineKeyboardMarkup(row_width=2)
            buttons = [types.InlineKeyboardButton(text=r[0].capitalize(), callback_data=f"view_{r[0]}") for r in rows]
            markup.add(*buttons)
            bot.reply_to(message, "📋 **Select an item to compare prices:**", reply_markup=markup, parse_mode="Markdown")
        else:
            bot.reply_to(message, "📭 Your list is empty.")
    except Exception as e:
        logger.error(f"List error: {e}")

@bot.callback_query_handler(func=lambda call: call.data.startswith('view_'))
def handle_item_select(call):
    item = call.data.replace("view_", "")
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.execute("SELECT price, currency, store, date FROM price_log WHERE item=? ORDER BY currency ASC, price ASC", (item,))
    rows = cursor.fetchall()
    conn.close()

    if rows:
        response = f"📊 **Price history for {item.capitalize()}:**\n\n"
        for r in rows:
            response += f"• **{r[0]:.2f} {r[1]}** — {r[2]} ({r[3]})\n"
        bot.answer_callback_query(call.id) # Stops the loading spinner
        bot.send_message(call.message.chat.id, response, parse_mode="Markdown")
    else:
        bot.answer_callback_query(call.id, "No data found.")

@bot.message_handler(commands=['compare', 'check'])
def compare_prices(message):
    try:
        item = message.text.split()[1].lower()
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.execute("SELECT price, currency, store, date FROM price_log WHERE item=? ORDER BY currency ASC, price ASC", (item,))
        rows = cursor.fetchall()
        conn.close()
        
        if rows:
            response = f"📊 **Price history for {item.capitalize()}:**\n\n" + "\n".join([f"• **{r[0]:.2f} {r[1]}** — {r[2]} ({r[3]})" for r in rows])
            bot.reply_to(message, response, parse_mode="Markdown")
        else:
            bot.reply_to(message, f"❓ No records for '{item}'.")
    except:
        bot.reply_to(message, "⚠️ Usage: `/compare Milk`")

@bot.message_handler(commands=['edit'])
def edit_price(message):
    try:
        parts = message.text.split(maxsplit=4)
        if len(parts) < 5:
            bot.reply_to(message, "⚠️ Usage: `/edit [item] [price] [curr] [store]`")
            return
        
        item, new_price, new_curr, new_store = parts[1].lower(), float(parts[2]), parts[3].upper(), parts[4].upper()
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("SELECT id FROM price_log WHERE item=? ORDER BY id DESC LIMIT 1", (item,))
        row = cursor.fetchone()

        if row:
            cursor.execute("UPDATE price_log SET price=?, currency=?, store=?, date=? WHERE id=?", 
                           (new_price, new_curr, new_store, datetime.now().strftime("%Y-%m-%d"), row[0]))
            conn.commit()
            bot.reply_to(message, f"✏️ Updated last **{item}** entry successfully.")
        else:
            bot.reply_to(message, f"❓ Item '{item}' not found.")
        conn.close()
    except Exception:
        bot.reply_to(message, "❌ Edit failed. Format: `/edit Milk 2.50 SGD Giant`")

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
            bot.reply_to(message, f"🗑️ Deleted last entry for **{item}**.")
        else:
            bot.reply_to(message, "❓ Item not found.")
        conn.close()
    except:
        bot.reply_to(message, "⚠️ Usage: `/delete Milk`")

@bot.message_handler(commands=['backup'])
def backup_db(message):
    try:
        with open(DB_PATH, 'rb') as f:
            bot.send_document(message.chat.id, f, caption="📂 Your current database.")
    except Exception:
        bot.reply_to(message, "❌ Backup failed.")

# 5. START POLLING
if __name__ == "__main__":
    init_db()
    logger.info("Bot is starting...")
    bot.infinity_polling(timeout=10, long_polling_timeout=5)
