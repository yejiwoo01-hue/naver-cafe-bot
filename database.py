import sqlite3
import os

DB_PATH = "bot_data.db"

def init_db():
    """Initialize the database and tables if they don't exist."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS comment_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            cafe_url TEXT,
            post_id TEXT UNIQUE,
            author_id TEXT,
            keyword TEXT,
            comment_text TEXT,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Migration: Add author_id column to existing table if it doesn't exist
    try:
        cursor.execute("ALTER TABLE comment_history ADD COLUMN author_id TEXT")
    except sqlite3.OperationalError:
        pass # Column already exists
        
    conn.commit()
    conn.close()


def has_commented(post_id: str) -> bool:
    """Check if the given post ID has already been commented on."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT 1 FROM comment_history WHERE post_id = ?", (post_id,))
    result = cursor.fetchone()
    conn.close()
    return result is not None

def has_commented_to_author(author_id: str) -> bool:
    """Check if the given author ID has already received a comment from us."""
    if not author_id:
        return False
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT 1 FROM comment_history WHERE author_id = ?", (author_id,))
    result = cursor.fetchone()
    conn.close()
    return result is not None


def mark_commented(cafe_url: str, post_id: str, author_id: str, keyword: str, comment_text: str):
    """Record that a comment has been posted."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    try:
        cursor.execute(
            "INSERT INTO comment_history (cafe_url, post_id, author_id, keyword, comment_text) VALUES (?, ?, ?, ?, ?)",
            (cafe_url, post_id, author_id, keyword, comment_text)
        )
        conn.commit()
    except sqlite3.IntegrityError:
        pass  # Already exists
    finally:
        conn.close()


if __name__ == "__main__":
    init_db()
    print("Database initialized.")
