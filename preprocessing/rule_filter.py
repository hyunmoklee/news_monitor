# preprocessing/rule_filter.py
import re
from typing import Tuple, Dict, Any, List

def evaluate_rule_filter(
    title: str,
    cleaned_body: str,
    config: Dict[str, Any]
) -> Tuple[bool, str, Dict[str, Any]]:
    """
    [Stage 3.2: Universal High-Precision Rule-based Filtering]
    Dynamic, configuration-driven filtering engine applicable to ANY corporate target.
    Eliminates stock chatter, spam, competitor-only subjects, and broad market roundups.
    """
    pipeline_cfg = config.get("pipeline", {})
    rule_cfg = config.get("rule_filter", {})
    
    target_company = pipeline_cfg.get("target_company", "")
    aliases = pipeline_cfg.get("aliases", [])
    executives = pipeline_cfg.get("related_executives", [])
    industry_keywords = pipeline_cfg.get("industry_keywords", [])
    
    all_target_terms = [t for t in ([target_company] + aliases + executives) if t]
    
    min_length = rule_cfg.get("min_body_length", 250)
    min_mentions = rule_cfg.get("min_company_mentions", 2)
    spam_keywords = rule_cfg.get("spam_keywords", [])
    junk_title_patterns = rule_cfg.get("junk_title_patterns", [])
    stock_price_patterns = rule_cfg.get("stock_price_theme_patterns", [])
    other_major_companies = rule_cfg.get("other_major_companies", [])
    
    body_no_spaces = re.sub(r'\s+', '', cleaned_body)
    char_length = len(body_no_spaces)
    
    # 1. Target mentions in body & title
    total_mentions = sum(cleaned_body.count(term) for term in all_target_terms)
    title_has_target = any(term in title for term in all_target_terms)
    
    # 2. Industry keywords in title
    title_has_industry_topic = any(topic in title for topic in industry_keywords) if industry_keywords else False
    
    # 3. Check position (first 2 sentences)
    sentences = [s.strip() for s in re.split(r'[\.\?\!\n]+', cleaned_body) if s.strip()]
    first_2 = " ".join(sentences[:2]) if sentences else ""
    lead_has_target = any(term in first_2 for term in all_target_terms)
    
    # 4. Detect Stock Price / Theme Chatter
    is_stock_price_chatter = False
    matched_stock_theme = None
    for spat in stock_price_patterns:
        if re.search(spat, title) or re.search(spat, first_2):
            is_stock_price_chatter = True
            matched_stock_theme = spat
            break

    # 5. Detect competitor / other company subject in title (Target not in title)
    has_other_subject = False
    matched_other_sub = None
    for other_sub in other_major_companies:
        if other_sub in title and not any(tt in title for tt in all_target_terms):
            has_other_subject = True
            matched_other_sub = other_sub
            break

    # 6. Detect multi-company broad market / portfolio articles
    other_found = []
    for comp in other_major_companies:
        cnt = cleaned_body.count(comp)
        if cnt > 0 and comp not in all_target_terms:
            other_found.append(comp)
            
    is_broad_market = False
    if len(other_found) >= 4 and total_mentions <= 2 and not title_has_target:
        is_broad_market = True

    audit_log = {
        "target_company": target_company,
        "char_length": char_length,
        "min_required_length": min_length,
        "company_mentions_in_body": total_mentions,
        "company_in_title": title_has_target,
        "industry_topic_in_title": title_has_industry_topic,
        "company_in_lead": lead_has_target,
        "is_stock_price_chatter": is_stock_price_chatter,
        "other_companies_found": other_found[:5],
        "is_broad_market": is_broad_market,
        "matched_spam": None,
        "matched_junk_pattern": None,
        "rule_passed": True,
        "rejection_reason": None
    }
    
    # Filter 1: Body Length Check
    if char_length < min_length:
        reason = f"본문 길이 부족 ({char_length}자 < 기준 {min_length}자)"
        audit_log["rule_passed"] = False
        audit_log["rejection_reason"] = reason
        return False, reason, audit_log

    # Filter 2: Direct Spam Keywords
    for spam_kw in spam_keywords:
        if spam_kw in title or spam_kw in cleaned_body:
            reason = f"스팸/리딩방 키워드 탐지 ('{spam_kw}')"
            audit_log["matched_spam"] = spam_kw
            audit_log["rule_passed"] = False
            audit_log["rejection_reason"] = reason
            return False, reason, audit_log

    # Filter 3: Junk Title / Headline / Briefing / Roundups
    for junk_kw in junk_title_patterns:
        if junk_kw in title:
            reason = f"단순 시황/브리핑/헤드라인 모음집 ('{junk_kw}')"
            audit_log["matched_junk_pattern"] = junk_kw
            audit_log["rule_passed"] = False
            audit_log["rejection_reason"] = reason
            return False, reason, audit_log

    # Filter 4: Stock Price / Theme Chatter
    if is_stock_price_chatter:
        reason = f"단순 주가/시세/테마주 동향 기사 (패턴: '{matched_stock_theme}')"
        audit_log["rule_passed"] = False
        audit_log["rejection_reason"] = reason
        return False, reason, audit_log

    # Filter 5: Other Company Subject
    if has_other_subject:
        reason = f"타사 단독 기사 내 단순 언급 (주제: '{matched_other_sub}')"
        audit_log["rule_passed"] = False
        audit_log["rejection_reason"] = reason
        return False, reason, audit_log

    # Filter 6: Broad Multi-Stock Portfolio Article
    if is_broad_market:
        reason = f"단순 증시/섹터 다수 종목 나열 기사 (타 종목 {len(other_found)}개 언급 대비 {target_company} 단독 이슈 아님)"
        audit_log["rule_passed"] = False
        audit_log["rejection_reason"] = reason
        return False, reason, audit_log

    # Filter 7: Target / Industry Relevance Rule
    is_relevant = title_has_target or (title_has_industry_topic and total_mentions >= 2) or (lead_has_target and total_mentions >= 3)
    if not is_relevant:
        reason = f"타깃 기업/핵심 산업 관련성 미달 (제목/도입부 미등장, 본문 언급 {total_mentions}회)"
        audit_log["rule_passed"] = False
        audit_log["rejection_reason"] = reason
        return False, reason, audit_log

    # Filter 8: Minimum Body Mentions
    required_mentions = 1 if title_has_target else min_mentions
    if total_mentions < required_mentions:
        reason = f"기업명 언급 빈도 미달 ({total_mentions}회 < 기준 {required_mentions}회)"
        audit_log["rule_passed"] = False
        audit_log["rejection_reason"] = reason
        return False, reason, audit_log
        
    return True, "1차 규칙 필터 통과", audit_log
