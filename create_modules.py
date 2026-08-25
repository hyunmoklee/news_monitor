# create_modules.py
import os

modules = {}

# 1. trafilatura_extractor.py
modules["extractor/trafilatura_extractor.py"] = '''# extractor/trafilatura_extractor.py
import logging
from typing import Dict, Any, Optional
import trafilatura

logger = logging.getLogger(__name__)

def extract_with_trafilatura(html: str, url: str = "") -> Dict[str, Any]:
    """
    Extracts article content using Trafilatura in both standard (recall-focused)
    and precision (precision-focused) modes, along with article metadata.

    Returns:
    {
        "standard": {"text": str, "length": int, "success": bool},
        "precision": {"text": str, "length": int, "success": bool},
        "metadata": {"title": str, "author": str, "date": str, "sitename": str}
    }
    """
    if not html or not html.strip():
        return {
            "standard": {"text": "", "length": 0, "success": False},
            "precision": {"text": "", "length": 0, "success": False},
            "metadata": {"title": "", "author": "", "date": "", "sitename": ""}
        }

    # 1. Standard mode extraction (favor_precision=False)
    standard_text = ""
    try:
        res_std = trafilatura.extract(
            html,
            url=url,
            favor_precision=False,
            include_links=False,
            include_images=False,
            include_comments=False,
            output_format="txt"
        )
        standard_text = (res_std or "").strip()
    except Exception as e:
        logger.warning(f"Trafilatura standard extraction error for {url}: {e}")

    # 2. Precision mode extraction (favor_precision=True)
    precision_text = ""
    try:
        res_prec = trafilatura.extract(
            html,
            url=url,
            favor_precision=True,
            include_links=False,
            include_images=False,
            include_comments=False,
            output_format="txt"
        )
        precision_text = (res_prec or "").strip()
    except Exception as e:
        logger.warning(f"Trafilatura precision extraction error for {url}: {e}")

    # 3. Metadata extraction
    meta_title = ""
    meta_author = ""
    meta_date = ""
    meta_sitename = ""
    try:
        meta = trafilatura.extract_metadata(html, default_url=url)
        if meta:
            meta_title = meta.title or ""
            meta_author = meta.author or ""
            meta_date = meta.date or ""
            meta_sitename = meta.sitename or ""
    except Exception as e:
        logger.debug(f"Trafilatura metadata extraction error for {url}: {e}")

    return {
        "standard": {
            "text": standard_text,
            "length": len(standard_text),
            "success": len(standard_text) > 0
        },
        "precision": {
            "text": precision_text,
            "length": len(precision_text),
            "success": len(precision_text) > 0
        },
        "metadata": {
            "title": meta_title,
            "author": meta_author,
            "date": meta_date,
            "sitename": meta_sitename
        }
    }
'''

# 2. quality_scorer.py
modules["extractor/quality_scorer.py"] = '''# extractor/quality_scorer.py
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
            "reasonable_length": {"weight": 15, "min_chars": 200, "max_chars": 20000},
            "paragraph_count": {"weight": 10, "min_paragraphs": 2},
            "low_link_density": {"weight": 15, "max_link_char_ratio": 0.15},
            "title_body_overlap": {"weight": 10, "min_overlap_ratio": 0.2},
            "dom_article_tag_match": {"weight": 15},
            "korean_char_ratio": {"weight": 10, "min_ratio": 0.6}
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
        md_links = re.findall(r'\\[([^\\]]+)\\]\\([^\\)]+\\)', clean_text)
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
        has_article_tag = bool(re.search(r'<(article|main)\\b|id=["\\\'](?:article|newsct|content)["\\\']|class=["\\\'][^"\\\']*(?:article-body|news_body|story-news)[^"\\\']*["\\\']', html, re.IGNORECASE))
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
    non_space_chars = len(re.findall(r'\\S', clean_text)) or 1
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
    sentences = [s.strip() for s in re.split(r'[.!?]\\s+|\\n+', clean_text) if len(s.strip()) > 15]
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

    # Final score clamping (0 ~ 100)
    final_score = max(0, min(100, score))
    detail["total_score"] = final_score
    return final_score, detail
'''

# 3. site_extractor.py
modules["extractor/site_extractor.py"] = '''# extractor/site_extractor.py
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
                    body_text = body_elem.get_text(separator="\\n").strip()

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
'''

