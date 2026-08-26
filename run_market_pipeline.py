"""
전체 수집 기사(221건) 대상 시황 스마트 필터링 배치 실행 파이프라인.
"""
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

async def execute_market_filter():
    config_path = os.path.join(BASE_DIR, "market_filter_config.yaml")
    db_path = os.path.join(BASE_DIR, "news_monitor.db")
    
    with open(config_path, "r", encoding="utf-8") as f:
        config = yaml.safe_load(f)
        
    curr_version = config.get("version", "v1.0")
    company_list = get_listed_companies()
    
    # 1. READ (Fetch all articles & close DB)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    cur.execute("SELECT url, title, body, chosen_text, published_at FROM articles ORDER BY published_at ASC")
    raw_rows = cur.fetchall()
    conn.close()
    
    print(f"=== [Market News Filter Pipeline] Processing {len(raw_rows)} Articles ===")
    
    articles_list = [dict(r) for r in raw_rows]
    
    # Step 1. Exact Dedup
    deduped = run_exact_dedup(
        articles_list,
        title_threshold=config.get("dedup", {}).get("title_jaccard_threshold", 0.85),
        lead_threshold=config.get("dedup", {}).get("lead_jaccard_threshold", 0.85)
    )
    
    now_ts = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    update_payloads = []
    
    counts = {"exact_dup": 0, "group_a_company": 0, "group_b_market": 0, "group_c_llm": 0}
    
    for art in deduped:
        u = art["url"]
        t = art.get("title") or ""
        body = art.get("chosen_text") or art.get("body") or ""
        is_exact_dup = art.get("is_exact_dup", 0)
        
        if is_exact_dup == 1:
            counts["exact_dup"] += 1
            update_payloads.append((1, 1, 0, "n/a", curr_version, now_ts, u))
            continue
            
        score, detail = calculate_market_score(t, body, config, company_list)
        group, rule_is_market = evaluate_decision(score, config)
        
        if group == "Group A":
            counts["group_a_company"] += 1
            is_mkt = False
            status = "n/a"
        elif group == "Group B":
            counts["group_b_market"] += 1
            is_mkt = True
            status = "n/a"
        else: # Group C
            counts["group_c_llm"] += 1
            lead_300 = body[:300]
            # LLM Evaluation
            is_mkt, status = await call_gemini_fallback(t, lead_300, config)
            
        # [Requirement 3] Short-Circuit Serialization:
        # Compute value_score ONLY if is_mkt == False (Company Core).
        # Skip value_score computation entirely for pure market news (is_mkt == True) to save CPU resources.
        if not is_mkt:
            from preprocessing.value_scorer import compute_value_score
            val_result = compute_value_score({"title": t, "cleaned_body": body, "url": u, "media_name": art.get("media_name", "")}, config)
            val_score = val_result.get("total_score", 0.0)
        else:
            val_score = 0.0  # Short-circuited
            
        update_payloads.append((0, 1 if is_mkt else 0, score, status, curr_version, now_ts, u))

        
    # 4. BULK WRITE
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
    
    print("\n[Pipeline Execution Summary]")
    print(f"  * Total Articles Processed     : {len(update_payloads)}")
    print(f"  * Exact Duplicates (is_exact_dup=1): {counts['exact_dup']}")
    print(f"  * Group A (Company Core News)  : {counts['group_a_company']}")
    print(f"  * Group B (Pure Market News)   : {counts['group_b_market']}")
    print(f"  * Group C (LLM Evaluated News) : {counts['group_c_llm']}")
    
    # Check final Company news count (is_exact_dup=0 AND is_market_news=0)
    final_company_count = sum(1 for p in update_payloads if p[0] == 0 and p[1] == 0)
    final_market_count = sum(1 for p in update_payloads if p[0] == 0 and p[1] == 1)
    print(f"\n[Final Filtered Result for Dashboard]")
    print(f"  * Pure Company Core Articles (Default View): {final_company_count}")
    print(f"  * Market / Ranking Articles (Hidden/Toggle) : {final_market_count}")


if __name__ == "__main__":
    asyncio.run(execute_market_filter())
