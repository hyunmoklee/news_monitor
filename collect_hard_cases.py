# collect_hard_cases.py
"""
Hard Case Collection Script
Queries articles with quality_score < 60, needs_review = 1, or unrated articles,
categorizes them into 6 benchmark categories, and exports them to the hard_cases/ directory.
"""
import os
import sys
import json
import asyncio
import aiosqlite
from datetime import datetime
from config import DB_PATH, HARD_CASES_DIR

if sys.stdout.encoding != 'utf-8':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

def categorize_hard_case(row: dict) -> str:
    """Classifies the hard case into one of the 6 benchmark categories."""
    mismatch = row.get("mismatch_reason") or ""
    body = row.get("chosen_text") or row.get("body") or ""
    score_detail = {}
    try:
        score_detail = json.loads(row.get("quality_score_detail") or "{}")
    except Exception:
        pass

    if len(body.strip()) < 100:
        return "empty_or_too_short"
    if "length mismatch" in mismatch:
        return "mismatch_or_truncated"
    if score_detail.get("boilerplate_penalty", 0) < 0:
        return "ads_and_boilerplate_mixed"
    if score_detail.get("repeated_sentences_penalty", 0) < 0:
        return "repeated_noise"
    if score_detail.get("short_paragraph_penalty", 0) < 0:
        return "caption_or_fragments"
    return "general_low_quality"

async def collect_hard_cases():
    os.makedirs(HARD_CASES_DIR, exist_ok=True)
    
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("""
            SELECT * FROM articles 
            WHERE needs_review = 1 OR quality_score < 60 OR quality_score IS NULL
            ORDER BY created_at DESC
        """) as cursor:
            rows = await cursor.fetchall()

    print(f"[*] Found {len(rows)} candidate hard case articles in database.")
    
    dataset = []
    category_counts = {}

    for r in rows:
        item = dict(r)
        cat = categorize_hard_case(item)
        item["hard_case_category"] = cat
        category_counts[cat] = category_counts.get(cat, 0) + 1
        
        dataset.append({
            "url": item.get("url"),
            "title": item.get("title"),
            "publisher_domain": item.get("publisher_domain"),
            "hard_case_category": cat,
            "quality_score": item.get("quality_score"),
            "quality_score_detail": item.get("quality_score_detail"),
            "extraction_method": item.get("extraction_method"),
            "mismatch_reason": item.get("mismatch_reason"),
            "chosen_text": item.get("chosen_text") or item.get("body"),
            "has_raw_html": bool(item.get("raw_html")),
            "created_at": item.get("created_at")
        })

    today = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_json = os.path.join(HARD_CASES_DIR, f"hard_cases_{today}.json")
    
    with open(out_json, "w", encoding="utf-8") as f:
        json.dump(dataset, f, ensure_ascii=False, indent=2)

    print(f"\n✅ Exported {len(dataset)} hard cases to: {out_json}")
    print("\n📊 Hard Case Category Distribution:")
    for cat, count in category_counts.items():
        print(f"  - {cat}: {count}건")

if __name__ == "__main__":
    asyncio.run(collect_hard_cases())
