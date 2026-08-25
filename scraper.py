# scraper.py
import re
import json
import html
import asyncio
import urllib.parse
import urllib.request
from email.utils import parsedate_to_datetime
from typing import List, Dict, Any, Optional
from urllib.parse import urlparse
from bs4 import BeautifulSoup
from crawl4ai import AsyncWebCrawler, CrawlerRunConfig, CacheMode
from crawl4ai.extraction_strategy import JsonCssExtractionStrategy
from config import NAVER_CLIENT_ID, NAVER_CLIENT_SECRET, NAVER_NEWS_API_URL

# Naver News Specific Extraction Schema
NAVER_ARTICLE_SCHEMA = {
    "name": "NaverNewsArticle",
    "baseSelector": "html",
    "fields": [
        {
            "name": "title",
            "selector": "#title_area span, .media_end_head_title, h2#title_area",
            "type": "text"
        },
        {
            "name": "subtitle",
            "selector": "h4.media_end_head_subtitle, .media_end_head_sub_head, #newsct_article em.media_end_summary, .media_end_summary, .media_end_head_summary",
            "type": "text"
        },
        {
            "name": "media_name",
            "selector": ".media_end_head_top_logo img, .media_end_head_top_logo_text",
            "type": "attribute",
            "attribute": "alt"
        },
        {
            "name": "journalist_css",
            "selector": ".media_end_head_journalist_name, .byline_s, .byline, .journalist_name, em.media_end_head_journalist_name, .media_end_head_info_datestamp_byl, .c_journalist_name",
            "type": "text"
        },
        {
            "name": "body",
            "selector": "#newsct_article, #artice_body, #news_body_area",
            "type": "text"
        }
    ]
}

# Common CSS selectors for generic Korean news websites (prioritized by specificity)
GENERIC_BODY_SELECTORS = [
    "#article-view-content-div",
    "#articleBody",
    "div[itemprop='articleBody']",
    "#news_body_area",
    ".article-body",
    ".article_body",
    ".article_txt",
    "#article_body",
    "#news_body",
    "#artice_body",
    "div.news_cnt",
    "div.view_con",
    "div.article-content",
    "div[class*='article-content']",
    "div[class*='article-body']",
    "div.content_area",
    "div.story-news",
    "div.article_view"
]

INVALID_JOURNALIST_NAMES = {
    '전문', '시민', '취재', '객원', '수습', '사진', '영상', '인턴', '뉴스', '연합', 
    '금지', '배포', '무단', '재배포', '구독', '제보', '댓글', '출시', '기획', '특집', 
    '종합', '단독', '속보', '인터뷰', '연관', '오늘', '어제', '내일', '지난', '이번',
    '관련', '보도', '언론', '일보', '신문', '방송', '미디어', '통신', '경제', '사회', '정치', 
    '내용입력', '초읽기', '등록', '수정', '입력', '작성', '작성이', '작성일', '일자', '발행', '홈페이지', 
    '정렬', '추천', '인기', '설정', '설립', '선정', '설명', '검색', '안내', '공지', '소개', '주요', '전체',
    '그래픽', '헤드라인', '브리핑', '모음', '탐구', '인물', '원전', '핵심', '기자재', '부품', '공급', '계약', '제작', '수주', '사업',
    '하는', '되는', '있는', '없는', '보는', '주는', '원자로', '발전소', '에너지', '기술', '미국', '한국'
}


KOREAN_SURNAMES = {
    '김', '이', '박', '최', '정', '강', '조', '윤', '장', '임', '한', '오', '서', '신', '권', '황', '안', 
    '송', '류', '홍', '전', '고', '문', '손', '양', '배', '백', '허', '유', '남', '심', '노', '하', '곽', 
    '성', '차', '주', '우', '구', '라', '민', '진', '지', '엄', '채', '원', '천', '방', '공', '현', '함', 
    '변', '염', '추', '탁', '도', '표', '선', '여', '설', '마', '길', '옥', '육', '위', '나'
}

def parse_pub_date(pub_date_str: str) -> str:
    """Parses RFC 822/1123 pubDate string from Naver API to 'YYYY-MM-DD HH:MM' format."""
    if not pub_date_str:
        return ""
    try:
        dt = parsedate_to_datetime(pub_date_str)
        return dt.strftime("%Y-%m-%d %H:%M")
    except Exception:
        return pub_date_str

