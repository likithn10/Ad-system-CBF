# init_users_db.py
import sqlite3
DB = "users.db"

conn = sqlite3.connect(DB)
c = conn.cursor()

c.execute("""
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT UNIQUE NOT NULL,
    password TEXT NOT NULL,
    role TEXT DEFAULT 'user'
)
""")

# Optional: insert a test user (admin/admin123)
try:
    c.execute("INSERT INTO users (username, password, role) VALUES (?, ?, ?)",
              ("admin", "admin123", "admin"))
except sqlite3.IntegrityError:
    pass

conn.commit()
conn.close()
print("✅ users.db created (or already existed). Test user: admin/admin123")
