# preprocessing/company_focus.py
"""
Target Company Focus & Entity Prominence Evaluation Engine (V2 - Role-Based Partitioning)
Distinguishes between Strategic Clients/Partners (e.g. TerraPower, Nvidia, TSMC) 
and true Competitors/Peers (e.g. Samsung, Hyundai, LG).
"""
import re
from typing import Dict, Any, List, Tuple

# Strategic Clients / Counterparties / Technology Partners by Company
# Mentions of these partners represent the target company's business milestones, NOT peer dilution!
STRATEGIC_PARTNERS = {
    "두산에너빌리티": [
        "테라파워", "TerraPower", "웨스팅하우스", "Westinghouse", "엑스에너지", "X-energy", 
        "뉴스케일", "NuScale", "빌 게이츠", "Bill Gates", "GE", "지멘스", "Siemens", "프라마톰",
        "한수원", "한국수력원자력", "한전", "한국전력", "팀코리아"
    ],
    "SK하이닉스": [
        "엔비디아", "Nvidia", "NVIDIA", "TSMC", "애플", "Apple", "마이크로소프트", "Microsoft", "MS",
        "오픈AI", "OpenAI", "구글", "Google", "AMD", "테슬라", "Tesla", "아마존", "AWS", "메타", "Meta",
        "ASML", "퀄컴", "Qualcomm"
    ]
}

# True Competitors / Broad Market Peers (Collision indicates actual dilution or sector roundup)
COMPETITORS_AND_PEERS = {
    "두산에너빌리티": [
        "삼성전자", "LG에너지솔루션", "현대차", "기아", "POSCO홀딩스", "포스코", "NAVER", "네이버", 
        "카카오", "KB금융", "신한지주", "삼성바이오로직스", "셀트리온", "한화에어로스페이스", 
        "HD현대중공업", "HD한국조선해양", "한화오션", "삼성SDI", "LG화학", "LG전자", "현대모비스",
        "효성중공업", "LS일렉트릭", "대한전선", "SNT홀딩스", "스맥", "유니슨", "금화피에스시"
    ],
    "SK하이닉스": [
        "삼성전자", "마이크론", "Micron", "인텔", "Intel", "LG에너지솔루션", "현대차", "기아", 
        "POSCO홀딩스", "포스코", "NAVER", "네이버", "카카오", "KB금융", "신한지주", "삼성바이오로직스",
        "셀트리온", "한화에어로스페이스", "HD현대중공업", "한화오션", "LG전자", "현대모비스",
        "제주반도체", "한미반도체", "리노공업", "HPSP"
    ]
}

COMPANY_ALIASES = {
    "두산에너빌리티": ["두산에너빌리티", "두산에너빌", "두산에너빌리티(주)", "두산중공업"],
    "SK하이닉스": ["SK하이닉스", "하이닉스", "에스케이하이닉스", "SK hynix", "SK Hynix", "SK하이닉스(주)"]
}

# Single headline milestone patterns (e.g. "두산에너빌리티, 美 테라파워 SMR 기자재 수주")
SOLO_MILESTONE_VERBS = [
    "수주", "공급", "계약", "체결", "납품", "제작", "개발", "협력", "합의", "확정", "선정", "출하", "양산"
]

