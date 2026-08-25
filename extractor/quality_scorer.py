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
    w_p = p_cnt_cfg.get("weight", 15)
    
    # Check paragraphs or sentence count as fallback (handle periods without spaces, common in broadcast news)
    sentences = [s.strip() for s in re.split(r'(?<=[.!?])\s*|\n+', clean_text) if len(s.strip()) > 8]
    if len(paragraphs) >= min_p:
        score += w_p
        detail["paragraph_count"] = w_p
    elif len(sentences) >= 3 or char_len >= 250:
        # Monolithic article with multiple valid sentences or sufficient length gets full paragraph weight
        score += w_p
        detail["paragraph_count"] = w_p
        detail["paragraph_count_type"] = "sentence_fallback"
    elif len(sentences) >= 2:
        partial_p = int(w_p * 0.7)
        score += partial_p
        detail["paragraph_count"] = partial_p
        detail["paragraph_count_type"] = "partial_sentence_fallback"
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

    # 4. Positive Signal: Korean Character Ratio
    p_kr_cfg = pos_cfg.get("korean_character_ratio", {})
    min_kr = p_kr_cfg.get("min_korean_ratio", 0.6)
    w_kr = p_kr_cfg.get("weight", 15)
    kr_chars = len(re.findall(r'[가-힣]', clean_text))
    kr_ratio = kr_chars / max(char_len, 1)
    detail["korean_char_ratio"] = round(kr_ratio, 2)
    if kr_ratio >= min_kr:
        score += w_kr
        detail["korean_char_signal"] = w_kr
    elif kr_ratio >= 0.4:
        partial_kr = int(w_kr * 0.7)
        score += partial_kr
        detail["korean_char_signal"] = partial_kr
    else:
        detail["korean_char_signal"] = 0

    # 5. Positive Signal: Title-Body Overlap
    p_title_cfg = pos_cfg.get("title_body_overlap", {})
    w_title = p_title_cfg.get("weight", 15)
    min_overlap = p_title_cfg.get("min_overlap_ratio", 0.15)
    if title:
        title_tokens = set(re.findall(r'[가-힣a-zA-Z0-9]{2,}', title))
        if title_tokens:
            matched_tokens = [t for t in title_tokens if t in clean_text]
            overlap_ratio = len(matched_tokens) / len(title_tokens)
            if overlap_ratio >= min_overlap:
                score += w_title
                detail["title_body_overlap"] = w_title
            elif char_len >= 300 and kr_ratio >= 0.5:
                # If body is substantial and clearly in Korean, grant partial points for metaphoric/creative headlines
                partial_title = int(w_title * 0.7)
                score += partial_title
                detail["title_body_overlap"] = partial_title
            else:
                detail["title_body_overlap"] = 0
            detail["title_overlap_ratio"] = round(overlap_ratio, 2)
        else:
            score += w_title
            detail["title_body_overlap"] = w_title
    else:
        score += int(w_title * 0.5)
        detail["title_body_overlap"] = int(w_title * 0.5)

    # 6. Positive Signal: DOM Article Tag Match
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
        # If HTML is omitted but text is clean and long enough (>= 300 chars), grant full DOM tag weight
        if char_len >= 300:
            score += w_dom
            detail["dom_article_tag_match"] = w_dom
        else:
            partial_dom = int(w_dom * 0.5)
            score += partial_dom
            detail["dom_article_tag_match"] = partial_dom


    # ==========================================
    # NEGATIVE PENALTIES
    # ==========================================
    neg_cfg = config.get("negative_penalties", {})

    # 1. Penalty: Boilerplate & Promotional Keywords
    bp_cfg = neg_cfg.get("boilerplate_keywords", {})
    bp_keywords = bp_cfg.get("keywords", [])
    pen_bp = bp_cfg.get("penalty_per_hit", 10)
    max_pen_bp = bp_cfg.get("max_penalty", 30)
    bp_hits = sum(1 for kw in bp_keywords if kw in clean_text)
    if bp_hits > 0:
        bp_pen_applied = min(bp_hits * pen_bp, max_pen_bp)
        score -= bp_pen_applied
        detail["boilerplate_penalty"] = -bp_pen_applied
    else:
        detail["boilerplate_penalty"] = 0
    detail["boilerplate_hits"] = bp_hits

    # 2. Penalty: Repeated Sentences
    rep_cfg = neg_cfg.get("repeated_sentences", {})
    max_rep_ratio = rep_cfg.get("max_repeated_sentence_ratio", 0.15)
    pen_rep = rep_cfg.get("penalty_weight", 15)
    if sentences:
        from collections import Counter
        sent_counts = Counter(sentences)
        dupes = sum(cnt - 1 for s, cnt in sent_counts.items() if cnt > 1)
        dupe_ratio = dupes / len(sentences)
        if dupe_ratio > max_rep_ratio:
            rep_pen = int(dupe_ratio * pen_rep)
            score -= rep_pen
            detail["repeated_sentences_penalty"] = -rep_pen
        else:
            detail["repeated_sentences_penalty"] = 0
    else:
        detail["repeated_sentences_penalty"] = 0

    # 3. Penalty: Short Paragraphs Dominance (Listings / Menus)
    sp_cfg = neg_cfg.get("short_paragraphs", {})
    max_sp_len = sp_cfg.get("max_char_len", 30)
    max_sp_ratio = sp_cfg.get("max_short_paragraph_ratio", 0.6)
    pen_sp = sp_cfg.get("penalty_weight", 10)
    if paragraphs and len(paragraphs) >= 3:
        short_p = sum(1 for p in paragraphs if len(p) <= max_sp_len)
        sp_ratio = short_p / len(paragraphs)
        detail["short_paragraph_ratio"] = round(sp_ratio, 2)
        # If overall body is long (> 600 chars), forgive minor short-paragraph fragments
        if sp_ratio > max_sp_ratio and char_len < 600:
            score -= pen_sp
            detail["short_paragraph_penalty"] = -pen_sp
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
    # Relaxed validation: Check the last 300 characters to tolerate appended SNS links, photo captions, or menus
    ending_text = clean_text[-300:]
    # Remove markdown links like [naver 블로그](https://...) to expose the actual article ending
    ending_text_clean = re.sub(r'\[([^\]]+)\]\([^\)]+\)', r'\1', ending_text)
    ending_text_clean = re.sub(r'https?://[^\s]+', '', ending_text_clean)
    
    # Strip common trailing photo credits, citations, and media signatures (e.g. 사진=한경DB, 충청매일 CCDN, 연합뉴스 자료사진)
    trailing_caption_patterns = [
        r'(?:사진|자료|출처|그래픽)\s*=\s*[가-힣A-Za-z0-9\s]+$',
        r'[가-힣A-Za-z0-9\s]+(?:사진|자료사진|제공|DB)\s*$',
        r'전문보기\s*:?\s*$',
        r'충청매일\s*CCDN\s*$',
        r'한경\s*DB\s*$',
        r'키움증권\s*$',
        r'후원하기\s*$'
    ]
    trimmed_ending = ending_text_clean.strip()
    for cap_pat in trailing_caption_patterns:
        trimmed_ending = re.sub(cap_pat, '', trimmed_ending, flags=re.IGNORECASE).strip()
    
    # Valid ending signals:
    # 1. Standard punctuation (. ? ! " ')
    # 2. News/Broadcast predicates (습니다, 합니다, 입니다, 바랍니다, 보였습니다, 나타났습니다, 올랐습니다, 하락했습니다, 집계됐습니다, 설명했다, 밝혔다 등)
    # 3. Reporter byline / email / copyright
    # 4. Market numbers/units (% , 원, 선, 포인트, 상승, 하락, 거래 등)
    valid_ending_pattern = r'([.?!]\s*[\"\'”’]?\s*$|(?:습니다|합니다|입니다|바랍니다|보였습니다|나타났습니다|기록했습니다|올랐습니다|내렸습니다|집계됐습니다|밝혔습니다|전망입니다|풀이됩니다|설명했다|밝혔다|전했다|말했다|본다)\s*[\"\'”’]?\s*$|기자\s*=?|@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}|\b[ⓒ©]|\bCopyright|(?:%|원|선|포인트|상승|하락|마감|거래|순|기록|수준)\s*$)'
    has_valid_ending = bool(re.search(valid_ending_pattern, trimmed_ending))
    detail["has_valid_ending"] = has_valid_ending
    
    # If it does NOT have a valid ending even after stripping links and recognizing predicates, suspect truncation
    if not has_valid_ending:
        penalty = -10 # Relaxed penalty for truncated ending
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
