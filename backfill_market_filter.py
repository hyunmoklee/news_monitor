"""
Phase B-2: 수동 과거 데이터 재처리 CLI (Manual Backfill Pipeline).
- CLI 인수: --reprocess-from-version v1.0 --target-version v1.1
- 절대 자동화 금지 (수동 전용)
- I/O 분리: Fetch -> Close -> In-Memory Eval -> Bulk Update
"""
import argparse
import asyncio
import datetime
import os
import sqlite3
import yaml
import sys

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE_DIR)

from market_filter.company_dict import get_listed_companies
from market_filter.scoring import calculate_market_score
from market_filter.dedup import run_exact_dedup
from market_filter.decision import evaluate_decision, call_gemini_fallback

async def run_backfill(reprocess_version: str, target_version: str = None, limit: int = None):
    config_path = os.path.join(BASE_DIR, "market_filter_config.yaml")
    db_path = os.path.join(BASE_DIR, "news_monitor.db")
    
    with open(config_path, "r", encoding="utf-8") as f:
        config = yaml.safe_load(f)
        
    current_version = target_version or config.get("version", "v1.0")
    company_list = get_listed_companies()
    
    # 1. READ: Fetch 대상 기사 메모리 로드 후 DB 세션 즉시 종료 (DB Lock 방지)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    
    query = "SELECT url, title, body, chosen_text, published_at FROM articles WHERE scoring_version = ? OR scoring_version IS NULL"
    if limit:
        query += f" LIMIT {limit}"
    cur.execute(query, (reprocess_version,))
    raw_rows = cur.fetchall()
    conn.close()
    
    print(f"=== [Manual Backfill CLI] Reprocessing from {reprocess_version} to {current_version} ===")
    print(f"Total Target Records: {len(raw_rows)} articles")
    
    if not raw_rows:
        print("No articles to reprocess.")
        return
        
    articles_list = [dict(r) for r in raw_rows]
    
    # Step 1: Dedup Module
    deduped_articles = run_exact_dedup(
        articles_list,
        title_threshold=config.get("dedup", {}).get("title_jaccard_threshold", 0.85),
        lead_threshold=config.get("dedup", {}).get("lead_jaccard_threshold", 0.85)
    )
    
    # Step 2 & 3: In-Memory Scoring & Decision
    now_ts = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    update_payloads = []
    
    for art in deduped_articles:
        u = art["url"]
        t = art.get("title") or ""
        body = art.get("chosen_text") or art.get("body") or ""
        is_exact_dup = art.get("is_exact_dup", 0)
        
        if is_exact_dup == 1:
            # 중복 기사는 시황 평가 생략 (숨김 유지)
            update_payloads.append((1, 1, 0, "n/a", current_version, now_ts, u))
            continue
            
        score, detail = calculate_market_score(t, body, config, company_list)
        group, rule_is_market = evaluate_decision(score, config)
        
        if group == "Group C":
            # LLM API I/O 분리 호출
            lead_300 = body[:300]
            is_mkt, status = await call_gemini_fallback(t, lead_300, config)
        else:
            is_mkt = rule_is_market
            status = "n/a"
            
        update_payloads.append((0, 1 if is_mkt else 0, score, status, current_version, now_ts, u))
        
    # 4. BULK WRITE: 단일 트랜잭션으로 일괄 UPDATE
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    cur.executemany(
        """UPDATE articles SET 
            is_exact_dup = ?,
            is_market_news = ?,
            market_score = ?,
            llm_status = ?,
            scoring_version = ?,
            market_processed_at = ?
           WHERE url = ?""",
        update_payloads
    )
    conn.commit()
    conn.close()
    
    print(f"Successfully backfilled {len(update_payloads)} articles to version {current_version}.")

def main():
    parser = argparse.ArgumentParser(description="Manual Backfill CLI for Market News Filter")
    parser.add_argument("--reprocess-from-version", required=True, help="Source version to reprocess (e.g. v1.0)")
    parser.add_argument("--target-version", default=None, help="Target scoring version (e.g. v1.1)")
    parser.add_argument("--limit", type=int, default=None, help="Max articles to process")
    args = parser.parse_args()
    
    asyncio.run(run_backfill(args.reprocess_from-version, args.target-version, args.limit))

if __name__ == "__main__":
    main()
