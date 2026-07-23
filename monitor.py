# monitor.py
import os
import asyncio
from datetime import datetime
from config import KEYWORDS, SEARCH_LIMIT, REPORT_DIR
import db
import scraper

async def run_monitoring():
    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Starting News Monitoring System...")
    
    # 1. Initialize database
    await db.init_db()
    
    scraped_articles = []
    
    # 2. Iterate through keywords
    for keyword in KEYWORDS:
        print(f"\n[KEYWORD: '{keyword}'] Fetching recent news links...")
        urls = await scraper.fetch_news_links(keyword, limit=SEARCH_LIMIT)
        print(f"Found {len(urls)} matching news links.")
        
        for url in urls:
            # 3. Check for duplicates
            if await db.is_crawled(url):
                print(f" -> Skipping (already crawled): {url}")
                continue
                
            print(f" -> Crawling new article: {url}")
            # 4. Scrape article details
            details = await scraper.scrape_article_details(url)
            
            title = details.get("title")
            media_name = details.get("media_name") or "알 수 없음"
            journalist = details.get("journalist") or "알 수 없음"
            body = details.get("body")
            
            if title and body:
                # Clean up extracted strings
                title = title.strip()
                media_name = media_name.strip()
                journalist = journalist.strip()
                body = body.strip()
                
                # 5. Save to database
                await db.save_article(
                    url=url,
                    title=title,
                    media_name=media_name,
                    journalist=journalist,
                    body=body,
                    keyword=keyword
                )
                
                scraped_articles.append({
                    "url": url,
                    "title": title,
                    "media_name": media_name,
                    "journalist": journalist,
                    "body": body,
                    "keyword": keyword
                })
                print(f"    ✓ Successfully scraped & saved: {title[:30]}...")
            else:
                print(f"    ✗ Failed to parse title or body for: {url}")
            
            # Short sleep to be polite to the server
            await asyncio.sleep(1)

    # 6. Generate report if any new articles were scraped
    if scraped_articles:
        generate_report(scraped_articles)
    else:
        print("\nNo new articles crawled. Skipping report generation.")
        
    print(f"\n[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] News Monitoring Finished.")

def generate_report(articles):
    today = datetime.now().strftime("%Y%m%d")
    report_filename = f"news_report_{today}.md"
    report_path = os.path.join(REPORT_DIR, report_filename)
    
    # Group articles by keyword
    grouped = {}
    for article in articles:
        kw = article["keyword"]
        if kw not in grouped:
            grouped[kw] = []
        grouped[kw].append(article)
        
    # Write report content
    with open(report_path, "a", encoding="utf-8") as f:
        # If it's a new file, add header
        if not os.path.exists(report_path) or os.path.getsize(report_path) == 0:
            f.write(f"# Daily News Monitoring Report - {datetime.now().strftime('%Y-%m-%d')}\n\n")
            
        for kw, items in grouped.items():
            f.write(f"## 🏷️ 키워드: {kw}\n\n")
            for item in items:
                preview = item['body'][:250].replace('\n', ' ') + "..."
                f.write(f"### 📰 [{item['title']}]({item['url']})\n")
                f.write(f"* **매체명**: {item['media_name']} | **기자**: {item['journalist']}\n")
                f.write(f"* **본문 요약**: {preview}\n\n")
            f.write("---\n\n")
            
    print(f"\n📝 Daily news report updated: '{report_filename}'")
