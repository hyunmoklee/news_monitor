# extractor/quality_scorer.py
import re
import yaml
import os
from typing import Dict, Any, Tuple, Optional
from bs4 import BeautifulSoup

def load_scoring_config(config_path: str = "scoring_config.yaml") -> Dict[str, Any]:
    """Loads quality scoring configuration from YAML."""
    if os.path.exists(config_path):
        with open(config_path, "r", encoding="utf-8") as f:
            return yaml.safe_load(f) or {}
    return {
        "positive_signals": {
            "reasonable_length": {"weight": 20, "min_chars": 200, "max_chars": 20000},
            "paragraph_count": {"weight": 15, "min_paragraphs": 2},
            "low_link_density": {"weight": 20, "max_link_char_ratio": 0.15},
            "title_body_overlap": {"weight": 15, "min_overlap_ratio": 0.2},
            "dom_article_tag_match": {"weight": 15},
            "korean_char_ratio": {"weight": 15, "min_ratio": 0.6}
        },
        "negative_signals": {
            "boilerplate_keywords": {
                "weight": -20,
                "keywords": ["관련기사", "많이 본 뉴스", "추천기사", "무단전재", "재배포 금지", "저작권자", "구독", "댓글", "협찬", "제휴"]
            },
            "repeated_sentences": {"weight": -15},
            "excessive_short_paragraphs": {"weight": -10, "max_ratio": 0.4, "short_char_threshold": 20}
        },
        "thresholds": {
            "high_confidence": 85,
            "low_confidence": 60
        }
    }

