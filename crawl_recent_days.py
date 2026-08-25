# crawl_recent_days.py
import sys
import os

if sys.stdout.encoding != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8')

sys.path.insert(0, r"d:\1_MyProject\6_NaverNewsCrawler")
import asyncio
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
import db
import scraper
import build_dashboard

KEYWORD = '"두산에너빌리티"'
DAYS_AGO = 3

async def crawl_keyword_recent_days():
    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Starting Recent {DAYS_AGO}-Day Crawl for: {KEYWORD}")
    
    # 1. Initialize database
    await db.init_db()
    
    crawler = scraper.NaverNewsCrawler()
    
    # Calculate cutoff time (3 days ago from now)
    now_utc = datetime.now(timezone.utc)
    cutoff_time = now_utc - timedelta(days=DAYS_AGO)
    print(f"Time threshold (Cutoff): {cutoff_time.strftime('%Y-%m-%d %H:%M:%S %Z')} ~ Now")
    
    collected_items = []
    start = 1
    display = 100 # Maximum batch size per request
    
    # 2. Fetch all matching news from API across pages until cutoff
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
                    if dt < cutoff_time:
                        print(f"  -> Reached article older than 3 days: {dt.strftime('%Y-%m-%d %H:%M')} (Title: {scraper.clean_html_text(item.get('title',''))[:20]}...)")
                        reached_cutoff = True
                        break
                except Exception:
                    pass
                    
            collected_items.append(item)
            
        if reached_cutoff or len(items) < display:
            break
            
        start += display
        await asyncio.sleep(0.3)
        
    print(f"\nTotal articles within the last {DAYS_AGO} days: {len(collected_items)}")
    
    # 3. Process & Scrape Full Body for all collected articles
    saved_count = 0
    skipped_count = 0
    
    for idx, item in enumerate(collected_items, 1):
        raw_url = item.get("link", "")
        orig_url = item.get("originallink", "")
        title = scraper.clean_html_text(item.get("title", ""))
        
        if scraper.is_naver_news_url(raw_url):
            target_url = raw_url.split("?")[0]
        else:
            target_url = orig_url or raw_url
            
        # Check duplicate
        if await db.is_crawled(target_url) or (orig_url and await db.is_crawled(orig_url)):
            skipped_count += 1
            print(f"[{idx}/{len(collected_items)}] [SKIP - Already Exists] {title[:30]}...")
            continue
            
        print(f"[{idx}/{len(collected_items)}] [CRAWLING] {title[:35]}...")
        
        article = await crawler.process_item_hybrid(item)
        
        final_url = article.get("url", target_url)
        final_title = article.get("title", title)
        final_media = article.get("media_name", "알 수 없음")
        final_journalist = article.get("journalist", "알 수 없음")
        final_body = article.get("body", "")
        final_pub = article.get("published_at") or scraper.parse_pub_date(item.get("pubDate", ""))
        
        await db.save_article(
            url=final_url,
            title=final_title,
            media_name=final_media,
            journalist=final_journalist,
            body=final_body or "본문 없음",
            keyword="두산에너빌리티",
            published_at=final_pub
        )
        saved_count += 1
        print(f"    ✓ Saved: [{final_media}] {final_journalist} | Body: {len(final_body)} chars | Pub: {final_pub}")
        
        # Brief pause to avoid aggressive crawling
        await asyncio.sleep(0.5)
        
    print(f"\n========================================================")
    print(f"Crawl Complete: {saved_count} newly saved, {skipped_count} skipped.")
    print(f"========================================================")
    
    # 4. Rebuild Web Dashboard
    build_dashboard.generate_dashboard()

if __name__ == '__main__':
    asyncio.run(crawl_keyword_recent_days())
