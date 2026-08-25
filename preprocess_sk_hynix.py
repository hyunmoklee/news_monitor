# preprocess_sk_hynix.py
"""
SK Hynix News Preprocessing Pipeline (Stages 1 to 9)
Includes NLP Deduplication, Value Scoring, Global Relevance & Company Focus Evaluation.
"""
import sys
import os
import json
import yaml

if sys.stdout.encoding != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8')

sys.path.insert(0, r"d:\1_MyProject\6_NaverNewsCrawler")
import asyncio
import aiosqlite
import db
from config import DB_PATH
from preprocessing.text_cleaner import clean_text
from preprocessing.rule_filter import evaluate_rule_filter
from preprocessing.candidate_cluster import generate_candidate_pairs
from preprocessing.embedding_dedup import cluster_and_deduplicate
from preprocessing.value_scorer import select_master_articles
from preprocessing.promo_classifier import evaluate_promotional
from preprocessing.global_relevance import evaluate_global_relevance
from preprocessing.company_focus import evaluate_company_focus

def load_config(config_path: str = "filter_config_sk_hynix.yaml") -> dict:
    if os.path.exists(config_path):
        with open(config_path, "r", encoding="utf-8") as f:
            return yaml.safe_load(f)
    return {}

async def run_sk_hynix_pipeline():
    target_keyword = "SK하이닉스"
    print("==================================================================")
    print(f"🚀 Starting SK Hynix News Preprocessing Pipeline (Audit Trail, Global & Focus)")
    print("==================================================================")
    
    config = load_config("filter_config_sk_hynix.yaml")
    await db.init_db()
    
    # 1. Fetch RAWDATA from articles table for SK Hynix
    async with aiosqlite.connect(DB_PATH) as conn:
        conn.row_factory = aiosqlite.Row
        async with conn.execute(
            "SELECT * FROM articles WHERE keyword = ? ORDER BY published_at DESC", 
            (target_keyword,)
        ) as cursor:
            raw_rows = await cursor.fetchall()
            
    total_raw = len(raw_rows)
    print(f"[*] Step 0: Loaded {total_raw} raw articles for [{target_keyword}] from [articles] table.")
    
    if total_raw == 0:
        print("[!] No articles found for SK Hynix. Please run crawl_sk_hynix.py first.")
        return
        
    cleaned_articles = []
    filtered_articles = []
    
    # Step 1 (Text Cleaning) & Step 2 (Rule Filtering)
    print("\n[*] Step 1 & 2: Executing Text Cleaning and Rule-Based First-Pass Filtering...")
    for idx, r in enumerate(raw_rows):
        raw_dict = dict(r)
        
        # 3.1 Text Cleaning
        cleaned_body, clean_audit = clean_text(raw_dict.get("body", ""), raw_dict.get("title", ""), raw_dict.get("media_name", ""))
        raw_dict["cleaned_body"] = cleaned_body
        raw_dict["clean_audit"] = clean_audit
        
        # 3.2 Rule Filtering
        passed, filter_reason, rule_audit = evaluate_rule_filter(
            raw_dict.get("title", ""),
            cleaned_body,
            config
        )
        raw_dict["rule_passed"] = passed
        raw_dict["rule_audit"] = rule_audit
        raw_dict["filter_reason"] = filter_reason
        
        if passed:
            cleaned_articles.append(raw_dict)
        else:
            raw_dict["status"] = "FILTERED"
            raw_dict["cluster_id"] = "FILTERED_OUT"
            raw_dict["value_score"] = 0.0
            raw_dict["final_decision"] = "FILTERED"
            raw_dict["final_reason"] = f"[규칙 필터 탈락] {filter_reason}"
            filtered_articles.append(raw_dict)
            
    print(f"  -> Passed Rule Filter: {len(cleaned_articles)} articles")
    print(f"  -> Filtered Out (Spam/Stock/Length): {len(filtered_articles)} articles")
    
    # Step 3: Morphological Candidate Pairs (Kiwi)
    if cleaned_articles:
        print("\n[*] Step 3: Extracting Kiwi Nouns/Numbers & Reducing Candidate Pairs...")
        candidate_pairs = generate_candidate_pairs(
            cleaned_articles, 
            min_jaccard=config.get("embedding_dedup", {}).get("min_jaccard_candidate", 0.04)
        )
        print(f"  -> Generated {len(candidate_pairs)} candidate pairs for deep embedding comparison.")
        
        # Step 4 & 5: Time Window + sBERT Embedding Deduplication
        print("\n[*] Step 4 & 5: Computing sBERT Cosine Similarities & Clustering...")
        clustered_articles = cluster_and_deduplicate(cleaned_articles, candidate_pairs, config)
        
        # Step 6: Value Scoring & Master Article Selection
        print("\n[*] Step 6: Calculating Informative Value Scores & Selecting Master Articles...")
        final_processed_articles = select_master_articles(clustered_articles, config)
        
        # Step 7: Promotional Detection
        print("\n[*] Step 7: Checking Promotional Patterns...")
        for art in final_processed_articles:
            promo_audit = evaluate_promotional(art)
            art["promo_audit"] = promo_audit
            if promo_audit["is_promotional"] and art["status"] == "MASTER":
                art["status"] = "PROMOTIONAL"
                art["final_decision"] = "PROMOTIONAL"
                art["final_reason"] = "[홍보성 의심] 이벤트/홍보성 패턴 다수 감지"
    else:
        final_processed_articles = []
            
    # Combine All Articles (Master + Duplicate + Filtered)
    all_final = final_processed_articles + filtered_articles
    
    # Step 8: Evaluate Global Investor Relevance & Company Focus for ALL Articles
    print("\n[*] Step 8: Evaluating Global Investor Relevance & Company Focus for ALL articles...")
    global_relevant_count = 0
    solo_focus_count = 0
    
    for art in all_final:
        # Global Relevance
        global_eval = evaluate_global_relevance(
            title=art.get("title", ""),
            body=art.get("cleaned_body", art.get("body", "")),
            keyword=target_keyword
        )
        art["global_eval"] = global_eval
        if global_eval.get("is_global_relevant"):
            global_relevant_count += 1
            
        # Company Focus
        focus_eval = evaluate_company_focus(
            title=art.get("title", ""),
            body=art.get("cleaned_body", art.get("body", "")),
            target_keyword=target_keyword
        )
        art["focus_eval"] = focus_eval
        if focus_eval.get("focus_type") == "EXCLUSIVE_SOLO":
            solo_focus_count += 1
            
    print(f"  -> 🌐 Global Relevant (글로벌 투자 유의미): {global_relevant_count}/{len(all_final)}건")
    print(f"  -> 🎯 Exclusive Solo Focus (단독 조명 기사): {solo_focus_count}/{len(all_final)}건")
    
    # Save to processed_articles with full Audit Trail in extra_meta
    print(f"\n[*] Step 9: Saving {len(all_final)} SK Hynix articles with Full Audit Trail to [processed_articles] table...")
    master_count = sum(1 for a in all_final if a.get("status") == "MASTER")
    duplicate_count = sum(1 for a in all_final if a.get("status") == "DUPLICATE")
    filtered_count = sum(1 for a in all_final if a.get("status") == "FILTERED")
    promo_count = sum(1 for a in all_final if a.get("status") == "PROMOTIONAL")
    
    for art in all_final:
        audit_trail = {
            "title": art.get("title"),
            "status": art.get("status"),
            "final_decision": art.get("final_decision"),
            "final_reason": art.get("final_reason"),
            "cluster_id": art.get("cluster_id"),
            "value_score": art.get("value_score", 0.0),
            "step1_clean": art.get("clean_audit"),
            "step2_rule_filter": art.get("rule_audit"),
            "step3_value_breakdown": art.get("value_score_details"),
            "step4_promo": art.get("promo_audit"),
            "global_eval": art.get("global_eval"),
            "focus_eval": art.get("focus_eval")
        }
        
        await db.save_processed_article(
            url=art["url"],
            title=art["title"],
            media_name=art.get("media_name", "알 수 없음"),
            journalist=art.get("journalist", "알 수 없음"),
            cleaned_body=art.get("cleaned_body", ""),
            keyword=target_keyword,
            published_at=art.get("published_at"),
            summary=art.get("final_reason"),
            category=art.get("status"),
            extra_meta=audit_trail
        )
        
    print(f"\n==================================================================")
    print(f"🎉 SK Hynix Preprocessing Pipeline Complete Summary:")
    print(f"   - 🌟 MASTER (최종 핵심 유효 기사): {master_count}건")
    print(f"   - 🎯 EXCLUSIVE SOLO (단독 조명 기사): {solo_focus_count}건")
    print(f"   - 🌐 GLOBAL RELEVANT (영어권 투자 유의미): {global_relevant_count}건")
    print(f"   - 📑 DUPLICATE (동일 사건 중복 기사): {duplicate_count}건")
    print(f"   - 🚫 FILTERED (단순시황/스팸/길이 미달): {filtered_count}건")
    print(f"   - TOTAL PROCESSED: {len(all_final)}건")
    print(f"==================================================================")

if __name__ == '__main__':
    asyncio.run(run_sk_hynix_pipeline())