def clean_html_text(raw_text: str) -> str:
    """Removes HTML tags and unescapes HTML entities."""
    if not raw_text:
        return ""
    cleaned = re.sub(r'<[^>]+>', '', raw_text)
    cleaned = html.unescape(cleaned)
    return cleaned.strip()

def extract_domain_as_media(url: str) -> str:
    """Extracts a readable domain name from a URL as a fallback media name."""
    try:
        netloc = urlparse(url).netloc
        if netloc.startswith("www."):
            netloc = netloc[4:]
        return netloc or "언론사"
    except Exception:
        return "언론사"

def is_naver_news_url(url: str) -> bool:
    """Checks if a URL belongs to Naver News service."""
    return bool(url and "news.naver.com" in url and "article" in url)

def clean_final_journalist_name(raw_name: str) -> str:
    """
    Strictly standardizes journalist output to '홍길동 기자'.
    Removes email addresses, affiliation text, and brackets.
    """
    if not raw_name or raw_name in ["알 수 없음", "-", ""]:
        return "알 수 없음"
        
    # Remove email addresses and parenthesized content
    text = re.sub(r'\(?[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+\)?', '', raw_name)
    text = re.sub(r'[\(\)\[\]\{\}\<\>|]', ' ', text)
    text = re.sub(r'[a-zA-Z0-9]', ' ', text)
    
    matches = re.finditer(r'([가-힣]{2,10})\s*(?:기자|특파원|논설위원|CP|PD|에디터|위원)?', text)
    for m in matches:
        word = m.group(1).strip()
        candidates = []
        if len(word) > 3:
            candidates.append(word[-3:])
            candidates.append(word[-2:])
        else:
            candidates.append(word)
            
        for cand in candidates:
            if cand in INVALID_JOURNALIST_NAMES:
                continue
            if any(inv in cand for inv in ['금지', '배포', '무단', '제보', '구독', '사진', '댓글', '기사', '일보', '신문', '통신', '미디어', '이코노미', '연합', '원전', '핵심', '기자재']):
                continue
            if 2 <= len(cand) <= 3 and cand[0] in KOREAN_SURNAMES:
                return f"{cand} 기자"
                
    return "알 수 없음"

def extract_journalist_from_text(text: str, html_str: str = "") -> str:
    """
    Extracts journalist name safely from body text, title, or HTML metadata.
    Handles bracket/pipe prefixes like '[글로벌에픽 안재후 CP]', '|스마트투데이=나기천 기자|'
    """
    search_corpus = f"{html_str}\n{text}"
    
    # 0. JSON-LD / Meta Author extraction from HTML
    if html_str:
        try:
            soup = BeautifulSoup(html_str, "html.parser")
            for script in soup.find_all("script", type="application/ld+json"):
                try:
                    data = json.loads(script.string)
                    if isinstance(data, dict) and "author" in data:
                        auth = data["author"]
                        if isinstance(auth, dict) and "name" in auth:
                            res = clean_final_journalist_name(auth["name"])
                            if res != "알 수 없음":
                                return res
                        elif isinstance(auth, list) and len(auth) > 0:
                            res = clean_final_journalist_name(auth[0].get("name", ""))
                            if res != "알 수 없음":
                                return res
                except Exception:
                    pass
            for meta in soup.find_all("meta"):
                name = meta.get("name", "") or meta.get("property", "")
                if name.lower() in ["author", "dable:author", "article:author", "og:article:author"]:
                    res = clean_final_journalist_name(meta.get("content", ""))
                    if res != "알 수 없음":
                        return res
        except Exception:
            pass
            
    # 1. Pipe/Bracket header patterns: e.g. '|스마트투데이=나기천 기자|', '[글로벌에픽 안재후 CP]'
    pipe_m = re.findall(r'[|\[][^|\]]*?([가-힣]{2,3})\s*(?:기자|CP|PD|에디터|특파원|위원)[^|\]]*?[|\]]', search_corpus)
    for name in pipe_m:
        if name not in INVALID_JOURNALIST_NAMES and name[0] in KOREAN_SURNAMES:
            return f"{name} 기자"

    # 2. General 'XXX 기자/특파원/논설위원/CP/PD/에디터'
    matches = re.finditer(r'([가-힣]{2,10})\s*(기자|특파원|논설위원|CP|PD|에디터)', search_corpus)
    for m in matches:
        full_word = m.group(1).strip()
        candidates = []
        if len(full_word) > 3:
            candidates.append(full_word[-3:])
            candidates.append(full_word[-2:])
        else:
            candidates.append(full_word)
            
        for cand in candidates:
            if cand in INVALID_JOURNALIST_NAMES:
                continue
            if any(inv in cand for inv in ['금지', '배포', '무단', '제보', '구독', '사진', '댓글', '기사', '일보', '신문', '통신', '미디어', '포스트', '트리', '전문', '시민', '취재', '뉴스', '부모', '학생', '교사', '정렬', '추천', '원전', '핵심', '기자재']):
                continue
            if 2 <= len(cand) <= 3 and cand[0] in KOREAN_SURNAMES:
                return f"{cand} 기자"
                
    # 3. Look for '기자: 홍길동' or '글: 홍길동'
    matches2 = re.finditer(r'(?:기자|글|작성자|취재|편집)\s*[:=/\s]\s*([가-힣]{2,4})\b', search_corpus)
    for m in matches2:
        name = m.group(1).strip()
        if name in INVALID_JOURNALIST_NAMES or len(name) < 2 or len(name) > 3:
            continue
        if name[0] in KOREAN_SURNAMES and not any(inv in name for inv in ['금지', '배포', '무단', '제보']):
            return f"{name} 기자"
            
    return "알 수 없음"

