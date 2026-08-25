# crawl_sk_hynix.py
import sys
import os

if sys.stdout.encoding != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8')

sys.path.insert(0, r"d:\1_MyProject\6_NaverNewsCrawler")
import asyncio
from datetime import datetime, timezone, timedelta
from email.utils import parsedate_to_datetime
import db
import scraper

KEYWORD = '"SK하이닉스"'
KEYWORD_TAG = "SK하이닉스"
TARGET_DATE_STR = "2026-08-17" # 오늘 8월 17일

async def crawl_sk_hynix_today():
    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Starting Today's Crawl for: {KEYWORD} (Target Date: {TARGET_DATE_STR})")
    
    # 1. Initialize database
    await db.init_db()
    
    crawler = scraper.NaverNewsCrawler()
    
    # KST 기준 2026-08-17 00:00:00 ~ 23:59:59
    kst = timezone(timedelta(hours=9))
    target_date = datetime.strptime(TARGET_DATE_STR, "%Y-%m-%d").date()
    
    collected_items = []
    start = 1
    display = 100 # Maximum batch size per request
    
    # 2. Fetch all matching news from API across pages for today
    while start <= 1000:
        print(f"Fetching API search results (start={start}, display={display}, sort=date)...")
        items = await crawler.search_news_api_async(KEYWORD, limit=display, start=start, sort="date")
        
        if not items:
            print("No more items returned by API.")
            break
            
        print(f"  -> Received {len(items)} items from API.")
        reached_before_today = False
        
        for item in items:
            pub_date_str = item.get("pubDate", "")
            if pub_date_str:
                try:
                    dt = parsedate_to_datetime(pub_date_str)
                    dt_kst = dt.astimezone(kst)
                    item_date = dt_kst.date()
                    
                    if item_date < target_date:
                        print(f"  -> Reached article before target date: {dt_kst.strftime('%Y-%m-%d %H:%M')} (Title: {scraper.clean_html_text(item.get('title',''))[:20]}...)")
                        reached_before_today = True
                        break
                    elif item_date == target_date:
                        collected_items.append(item)
                    else:
                        # Future date (if any time mismatch)
                        collected_items.append(item)
                except Exception as e:
                    print(f"Date parse error: {e}")
                    collected_items.append(item)
            else:
                collected_items.append(item)
                
        if reached_before_today or len(items) < display:
            break
            
        start += display
        await asyncio.sleep(0.3)
        
    print(f"\nTotal articles for {KEYWORD} on {TARGET_DATE_STR}: {len(collected_items)} articles.")
    
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
            keyword=KEYWORD_TAG,
            published_at=final_pub
        )
        saved_count += 1
        print(f"    ✓ Saved: [{final_media}] {final_journalist} | Body: {len(final_body)} chars | Pub: {final_pub}")
        
        await asyncio.sleep(0.4)
        
    print(f"\n========================================================")
    print(f"SK Hynix Crawl Complete: {saved_count} newly saved, {skipped_count} skipped. Total: {len(collected_items)}")
    print(f"========================================================")

if __name__ == '__main__':
    asyncio.run(crawl_sk_hynix_today())
