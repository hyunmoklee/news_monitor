"""
threading/timeline_engine.py
기업 핵심 기사들을 대상으로 임베딩을 추출하고, 타임라인 스레드 테이블을 생성/적재하는 오케스트레이터.
"""
import os
import sys
import sqlite3
from typing import List, Dict

try:
    sys.stdout.reconfigure(encoding='utf-8')
except Exception:
    pass

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import DB_PATH

from .embedder import get_text_embedding
from .clusterer import cluster_articles_by_event

def init_thread_tables(db_path: str = DB_PATH):
    """타임라인 스레드 관련 테이블 초기화"""
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS article_threads (
            thread_id INTEGER PRIMARY KEY AUTOINCREMENT,
            thread_title TEXT,
            topic_category VARCHAR(50),
            first_event_at TIMESTAMP,
            last_event_at TIMESTAMP,
            article_count INTEGER,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS article_thread_members (
            thread_id INTEGER,
            url TEXT,
            similarity_score REAL,
            is_key_anchor BOOLEAN DEFAULT 0,
            PRIMARY KEY (thread_id, url)
        )
    """)
    # articles 테이블에 thread_id 컬럼 추가 (없을 경우)
    try:
        cur.execute("ALTER TABLE articles ADD COLUMN thread_id INTEGER")
    except Exception:
        pass
    conn.commit()
    conn.close()

def build_event_threads(
    db_path: str = DB_PATH,
    similarity_threshold: float = 0.82
) -> Dict:
    """
    1. 기업 핵심 기사(is_market_news=0) 조회
    2. gemini-embedding-2로 768차원 벡터화
    3. 클러스터링을 거쳐 article_threads 및 members 테이블에 적재
    """
    init_thread_tables(db_path)
    
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    
    cur.execute("""
        SELECT url, title, body, chosen_text, published_at, created_at, media_name
        FROM articles
        WHERE is_market_news = 0 AND (is_exact_dup = 0 OR is_exact_dup IS NULL)
        ORDER BY published_at ASC
    """)
    rows = cur.fetchall()
    conn.close()
    
    if not rows:
        print("스레딩 대상 기업 핵심 기사가 없습니다.")
        return {"threads_count": 0, "articles_count": 0}
        
    print(f"\n🧵 [Event Threading] Processing {len(rows)} company core articles with gemini-embedding-2...")
    
    articles = []
    for r in rows:
        title = r["title"]
        lead = (r["body"] or r["chosen_text"] or "")[:200]
        text_to_embed = f"{title}\n{lead}"
        vec = get_text_embedding(text_to_embed)
        
        articles.append({
            "url": r["url"],
            "title": title,
            "published_at": r["published_at"] or r["created_at"],
            "media_name": r["media_name"],
            "embedding": vec
        })
        
    # 사건 단위 클러스터링
    clusters = cluster_articles_by_event(articles, similarity_threshold=similarity_threshold)
    
    # DB 적재
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    
    # 기존 스레드 초기화
    cur.execute("DELETE FROM article_thread_members")
    cur.execute("DELETE FROM article_threads")
    cur.execute("UPDATE articles SET thread_id = NULL")
    
    thread_summaries = []
    
    for cluster in clusters:
        # 시간순 정렬
        cluster_sorted = sorted(cluster, key=lambda x: x.get("published_at", ""))
        anchor_article = cluster_sorted[0]
        latest_article = cluster_sorted[-1]
        
        # 대표 스레드 타이틀 결정
        thread_title = anchor_article["title"]
        first_at = anchor_article["published_at"]
        last_at = latest_article["published_at"]
        count = len(cluster_sorted)
        
        cur.execute("""
            INSERT INTO article_threads (thread_title, topic_category, first_event_at, last_event_at, article_count)
            VALUES (?, 'BUSINESS_EVENT', ?, ?, ?)
        """, (thread_title, first_at, last_at, count))
        thread_id = cur.lastrowid
        
        for idx, art in enumerate(cluster_sorted):
            sim = art.get("similarity_to_anchor", 1.0 if idx == 0 else 0.85)
            is_anchor = 1 if idx == 0 else 0
            cur.execute("""
                INSERT INTO article_thread_members (thread_id, url, similarity_score, is_key_anchor)
                VALUES (?, ?, ?, ?)
            """, (thread_id, art["url"], sim, is_anchor))
            
            cur.execute("UPDATE articles SET thread_id = ? WHERE url = ?", (thread_id, art["url"]))
            
        thread_summaries.append({
            "thread_id": thread_id,
            "title": thread_title,
            "count": count,
            "first_at": first_at,
            "last_at": last_at
        })
        
    conn.commit()
    conn.close()
    
    print(f"✅ Generated {len(thread_summaries)} event threads from {len(rows)} articles.")
    return {
        "threads_count": len(thread_summaries),
        "articles_count": len(rows),
        "threads": thread_summaries
    }