def normalize_inline_breaks(text: str) -> str:
    """
    Fixes unnatural vertical line-breaks caused by inline tags (e.g. stock names like '삼성전자 \n\n 와 \n\n SK하이닉스').
    Re-attaches short floating words (<= 12 chars) into continuous sentences unless they look like real headers.
    """
    if not text:
        return ""
    
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    if not lines:
        return ""
        
    merged_lines = []
    current_para = []
    
    for line in lines:
        # If the line is a single short entity/word (e.g. "삼성전자", "와", "키움증권", "순이었습니다.")
        # and doesn't look like a formal title or bullet point, merge with current sentence
        is_short_fragment = len(line) <= 15 and not line.startswith(('#', '-', '*', '■', '▲', '[', '【'))
        ends_with_sentence = bool(re.search(r'[.?!\"\']$', line))
        
        if current_para and (is_short_fragment or not ends_with_sentence):
            # Check if previous line ended without sentence terminator or is a fragment
            prev_line = current_para[-1]
            if len(prev_line) < 25 or not re.search(r'[.?!\"\']$', prev_line):
                current_para[-1] = f"{prev_line} {line}".strip()
                continue
                
        current_para.append(line)
        
    return "\n\n".join(current_para)

def sanitize_body_text(text: str) -> str:
    """Cleans up raw crawled body text, removing redundant nav links, ads, and empty lines."""
    if not text:
        return ""
    
    # Filter out common noise markdown lines
    noise_patterns = [
        r'\[.*?바로가기\]\(.*?\)',
        r'\[.*?기사제보\]\(.*?\)',
        r'\[.*?저작권자.*?\]',
        r'\[.*?로그인.*?\]\(.*?\)',
        r'\[.*?로그아웃.*?\]\(.*?\)',
        r'\[.*?회원가입.*?\]\(.*?\)',
        r'\[.*?마이페이지.*?\]\(.*?\)',
        r'무단전재 및 재배포 금지',
        r'©.*?(?:무단전재|All rights reserved)',
        r'네이버에서.*?구독하세요',
        r'기자의 다른 기사 보기'
    ]
    
    cleaned = text
    for pat in noise_patterns:
        cleaned = re.sub(pat, '', cleaned, flags=re.IGNORECASE)
        
    cleaned = normalize_inline_breaks(cleaned)
    lines = [line.strip() for line in cleaned.splitlines() if line.strip()]
    cleaned = "\n\n".join(lines)
    cleaned = re.sub(r'\n{3,}', '\n\n', cleaned)
    return cleaned.strip()


