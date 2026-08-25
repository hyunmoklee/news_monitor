# preprocessing/candidate_cluster.py
from typing import List, Dict, Any, Set, Tuple
from kiwipiepy import Kiwi

# Singleton Kiwi instance for high performance
_kiwi = Kiwi()

def extract_nouns_and_numbers(text: str) -> Set[str]:
    """
    Extracts meaningful nouns (NNG, NNP), numbers (SN), and foreign words (SL) using Kiwi.
    """
    if not text:
        return set()
    tokens = _kiwi.tokenize(text)
    keywords = set()
    for t in tokens:
        if t.tag in ['NNG', 'NNP', 'SN', 'SL'] and len(t.form) > 1:
            keywords.add(t.form)
    return keywords

def calculate_jaccard_similarity(set1: Set[str], set2: Set[str]) -> float:
    """Calculates Jaccard similarity between two keyword sets."""
    if not set1 or not set2:
        return 0.0
    intersection = len(set1.intersection(set2))
    union = len(set1.union(set2))
    return float(intersection) / union if union > 0 else 0.0

def generate_candidate_pairs(
    articles: List[Dict[str, Any]],
    min_jaccard: float = 0.08
) -> List[Tuple[int, int, float]]:
    """
    [Stage 3.3: Morphological Lightweight Candidate Reduction]
    Extracts Kiwi nouns & numbers for each article, then filters candidate pairs
    with Jaccard similarity >= min_jaccard for deep embedding comparison.
    Returns list of (idx1, idx2, jaccard_score).
    """
    # Pre-extract keywords for each article (title + lead 300 chars)
    kw_cache = []
    for art in articles:
        text = f"{art.get('title', '')} {art.get('cleaned_body', '')[:300]}"
        kw_cache.append(extract_nouns_and_numbers(text))
        
    candidate_pairs = []
    n = len(articles)
    for i in range(n):
        for j in range(i + 1, n):
            score = calculate_jaccard_similarity(kw_cache[i], kw_cache[j])
            if score >= min_jaccard:
                candidate_pairs.append((i, j, score))
                
    return candidate_pairs
