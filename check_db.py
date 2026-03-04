import sqlite3

conn = sqlite3.connect("database.db")
cur = conn.cursor()

print("USERS TABLE")
for row in cur.execute("SELECT * FROM users"):
    print(row)

print("\nNGOS TABLE")
for row in cur.execute("SELECT * FROM ngos"):
    print(row)

conn.close()