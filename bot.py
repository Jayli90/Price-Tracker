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
DB_PATH = "/app/data/prices.db"

bot = telebot.TeleBot(TOKEN)
user_edit_state = {} # Temporary storage for editing

# 3. DATABASE INITIALIZATION & AUTO-MIGRATION
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
                currency TEXT DEFAULT 'SGD',
                store TEXT NOT NULL,
                date TEXT NOT NULL
            )
        ''')
        cursor.execute("PRAGMA table_info(price_log)")
        columns = [column[1] for column in cursor.fetchall()]
        if 'currency' not in columns:
            cursor.execute("ALTER TABLE price_log ADD COLUMN currency TEXT DEFAULT 'SGD'")
        conn.commit()
        conn.close()
        logger.info("✅ Database ready.")
    except Exception as e:
        logger.error(f"❌ Database error: {e}")

# 4. BOT COMMANDS

@bot.message_handler(commands=['start', 'help'])
def send_welcome(message):
    welcome_text = (
        "🛒 **Price Tracker Pro (Buttons Edition)**\n\n"
        "**Core Commands:**\n"
        "• `/add [item] [price] [curr] [store]` — Save a price\n"
        "• `/list` — View prices (Interactive buttons)\n\n"
        "**Management:**\n"
        "• `/edit` — Choose a line to update\n"
        "• `/delete` — Choose a line to remove\n"
        "• `/backup` — Download your database file"
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
        bot.reply_to(message, "❌ Format error. Use: `/add Milk 2.50 SGD NTUC`")

# --- LIST / VIEW LOGIC ---
@bot.message_handler(commands=['list'])
def list_items(message):
    show_item_grid(message, "view")

# --- DELETE LOGIC ---
@bot.message_handler(commands=['delete'])
def delete_start(message):
    show_item_grid(message, "delsearch")

# --- EDIT LOGIC ---
@bot.message_handler(commands=['edit'])
def edit_start(message):
    show_item_grid(message, "editsearch")

def show_item_grid(message, prefix):
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("SELECT DISTINCT item FROM price_log ORDER BY item ASC")
        rows = cursor.fetchall()
        conn.close()
        if rows:
            markup = types.InlineKeyboardMarkup(row_width=2)
            buttons = [types.InlineKeyboardButton(text=r[0].capitalize(), callback_data=f"{prefix}_{r[0]}") for r in rows]
            markup.add(*buttons)
            prompt = "Select an item:"
            if prefix == "delsearch": prompt = "🗑️ **Delete which item?**"
            elif prefix == "editsearch": prompt = "✏️ **Edit which item?**"
            bot.reply_to(message, prompt, reply_markup=markup, parse_mode="Markdown")
        else:
            bot.reply_to(message, "📭 Database is empty.")
    except Exception as e:
        logger.error(f"Grid error: {e}")

# --- CALLBACK HANDLERS ---
@bot.callback_query_handler(func=lambda call: True)
def handle_query(call):
    data = call.data
    
    # VIEW ITEM
    if data.startswith("view_"):
        item = data.replace("view_", "")
        display_prices(call, item)

    # DELETE STEP 2: SHOW ENTRIES
    elif data.startswith("delsearch_"):
        item = data.replace("delsearch_", "")
        show_entries(call, item, "confirmdel", "Select entry to REMOVE:")

    # DELETE STEP 3: EXECUTE
    elif data.startswith("confirmdel_"):
        execute_delete(call)

    # EDIT STEP 2: SHOW ENTRIES
    elif data.startswith("editsearch_"):
        item = data.replace("editsearch_", "")
        show_entries(call, item, "selectedit", "Select entry to EDIT:")

    # EDIT STEP 3: PROMPT FOR INPUT
    elif data.startswith("selectedit_"):
        entry_id = data.replace("selectedit_", "")
        user_edit_state[call.from_user.id] = entry_id
        bot.answer_callback_query(call.id)
        msg = bot.send_message(call.message.chat.id, "⌨️ **Enter new details:**\n`item price currency store`", parse_mode="Markdown")
        bot.register_next_step_handler(msg, process_edit_save)

def display_prices(call, item):
    conn = sqlite3.connect(DB_PATH)
    rows = conn.execute("SELECT price, currency, store, date FROM price_log WHERE item=? ORDER BY currency, price ASC", (item,)).fetchall()
    conn.close()
    res = f"📊 **{item.capitalize()}** history:\n\n" + "\n".join([f"• {r[0]:.2f} {r[1]} @ {r[2]} ({r[3]})" for r in rows])
    bot.answer_callback_query(call.id)
    bot.send_message(call.message.chat.id, res, parse_mode="Markdown")

def show_entries(call, item, prefix, text):
    conn = sqlite3.connect(DB_PATH)
    rows = conn.execute("SELECT id, price, currency, store, date FROM price_log WHERE item=? ORDER BY id DESC LIMIT 5", (item,)).fetchall()
    conn.close()
    markup = types.InlineKeyboardMarkup(row_width=1)
    for r in rows:
        markup.add(types.InlineKeyboardButton(text=f"{r[1]} {r[2]} @ {r[3]} ({r[4]})", callback_data=f"{prefix}_{r[0]}"))
    bot.answer_callback_query(call.id)
    bot.send_message(call.message.chat.id, f"⚠️ **{text}**", reply_markup=markup, parse_mode="Markdown")

def execute_delete(call):
    eid = call.data.replace("confirmdel_", "")
    conn = sqlite3.connect(DB_PATH)
    conn.execute("DELETE FROM price_log WHERE id=?", (eid,))
    conn.commit()
    conn.close()
    bot.answer_callback_query(call.id, "Deleted!")
    bot.edit_message_text("✅ Entry removed.", call.message.chat.id, call.message.id)

def process_edit_save(message):
    uid = message.from_user.id
    if uid not in user_edit_state: return
    try:
        p = message.text.split(maxsplit=3)
        conn = sqlite3.connect(DB_PATH)
        conn.execute("UPDATE price_log SET item=?, price=?, currency=?, store=?, date=? WHERE id=?", 
                     (p[0].lower(), float(p[1]), p[2].upper(), p[3].upper(), datetime.now().strftime("%Y-%m-%d"), user_edit_state[uid]))
        conn.commit()
        conn.close()
        bot.reply_to(message, "✅ Entry updated!")
        del user_edit_state[uid]
    except Exception:
        bot.reply_to(message, "❌ Error. Try /edit again.")

@bot.message_handler(commands=['backup'])
def backup_db(message):
    try:
        with open(DB_PATH, 'rb') as f:
            bot.send_document(message.chat.id, f)
    except Exception:
        bot.reply_to(message, "❌ Backup failed.")

if __name__ == "__main__":
    init_db()
    bot.infinity_polling()
