# preprocessing/embedding_dedup.py
import re
from datetime import datetime
from typing import List, Dict, Any, Tuple, Set
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
from kiwipiepy import Kiwi

_kiwi = Kiwi()

ANALYSIS_TITLE_KEYWORDS = ["왜", "어떻게", "속내는", "전망", "분석", "기획", "쟁점", "포커스", "택했나", "배경은", "들썩", "이슈분석", "심층", "리포트"]

def is_analysis_article(title: str) -> bool:
    """Checks if article is an analytical/in-depth feature rather than a simple PR release."""
    return any(ak in title for ak in ANALYSIS_TITLE_KEYWORDS)

def kiwi_tokenize(text: str) -> List[str]:
    """Tokenizes Korean text into nouns, numbers, and roots for TF-IDF."""
    if not text:
        return []
    tokens = _kiwi.tokenize(text)
    return [t.form for t in tokens if t.tag in ['NNG', 'NNP', 'SN', 'SL', 'VV', 'VA'] and len(t.form) > 1]

def extract_proper_nouns_and_keywords(title: str) -> Tuple[Set[str], Set[str]]:
    """Extracts proper nouns (NNP - countries/projects/entities) and general nouns (NNG/SN) from headline."""
    if not title:
        return set(), set()
    tokens = _kiwi.tokenize(title)
    proper_nouns = {t.form for t in tokens if t.tag in ['NNP'] and len(t.form) > 1}
    all_keywords = {t.form for t in tokens if t.tag in ['NNG', 'NNP', 'SN', 'SL'] and len(t.form) > 1}
    return proper_nouns, all_keywords

def calculate_jaccard(s1: Set[str], s2: Set[str]) -> float:
    if not s1 or not s2:
        return 0.0
    return float(len(s1.intersection(s2))) / len(s1.union(s2))

def parse_iso_or_custom_date(date_str: str) -> datetime:
    if not date_str or date_str == "-":
        return datetime.min
    try:
        if len(date_str) == 16:
            return datetime.strptime(date_str, "%Y-%m-%d %H:%M")
        elif len(date_str) >= 19:
            return datetime.strptime(date_str[:19].replace("T", " "), "%Y-%m-%d %H:%M:%S")
        else:
            return datetime.fromisoformat(date_str)
    except Exception:
        return datetime.min

def check_event_conflicts(art1: Dict[str, Any], art2: Dict[str, Any]) -> bool:
    """
    [Universal Event Conflict Detector]
    Checks if two articles represent inherently different event scopes
    by comparing analytical depth, conflicting proper nouns, and conflicting numeric project units.
    """
    t1, t2 = art1.get("title", ""), art2.get("title", "")
    
    # 1. Analytical feature vs Simple PR release separation
    if is_analysis_article(t1) != is_analysis_article(t2):
        return True
        
    # 2. Conflicting Proper Nouns (Geographical locations / Projects / Overseas countries)
    pn1, _ = extract_proper_nouns_and_keywords(t1)
    pn2, _ = extract_proper_nouns_and_keywords(t2)
    # If both have explicit proper nouns in headline and have zero overlap, they are distinct foreign projects
    if pn1 and pn2 and len(pn1.intersection(pn2)) == 0:
        return True
        
    # 3. Unit number conflicts (1호기 vs 2호기, etc.)
    units1 = set(re.findall(r'(\d+호기|\d+단계|\d+호)', t1 + " " + art1.get("cleaned_body", "")[:300]))
    units2 = set(re.findall(r'(\d+호기|\d+단계|\d+호)', t2 + " " + art2.get("cleaned_body", "")[:300]))
    if units1 and units2 and not units1.intersection(units2):
        return True
        
    return False

def cluster_and_deduplicate(
    articles: List[Dict[str, Any]],
    candidate_pairs: List[Tuple[int, int, float]],
    config: Dict[str, Any]
) -> List[Dict[str, Any]]:
    """
    [Stages 3.4 & 3.5: Universal High-Precision Event Clustering]
    Merges duplicate coverage of the same PR/event while strictly separating distinct events and analyses.
    """
    emb_cfg = config.get("embedding_dedup", {})
    time_window_hours = emb_cfg.get("time_window_hours", 72)
    body_threshold = emb_cfg.get("body_similarity_threshold", 0.25)
    title_jaccard_threshold = emb_cfg.get("title_jaccard_threshold", 0.30)
    
    n = len(articles)
    if n == 0:
        return []
        
    texts_to_encode = [
        f"{art.get('title', '')} {art.get('cleaned_body', '')[:500]}" for art in articles
    ]
    title_keywords = [extract_proper_nouns_and_keywords(art.get("title", ""))[1] for art in articles]
    
    vectorizer = TfidfVectorizer(tokenizer=kiwi_tokenize, token_pattern=None, min_df=1)
    tfidf_matrix = vectorizer.fit_transform(texts_to_encode)
    
    parent = list(range(n))
    def find(i):
        if parent[i] == i:
            return i
        parent[i] = find(parent[i])
        return parent[i]
        
    def union(i, j):
        root_i = find(i)
        root_j = find(j)
        if root_i != root_j:
            parent[root_j] = root_i

    for i, j, cand_score in candidate_pairs:
        # Time window check
        d1 = parse_iso_or_custom_date(articles[i].get("published_at"))
        d2 = parse_iso_or_custom_date(articles[j].get("published_at"))
        if d1 != datetime.min and d2 != datetime.min:
            diff_hours = abs((d1 - d2).total_seconds()) / 3600.0
            if diff_hours > time_window_hours:
                continue
                
        # Check universal event conflict
        if check_event_conflicts(articles[i], articles[j]):
            continue
            
        body_cos_sim = float(cosine_similarity(tfidf_matrix[i], tfidf_matrix[j])[0][0])
        title_jac = calculate_jaccard(title_keywords[i], title_keywords[j])
        
        is_same_event = False
        if title_jac >= 0.45:
            is_same_event = True
        elif title_jac >= title_jaccard_threshold and body_cos_sim >= 0.18:
            is_same_event = True
        elif body_cos_sim >= body_threshold:
            is_same_event = True
            
        if is_same_event:
            union(i, j)
            
    clusters = {}
    for i in range(n):
        root = find(i)
        if root not in clusters:
            clusters[root] = []
        clusters[root].append(i)
        
    cluster_idx = 1
    for root, member_indices in clusters.items():
        cluster_id = f"CLUSTER_{cluster_idx:03d}"
        for member_i in member_indices:
            articles[member_i]["cluster_id"] = cluster_id
            articles[member_i]["cluster_size"] = len(member_indices)
            articles[member_i]["cluster_members"] = member_indices
        cluster_idx += 1
        
    return articles