def calculate_quality_score(
    text: str,
    html: str = "",
    title: str = "",
    config: Optional[Dict[str, Any]] = None
) -> Tuple[int, Dict[str, Any]]:
    """
    Pure function to evaluate rule-based quality score (0 to 100) and details.
    """
    if config is None:
        config = load_scoring_config()

    pos_cfg = config.get("positive_signals", {})
    neg_cfg = config.get("negative_signals", {})
    
    clean_text = (text or "").strip()
    char_len = len(clean_text)
    
    if char_len == 0:
        return 0, {"base_score": 0, "total_score": 0, "reason": "empty_text"}
        
    score = 0
    detail = {}

    # 1. Positive Signal: Reasonable Length
    p_len_cfg = pos_cfg.get("reasonable_length", {})
    min_c = p_len_cfg.get("min_chars", 200)
    max_c = p_len_cfg.get("max_chars", 20000)
    w_len = p_len_cfg.get("weight", 15)
    if min_c <= char_len <= max_c:
        score += w_len
        detail["reasonable_length"] = w_len
    elif char_len > max_c:
        detail["reasonable_length"] = int(w_len * 0.5)
        score += detail["reasonable_length"]
    else:
        detail["reasonable_length"] = 0

    # 2. Positive Signal: Paragraph Count
    paragraphs = [p.strip() for p in clean_text.splitlines() if p.strip()]
    p_cnt_cfg = pos_cfg.get("paragraph_count", {})
    min_p = p_cnt_cfg.get("min_paragraphs", 2)
    w_p = p_cnt_cfg.get("weight", 10)
    if len(paragraphs) >= min_p:
        score += w_p
        detail["paragraph_count"] = w_p
    else:
        detail["paragraph_count"] = 0

    # 3. Positive Signal: Low Link Density
    p_link_cfg = pos_cfg.get("low_link_density", {})
    max_link_ratio = p_link_cfg.get("max_link_char_ratio", 0.15)
    w_link = p_link_cfg.get("weight", 15)
    link_ratio = 0.0
    if html:
        try:
            soup = BeautifulSoup(html, "html.parser")
            total_text_len = len(soup.get_text()) or 1
            link_text_len = sum(len(a.get_text()) for a in soup.find_all("a"))
            link_ratio = link_text_len / total_text_len
        except Exception:
            link_ratio = 0.0
    else:
        # Estimate markdown links
        md_links = re.findall(r'\[([^\]]+)\]\([^\)]+\)', clean_text)
        link_chars = sum(len(m) for m in md_links)
        link_ratio = link_chars / max(char_len, 1)

    if link_ratio <= max_link_ratio:
        score += w_link
        detail["low_link_density"] = w_link
    else:
        detail["low_link_density"] = 0
    detail["link_ratio"] = round(link_ratio, 3)

    # 4. Positive Signal: Title-Body Overlap
    p_title_cfg = pos_cfg.get("title_body_overlap", {})
    w_title = p_title_cfg.get("weight", 10)
    min_overlap = p_title_cfg.get("min_overlap_ratio", 0.2)
    if title:
        title_tokens = set(re.findall(r'[가-힣a-zA-Z0-9]{2,}', title))
        if title_tokens:
            matched_tokens = [t for t in title_tokens if t in clean_text]
            overlap_ratio = len(matched_tokens) / len(title_tokens)
            if overlap_ratio >= min_overlap:
                score += w_title
                detail["title_body_overlap"] = w_title
            else:
                detail["title_body_overlap"] = 0
            detail["title_overlap_ratio"] = round(overlap_ratio, 2)
        else:
            score += w_title
            detail["title_body_overlap"] = w_title
    else:
        score += int(w_title * 0.5)
        detail["title_body_overlap"] = int(w_title * 0.5)

    # 5. Positive Signal: DOM Article Tag Match
    p_dom_cfg = pos_cfg.get("dom_article_tag_match", {})
    w_dom = p_dom_cfg.get("weight", 15)
    if html:
        has_article_tag = bool(re.search(r'<(article|main)\b|id=["\'](?:article|newsct|content)["\']|class=["\'][^"\']*(?:article-body|news_body|story-news)[^"\']*["\']', html, re.IGNORECASE))
        if has_article_tag:
            score += w_dom
            detail["dom_article_tag_match"] = w_dom
        else:
            detail["dom_article_tag_match"] = 0
    else:
        score += int(w_dom * 0.5)
        detail["dom_article_tag_match"] = int(w_dom * 0.5)

    # 6. Positive Signal: Korean Character Ratio
    p_kr_cfg = pos_cfg.get("korean_char_ratio", {})
    min_kr = p_kr_cfg.get("min_ratio", 0.6)
    w_kr = p_kr_cfg.get("weight", 10)
    kr_chars = len(re.findall(r'[가-힣]', clean_text))
    non_space_chars = len(re.findall(r'\S', clean_text)) or 1
    kr_ratio = kr_chars / non_space_chars
    detail["korean_char_ratio"] = round(kr_ratio, 2)
    if kr_ratio >= min_kr:
        score += w_kr
        detail["korean_char_signal"] = w_kr
    else:
        detail["korean_char_signal"] = 0

    # 7. Negative Signal: Boilerplate Keywords
    n_bp_cfg = neg_cfg.get("boilerplate_keywords", {})
    bp_keywords = n_bp_cfg.get("keywords", [])
    w_bp = n_bp_cfg.get("weight", -20)
    bp_hits = 0
    affected_paragraphs = 0
    for p in paragraphs:
        p_hit = [kw for kw in bp_keywords if kw in p]
        if p_hit:
            bp_hits += len(p_hit)
            affected_paragraphs += 1
    
    para_len = max(len(paragraphs), 1)
    affected_ratio = affected_paragraphs / para_len
    if affected_ratio > 0:
        penalty = int(w_bp * min(affected_ratio * 1.5, 1.0))
        score += penalty
        detail["boilerplate_penalty"] = penalty
    else:
        detail["boilerplate_penalty"] = 0
    detail["boilerplate_hits"] = bp_hits

    # 8. Negative Signal: Repeated Sentences
    n_rep_cfg = neg_cfg.get("repeated_sentences", {})
    w_rep = n_rep_cfg.get("weight", -15)
    sentences = [s.strip() for s in re.split(r'[.!?]\s+|\n+', clean_text) if len(s.strip()) > 15]
    if len(sentences) >= 4:
        seen = set()
        duplicates = 0
        for s in sentences:
            if s in seen:
                duplicates += 1
            seen.add(s)
        dup_ratio = duplicates / len(sentences)
        if dup_ratio > 0.15:
            penalty = int(w_rep * min(dup_ratio * 2.0, 1.0))
            score += penalty
            detail["repeated_sentences_penalty"] = penalty
        else:
            detail["repeated_sentences_penalty"] = 0
    else:
        detail["repeated_sentences_penalty"] = 0

    # 9. Negative Signal: Excessive Short Paragraphs
    n_short_cfg = neg_cfg.get("excessive_short_paragraphs", {})
    w_short = n_short_cfg.get("weight", -10)
    max_short_ratio = n_short_cfg.get("max_ratio", 0.4)
    short_thresh = n_short_cfg.get("short_char_threshold", 20)
    if len(paragraphs) >= 3:
        short_count = sum(1 for p in paragraphs if len(p) < short_thresh)
        short_ratio = short_count / len(paragraphs)
        detail["short_paragraph_ratio"] = round(short_ratio, 2)
        if short_ratio > max_short_ratio:
            score += w_short
            detail["short_paragraph_penalty"] = w_short
        else:
            detail["short_paragraph_penalty"] = 0
    else:
        detail["short_paragraph_penalty"] = 0

    # === NEW: Hard Drop for Paywall / Block (Case 2) ===
    paywall_keywords = ["로그인 해주세요", "유료회원 전용", "보안프로그램이 미설치", "서비스 결제 후 확인", "가입 후 이용", "본문 접속이 차단"]
    for kw in paywall_keywords:
        if kw in clean_text:
            return 0, {"reason": "paywall_or_block", "total_score": 0, "matched_keyword": kw}

    # === NEW: Ending Validation for Truncation (Case 3) ===
    # Relaxed validation: Check the last 300 characters to tolerate appended SNS links or menus
    ending_text = clean_text[-300:]
    # Remove markdown links like [naver 블로그](https://...) to expose the actual article ending
    ending_text_no_links = re.sub(r'\[([^\]]+)\]\([^\)]+\)', r'\1', ending_text)
    ending_text_no_links = re.sub(r'https?://[^\s]+', '', ending_text_no_links)
    
    # Valid ending signals: period, exclamation, quote mark, email address, copyright mark, or reporter byline
    has_valid_ending = bool(re.search(r'([.?!]\s*[\"\'”’]?\s*$|기자\s*=?|@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}|\b[ⓒ©]|\bCopyright)', ending_text_no_links.strip()))
    detail["has_valid_ending"] = has_valid_ending
    
    # If it does NOT have a valid ending even after stripping links, we suspect truncation
    if not has_valid_ending:
        penalty = -10 # Relaxed penalty for truncated ending (was -25)
        score += penalty
        detail["truncation_penalty"] = penalty

    # === NEW: Domain Whitelist / Short News Bypass (Case 1) ===
    # If it's a short text but has a valid ending and looks like a real news (e.g., from Naver, KBS, etc.)
    # In Naver News, sometimes there are short breaking news.
    is_trusted_short_news = False
    if char_len >= 100 and char_len < min_c and has_valid_ending:
        # Check if it has a strong title-body overlap or high korean ratio indicating it's not a menu
        if detail.get("title_overlap_ratio", 0) >= 0.3 or detail.get("korean_char_ratio", 0) >= 0.7:
            is_trusted_short_news = True
            
    if is_trusted_short_news:
        if detail.get("reasonable_length", 0) == 0:
            restored = int(w_len * 0.8)
            detail["reasonable_length_restored"] = restored
            score += restored
        if detail.get("paragraph_count", 0) == 0:
            restored = int(w_p * 0.8)
            detail["paragraph_count_restored"] = restored
            score += restored

    # Final score clamping (0 ~ 100)
    final_score = max(0, min(100, score))
    detail["total_score"] = final_score
    return final_score, detail
