# preprocess.py
"""
Data Preprocessing Pipeline Module
Reads from raw [articles] table, applies customizable preprocessing logic,
and saves the result into [processed_articles] table.
"""
import sys
import os

if sys.stdout.encoding != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8')

sys.path.insert(0, r"d:\1_MyProject\6_NaverNewsCrawler")
import asyncio
import aiosqlite
import db
import build_dashboard
from config import DB_PATH

def preprocess_article(raw: dict) -> dict:
    """
    [Data Preprocessing Logic Placeholder]
    Custom preprocessing logic will be defined here according to future instructions.
    Currently applies basic normalization.
    """
    title = raw.get("title", "").strip()
    body = raw.get("body", "").strip()
    
    # Placeholder: Clean whitespace and formatting
    cleaned_body = body
    
    # Placeholder for summary / category / sentiment / tags
    summary = cleaned_body[:200] + "..." if len(cleaned_body) > 200 else cleaned_body
    category = "일반"
    
    return {
        "url": raw["url"],
        "title": title,
        "media_name": raw.get("media_name", "알 수 없음"),
        "journalist": raw.get("journalist", "알 수 없음"),
        "cleaned_body": cleaned_body,
        "summary": summary,
        "keyword": raw.get("keyword", "두산에너빌리티"),
        "category": category,
        "published_at": raw.get("published_at"),
        "extra_meta": {
            "char_count": len(cleaned_body),
            "status": "PREPROCESSED"
        }
    }

async def run_preprocessing():
    print("Initializing database and starting Preprocessing Pipeline...")
    await db.init_db()
    
    async with aiosqlite.connect(DB_PATH) as conn:
        conn.row_factory = aiosqlite.Row
        async with conn.execute("SELECT * FROM articles ORDER BY published_at DESC") as cursor:
            raw_rows = await cursor.fetchall()
            
        print(f"Found {len(raw_rows)} raw articles in [articles] table.")
        
        processed_count = 0
        for r in raw_rows:
            raw_dict = dict(r)
            processed_data = preprocess_article(raw_dict)
            
            await db.save_processed_article(
                url=processed_data["url"],
                title=processed_data["title"],
                media_name=processed_data["media_name"],
                journalist=processed_data["journalist"],
                cleaned_body=processed_data["cleaned_body"],
                keyword=processed_data["keyword"],
                published_at=processed_data["published_at"],
                summary=processed_data["summary"],
                category=processed_data["category"],
                extra_meta=processed_data["extra_meta"]
            )
            processed_count += 1
            
        print(f"Successfully processed and saved {processed_count} articles into [processed_articles] table.")

    # Rebuild dashboard with updated raw and processed tabs
    build_dashboard.generate_dashboard()

if __name__ == '__main__':
    asyncio.run(run_preprocessing())
