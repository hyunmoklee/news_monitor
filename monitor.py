# monitor.py
import os
import asyncio
from datetime import datetime
from config import KEYWORDS, SEARCH_LIMIT, SEARCH_SORT, REPORT_DIR
import db
import scraper

async def run_monitoring():
    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Starting NAVER API HUB Hybrid News Monitoring...")
    
    # 1. Initialize database
    await db.init_db()
    
    scraped_articles = []
    
    # 2. Iterate through keywords
    for keyword in KEYWORDS:
        print(f"\n[KEYWORD: '{keyword}'] Querying NAVER API HUB (Sort: {SEARCH_SORT}, Limit: {SEARCH_LIMIT})...")
        items = await scraper.fetch_news_via_api(keyword, limit=SEARCH_LIMIT, sort=SEARCH_SORT)
        print(f"Found {len(items)} matching news items from API.")
        
        for item in items:
            raw_url = item.get("link", "")
            original_url = item.get("originallink", "")
            
            if scraper.is_naver_news_url(raw_url):
                target_url = raw_url.split("?")[0]
            else:
                target_url = original_url or raw_url
            
            if not target_url:
                continue

                
            # 3. Check for duplicates in SQLite
            if await db.is_crawled(target_url) or (original_url and await db.is_crawled(original_url)):
                print(f" -> Skipping (already crawled): {scraper.clean_html_text(item.get('title', ''))[:25]}...")
                continue
                
            print(f" -> Processing: {scraper.clean_html_text(item.get('title', ''))[:30]}...")
            
            # 4. Hybrid scraping (Crawl4AI for Naver News & External / API fallback)
            article = await scraper.scrape_article_hybrid(item)
            
            url = article["url"]
            title = article["title"]
            media_name = article["media_name"]
            journalist = article["journalist"]
            body = article["body"]
            
            if title and (body or url):
                # 5. Save to database
                await db.save_article(
                    url=url,
                    title=title,
                    media_name=media_name,
                    journalist=journalist,
                    body=body or "본문 없음",
                    keyword=keyword,
                    published_at=article.get("published_at") or article.get("pub_date")
                )

                
                scraped_articles.append({
                    "url": url,
                    "title": title,
                    "media_name": media_name,
                    "journalist": journalist,
                    "body": body,
                    "keyword": keyword,
                    "originallink": article.get("originallink", url),
                    "pub_date": article.get("pub_date", "")
                })
                print(f"    ✓ Successfully saved [{media_name}]: {title[:30]}...")


            else:
                print(f"    ✗ Failed to process item: {url}")
            
            # Short sleep to prevent rate spikes
            await asyncio.sleep(0.5)

    # 6. Generate report if any new articles were scraped
    if scraped_articles:
        generate_report(scraped_articles)
    else:
        print("\nNo new articles crawled today. Everything is up-to-date.")
        
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
        
    file_exists = os.path.exists(report_path) and os.path.getsize(report_path) > 0
    
    # Write report content
    with open(report_path, "a", encoding="utf-8") as f:
        # If it's a new file, add header
        if not file_exists:
            f.write(f"# 📰 Daily News Monitoring Report - {datetime.now().strftime('%Y-%m-%d')}\n\n")
            f.write("> 본 리포트는 NAVER API HUB와 하이브리드 크롤러에 의해 자동 생성되었습니다.\n\n---\n\n")
            
        for kw, items in grouped.items():
            f.write(f"## 🏷️ 키워드: {kw} (신규 수집: {len(items)}건)\n\n")
            for item in items:
                preview = (item['body'][:250].replace('\n', ' ') + "...") if item['body'] else "요약 없음"
                pub_info = f" | **발행일**: {item['pub_date']}" if item.get('pub_date') else ""
                f.write(f"### 📌 [{item['title']}]({item['url']})\n")
                f.write(f"- **언론사**: {item['media_name']} | **기자**: {item['journalist']}{pub_info}\n")
                if item.get('originallink') and item['originallink'] != item['url']:
                    f.write(f"- **원문 링크**: [원문 바로가기]({item['originallink']})\n")
                f.write(f"- **본문 요약**: {preview}\n\n")
            f.write("---\n\n")
            
    print(f"\n📝 Daily news report updated: '{report_filename}'")

