# preprocessing/value_scorer.py
import re
from typing import List, Dict, Any

def compute_value_score(article: Dict[str, Any], config: Dict[str, Any]) -> Dict[str, Any]:
    """
    [Stage 3.6: Universal High-Precision Value Scoring]
    Universal scoring engine balancing media credibility, official portal quality,
    analytical depth, and factual metric disclosures for any enterprise target.
    """
    pipeline_cfg = config.get("pipeline", {})
    score_cfg = config.get("value_scoring", {})
    tier1_list = config.get("tier1_media", [])
    
    target_company = pipeline_cfg.get("target_company", "")
    aliases = pipeline_cfg.get("aliases", [])
    executives = pipeline_cfg.get("related_executives", [])
    all_targets = [t for t in ([target_company] + aliases + executives) if t]
    
    tier1_bonus = score_cfg.get("tier1_media_bonus", 25)
    naver_bonus = score_cfg.get("naver_inlink_bonus", 15)
    disclosure_weight = score_cfg.get("disclosure_score", 15)
    lead_weight = score_cfg.get("lead_mention_score", 15)
    metric_weight = score_cfg.get("metric_score", 5)
    quote_weight = score_cfg.get("quote_score", 5)
    noise_penalty = score_cfg.get("noise_penalty", -30)
    
    title = article.get("title", "")
    body = article.get("cleaned_body", "")
    url = article.get("url", "")
    media_name = article.get("media_name", "")
    full_text = f"{title}\n{body}"
    clean_audit = article.get("clean_audit", {})
    
    # 1. Media Credibility Tier Bonus
    is_tier1 = any(t1 in media_name for t1 in tier1_list)
    tier_score = tier1_bonus if is_tier1 else 0
    
    # 2. Naver In-Link Quality Bonus
    is_naver_inlink = "news.naver.com" in url
    inlink_score = naver_bonus if is_naver_inlink else 0
    
    # 3. DART / Regulatory Filing / Official Disclosure Mentions
    disclosure_keywords = ["DART", "전자공시", "공시", "사업보고서", "분기보고서", "IR", "공시했다", "공시를 통해"]
    has_disclosure = any(dk in full_text for dk in disclosure_keywords)
    disclosure_score = disclosure_weight if has_disclosure else 0
    
    # 4. Target company in lead sentence
    sentences = [s.strip() for s in re.split(r'[\.\?\!\n]+', body) if s.strip()]
    first_sent = sentences[0] if sentences else ""
    target_in_lead = any(term in first_sent for term in all_targets) if all_targets else False
    lead_score = lead_weight if target_in_lead else 0

    # 5. Metric / Number Count
    metric_matches = re.findall(r'(\d+(?:\.\d+)?\s*(?:조|억|만)?\s*원|\d+(?:\.\d+)?\s*(?:MW|GW|MWe|kW|kWh|톤|t|%|km|배|달러|불))', full_text)
    metric_count = len(metric_matches)
    metric_score = min(metric_count * metric_weight, 15)
    
    # 6. Direct Quotes
    quote_matches = re.findall(r'["“][^"”]{5,}?["”]', body)
    quote_count = len(quote_matches)
    quote_score = min(quote_count * quote_weight, 15)
    
    # 7. Quality & Purity Penalties
    purity_penalty = 0
    if clean_audit.get("has_noise"):
        purity_penalty += noise_penalty
    total_target_mentions = sum(body.count(term) for term in all_targets)
    if len(body) > 4000 and total_target_mentions < 3:
        purity_penalty += -25
        
    # 8. Length Bonus (capped at 10)
    length_score = min(len(body) / 150.0, 10.0)
    
    total_score = max(tier_score + inlink_score + disclosure_score + lead_score + metric_score + quote_score + length_score + purity_penalty, 5.0)
    
    return {
        "total_score": round(total_score, 1),
        "tier_score": tier_score,
        "is_tier1_media": is_tier1,
        "inlink_score": inlink_score,
        "is_naver_inlink": is_naver_inlink,
        "disclosure_score": disclosure_score,
        "lead_score": lead_score,
        "metric_score": metric_score,
        "metric_count": metric_count,
        "quote_score": quote_score,
        "quote_count": quote_count,
        "purity_penalty": purity_penalty,
        "length_score": round(length_score, 1)
    }

def select_master_articles(
    articles: List[Dict[str, Any]],
    config: Dict[str, Any]
) -> List[Dict[str, Any]]:
    """
    Evaluates value scores for all articles and selects the single Master article per cluster.
    """
    for art in articles:
        art["value_score_details"] = compute_value_score(art, config)
        art["value_score"] = art["value_score_details"]["total_score"]
        
    clusters = {}
    for art in articles:
        cid = art.get("cluster_id", "SINGLETON")
        if cid not in clusters:
            clusters[cid] = []
        clusters[cid].append(art)
        
    for cid, members in clusters.items():
        members.sort(key=lambda x: (
            x["value_score"],
            1 if "news.naver.com" in x.get("url", "") else 0,
            len(x.get("cleaned_body", ""))
        ), reverse=True)
        master = members[0]
        
        master["status"] = "MASTER"
        master["is_master"] = True
        master["master_url"] = master["url"]
        master["final_decision"] = "MASTER"
        master["final_reason"] = f"클러스터({cid}) 대표 기사 선정 (신뢰도/가치점수: {master['value_score']}점, [{master['media_name']}], 동종 {len(members)}건 중 1위)"
        
        for dup in members[1:]:
            dup["status"] = "DUPLICATE"
            dup["is_master"] = False
            dup["master_url"] = master["url"]
            dup["master_title"] = master["title"]
            dup["final_decision"] = "DUPLICATE"
            dup["final_reason"] = f"동일 사건 중복 기사 (대표 기사: [{master['media_name']}] '{master['title'][:25]}...' 채택)"
            
    return articles