def extract_full_title(soup: BeautifulSoup, fallback_title: str = "") -> str:
    """Extracts untruncated clean headline from HTML meta tags (og:title), h1, or title tag (strictly <= 120 chars)."""
    if not soup:
        return fallback_title
        
    def is_valid_headline(t: str) -> bool:
        if not t or len(t) < 5 or len(t) > 120:
            return False
        if t.endswith("...") or t.endswith("…"):
            return False
        if "/사진=" in t or "이미지 확대" in t or "기자]" in t or "무단전재" in t:
            return False
        return True

    # 1. Meta og:title / twitter:title (Most reliable standard)
    for meta in soup.find_all("meta"):
        prop = (meta.get("property", "") or meta.get("name", "")).lower()
        if prop in ["og:title", "twitter:title", "dable:title", "article:title"]:
            content = meta.get("content", "").strip()
            # Remove trailing media suffix (e.g. " - 한국금융신문", " | 연합뉴스")
            cleaned = re.sub(r'\s*[-|]\s*[가-힣A-Za-z0-9\s]+$', '', content)
            cleaned = html.unescape(cleaned).strip()
            if is_valid_headline(cleaned):
                return cleaned
                
    # 2. h1 tag (must be clean and short)
    for h1 in soup.find_all("h1"):
        text = h1.get_text().strip()
        cleaned = re.sub(r'\s*[-|]\s*[가-힣A-Za-z0-9\s]+$', '', text)
        cleaned = html.unescape(cleaned).strip()
        if is_valid_headline(cleaned):
            return cleaned
            
    # 3. title tag
    title_tag = soup.find("title")
    if title_tag:
        text = title_tag.get_text().strip()
        cleaned = re.sub(r'\s*[-|]\s*[가-힣A-Za-z0-9\s]+$', '', text)
        cleaned = html.unescape(cleaned).strip()
        if is_valid_headline(cleaned):
            return cleaned
            
    return fallback_title

