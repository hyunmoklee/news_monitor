"""
threading/timeline_engine.py
- Event Timeline Threading Orchestrator
- Supports Corporate Event Threading & Filtered Market News Threading
- Automatically distinguishes broker entities (e.g., KB증권 vs 한국투자증권)
"""
import os
import sys
import sqlite3
import json
import re
from typing import List, Dict

try:
    sys.stdout.reconfigure(encoding='utf-8')
except Exception:
    pass

from config import DB_PATH
from .embedder import get_text_embedding, get_batch_text_embeddings, compute_cosine_similarity
from .clusterer import cluster_articles_by_event



# 30+ Major Generic Brokerage & Research Entities
BROKER_ENTITIES = [
    "KB증권", "한국투자증권", "한투증권", "미래에셋증권", "미래에셋", 
    "NH투자증권", "신한투자증권", "신한증권", "하나증권", "키움증권", 
    "대신증권", "삼성증권", "유진투자증권", "메리츠증권", "교보증권",
    "하이투자증권", "iM증권", "현대차증권", "IBK투자증권", "DB금융투자",
    "모건스탠리", "JP모건", "골드만삭스", "노무라", "맥쿼리", "씨티그룹"
]

def extract_broker_entity(title: str, body: str) -> str:
    """기사 제목 및 서두에서 리포트 발행 기관을 표준 명칭으로 정규화하여 추출"""
    content = f"{title} {(body or '')[:200]}"
    for b in BROKER_ENTITIES:
        if b in content:
            if b in ["한투증권", "한국투자증권"]: return "한국투자증권"
            if b in ["미래에셋", "미래에셋증권"]: return "미래에셋증권"
            if b in ["신한증권", "신한투자증권"]: return "신한투자증권"
            if b in ["하이투자증권", "iM증권"]: return "iM증권"
            return b
    return "일반"


