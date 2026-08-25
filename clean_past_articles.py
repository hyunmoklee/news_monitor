# clean_past_articles.py
import sqlite3
import shutil
import asyncio
import os
import sys

sys.path.insert(0, r"d:\1_MyProject\6_NaverNewsCrawler")
from preprocess_pipeline import run_pipeline
import build_dashboard

def clean_and_rebuild():
    # 1. DB Backup
    shutil.copyfile('news_monitor.db', 'news_monitor_backup_before_delete.db')
    print('Backed up DB to news_monitor_backup_before_delete.db')

    # 2. Delete past articles
    conn = sqlite3.connect('news_monitor.db')
    cur = conn.cursor()

    cur.execute("DELETE FROM articles WHERE published_at NOT LIKE '2026-08-25%' OR published_at IS NULL")
    deleted_raw = cur.rowcount
    print(f"Deleted {deleted_raw} past raw articles from [articles] table.")

    cur.execute("DELETE FROM processed_articles WHERE published_at NOT LIKE '2026-08-25%' OR published_at IS NULL")
    deleted_proc = cur.rowcount
    print(f"Deleted {deleted_proc} past processed articles from [processed_articles] table.")

    conn.commit()

    cur.execute("SELECT count(*) FROM articles")
    remaining_raw = cur.fetchone()[0]
    cur.execute("SELECT count(*) FROM processed_articles")
    remaining_proc = cur.fetchone()[0]
    print(f"Remaining in articles: {remaining_raw} (all from today 2026-08-25)")
    print(f"Remaining in processed_articles: {remaining_proc}")
    conn.close()

    # 3. Re-run Preprocessing Pipeline on only today's 76 articles
    print("\nRe-running Preprocessing Pipeline for today-only articles...")
    asyncio.run(run_pipeline())

    # 4. Rebuild Web Dashboard
    print("\nRebuilding Web Dashboard...")
    build_dashboard.generate_dashboard("두산에너빌리티", "index.html")
    print("\nSuccessfully finished today-only cleanup and dashboard rebuild!")

if __name__ == '__main__':
    clean_and_rebuild()
