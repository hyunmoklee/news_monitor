# db.py
import json
import aiosqlite
from datetime import datetime
from typing import Optional, List, Dict, Any
from config import DB_PATH, PIPELINE_VERSION

async def init_db():
    """Initializes the database and creates/updates raw and processed tables."""
    async with aiosqlite.connect(DB_PATH) as db:
        # 1. RAWDATA / Extracted Articles Table
        await db.execute("""
            CREATE TABLE IF NOT EXISTS articles (
                url TEXT PRIMARY KEY,
                title TEXT NOT NULL,
                subtitle TEXT,
                media_name TEXT,
                journalist TEXT,
                author TEXT,
                body TEXT,
                chosen_text TEXT,
                keyword TEXT,
                raw_html TEXT,
                raw_html_hash TEXT,
                publisher_domain TEXT,
                pipeline_version TEXT,
                extraction_method TEXT,
                quality_score INTEGER,
                quality_score_detail TEXT,
                needs_review INTEGER DEFAULT 0,
                mismatch_reason TEXT,
                published_at TEXT,
                created_at TEXT NOT NULL,
                processed_at TEXT
            )
        """)
        
        # 2. DATA PREPROCESSING RESULT Table (Preprocessed & structured articles)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS processed_articles (
                url TEXT PRIMARY KEY,
                title TEXT NOT NULL,
                media_name TEXT,
                journalist TEXT,
                cleaned_body TEXT,
                summary TEXT,
                keyword TEXT,
                category TEXT,
                published_at TEXT,
                processed_at TEXT NOT NULL,
                extra_meta TEXT
            )
        """)
        
        # Check and migrate columns for articles if missing
        async with db.execute("PRAGMA table_info(articles)") as cursor:
            columns = [row[1] for row in await cursor.fetchall()]
            
            new_columns = {
                "author": "TEXT",
                "chosen_text": "TEXT",
                "raw_html": "TEXT",
                "raw_html_hash": "TEXT",
                "publisher_domain": "TEXT",
                "pipeline_version": "TEXT",
                "extraction_method": "TEXT",
                "quality_score": "INTEGER",
                "quality_score_detail": "TEXT",
                "needs_review": "INTEGER DEFAULT 0",
                "mismatch_reason": "TEXT",
                "published_at": "TEXT",
                "processed_at": "TEXT"
            }
            
            for col_name, col_type in new_columns.items():
                if col_name not in columns:
                    try:
                        await db.execute(f"ALTER TABLE articles ADD COLUMN {col_name} {col_type}")
                    except Exception as e:
                        print(f"Schema migration warning ({col_name}): {e}")
                        
        await db.commit()

async def is_crawled(url: str) -> bool:
    """Checks if a URL has already been crawled."""
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT 1 FROM articles WHERE url = ?", (url,)) as cursor:
            row = await cursor.fetchone()
            return row is not None

async def save_article(url: str, title: str, media_name: str, journalist: str, body: str, keyword: str, published_at: Optional[str] = None):
    """Saves a crawled raw article to the database (legacy support)."""
    created_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            INSERT OR REPLACE INTO articles (
                url, title, media_name, journalist, body, chosen_text, keyword, published_at, created_at, pipeline_version
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (url, title, media_name, journalist, body, body, keyword, published_at, created_at, PIPELINE_VERSION))
        await db.commit()

async def save_extracted_article(
    url: str,
    title: str,
    publisher_domain: str,
    raw_html: str,
    raw_html_hash: str,
    extraction_method: str,
    chosen_text: str,
    quality_score: int,
    quality_score_detail: Dict[str, Any],
    needs_review: bool,
    mismatch_reason: Optional[str] = None,
    media_name: Optional[str] = None,
    journalist: Optional[str] = None,
    author: Optional[str] = None,
    published_at: Optional[str] = None,
    keyword: Optional[str] = None,
    subtitle: Optional[str] = None,
    pipeline_version: str = PIPELINE_VERSION
):
    """Saves a fully extracted article with quality scores and metadata."""
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    score_detail_json = json.dumps(quality_score_detail or {}, ensure_ascii=False)
    needs_review_int = 1 if needs_review else 0
    
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            INSERT OR REPLACE INTO articles (
                url, title, subtitle, media_name, journalist, author, body, chosen_text,
                keyword, raw_html, raw_html_hash, publisher_domain, pipeline_version,
                extraction_method, quality_score, quality_score_detail, needs_review,
                mismatch_reason, published_at, created_at, processed_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            url, title, subtitle, media_name or publisher_domain, journalist or author or "알 수 없음", author,
            chosen_text, chosen_text, keyword, raw_html, raw_html_hash, publisher_domain, pipeline_version,
            extraction_method, quality_score, score_detail_json, needs_review_int,
            mismatch_reason, published_at, now_str, now_str
        ))
        await db.commit()

async def save_processed_article(
    url: str,
    title: str,
    media_name: str,
    journalist: str,
    cleaned_body: str,
    keyword: str,
    published_at: Optional[str] = None,
    summary: Optional[str] = None,
    category: Optional[str] = None,
    extra_meta: Optional[Dict[str, Any]] = None
):
    """Saves a preprocessed article to the processed_articles table."""
    processed_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    meta_json = json.dumps(extra_meta or {}, ensure_ascii=False)
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            INSERT OR REPLACE INTO processed_articles (
                url, title, media_name, journalist, cleaned_body, summary, keyword, category, published_at, processed_at, extra_meta
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (url, title, media_name, journalist, cleaned_body, summary, keyword, category, published_at, processed_at, meta_json))
        await db.commit()
