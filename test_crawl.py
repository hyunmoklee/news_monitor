import sys
import json
import asyncio
from crawl4ai import AsyncWebCrawler, CrawlerRunConfig, CacheMode
from crawl4ai.extraction_strategy import JsonCssExtractionStrategy

# Reconfigure console output to UTF-8 to prevent Windows terminal encoding errors
if sys.stdout.encoding != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8')

async def main():
    # Define the extraction schema targeting Naver News structure
    schema = {
        "name": "NaverNewsArticle",
        "baseSelector": "html",
        "fields": [
            {
                "name": "title",
                "selector": "#title_area span, .media_end_head_title",
                "type": "text"
            },
            {
                "name": "media_name",
                "selector": ".media_end_head_top_logo img",
                "type": "attribute",
                "attribute": "alt"
            },
            {
                "name": "journalist",
                "selector": ".media_end_head_journalist_name",
                "type": "text"
            },
            {
                "name": "body",
                "selector": "#newsct_article",
                "type": "text"
            }
        ]
    }
    
    extraction_strategy = JsonCssExtractionStrategy(schema, verbose=True)
    
    config = CrawlerRunConfig(
        cache_mode=CacheMode.BYPASS,
        extraction_strategy=extraction_strategy
    )
    
    async with AsyncWebCrawler() as crawler:
        result = await crawler.arun(
            url="https://n.news.naver.com/article/293/0000088007?cds=news_media_pc&type=editn",
            config=config
        )
        
        if result.success:
            data = json.loads(result.extracted_content)
            # Save the clean output to a JSON file
            with open("clean_result.json", "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=4)
            print("\nSuccessfully extracted structured data!")
            print(json.dumps(data, ensure_ascii=False, indent=4))
        else:
            print(f"Crawl failed: {result.error_message}")

if __name__ == "__main__":
    asyncio.run(main())
