"""
threading/clusterer.py
- Universal Complete-Linkage Agglomerative Event Clusterer
- High-Precision Multi-Tenant Event Threading
- Hard Constraints for Source/Broker Entities (e.g. KB증권 vs 한국투자증권 100% 분리)
"""
from typing import List, Dict
from .embedder import compute_cosine_similarity

def cluster_articles_by_event(
    articles: List[Dict],
    similarity_threshold: float = 0.88
) -> List[List[Dict]]:
    """
    완전연결 계층적 군집화 (Complete-Linkage Agglomerative Clustering)를 통해
    사건 단위의 고응집 타임라인 스레드를 생성합니다.
    """
    n = len(articles)
    if n == 0:
        return []

    # 1. 초기 상태: 각 기사를 개별 클러스터로 초기화
    clusters = [[art] for art in articles]

    # 2. 상향식 계층 병합 (Bottom-Up Agglomerative Merge)
    while True:
        best_sim = -1.0
        merge_pair = None

        # 모든 클러스터 쌍 (i, j) 간의 완전연결(Complete-Linkage) 최소 유사도 탐색
        for i in range(len(clusters)):
            for j in range(i + 1, len(clusters)):
                cluster_a = clusters[i]
                cluster_b = clusters[j]

                # [Hard Constraint 1: 출처/분석기관 상호 배타성 검사]
                brokers_a = {a.get("broker") for a in cluster_a if a.get("broker") and a.get("broker") != "일반"}
                brokers_b = {b.get("broker") for b in cluster_b if b.get("broker") and b.get("broker") != "일반"}
                if brokers_a and brokers_b and brokers_a != brokers_b:
                    # 서로 다른 증권사/분석기관 리포트는 유사도가 높아도 병합 불가
                    continue

                # [Complete-Linkage: 두 클러스터 내 모든 기사 쌍 간의 최소 유사도 계산]
                min_sim_between = 1.0
                for a in cluster_a:
                    for b in cluster_b:
                        cos_sim = compute_cosine_similarity(a["embedding"], b["embedding"])
                        if cos_sim < min_sim_between:
                            min_sim_between = cos_sim

                # 전체 최소 유사도가 임계값 이상이고, 현재 탐색된 쌍 중 가장 높은 경우
                if min_sim_between >= similarity_threshold and min_sim_between > best_sim:
                    best_sim = min_sim_between
                    merge_pair = (i, j)

        # 더 이상 임계값을 만족하는 병합 후보가 없으면 종료
        if not merge_pair:
            break

        # 최적 쌍 병합
        idx1, idx2 = merge_pair
        clusters[idx1].extend(clusters[idx2])
        clusters.pop(idx2)

    # 3. 각 클러스터 내 기사들을 발행 시각순으로 정렬
    for c in clusters:
        c.sort(key=lambda x: x.get("published_at", ""))

    # 4. 기사 수가 많고 최신인 순으로 클러스터 정렬
    clusters.sort(key=lambda c: (len(c), c[0].get("published_at", "")), reverse=True)

    return clusters
