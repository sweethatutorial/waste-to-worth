import sqlite3

conn = sqlite3.connect("database.db")
cur = conn.cursor()

# NGO table create
cur.execute("""
CREATE TABLE IF NOT EXISTS ngos (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ngo_name TEXT,
    email TEXT,
    password TEXT,
    address TEXT,
    certificate TEXT
)
""")

conn.commit()
conn.close()

print("NGOS table created successfully")