# 4. validator.py
modules["extractor/validator.py"] = '''# extractor/validator.py
from typing import Dict, Any, Optional

def validate_candidates(
    selector_result: Optional[Dict[str, Any]],
    trafilatura_std: Dict[str, Any],
    trafilatura_prec: Dict[str, Any],
    std_score: int,
    prec_score: int,
    selector_score: int = 0,
    threshold_ratio: float = 0.3,
    high_threshold: int = 85,
    low_threshold: int = 60
) -> Dict[str, Any]:
    """
    Validates candidates between Trafilatura and Site Selector.
    """
    # Determine best Trafilatura candidate
    if prec_score >= std_score and trafilatura_prec.get("success"):
        best_traf_method = "trafilatura_precision"
        best_traf_text = trafilatura_prec.get("text", "")
        best_traf_score = prec_score
    else:
        best_traf_method = "trafilatura_standard"
        best_traf_text = trafilatura_std.get("text", "")
        best_traf_score = std_score

    # Case 1: Site Selector exists
    if selector_result and selector_result.get("success"):
        selector_text = selector_result.get("body", "")
        len_sel = len(selector_text)
        len_traf = len(best_traf_text)
        max_len = max(len_sel, len_traf, 1)
        diff_ratio = abs(len_sel - len_traf) / max_len

        if diff_ratio > threshold_ratio:
            reason = f"Selector vs Trafilatura length mismatch ({round(diff_ratio * 100, 1)}% difference: selector={len_sel} chars, trafilatura={len_traf} chars)"
            return {
                "chosen_method": "site_selector",
                "chosen_text": selector_text,
                "quality_score": selector_score,
                "needs_review": True,
                "mismatch_reason": reason,
                "length_diff_ratio": diff_ratio
            }
        else:
            needs_rev = selector_score < high_threshold
            return {
                "chosen_method": "site_selector",
                "chosen_text": selector_text,
                "quality_score": selector_score,
                "needs_review": needs_rev,
                "mismatch_reason": None,
                "length_diff_ratio": diff_ratio
            }

    # Case 2: No Site Selector (Trafilatura only)
    if not best_traf_text:
        return {
            "chosen_method": "failed",
            "chosen_text": "",
            "quality_score": 0,
            "needs_review": True,
            "mismatch_reason": "All extraction methods returned empty text",
            "length_diff_ratio": 0.0
        }

    needs_rev = best_traf_score < high_threshold
    mismatch_reason = None
    if best_traf_score < low_threshold:
        mismatch_reason = f"Low quality score ({best_traf_score} < {low_threshold})"
    elif needs_rev:
        mismatch_reason = f"Moderate quality score ({best_traf_score} in {low_threshold}~{high_threshold})"

    return {
        "chosen_method": best_traf_method,
        "chosen_text": best_traf_text,
        "quality_score": best_traf_score,
        "needs_review": needs_rev,
        "mismatch_reason": mismatch_reason,
        "length_diff_ratio": 0.0
    }
'''

# 5. gemini_models.py
modules["extractor/gemini_models.py"] = '''# extractor/gemini_models.py
import os
from typing import List, Dict, Any, Optional

GEMINI_SUPPORTED_MODELS: List[Dict[str, Any]] = [
    {
        "id": "gemini-2.5-flash",
        "name": "Gemini 2.5 Flash",
        "recommended": True,
        "description": "최신 고속 경량 모델. 본문 정제 및 노이즈 제거 작업에 가장 추천됨.",
        "input_cost_per_1m": 0.075,
        "output_cost_per_1m": 0.30
    },
    {
        "id": "gemini-2.5-pro",
        "name": "Gemini 2.5 Pro",
        "recommended": False,
        "description": "최고 정밀도 추론 모델. 복잡한 구조 분석 및 고난도 본문 추출 시 활용.",
        "input_cost_per_1m": 1.25,
        "output_cost_per_1m": 5.00
    },
    {
        "id": "gemini-2.0-flash",
        "name": "Gemini 2.0 Flash",
        "recommended": False,
        "description": "2.0 세대 차세대 고속 모델.",
        "input_cost_per_1m": 0.10,
        "output_cost_per_1m": 0.40
    },
    {
        "id": "gemini-2.0-flash-lite",
        "name": "Gemini 2.0 Flash Lite",
        "recommended": False,
        "description": "초저비용 대량 정제 처리에 최적화된 초경량 모델.",
        "input_cost_per_1m": 0.0375,
        "output_cost_per_1m": 0.15
    },
    {
        "id": "gemini-1.5-flash",
        "name": "Gemini 1.5 Flash",
        "recommended": False,
        "description": "안정적인 1.5 세대 고속 모델 (하위 호환).",
        "input_cost_per_1m": 0.075,
        "output_cost_per_1m": 0.30
    },
    {
        "id": "gemini-1.5-pro",
        "name": "Gemini 1.5 Pro",
        "recommended": False,
        "description": "1.5 세대 고성능 모델.",
        "input_cost_per_1m": 1.25,
        "output_cost_per_1m": 5.00
    }
]

def list_available_gemini_models(api_key: Optional[str] = None) -> List[Dict[str, Any]]:
    key = api_key or os.getenv("GEMINI_API_KEY", "")
    if not key:
        return GEMINI_SUPPORTED_MODELS

    try:
        from google import genai
        client = genai.Client(api_key=key)
        live_models = client.models.list()
        
        supported_ids = {m["id"] for m in GEMINI_SUPPORTED_MODELS}
        results = []
        for model in live_models:
            model_name = getattr(model, "name", str(model))
            clean_id = model_name.replace("models/", "")
            if clean_id in supported_ids:
                meta = next(item for item in GEMINI_SUPPORTED_MODELS if item["id"] == clean_id)
                results.append(meta)
        return results if results else GEMINI_SUPPORTED_MODELS
    except Exception:
        return GEMINI_SUPPORTED_MODELS
'''

