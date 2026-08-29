"""
threading/embedder.py
gemini-embedding-2 모델을 사용하여 기사 텍스트를 768차원 의미 벡터로 추출하는 모듈.
"""
import os
import sys
import numpy as np
from typing import List, Dict
from config import get_gemini_client

def get_text_embedding(text: str, model_name: str = "gemini-embedding-2") -> List[float]:
    """텍스트 1건을 gemini-embedding-2로 768차원 벡터 변환"""
    clean_text = (text or "").strip()
    if not clean_text:
        return [0.0] * 768
        
    client = get_gemini_client()
    try:
        response = client.models.embed_content(
            model=model_name,
            contents=clean_text
        )
        if hasattr(response, 'embeddings') and response.embeddings:
            return response.embeddings[0].values
        elif hasattr(response, 'embedding') and response.embedding:
            return response.embedding.values
        return [0.0] * 768

    except Exception as e:
        print(f"Embedding error on text: {clean_text[:30]}... ({e})")
        return [0.0] * 768

def compute_cosine_similarity(vec1: List[float], vec2: List[float]) -> float:
    """두 벡터 간의 코사인 유사도 계산"""
    v1 = np.array(vec1)
    v2 = np.array(vec2)
    norm1 = np.linalg.norm(v1)
    norm2 = np.linalg.norm(v2)
    if norm1 == 0 or norm2 == 0:
        return 0.0
    return float(np.dot(v1, v2) / (norm1 * norm2))
