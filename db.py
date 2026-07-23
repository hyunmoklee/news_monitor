# db.py
import aiosqlite
from datetime import datetime
from config import DB_PATH

async def init_db():
    """Initializes the database and creates the articles table if it doesn't exist."""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS articles (
                url TEXT PRIMARY KEY,
                title TEXT NOT NULL,
                media_name TEXT,
                journalist TEXT,
                body TEXT,
                keyword TEXT,
                created_at TEXT NOT NULL
            )
        """)
        await db.commit()

async def is_crawled(url: str) -> bool:
    """Checks if a URL has already been crawled."""
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT 1 FROM articles WHERE url = ?", (url,)) as cursor:
            row = await cursor.fetchone()
            return row is not None

async def save_article(url: str, title: str, media_name: str, journalist: str, body: str, keyword: str):
    """Saves a crawled article to the database."""
    created_at = datetime.now().isoformat()
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            INSERT OR IGNORE INTO articles (url, title, media_name, journalist, body, keyword, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (url, title, media_name, journalist, body, keyword, created_at))
        await db.commit()