def evaluate_company_focus(title: str, body: str, target_keyword: str) -> Dict[str, Any]:
    """
    Evaluates whether an article is exclusively focused on the target company using Role-Based Entity Partitioning.
    """
    clean_keyword = "SK하이닉스" if ("하이닉스" in target_keyword or "SK" in target_keyword) else "두산에너빌리티"
    target_aliases = COMPANY_ALIASES.get(clean_keyword, [clean_keyword])
    partners = STRATEGIC_PARTNERS.get(clean_keyword, [])
    competitors = COMPETITORS_AND_PEERS.get(clean_keyword, [])
    
    # 1. Split body sentences
    sentences = [s.strip() for s in re.split(r'[\.\?\!\n]+', body) if s.strip()]
    lead_sentence = " ".join(sentences[:2]) if sentences else ""
    
    # 2. Count target mentions (including contextual short names like "두산은", "하이닉스는")
    target_mentions = sum(body.count(a) for a in target_aliases)
    
    # Contextual alias bonus for short names
    if clean_keyword == "두산에너빌리티":
        target_mentions += len(re.findall(r'\b두산(?:은|이|의|을|과|도)\b', body))
    elif clean_keyword == "SK하이닉스":
        target_mentions += len(re.findall(r'\b(?:SK|하이닉스)(?:은|이|의|를|와|도)\b', body))

    # 3. Detect Partners vs True Competitors
    partner_mentions = {}
    for p in partners:
        cnt = body.count(p)
        if cnt > 0:
            partner_mentions[p] = cnt
            
    competitor_mentions = {}
    for comp in competitors:
        cnt_body = body.count(comp)
        cnt_title = title.count(comp)
        if cnt_body > 0 or cnt_title > 0:
            competitor_mentions[comp] = {
                "count": cnt_body,
                "in_title": cnt_title > 0,
                "in_lead": comp in lead_sentence
            }
            
    total_partner_count = sum(partner_mentions.values())
    total_competitor_count = sum(v["count"] for v in competitor_mentions.values())
    unique_competitors = len(competitor_mentions)
    
    # 4. Title Structure Analysis
    title_has_target = any(a in title for a in target_aliases)
    title_has_competitor = any(v["in_title"] for v in competitor_mentions.values())
    title_has_partner = any(p in title for p in partners)
    title_has_milestone_verb = any(v in title for v in SOLO_MILESTONE_VERBS)
    
    is_solo_milestone_headline = (title_has_target and title_has_partner and title_has_milestone_verb and not title_has_competitor)
    
    if is_solo_milestone_headline or (title_has_target and not title_has_competitor):
        title_status = "SOLO_TARGET"
    elif title_has_target and title_has_competitor:
        title_status = "CO_MENTION"
    elif not title_has_target and title_has_competitor:
        title_status = "OTHER_ONLY"
    else:
        title_status = "NO_COMPANY"
        
    # Lead structure analysis
    lead_has_target = any(a in lead_sentence for a in target_aliases)
    lead_has_competitor = any(v["in_lead"] for v in competitor_mentions.values())
    
    if lead_has_target and not lead_has_competitor:
        lead_status = "SOLO_TARGET"
    elif lead_has_target and lead_has_competitor:
        lead_status = "CO_MENTION"
    elif not lead_has_target and lead_has_competitor:
        lead_status = "OTHER_ONLY"
    else:
        lead_status = "NO_COMPANY"

    # 5. Focus Score Calculation (0 ~ 100)
    # Effective Target Volume = Target Mentions + (Partner Mentions * 0.5) (Partner context reinforces target milestone)
    effective_target_vol = target_mentions + (total_partner_count * 0.4)
    total_entity_vol = effective_target_vol + total_competitor_count
    
    if total_entity_vol > 0:
        mention_share = effective_target_vol / total_entity_vol
    else:
        mention_share = 0.5
        
    mention_score = mention_share * 50.0 # 0 ~ 50 pts
    
    # Title Score (0 ~ 30 pts)
    if is_solo_milestone_headline:
        title_score = 30.0
    elif title_status == "SOLO_TARGET":
        title_score = 30.0
    elif title_status == "CO_MENTION":
        title_score = 10.0
    elif title_status == "NO_COMPANY":
        title_score = 15.0
    else:
        title_score = 0.0
        
    # Lead Score (0 ~ 20 pts)
    if lead_status == "SOLO_TARGET":
        lead_score = 20.0
    elif lead_status == "CO_MENTION":
        lead_score = 8.0
    elif lead_status == "NO_COMPANY":
        lead_score = 10.0
    else:
        lead_score = 0.0
        
    # Competitor Dilution Penalty
    dilution_penalty = 0.0
    if unique_competitors >= 4:
        dilution_penalty = 30.0
    elif unique_competitors >= 2:
        dilution_penalty = 15.0
    elif unique_competitors == 1:
        dilution_penalty = 5.0
        
    raw_focus_score = mention_score + title_score + lead_score - dilution_penalty
    
    # Milestone boost
    if is_solo_milestone_headline and unique_competitors == 0:
        raw_focus_score = max(raw_focus_score, 95.0)
        
    focus_score = round(max(0.0, min(100.0, raw_focus_score)), 1)
    
    # Classification
    if focus_score >= 80.0 and unique_competitors <= 1:
        focus_type = "EXCLUSIVE_SOLO"
        focus_label = "🎯 단독 조명 (Solo Focus)"
        if partner_mentions:
            top_p = list(partner_mentions.keys())[:2]
            focus_desc = f"{clean_keyword}의 단독 성과 및 파트너({', '.join(top_p)}) 수주/공급 기사"
        else:
            focus_desc = f"오직 {clean_keyword}에 집중된 100% 단독 기사"
    elif focus_score >= 50.0:
        focus_type = "PRIMARY_FOCUS"
        focus_label = "⚖️ 주요 조명 (Primary Focus)"
        top_comps = list(competitor_mentions.keys())[:2]
        focus_desc = f"{clean_keyword} 중심이나 타사({', '.join(top_comps)}) 비교/섹터 언급 포함"
    else:
        focus_type = "MULTI_MENTION"
        focus_label = "👥 다수기업 혼합 (Multi Mention)"
        focus_desc = f"{unique_competitors}개 이상 타 기업이 나열된 증시/섹터 분산 기사"

    # Sorted list of competitors found
    top_competitors_list = sorted(
        [{"name": k, "count": v["count"], "in_title": v["in_title"]} for k, v in competitor_mentions.items()],
        key=lambda x: (x["in_title"], x["count"]),
        reverse=True
    )
    
    # Partners list
    partner_list = [{"name": k, "count": v} for k, v in partner_mentions.items()]

    return {
        "focus_score": focus_score,
        "focus_type": focus_type,
        "focus_label": focus_label,
        "focus_desc": focus_desc,
        "target_mentions": target_mentions,
        "partner_mentions": partner_list[:4],
        "competitor_mentions": total_competitor_count,
        "unique_competitors": unique_competitors,
        "title_status": title_status,
        "lead_status": lead_status,
        "mention_share_pct": round(mention_share * 100, 1),
        "top_competitors": top_competitors_list[:5]
    }