def init_thread_tables(db_path: str = DB_PATH):
    """타임라인 스레드 관련 테이블 초기화"""
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    # 1. 기업 핵심 기사 스레드
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
    
    # 2. 시황 제외 기사 스레드
    cur.execute("""
        CREATE TABLE IF NOT EXISTS market_threads (
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
        CREATE TABLE IF NOT EXISTS market_thread_members (
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
    2. gemini-embedding-2로 768차원 벡터화 (Broker Entity 주입)
    3. 클러스터링을 거쳐 article_threads 및 members 테이블에 적재
    """
    init_thread_tables(db_path)
    
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    
    cur.execute("""
        SELECT url, title, body, chosen_text, published_at, created_at, media_name, structured_intelligence, event_category
        FROM articles
        WHERE is_market_news = 0 AND (is_exact_dup = 0 OR is_exact_dup IS NULL)
        ORDER BY published_at ASC
    """)
    rows = cur.fetchall()
    conn.close()
    
    if not rows:
        print("스레딩 대상 기업 핵심 기사가 없습니다.")
        return {"threads_count": 0, "articles_count": 0}
        
    print(f"\n🧵 [Corporate Event Threading v2.0] Processing {len(rows)} company core articles with gemini-embedding-2 (Broker-Aware)...")
    
    articles = []
    texts_to_embed = []
    meta_list = []
    for r in rows:
        title = r["title"]
        body = r["chosen_text"] or r["body"] or ""
        s_intel = {}
        try:
            if r["structured_intelligence"]:
                s_intel = json.loads(r["structured_intelligence"])
        except Exception:
            pass
            
        broker = extract_broker_entity(title, body)
        
        if s_intel and s_intel.get("executive_headline"):
            h_line = s_intel.get("executive_headline")
            cat = s_intel.get("event_category", "일반")
            entities = ", ".join(s_intel.get("key_entities", []))
            text_to_embed = f"[{cat}] [발행기관: {broker}] {h_line}\n주요 주체: {entities}"
        else:
            lead = body[:200]
            text_to_embed = f"[발행기관: {broker}] {title}\n{lead}"

        texts_to_embed.append(text_to_embed)
        meta_list.append({
            "url": r["url"],
            "title": s_intel.get("executive_headline") or title,
            "original_title": title,
            "published_at": r["published_at"] or r["created_at"],
            "media_name": r["media_name"],
            "broker": broker
        })

    vectors = get_batch_text_embeddings(texts_to_embed, concurrency=15)
    for meta, vec in zip(meta_list, vectors):
        meta["embedding"] = vec
        articles.append(meta)

    # 사건 단위 클러스터링
    clusters = cluster_articles_by_event(articles, similarity_threshold=similarity_threshold)

    
    # DB 적재
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    
    # 기존 스레드 초기화
    cur.execute("DELETE FROM article_thread_members")
    cur.execute("DELETE FROM article_threads")
    cur.execute("UPDATE articles SET thread_id = NULL WHERE is_market_news = 0")
    
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
        article_count = len(cluster_sorted)
        
        cur.execute("""
            INSERT INTO article_threads (thread_title, first_event_at, last_event_at, article_count)
            VALUES (?, ?, ?, ?)
        """, (thread_title, first_at, last_at, article_count))
        
        thread_id = cur.lastrowid
        
        for idx, art in enumerate(cluster_sorted):
            is_anchor = (idx == 0)
            from .embedder import compute_cosine_similarity
            sim_score = compute_cosine_similarity(anchor_article["embedding"], art["embedding"])
            
            cur.execute("""
                INSERT INTO article_thread_members (thread_id, url, similarity_score, is_key_anchor)
                VALUES (?, ?, ?, ?)
            """, (thread_id, art["url"], round(sim_score, 3), 1 if is_anchor else 0))
            
            cur.execute("""
                UPDATE articles SET thread_id = ? WHERE url = ?
            """, (thread_id, art["url"]))
            
        thread_summaries.append({
            "thread_id": thread_id,
            "title": thread_title,
            "count": article_count,
            "first_at": first_at
        })
        
    conn.commit()
    conn.close()
    
    print(f"✅ Generated {len(thread_summaries)} corporate event threads from {len(rows)} articles.")
    return {"threads_count": len(thread_summaries), "articles_count": len(rows), "threads": thread_summaries}


def build_market_event_threads(
    db_path: str = DB_PATH,
    similarity_threshold: float = 0.78
) -> Dict:
    """
    시황/노이즈로 제외된 기사들(is_market_news=1 또는 is_exact_dup=1)을 대상으로
    복제 보도자료/주제별로 클러스터링하여 market_threads 테이블에 적재.
    """
    init_thread_tables(db_path)
    
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    
    cur.execute("""
        SELECT url, title, body, chosen_text, published_at, created_at, media_name
        FROM articles
        WHERE is_market_news = 1 OR is_exact_dup = 1
        ORDER BY published_at ASC
    """)
    rows = cur.fetchall()
    conn.close()
    
    if not rows:
        return {"threads_count": 0, "articles_count": 0}
        
    print(f"\n🗑️ [Filtered Market News Threading] Clustering {len(rows)} filtered articles into grouped threads...")
    
    articles = []
    texts_to_embed = []
    meta_list = []
    for r in rows:
        title = r["title"]
        lead = (r["chosen_text"] or r["body"] or "")[:150]
        text_to_embed = f"{title}\n{lead}"
        texts_to_embed.append(text_to_embed)
        meta_list.append({
            "url": r["url"],
            "title": title,
            "published_at": r["published_at"] or r["created_at"],
            "media_name": r["media_name"]
        })

    vectors = get_batch_text_embeddings(texts_to_embed, concurrency=15)
    for meta, vec in zip(meta_list, vectors):
        meta["embedding"] = vec
        articles.append(meta)
        
    # 클러스터링
    clusters = cluster_articles_by_event(articles, similarity_threshold=similarity_threshold)

    
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    cur.execute("DELETE FROM market_thread_members")
    cur.execute("DELETE FROM market_threads")
    
    thread_summaries = []
    for cluster in clusters:
        cluster_sorted = sorted(cluster, key=lambda x: x.get("published_at", ""))
        anchor_article = cluster_sorted[0]
        latest_article = cluster_sorted[-1]
        
        thread_title = anchor_article["title"]
        first_at = anchor_article["published_at"]
        last_at = latest_article["published_at"]
        article_count = len(cluster_sorted)
        
        cur.execute("""
            INSERT INTO market_threads (thread_title, first_event_at, last_event_at, article_count)
            VALUES (?, ?, ?, ?)
        """, (thread_title, first_at, last_at, article_count))
        thread_id = cur.lastrowid
        
        for idx, art in enumerate(cluster_sorted):
            is_anchor = (idx == 0)
            from .embedder import compute_cosine_similarity
            sim_score = compute_cosine_similarity(anchor_article["embedding"], art["embedding"])
            
            cur.execute("""
                INSERT INTO market_thread_members (thread_id, url, similarity_score, is_key_anchor)
                VALUES (?, ?, ?, ?)
            """, (thread_id, art["url"], round(sim_score, 3), 1 if is_anchor else 0))
            
        thread_summaries.append({
            "thread_id": thread_id,
            "title": thread_title,
            "count": article_count
        })
        
    conn.commit()
    conn.close()
    
    print(f"✅ Grouped {len(rows)} filtered articles into {len(thread_summaries)} market threads.")
    return {"threads_count": len(thread_summaries), "articles_count": len(rows)}
