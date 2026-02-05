import sqlite3

DB_NAME = "complaints.db"

def get_db():
    return sqlite3.connect(DB_NAME)

def init_db():
    conn = get_db()
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS complaints (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            issue TEXT,
            department TEXT,
            location TEXT,
            detail TEXT,
            status TEXT DEFAULT 'รับเรื่องแล้ว'
        )
    """)
    conn.commit()
    conn.close()

init_db()
