# extractor/rule_learner.py
"""
Auto Rule Learner & Self-Healing Module (Pure Python, No LLM)
Uses DOM Text-to-Tag Density Algorithm to discover the optimal article CSS selector
from raw HTML and automatically registers it into publisher_rules.yaml.
"""
import os
import re
import yaml
from typing import Optional, Dict, Any, Tuple
from urllib.parse import urlparse
from bs4 import BeautifulSoup, Tag

RULES_FILE = "publisher_rules.yaml"

def extract_clean_domain(url: str) -> str:
    try:
        netloc = urlparse(url).netloc
        if netloc.startswith("www."):
            netloc = netloc[4:]
        return netloc.lower()
    except Exception:
        return ""

def generate_css_selector(elem: Tag) -> str:
    """Generates a precise and clean CSS selector for a given BeautifulSoup element."""
    # 1. Prefer ID if valid and meaningful
    elem_id = elem.get("id")
    if elem_id and isinstance(elem_id, str) and not re.search(r'^\d|ad|banner|header|footer|nav|menu', elem_id, re.IGNORECASE):
        return f"#{elem_id}"

    # 2. Use classes
    classes = elem.get("class", [])
    if isinstance(classes, list) and classes:
        valid_classes = [c for c in classes if not re.search(r'ad|banner|widget|sidebar|nav|menu|container|wrap', c, re.IGNORECASE)]
        if valid_classes:
            tag_name = elem.name
            return f"{tag_name}.{valid_classes[0]}"

    # 3. Use itemprop
    itemprop = elem.get("itemprop")
    if itemprop:
        return f"{elem.name}[itemprop='{itemprop}']"

    # 4. Fallback: tag + parent context
    parent = elem.parent
    if parent and parent.get("id"):
        return f"#{parent.get('id')} {elem.name}"
        
    return elem.name

def discover_article_selector(html: str) -> Optional[Tuple[str, str]]:
    """
    Scans HTML using DOM Text-to-Tag Density to discover the best article container.
    Returns (selector, extracted_text).
    """
    if not html:
        return None

    try:
        soup = BeautifulSoup(html, "html.parser")

        # Strip noisy elements first
        for tag in soup(["script", "style", "nav", "header", "footer", "aside", "form", "button", "iframe", "noscript"]):
            tag.decompose()

        candidates = []
        
        # Target container candidate tags
        for elem in soup.find_all(["article", "section", "div", "main"]):
            # Ignore tiny elements or huge full-page wrappers
            elem_classes = " ".join(elem.get("class", []) if isinstance(elem.get("class"), list) else [])
            elem_id = elem.get("id", "") or ""
            
            # Skip obvious non-content containers
            if re.search(r'comment|reply|footer|header|sidebar|gnb|lnb|popup|modal|banner|advert', f"{elem_classes} {elem_id}", re.IGNORECASE):
                continue

            text = elem.get_text(separator=" ").strip()
            text_len = len(text)
            
            if text_len < 200:
                continue

            # Calculate Density Signals
            kr_chars = len(re.findall(r'[가-힣]', text))
            kr_ratio = kr_chars / max(text_len, 1)
            
            # Skip if low Korean ratio
            if kr_ratio < 0.4:
                continue

            # Link text penalty
            links = elem.find_all("a")
            link_text_len = sum(len(a.get_text()) for a in links)
            link_ratio = link_text_len / max(text_len, 1)

            # Paragraph count bonus
            p_count = len(elem.find_all("p"))
            
            # DOM Depth (Penalize body or root wrapper)
            tag_count = len(elem.find_all())
            
            # Score formula: High Korean text, Low link density, Low tag count compared to text
            score = (kr_chars * (1.0 - link_ratio)) / max(tag_count * 0.5, 1.0)
            if p_count >= 2:
                score *= 1.3

            selector = generate_css_selector(elem)
            clean_body = elem.get_text(separator="\n").strip()
            candidates.append((score, selector, clean_body, text_len))

        if not candidates:
            return None

        # Pick candidate with highest score
        candidates.sort(key=lambda x: -x[0])
        best_score, best_selector, best_text, best_len = candidates[0]

        # Verify selector
        if best_len >= 250 and best_selector:
            return best_selector, best_text

        return None
    except Exception as e:
        print(f"[RuleLearner Error] {e}")
        return None

def auto_register_rule(domain: str, article_selector: str, remove_selectors: Optional[list] = None) -> bool:
    """Saves newly discovered selector to publisher_rules.yaml."""
    if not domain or not article_selector:
        return False

    if remove_selectors is None:
        remove_selectors = [".ad", ".ad-box", ".banner", ".related-news", ".sns-share", ".reporter-card", ".copyright"]

    data = {}
    if os.path.exists(RULES_FILE):
        try:
            with open(RULES_FILE, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f) or {}
        except Exception:
            data = {}

    publishers = data.setdefault("publishers", {})
    
    # If already exists and identical, skip
    if domain in publishers and publishers[domain].get("article_selector") == article_selector:
        return True

    publishers[domain] = {
        "article_selector": article_selector,
        "remove_selectors": remove_selectors,
        "notes": "Auto-discovered by Self-Learning DOM Density Engine"
    }

    try:
        with open(RULES_FILE, "w", encoding="utf-8") as f:
            yaml.dump(data, f, allow_unicode=True, default_flow_style=False, sort_keys=False)
        print(f"    ✨ [AUTO-LEARNED RULE] Successfully registered '{article_selector}' for domain '{domain}'")
        return True
    except Exception as e:
        print(f"[RuleLearner Save Error] {e}")
        return False