# 6. llm_cleaner.py
modules["extractor/llm_cleaner.py"] = '''# extractor/llm_cleaner.py
import re
import os
import logging
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)

STRICT_CLEANER_PROMPT = """역할: 너는 편집자가 아니라 정제기(cleaner)다.

입력:
[원문 본문 후보 텍스트]
{candidate_text}

지시사항:
1. 입력된 텍스트에서 기사 본문에 해당하지 않는 부분(광고 문구, 관련기사 링크, 추천기사 목록, 기자 바이라인/이메일, 저작권 문구, 무단전재 금지, 네이버 채널 구독 유도, 댓글 안내 등)만 깨끗이 제거하라.
2. 실제 기사 본문에 해당하는 문장은 단 한 글자도 요약, 재작성, 의역, 수정하지 마라. 원문 그대로 유지하라.
3. 기사 본문 문장인지 확신이 없는 문단은 임의로 삭제하지 말고 원문 그대로 남겨두어라.
4. 출력에는 부연 설명, 인사말, 코드 블록(```) 등 어떠한 추가 코멘트도 붙이지 말고 오직 '정제된 본문 텍스트'만 출력하라.
"""

def calculate_jaccard_similarity(text1: str, text2: str) -> float:
    if not text1 or not text2:
        return 0.0
    set1 = set(text1[i:i+2] for i in range(len(text1)-1))
    set2 = set(text2[i:i+2] for i in range(len(text2)-1))
    if not set1 or not set2:
        return 0.0
    intersection = len(set1 & set2)
    union = len(set1 | set2)
    return intersection / union if union > 0 else 0.0

def clean_with_gemini(
    candidate_text: str,
    api_key: Optional[str] = None,
    model_name: str = "gemini-2.5-flash",
    max_change_ratio: float = 0.4
) -> Dict[str, Any]:
    clean_original = (candidate_text or "").strip()
    if not clean_original:
        return {
            "cleaned_text": "",
            "needs_review": True,
            "success": False,
            "reason": "empty_input",
            "tokens_used": 0,
            "cost_usd": 0.0
        }

    key = api_key or os.getenv("GEMINI_API_KEY", "")
    if not key:
        return {
            "cleaned_text": clean_original,
            "needs_review": True,
            "success": False,
            "reason": "missing_api_key",
            "tokens_used": 0,
            "cost_usd": 0.0
        }

    prompt = STRICT_CLEANER_PROMPT.format(candidate_text=clean_original)

    try:
        from google import genai
        client = genai.Client(api_key=key)
        
        response = client.models.generate_content(
            model=model_name,
            contents=prompt,
        )
        
        cleaned_output = (response.text or "").strip()
        
        if cleaned_output.startswith("```") and cleaned_output.endswith("```"):
            cleaned_output = re.sub(r'^```[a-zA-Z]*\\n', '', cleaned_output)
            cleaned_output = re.sub(r'\\n```$', '', cleaned_output).strip()

        orig_len = len(clean_original)
        clean_len = len(cleaned_output)
        deletion_ratio = (orig_len - clean_len) / orig_len if orig_len > 0 else 1.0
        jaccard_sim = calculate_jaccard_similarity(clean_original, cleaned_output)

        est_input_tokens = len(prompt) // 2
        est_output_tokens = len(cleaned_output) // 2
        total_tokens = est_input_tokens + est_output_tokens
        cost_usd = (est_input_tokens * 0.075 + est_output_tokens * 0.30) / 1_000_000

        if deletion_ratio > max_change_ratio or jaccard_sim < 0.5:
            logger.warning(f"LLM Cleaner safety triggered: Deletion={round(deletion_ratio*100,1)}%, Jaccard={round(jaccard_sim, 2)}")
            return {
                "cleaned_text": cleaned_output,
                "needs_review": True,
                "safety_triggered": True,
                "reason": f"Excessive modification detected (deletion: {round(deletion_ratio*100, 1)}%, jaccard: {round(jaccard_sim, 2)})",
                "success": True,
                "tokens_used": total_tokens,
                "cost_usd": cost_usd
            }

        return {
            "cleaned_text": cleaned_output,
            "needs_review": False,
            "safety_triggered": False,
            "reason": None,
            "success": True,
            "tokens_used": total_tokens,
            "cost_usd": cost_usd
        }

    except Exception as e:
        logger.error(f"Gemini API invocation error: {e}")
        return {
            "cleaned_text": clean_original,
            "needs_review": True,
            "success": False,
            "reason": f"API error: {e}",
            "tokens_used": 0,
            "cost_usd": 0.0
        }
'''

