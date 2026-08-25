# extractor/site_extractor.py
import re
import os
import yaml
from urllib.parse import urlparse
from typing import Dict, Any, Optional
from bs4 import BeautifulSoup

class SiteExtractor:
    """
    Extracts article title, author, date, and body using publisher-specific rules (CSS selectors)
    from publisher_rules.yaml.
    """
    def __init__(self, rules_path: str = "publisher_rules.yaml"):
        self.rules_path = rules_path
        self.rules = self.load_rules(rules_path)

    def load_rules(self, rules_path: str) -> Dict[str, Any]:
        if os.path.exists(rules_path):
            try:
                with open(rules_path, "r", encoding="utf-8") as f:
                    data = yaml.safe_load(f) or {}
                    return data.get("publishers", {})
            except Exception:
                return {}
        return {}

    def get_domain(self, url: str) -> str:
        try:
            netloc = urlparse(url).netloc
            if netloc.startswith("www."):
                netloc = netloc[4:]
            return netloc.lower()
        except Exception:
            return ""

    def get_rule_for_url(self, url: str) -> Optional[Dict[str, Any]]:
        domain = self.get_domain(url)
        if not domain:
            return None
            
        if domain in self.rules:
            return self.rules[domain]
            
        for pub_domain, rule in self.rules.items():
            if domain == pub_domain or domain.endswith("." + pub_domain):
                return rule
        return None

    def extract(self, html: str, url: str = "") -> Optional[Dict[str, Any]]:
        rule = self.get_rule_for_url(url)
        if not rule or not html:
            return None

        try:
            soup = BeautifulSoup(html, "html.parser")
            
            # 1. Remove unwanted elements
            remove_selectors = rule.get("remove_selectors", [])
            for r_sel in remove_selectors:
                for el in soup.select(r_sel):
                    el.decompose()

            # 2. Extract Body
            article_selector = rule.get("article_selector", "")
            body_text = ""
            if article_selector:
                body_elem = soup.select_one(article_selector)
                if body_elem:
                    body_text = body_elem.get_text(separator="\n").strip()

            # 3. Extract Metadata
            date_selector = rule.get("date_selector", "")
            pub_date = ""
            if date_selector:
                d_elem = soup.select_one(date_selector)
                if d_elem:
                    pub_date = d_elem.get_text().strip()

            author_selector = rule.get("author_selector", "")
            author = ""
            if author_selector:
                a_elem = soup.select_one(author_selector)
                if a_elem:
                    author = a_elem.get_text().strip()

            if not body_text:
                return None

            return {
                "body": body_text,
                "length": len(body_text),
                "author": author,
                "published_at": pub_date,
                "domain": self.get_domain(url),
                "success": len(body_text) > 0
            }
        except Exception:
            return None
