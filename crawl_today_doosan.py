# crawl_today_doosan.py
import sys
import os
import asyncio
from datetime import datetime, timezone, timedelta
from email.utils import parsedate_to_datetime

if sys.stdout.encoding != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8')

sys.path.insert(0, r"d:\1_MyProject\6_NaverNewsCrawler")
import db
import scraper
import build_dashboard
from extractor.quality_scorer import calculate_quality_score
from preprocess_pipeline import run_pipeline

KEYWORD = '"두산에너빌리티"'

async def crawl_today():
    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Starting Today's (2026-08-25) Crawl for: {KEYWORD}")
    
    await db.init_db()
    crawler = scraper.NaverNewsCrawler()
    
    kst = timezone(timedelta(hours=9))
    today_start = datetime(2026, 8, 25, 0, 0, 0, tzinfo=kst)
    print(f"Filter Start Time: {today_start.strftime('%Y-%m-%d %H:%M:%S %Z')}")
    
    collected_items = []
    start = 1
    display = 100
    
    while start <= 1000:
        print(f"Fetching API search results (start={start}, display={display}, sort=date)...")
        items = await crawler.search_news_api_async(KEYWORD, limit=display, start=start, sort="date")
        
        if not items:
            print("No more items returned by API.")
            break
            
        print(f"  -> Received {len(items)} items from API.")
        reached_cutoff = False
        
        for item in items:
            pub_date_str = item.get("pubDate", "")
            if pub_date_str:
                try:
                    dt = parsedate_to_datetime(pub_date_str)
                    if dt < today_start:
                        print(f"  -> Reached article older than today: {dt.strftime('%Y-%m-%d %H:%M')}")
                        reached_cutoff = True
                        break
                except Exception as e:
                    pass
                    
            collected_items.append(item)
            
        if reached_cutoff or len(items) < display:
            break
            
        start += display
        await asyncio.sleep(0.3)
        
    print(f"\nTotal articles published today (2026-08-25): {len(collected_items)} items.")
    
    saved_count = 0
    
    for idx, item in enumerate(collected_items, 1):
        raw_url = item.get("link", "")
        orig_url = item.get("originallink", "")
        title = scraper.clean_html_text(item.get("title", ""))
        
        if scraper.is_naver_news_url(raw_url):
            target_url = raw_url.split("?")[0]
        else:
            target_url = orig_url or raw_url
            
        print(f"[{idx}/{len(collected_items)}] [PROCESSING] {title[:35]}...")
        
        article = await crawler.process_item_hybrid(item)
        
        final_url = article.get("url", target_url)
        final_title = article.get("title", title)
        final_media = article.get("media_name", "알 수 없음")
        final_journalist = article.get("journalist", "알 수 없음")
        final_body = article.get("body", "")
        final_pub = article.get("published_at") or scraper.parse_pub_date(item.get("pubDate", ""))
        
        score, score_detail = calculate_quality_score(final_body, "", final_title)
        needs_rev = score < 85
        mismatch = None
        if score == 0: mismatch = "Paywall / Block"
        elif score < 60: mismatch = f"Low Quality ({score})"
        elif needs_rev: mismatch = f"Moderate Quality ({score})"
        
        await db.save_extracted_article(
            url=final_url,
            title=final_title,
            publisher_domain=scraper.extract_domain_as_media(final_url),
            raw_html="",
            raw_html_hash="",
            extraction_method="hybrid_crawled_v1.1",
            chosen_text=final_body,
            quality_score=score,
            quality_score_detail=score_detail,
            needs_review=needs_rev,
            mismatch_reason=mismatch,
            media_name=final_media,
            journalist=final_journalist,
            published_at=final_pub,
            keyword="두산에너빌리티"
        )
        saved_count += 1
        print(f"    ✓ Saved: [{final_media}] {final_journalist} | Score: {score}점 ({'Clean' if not needs_rev else 'Review'}) | Body: {len(final_body)} chars")
        await asyncio.sleep(0.3)
        
    print(f"\n========================================================")
    print(f"Today's Crawl Finished: {saved_count} processed.")
    print(f"========================================================")
    
    print("\nRunning Preprocessing Pipeline for 두산에너빌리티...")
    await run_pipeline()
    
    print("\nRebuilding Web Dashboard...")
    build_dashboard.generate_dashboard("두산에너빌리티", "index.html")
    print("All tasks completed successfully!")

if __name__ == '__main__':
    asyncio.run(crawl_today())