# 7. tests/test_quality_scorer.py
modules["tests/test_quality_scorer.py"] = '''# tests/test_quality_scorer.py
import pytest
from extractor.quality_scorer import calculate_quality_score, load_scoring_config

SAMPLE_GOOD_ARTICLE = """
두산에너빌리티가 체코 신규 원전 건설 사업의 주계약 체결을 앞두고 핵심 주기기 제작 준비에 본격 착수했다.
이번 사업에서 두산에너빌리티는 증기발생기, 터빈 등 핵심 1차 계통 원전 기자재 공급을 전담하게 된다.

원전 업계에 따르면 체코 정부는 한국수력원자력을 우선협상대상자로 선정한 이후 세부 계약 협상을 순조롭게 이어가고 있다.
두산에너빌리티는 창원공장의 생산 설비를 사전 점검하고 고품질 기자재 제작을 위한 전담 태스크포스를 구성했다.

회사 관계자는 "체코 원전 프로젝트는 한국형 원전의 우수한 기술력과 시공 능력을 세계 시장에 입증하는 계기가 될 것"이라며
"철저한 품질 관리와 기한 내 납품을 통해 국가적 원전 수출 프로젝트의 성공을 적극 뒷받침하겠다"고 밝혔다.
"""

SAMPLE_NOISY_ARTICLE = """
[스폰서 광고] 지금 가입하면 50% 할인 혜택!
관련기사: 많이 본 뉴스 TOP 10
무단전재 및 재배포 금지. 저작권자 © 뉴스
구독하기 댓글 0개
"""

def test_quality_scorer_good_article():
    score, detail = calculate_quality_score(
        text=SAMPLE_GOOD_ARTICLE,
        title="두산에너빌리티, 체코 원전 주기기 제작 본격 착수",
        html="<article><div class='article-body'>content</div></article>"
    )
    assert score >= 85
    assert detail["reasonable_length"] > 0
    assert detail["paragraph_count"] > 0
    assert detail["korean_char_signal"] > 0
    assert detail["boilerplate_penalty"] == 0

def test_quality_scorer_noisy_article():
    score, detail = calculate_quality_score(
        text=SAMPLE_NOISY_ARTICLE,
        title="두산에너빌리티 소식",
        html="<div>ads</div>"
    )
    assert score < 60
    assert detail["boilerplate_penalty"] < 0
    assert detail["boilerplate_hits"] > 0

def test_quality_scorer_empty_text():
    score, detail = calculate_quality_score(text="", title="", html="")
    assert score == 0
'''

# 8. tests/test_validator.py
modules["tests/test_validator.py"] = '''# tests/test_validator.py
import pytest
from extractor.validator import validate_candidates

def test_validator_consistent():
    std = {"text": "두산에너빌리티 원전 수주 본문입니다. " * 20, "success": True}
    prec = {"text": "두산에너빌리티 원전 수주 본문입니다. " * 20, "success": True}
    sel = {"body": "두산에너빌리티 원전 수주 본문입니다. " * 20, "success": True}
    
    result = validate_candidates(
        selector_result=sel,
        trafilatura_std=std,
        trafilatura_prec=prec,
        std_score=90,
        prec_score=90,
        selector_score=90,
        threshold_ratio=0.3
    )
    assert result["chosen_method"] == "site_selector"
    assert result["needs_review"] is False
    assert result["mismatch_reason"] is None

def test_validator_mismatch_detected():
    std = {"text": "두산에너빌리티 원전 수주 본문입니다. " * 50, "success": True}
    prec = {"text": "두산에너빌리티 원전 수주 본문입니다. " * 50, "success": True}
    sel = {"body": "짧은 텍스트", "success": True}
    
    result = validate_candidates(
        selector_result=sel,
        trafilatura_std=std,
        trafilatura_prec=prec,
        std_score=88,
        prec_score=88,
        selector_score=40,
        threshold_ratio=0.3
    )
    assert result["needs_review"] is True
    assert "length mismatch" in result["mismatch_reason"]
'''

for filepath, code in modules.items():
    os.makedirs(os.path.dirname(filepath), exist_ok=True)
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(code.strip() + "\n")
    print(f"Generated: {filepath}")

print("All modules and tests generated successfully!")
