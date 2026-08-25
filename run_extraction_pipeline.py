# run_extraction_pipeline.py
"""
End-to-End News Extraction and Monitoring Pipeline.
Runs Discovery -> Crawl4AI Raw HTML -> Trafilatura Dual Extraction ->
Site Selector -> Quality Scoring -> Validation -> LLM Cleaner (Optional) -> Storage.
"""
import os
import sys
import asyncio
import hashlib
from datetime import datetime
from urllib.parse import urlparse

if sys.stdout.encoding != 'utf-8':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

import db
import scraper
from config import KEYWORDS, SEARCH_LIMIT, SEARCH_SORT, PIPELINE_VERSION, GEMINI_API_KEY, DEFAULT_GEMINI_MODEL
from extractor import (
    extract_with_trafilatura,
    calculate_quality_score,
    SiteExtractor,
    validate_candidates,
    clean_with_gemini
)

async def run_pipeline(keyword: str = '"두산에너빌리티"', limit: int = 5):
    print("=" * 70)
    print(f"🚀 Starting News Extraction Pipeline ({PIPELINE_VERSION})")
    print(f"   Keyword: {keyword} | Limit: {limit} | Sort: {SEARCH_SORT}")
    print("=" * 70)

    await db.init_db()
    site_extractor = SiteExtractor()
    
    # 1. API Discovery
    items = await scraper.fetch_news_via_api(keyword, limit=limit, sort=SEARCH_SORT)
    print(f"[*] Fetched {len(items)} news items from NAVER API HUB.")

    stats = {
        "total": len(items),
        "saved": 0,
        "needs_review": 0,
        "methods": {},
        "scores": [],
        "llm_calls": 0,
        "total_cost_usd": 0.0
    }

    for idx, item in enumerate(items, 1):
        raw_url = item.get("link", "")
        orig_url = item.get("originallink", "")
        title = scraper.clean_html_text(item.get("title", ""))
        
        target_url = orig_url or raw_url
        if scraper.is_naver_news_url(raw_url):
            target_url = raw_url.split("?")[0]

        pub_domain = urlparse(target_url).netloc.replace("www.", "")
        print(f"\n[{idx}/{len(items)}] Processing: {title[:35]}... ({pub_domain})")

        # 2. Crawl Raw HTML using Crawl4AI
        crawl_result = await scraper.scrape_raw_html(target_url)
        raw_html = crawl_result.get("html", "")
        if not raw_html:
            print("  ⚠️ Failed to fetch raw HTML.")
            continue

        raw_html_hash = hashlib.sha256(raw_html.encode("utf-8")).hexdigest()

        # 3. Trafilatura Dual Extraction (Standard & Precision)
        traf_res = extract_with_trafilatura(raw_html, url=target_url)
        std_data = traf_res.get("standard", {})
        prec_data = traf_res.get("precision", {})

        # 4. Quality Scoring for Trafilatura Candidates
        std_score, std_detail = calculate_quality_score(std_data.get("text", ""), raw_html, title)
        prec_score, prec_detail = calculate_quality_score(prec_data.get("text", ""), raw_html, title)

        # 5. Publisher Rule / Site Selector Extraction
        selector_res = site_extractor.extract(raw_html, target_url)
        selector_score = 0
        if selector_res and selector_res.get("success"):
            selector_score, _ = calculate_quality_score(selector_res.get("body", ""), raw_html, title)

        # 6. Candidate Validation & Mismatch Detection
        val_result = validate_candidates(
            selector_result=selector_res,
            trafilatura_std=std_data,
            trafilatura_prec=prec_data,
            std_score=std_score,
            prec_score=prec_score,
            selector_score=selector_score,
            threshold_ratio=0.3
        )

        chosen_method = val_result["chosen_method"]
        chosen_text = val_result["chosen_text"]
        quality_score = val_result["quality_score"]
        needs_review = val_result["needs_review"]
        mismatch_reason = val_result["mismatch_reason"]

        # 7. Optional LLM Fallback (Gemini Cleaner) if needs_review and API key is present
        if needs_review and GEMINI_API_KEY:
            print("  🤖 Triggering Gemini LLM Cleaner fallback...")
            llm_res = clean_with_gemini(chosen_text, api_key=GEMINI_API_KEY, model_name=DEFAULT_GEMINI_MODEL)
            if llm_res.get("success") and not llm_res.get("safety_triggered"):
                chosen_text = llm_res.get("cleaned_text")
                chosen_method = "llm_cleaned"
                needs_review = False
                stats["llm_calls"] += 1
                stats["total_cost_usd"] += llm_res.get("cost_usd", 0.0)

        # 8. Save to Database
        await db.save_extracted_article(
            url=target_url,
            title=title,
            publisher_domain=pub_domain,
            raw_html=raw_html,
            raw_html_hash=raw_html_hash,
            extraction_method=chosen_method,
            chosen_text=chosen_text,
            quality_score=quality_score,
            quality_score_detail=std_detail if "standard" in chosen_method else prec_detail,
            needs_review=needs_review,
            mismatch_reason=mismatch_reason,
            published_at=scraper.parse_pub_date(item.get("pubDate", "")),
            keyword=keyword
        )

        stats["saved"] += 1
        stats["scores"].append(quality_score)
        stats["methods"][chosen_method] = stats["methods"].get(chosen_method, 0) + 1
        if needs_review:
            stats["needs_review"] += 1

        status_tag = "⚠️ NEEDS_REVIEW" if needs_review else "✓ CLEAN"
        print(f"  [{status_tag}] Method: {chosen_method} | Score: {quality_score} | Length: {len(chosen_text)} chars")

    # Summary Report
    avg_score = round(sum(stats["scores"]) / len(stats["scores"]), 1) if stats["scores"] else 0.0
    print("\n" + "=" * 70)
    print("📊 Extraction Pipeline Execution Summary")
    print(f"  - Total Processed: {stats['saved']}/{stats['total']}")
    print(f"  - Needs Review Count: {stats['needs_review']} ({round(stats['needs_review']/max(stats['saved'],1)*100, 1)}%)")
    print(f"  - Average Quality Score: {avg_score}")
    print(f"  - Extraction Methods: {stats['methods']}")
    print(f"  - LLM Cleaner Calls: {stats['llm_calls']} (Est. Cost: ${stats['total_cost_usd']:.5f})")
    print("=" * 70)

if __name__ == "__main__":
    asyncio.run(run_pipeline())
