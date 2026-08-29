"""
threading/clusterer.py
임베딩 코사인 유사도(>=0.82) 및 고유명사 엔티티 매칭을 결합한 하이브리드 사건 클러스터러.
"""
from typing import List, Dict, Tuple
from .embedder import compute_cosine_similarity

def extract_key_topics(title: str) -> List[str]:
    """제목에서 주요 비즈니스 토픽/엔티티 추출"""
    topics = []
    candidates = ["체코", "원전", "SMR", "가스터빈", "수소", "풍력", "신한울", "주기기", "수주", "실적", "보령", "루마니아"]
    for c in candidates:
        if c in title:
            topics.append(c)
    return topics

def cluster_articles_by_event(
    articles: List[Dict],
    similarity_threshold: float = 0.82
) -> List[List[Dict]]:
    """
    임베딩 벡터와 토픽 일치를 활용하여 연관 기사들을 사건 단위 클러스터로 그룹화합니다.
    """
    n = len(articles)
    if n == 0:
        return []

    visited = [False] * n
    clusters = []

    for i in range(n):
        if visited[i]:
            continue

        current_cluster = [articles[i]]
        visited[i] = True
        vec_i = articles[i].get("embedding", [])
        topics_i = set(extract_key_topics(articles[i].get("title", "")))

        for j in range(i + 1, n):
            if visited[j]:
                continue

            vec_j = articles[j].get("embedding", [])
            topics_j = set(extract_key_topics(articles[j].get("title", "")))

            # 코사인 유사도 계산
            cos_sim = compute_cosine_similarity(vec_i, vec_j)
            
            # 토픽 자카드 일치도
            topic_overlap = len(topics_i & topics_j) / len(topics_i | topics_j) if (topics_i | topics_j) else 0.0

            # 하이브리드 결합 점수 (0.75 임베딩 + 0.25 엔티티 일치)
            hybrid_score = 0.75 * cos_sim + 0.25 * topic_overlap

            # 임계값 통과 시 동일 사건 클러스터로 병합
            if hybrid_score >= similarity_threshold or cos_sim >= 0.86:
                visited[j] = True
                articles[j]["similarity_to_anchor"] = round(cos_sim, 3)
                current_cluster.append(articles[j])

        clusters.append(current_cluster)

    return clusters
