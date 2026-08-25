import sys
import json
import asyncio
import scraper

# Reconfigure console output to UTF-8 to prevent Windows terminal encoding errors
if sys.stdout.encoding != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8')

async def main():
    print("=== 1. Testing NAVER API HUB News Search ===")
    keyword = "인공지능"
    items = await scraper.fetch_news_via_api(keyword, limit=3, sort="date")
    print(f"Fetched {len(items)} items for '{keyword}'")
    
    if not items:
        print("❌ Failed to fetch items from API.")
        return
        
    print("\n=== 2. Testing Hybrid Article Processing ===")
    for i, item in enumerate(items, 1):
        print(f"\n--- Item #{i} ---")
        print(f"API Title: {scraper.clean_html_text(item.get('title'))}")
        print(f"API Link: {item.get('link')}")
        print(f"Original Link: {item.get('originallink')}")
        
        result = await scraper.scrape_article_hybrid(item)
        print(f"Result URL: {result['url']}")
        print(f"Result Media: {result['media_name']}")
        print(f"Result Journalist: {result['journalist']}")
        print(f"Result Body Preview: {result['body'][:100]}...")
        
    print("\n✅ Hybrid crawler test completed successfully!")

if __name__ == "__main__":
    asyncio.run(main())

