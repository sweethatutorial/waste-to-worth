import sqlite3

# Database path
db_path = "database.db"

conn = sqlite3.connect(db_path)
cur = conn.cursor()

# Add new columns
try:
    cur.execute("ALTER TABLE users ADD COLUMN profile_image TEXT")
except sqlite3.OperationalError:
    print("profile_image column already exists")

try:
    cur.execute("ALTER TABLE users ADD COLUMN created_at TEXT")
except sqlite3.OperationalError:
    print("created_at column already exists")

conn.commit()
conn.close()
print("Columns added/verified successfully")