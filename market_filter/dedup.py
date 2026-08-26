"""
Step 1: 최근 72시간 윈도우 기사 대상 2-어절 Bi-gram Jaccard 중복 제거 모듈 (sBERT 배제).
"""
import re
from typing import List, Dict, Set, Tuple

def get_word_bigrams(text: str) -> Set[str]:
    cleaned = re.sub(r'[^\w\s]', ' ', text or '')
    words = [w for w in cleaned.split() if len(w) > 0]
    if len(words) < 2:
        return set(words)
    return {f"{words[i]}_{words[i+1]}" for i in range(len(words) - 1)}

def calculate_jaccard_similarity(set_a: Set[str], set_b: Set[str]) -> float:
    if not set_a and not set_b:
        return 1.0
    if not set_a or not set_b:
        return 0.0
    intersection = len(set_a & set_b)
    union = len(set_a | set_b)
    return intersection / union if union > 0 else 0.0

def run_exact_dedup(
    articles: List[Dict],
    title_threshold: float = 0.85,
    lead_threshold: float = 0.85
) -> List[Dict]:
    sorted_articles = sorted(articles, key=lambda x: str(x.get("published_at") or ""))
    seen_clusters: List[Tuple[Set[str], Set[str]]] = []
    
    for art in sorted_articles:
        title = art.get("title") or ""
        body = art.get("chosen_text") or art.get("body") or ""
        lead_200 = body[:200]
        
        t_bigrams = get_word_bigrams(title)
        l_bigrams = get_word_bigrams(lead_200)
        
        is_dup = False
        for seen_t, seen_l in seen_clusters:
            sim_t = calculate_jaccard_similarity(t_bigrams, seen_t)
            sim_l = calculate_jaccard_similarity(l_bigrams, seen_l)
            
            if sim_t >= title_threshold and sim_l >= lead_threshold:
                is_dup = True
                break
                
        if is_dup:
            art["is_exact_dup"] = 1
        else:
            art["is_exact_dup"] = 0
            seen_clusters.append((t_bigrams, l_bigrams))
            
    return sorted_articles