class NaverNewsCrawler:
    """
    Reusable Naver News Crawler Module for any Python project.
    Combines NAVER API HUB for reliable discovery + Crawl4AI for rich full-content extraction.
    """
    def __init__(self, client_id: Optional[str] = None, client_secret: Optional[str] = None, api_url: Optional[str] = None):
        self.client_id = client_id or NAVER_CLIENT_ID
        self.client_secret = client_secret or NAVER_CLIENT_SECRET
        self.api_url = api_url or NAVER_NEWS_API_URL

    def search_news_api(self, keyword: str, limit: int = 10, start: int = 1, sort: str = "date") -> List[Dict[str, Any]]:
        """Synchronously queries NAVER API HUB for news items."""
        encoded_query = urllib.parse.quote(keyword)
        url = f"{self.api_url}?query={encoded_query}&display={limit}&start={start}&sort={sort}&format=json"
        
        headers = {
            "X-NCP-APIGW-API-KEY-ID": self.client_id,
            "X-NCP-APIGW-API-KEY": self.client_secret
        }
        
        req = urllib.request.Request(url, headers=headers)
        try:
            with urllib.request.urlopen(req, timeout=10) as response:
                if response.status == 200:
                    payload = json.loads(response.read().decode("utf-8"))
                    return payload.get("items", [])
                else:
                    print(f"[API ERROR] HTTP Status {response.status} for keyword '{keyword}'")
                    return []
        except urllib.error.HTTPError as e:
            error_body = e.read().decode("utf-8", errors="ignore")
            print(f"[API HTTPError] {e.code} for keyword '{keyword}': {error_body}")
            return []
        except Exception as e:
            print(f"[API Request Error] Failed for keyword '{keyword}': {e}")
            return []

    async def search_news_api_async(self, keyword: str, limit: int = 10, start: int = 1, sort: str = "date") -> List[Dict[str, Any]]:
        """Asynchronously queries NAVER API HUB for news items."""
        return await asyncio.to_thread(self.search_news_api, keyword, limit, start, sort)

    async def scrape_naver_news_details(self, url: str) -> Dict[str, Any]:
        """Crawls a single Naver News article and extracts structured details."""
        extraction_strategy = JsonCssExtractionStrategy(NAVER_ARTICLE_SCHEMA)
        config = CrawlerRunConfig(
            cache_mode=CacheMode.BYPASS,
            extraction_strategy=extraction_strategy,
            magic=True,
            wait_until='networkidle'
        )
        
        async with AsyncWebCrawler() as crawler:
            result = await crawler.arun(url=url, config=config)
            
            if not result.success:
                return {}
                
            data = {}
            try:
                extracted_data = json.loads(result.extracted_content)
                if isinstance(extracted_data, list) and len(extracted_data) > 0:
                    data = extracted_data[0]
                elif isinstance(extracted_data, dict):
                    data = extracted_data
            except Exception:
                pass
                
            raw_body = data.get("body", "")
            raw_journalist = data.get("journalist_css", "").strip()
            
            # Clean and standardize journalist name strictly
            journalist = clean_final_journalist_name(raw_journalist)
            
            if journalist in ["알 수 없음", ""]:
                found_journalist = extract_journalist_from_text(raw_body, result.html)
                if found_journalist != "알 수 없음":
                    journalist = clean_final_journalist_name(found_journalist)
                    
            data["journalist"] = journalist
            return data

    async def scrape_external_news_details(self, url: str) -> Dict[str, Any]:
        """
        3-Tier Ultra-Fast & Self-Healing News Extractor:
        1. Tier 1: Direct HTTP GET (0.2s) + Publisher Rules & Trafilatura (90% success)
        2. Tier 2: Lightweight Browser (domcontentloaded, 1~2s) for JS-rendered pages
        3. Tier 3: Self-Healing DOM Text-Density Analyzer (Auto-discovers new CSS selector and saves to YAML)
        """
        import httpx
        import trafilatura
        from extractor.site_extractor import SiteExtractor
        from extractor.rule_learner import discover_article_selector, auto_register_rule, extract_clean_domain
        
        domain = extract_clean_domain(url)
        site_extractor = SiteExtractor()
        
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7"
        }
        
        html_content = ""
        extracted_title = ""
        body = ""
        journalist = "알 수 없음"


        def decode_bytes(raw_bytes: bytes, default_enc: str = "utf-8") -> str:
            if not raw_bytes:
                return ""

            # 1. Try detecting charset from meta tag
            charset_match = re.search(rb'charset=[\"\']?([a-zA-Z0-9_-]+)', raw_bytes, re.IGNORECASE)
            detected_enc = charset_match.group(1).decode('ascii', errors='ignore') if charset_match else default_enc
            for enc in [detected_enc, 'utf-8', 'euc-kr', 'cp949']:
                if not enc:
                    continue
                try:
                    return raw_bytes.decode(enc)
                except Exception:
                    pass
            return raw_bytes.decode('utf-8', errors='replace')

        # === Tier 1: Fast Direct HTTP GET ===
        try:
            async with httpx.AsyncClient(timeout=8, follow_redirects=True, headers=headers, verify=False) as client:
                resp = await client.get(url)
                if resp.status_code == 200 and len(resp.content) > 200:
                    text_candidate = decode_bytes(resp.content, resp.encoding or "utf-8")
                    # Check for meta http-equiv="refresh" redirect (e.g. m.skyedaily.com -> www.skyedaily.com)
                    meta_refresh = re.search(r'<meta[^>]+http-equiv=["\']refresh["\'][^>]+content=["\'][^"\']*url=[\'"]?([^\'" >]+)', text_candidate, re.IGNORECASE)
                    if not meta_refresh:
                        meta_refresh = re.search(r'content=["\'][0-9]+;\s*url=[\'"]?([^\'" >]+)', text_candidate, re.IGNORECASE)
                    if meta_refresh:
                        redirect_target = meta_refresh.group(1).strip().strip("'\"")
                        if redirect_target.startswith("/"):
                            parsed_u = urlparse(url)
                            redirect_target = f"{parsed_u.scheme}://{parsed_u.netloc}{redirect_target}"
                        resp2 = await client.get(redirect_target)
                        if resp2.status_code == 200:
                            html_content = decode_bytes(resp2.content, resp2.encoding or "utf-8")
                            url = redirect_target
                            domain = extract_clean_domain(url)
                    else:
                        html_content = text_candidate
        except Exception:
            pass


        # === Tier 2: Crawl4AI with domcontentloaded if Direct HTTP was empty or blocked ===
        if not html_content or len(html_content) < 500:
            try:
                config = CrawlerRunConfig(
                    cache_mode=CacheMode.BYPASS,
                    wait_until='domcontentloaded',
                    page_timeout=12000,
                    magic=True
                )
                async with AsyncWebCrawler() as crawler:
                    result = await crawler.arun(url=url, config=config)
                    if result.success and result.html:
                        html_content = result.html
            except Exception:
                pass

        if not html_content:
            return {
                "title": "",
                "body": "[본문 수집 불가: 사이트 접속 실패/차단]",
                "journalist": "알 수 없음",
                "success": False
            }

        # Extract Title & Metadata from HTML
        try:
            soup = BeautifulSoup(html_content, "html.parser")
            extracted_title = extract_full_title(soup)
        except Exception:
            pass

        # === Extraction Step A: Publisher Rules (Exact CSS Selector) ===
        site_res = site_extractor.extract(html_content, url)
        if site_res and site_res.get("success") and len(site_res.get("body", "")) >= 150:
            body = site_res["body"]
            if site_res.get("author"):
                journalist = clean_final_journalist_name(site_res["author"])

        # === Extraction Step B: Trafilatura Precision ===
        if not body or len(body.strip()) < 150:
            try:
                traf_text = trafilatura.extract(
                    html_content,
                    include_comments=False,
                    include_tables=False,
                    favor_precision=True
                )
                if traf_text and len(traf_text.strip()) >= 150:
                    body = traf_text.strip()
            except Exception:
                pass

        # === Extraction Step C: Self-Healing DOM Text-Density Learner ===
        # If extraction is still too short or empty, automatically discover the best selector!
        if not body or len(body.strip()) < 150:
            learned = discover_article_selector(html_content)
            if learned:
                best_selector, learned_text = learned
                if len(learned_text) >= 200:
                    body = learned_text
                    # Save newly learned rule for future 0.01s extraction!
                    if domain:
                        auto_register_rule(domain, best_selector)

        # === Extraction Step D: Generic Selectors Fallback ===
        if not body or len(body.strip()) < 100:
            try:
                soup = BeautifulSoup(html_content, "html.parser")
                for selector in GENERIC_BODY_SELECTORS:
                    el = soup.select_one(selector)
                    if el:
                        text = el.get_text(separator="\n").strip()
                        if len(text) > 100:
                            body = text
                            break
            except Exception:
                pass

        # Extract journalist if not found
        if journalist in ["알 수 없음", ""]:
            found_j = extract_journalist_from_text(body, html_content)
            journalist = clean_final_journalist_name(found_j)

        cleaned_body = sanitize_body_text(body)
        if not cleaned_body or len(cleaned_body) < 80:
            cleaned_body = "[본문 수집 불가: 구조 파싱 실패/유료회원 전용]"

        return {
            "title": extracted_title,
            "body": cleaned_body,
            "journalist": journalist,
            "success": "[본문 수집 불가" not in cleaned_body
        }


    async def process_item_hybrid(self, item: Dict[str, Any]) -> Dict[str, Any]:
        """
        Comprehensive hybrid article processor:
        1. Checks Naver News in-link first for full body + journalist + media.
        2. If external link, crawls the original publisher page with full query params for full body + journalist.
        3. Merges subtitle and full body into a single comprehensive 'body' field.
        4. Runs regex extraction for journalist fallback across all sources.
        5. Standardizes all journalist names strictly as '홍길동 기자' (removing emails, affiliations, etc.).
        """
        api_title = clean_html_text(item.get("title", ""))
        api_desc = clean_html_text(item.get("description", ""))
        naver_link = item.get("link", "")
        original_link = item.get("originallink", "")
        pub_date = item.get("pubDate", "")
        
        # Primary URL for storage and deduplication
        if is_naver_news_url(naver_link):
            target_url = naver_link.split("?")[0]
        else:
            target_url = original_link or naver_link
            
        title = api_title
        media_name = "알 수 없음"
        journalist = "알 수 없음"
        body = api_desc
        
        # 1. Naver News In-Link Crawling
        if is_naver_news_url(naver_link):
            try:
                crawled = await self.scrape_naver_news_details(naver_link)
                if crawled:
                    if crawled.get("title"):
                        title = clean_html_text(crawled["title"])
                    if crawled.get("media_name"):
                        media_name = crawled["media_name"].strip()
                    if crawled.get("journalist") and crawled["journalist"] != "알 수 없음":
                        journalist = crawled["journalist"].strip()
                        
                    crawled_body = crawled.get("body", "").strip()
                    subtitle = clean_html_text(crawled.get("subtitle", ""))
                    
                    if crawled_body and len(crawled_body) > 30:
                        if subtitle and subtitle not in crawled_body:
                            body = f"[{subtitle}]\n\n{crawled_body}"
                        else:
                            body = crawled_body
            except Exception as e:
                print(f"    ⚠️ Naver News crawl failed on {naver_link}: {e}")
                
        # 2. External News Site Full Body Crawling (using full query params)
        crawl_url = original_link or (naver_link if not is_naver_news_url(naver_link) else "")
        if not is_naver_news_url(naver_link) and crawl_url:
            try:
                ext_crawled = await self.scrape_external_news_details(crawl_url)
                ext_title = (ext_crawled.get("title") or "").strip()
                if ext_title and (title.endswith("...") or title.endswith("…")):
                    if len(ext_title) <= 100 and "/사진=" not in ext_title and "이미지 확대" not in ext_title:
                        title = ext_title
                if ext_crawled.get("body"):
                    body = ext_crawled["body"]
                if ext_crawled.get("journalist") and ext_crawled["journalist"] != "알 수 없음" and journalist in ["알 수 없음", ""]:
                    journalist = ext_crawled["journalist"]
            except Exception as e:
                print(f"    ⚠️ External news crawl failed on {crawl_url}: {e}")
                body = "[본문 수집 불가: 크롤링 에러 발생]"
                
        # 3. Final fallback from body + description
        if journalist in ["알 수 없음", ""]:
            found = extract_journalist_from_text(f"{title}\n{body}")
            if found != "알 수 없음":
                journalist = found
                
        # 4. Standardize final journalist format strictly (e.g. '홍길동 기자')
        final_journalist = clean_final_journalist_name(journalist)
                
        # 5. Fallback media name if still unknown
        if media_name in ["알 수 없음", ""] and (original_link or target_url):
            media_name = extract_domain_as_media(original_link or target_url)
            
        # Format publication date
        published_at = parse_pub_date(pub_date)
        
        final_body = sanitize_body_text(body)
        if not final_body or len(final_body) < 50:
            final_body = "[본문 수집 불가: 내용 파싱 실패]"
            
        return {
            "url": target_url,
            "title": title,
            "media_name": media_name,
            "journalist": final_journalist,
            "body": final_body,
            "originallink": original_link or target_url,
            "pub_date": pub_date,
            "published_at": published_at
        }


    async def scrape_raw_html(self, url: str) -> Dict[str, Any]:
        """Crawls a URL using Crawl4AI and returns unadulterated raw HTML."""
        config = CrawlerRunConfig(cache_mode=CacheMode.BYPASS, magic=True, wait_until='networkidle')
        try:
            async with AsyncWebCrawler() as crawler:
                result = await crawler.arun(url=url, config=config)
                if not result.success:
                    return {"html": "", "success": False, "error": getattr(result, "error_message", "crawl_failed")}
                return {
                    "html": result.html or "",
                    "markdown": result.markdown or "",
                    "success": True
                }
        except Exception as e:
            return {"html": "", "success": False, "error": str(e)}

# Global crawler instance for backward compatibility
_default_crawler = NaverNewsCrawler()

async def fetch_news_via_api(keyword: str, limit: int = 5, sort: str = "date") -> List[Dict[str, Any]]:
    return await _default_crawler.search_news_api_async(keyword, limit=limit, sort=sort)

async def scrape_article_details(url: str) -> Dict[str, Any]:
    return await _default_crawler.scrape_naver_news_details(url)

async def scrape_article_hybrid(item: Dict[str, Any]) -> Dict[str, Any]:
    return await _default_crawler.process_item_hybrid(item)

async def scrape_raw_html(url: str) -> Dict[str, Any]:
    return await _default_crawler.scrape_raw_html(url)
