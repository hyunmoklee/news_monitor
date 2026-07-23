# scraper.py
import json
import urllib.parse
from typing import List, Dict, Any
from crawl4ai import AsyncWebCrawler, CrawlerRunConfig, CacheMode
from crawl4ai.extraction_strategy import JsonCssExtractionStrategy

# Define the CSS extraction schema for Naver News article details
ARTICLE_SCHEMA = {
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

async def fetch_news_links(keyword: str, limit: int = 5) -> List[str]:
    """Searches Naver News for the keyword and returns a list of Naver News article URLs."""
    encoded_keyword = urllib.parse.quote(keyword)
    search_url = f"https://search.naver.com/search.naver?where=news&query={encoded_keyword}"
    
    # We bypass cache to get the latest search results
    config = CrawlerRunConfig(cache_mode=CacheMode.BYPASS)
    
    async with AsyncWebCrawler() as crawler:
        result = await crawler.arun(url=search_url, config=config)
        
        if not result.success:
            print(f"Failed to fetch search results for keyword '{keyword}': {result.error_message}")
            return []
            
        links = []
        # Find all external links matching Naver News pattern
        for link_type in ["external", "internal"]:
            for link_obj in result.links.get(link_type, []):
                href = link_obj.get("href", "")
                # Match both n.news.naver.com/article and n.news.naver.com/mnews/article
                if "news.naver.com" in href and "article" in href:
                    # Clean up URL parameters (like ?sid=... or ?cds=...)
                    clean_url = href.split("?")[0]
                    if clean_url not in links:
                        links.append(clean_url)
                        if len(links) >= limit:
                            break
            if len(links) >= limit:
                break
                
        return links

async def scrape_article_details(url: str) -> Dict[str, Any]:
    """Crawls a single Naver News article and extracts structured details."""
    extraction_strategy = JsonCssExtractionStrategy(ARTICLE_SCHEMA)
    config = CrawlerRunConfig(
        cache_mode=CacheMode.BYPASS,
        extraction_strategy=extraction_strategy
    )
    
    async with AsyncWebCrawler() as crawler:
        result = await crawler.arun(url=url, config=config)
        
        if not result.success:
            print(f"Failed to scrape article {url}: {result.error_message}")
            return {}
            
        try:
            extracted_data = json.loads(result.extracted_content)
            if isinstance(extracted_data, list) and len(extracted_data) > 0:
                return extracted_data[0]
            elif isinstance(extracted_data, dict):
                return extracted_data
        except Exception as e:
            print(f"Error parsing extracted content for {url}: {e}")
            
        return {}
