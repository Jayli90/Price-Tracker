import os
import telebot
import sqlite3
import logging
import requests
from datetime import datetime

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

TOKEN = os.getenv("BOT_TOKEN")
CURRENCY_API_KEY = os.getenv("EXCHANGE_RATE_KEY")
DB_PATH = "/app/data/prices.db" 

bot = telebot.TeleBot(TOKEN)

def get_sgd_price(amount, currency):
    """Converts any currency to SGD using live rates."""
    currency = currency.upper()
    if currency == "SGD":
        return amount
    
    try:
        url = f"https://v6.exchangerate-api.com/v6/{CURRENCY_API_KEY}/pair/{currency}/SGD/{amount}"
        response = requests.get(url)
        data = response.json()
        if data['result'] == 'success':
            return data['conversion_result']
    except Exception as e:
        logger.error(f"Currency conversion error: {e}")
    return None

# ... (init_db function stays the same) ...

@bot.message_handler(commands=['add'])
def add_price(message):
    try:
        # Format: /add [item] [price] [currency] [store]
        # Example: /add Milk 5.00 MYR Giant
        parts = message.text.split(maxsplit=4)
        if len(parts) < 5:
            bot.reply_to(message, "⚠️ Usage: `/add Milk 5.00 MYR Giant` (Use SGD if local)")
            return
        
        item = parts[1].lower()
        original_price = float(parts[2])
        currency = parts[3].upper()
        store = parts[4].upper()
        
        # Convert to SGD
        converted_price = get_sgd_price(original_price, currency)
        
        if converted_price is None:
            bot.reply_to(message, "❌ Currency conversion failed. Check your currency code (e.g., USD, MYR, JPY).")
            return

        conn = sqlite3.connect(DB_PATH)
        conn.execute("INSERT INTO price_log (item, price, store, date) VALUES (?, ?, ?, ?)",
                     (item, converted_price, store, datetime.now().strftime("%Y-%m-%d")))
        conn.commit()
        conn.close()
        
        bot.reply_to(message, f"✅ Recorded: **{item}**\n"
                              f"💰 Original: {original_price} {currency}\n"
                              f"🇸🇬 Converted: **${converted_price:.2f} SGD**\n"
                              f"🏪 Store: {store}")
    except ValueError:
        bot.reply_to(message, "❌ Invalid price. Use a number (e.g., 2.50).")
    except Exception as e:
        logger.error(f"Add error: {e}")

# ... (rest of the /compare, /delete, and /backup commands stay the same) ...

if __name__ == "__main__":
    # init_db() call here
    bot.infinity_polling()
