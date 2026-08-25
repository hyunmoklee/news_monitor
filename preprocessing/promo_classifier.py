# preprocessing/promo_classifier.py
import re
from typing import Dict, Any

PROMO_PATTERNS = [
    r'이벤트\s*진행',
    r'경품\s*증정',
    r'할인\s*프로모션',
    r'고객\s*감사',
    r'사은품',
    r'선착순\s*증정',
    r'출시기념',
    r'브랜드\s*대상\s*수상'
]

def evaluate_promotional(article: Dict[str, Any]) -> Dict[str, Any]:
    """
    [Stage 3.7: Promotional / PR Content Detection]
    Evaluates whether the article is promotional/PR content vs substantive hard news.
    """
    title = article.get("title", "")
    body = article.get("cleaned_body", "")
    text = f"{title}\n{body}"
    
    matches = []
    for pat in PROMO_PATTERNS:
        if re.search(pat, text):
            matches.append(pat)
            
    is_promo = len(matches) >= 2
    promo_score = len(matches) * 20
    
    return {
        "is_promotional": is_promo,
        "promo_score": promo_score,
        "matched_promo_patterns": matches
    }
