import os
import sqlite3

# Define the path to the persistent volume
# This MUST match the Mount Path you set in Step 2
DB_FOLDER = "/app/data"
DB_PATH = os.path.join(DB_FOLDER, "prices.db")

# Ensure the directory exists (prevents errors on first run)
if not os.path.exists(DB_FOLDER):
    os.makedirs(DB_FOLDER)

def get_db_connection():
    # This connects to the database on the permanent Volume
    conn = sqlite3.connect(DB_PATH)
    return conn
