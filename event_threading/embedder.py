# event_threading/embedder.py
"""
Dual-Mode gemini-embedding-2 Module
- 'gcp_enterprise': Ultra-fast concurrent async embedding (concurrency=15, 200 texts in ~2.5s)
- 'aistudio_free': Safe sequential single-call with 4.2s rate-limit delay (Free Tier 15 RPM compliant)
"""
import os
import sys
import time
import asyncio
import numpy as np
from typing import List, Dict
from config import get_gemini_client, API_TIER_MODE

def get_text_embedding(text: str, model_name: str = "gemini-embedding-2") -> List[float]:
    """Single synchronous text embedding (768/3072-dim vector)"""
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

async def _embed_single_async(client, text: str, model_name: str) -> List[float]:
    clean_text = (text or "").strip()
    if not clean_text:
        return [0.0] * 768
    try:
        resp = await client.aio.models.embed_content(
            model=model_name,
            contents=clean_text
        )
        if hasattr(resp, 'embeddings') and resp.embeddings:
            return resp.embeddings[0].values
        elif hasattr(resp, 'embedding') and resp.embedding:
            return resp.embedding.values
        return [0.0] * 768
    except Exception as e:
        print(f"Async embedding error: {clean_text[:30]}... ({e})")
        return [0.0] * 768

async def get_batch_text_embeddings_async(
    texts: List[str], 
    model_name: str = "gemini-embedding-2", 
    concurrency: int = 15,
    free_tier_delay: float = 4.2
) -> List[List[float]]:
    """
    Dual-mode high-speed async batch text embedding.
    - 'gcp_enterprise': Concurrent async gathering (concurrency=15).
    - 'aistudio_free': Safe sequential with delay.
    """
    if not texts:
        return []

    client = get_gemini_client()

    if API_TIER_MODE == "gcp_enterprise":
        print(f"  ⚡ [Embedding Engine] GCP Enterprise High-Speed Async Mode ({len(texts)} texts, Concurrency: {concurrency})...")
        sem = asyncio.Semaphore(concurrency)

        async def bounded_embed(t):
            async with sem:
                return await _embed_single_async(client, t, model_name)

        tasks = [bounded_embed(t) for t in texts]
        return await asyncio.gather(*tasks)
    else:
        print(f"  🛡️ [Embedding Engine] AI Studio Free Tier Mode (Safe 15 RPM Delay: {free_tier_delay}s)...")
        results = []
        for idx, t in enumerate(texts):
            vec = get_text_embedding(t, model_name)
            results.append(vec)
            if idx < len(texts) - 1 and free_tier_delay > 0:
                time.sleep(free_tier_delay)
        return results

def get_batch_text_embeddings(
    texts: List[str], 
    model_name: str = "gemini-embedding-2", 
    concurrency: int = 15,
    free_tier_delay: float = 4.2
) -> List[List[float]]:
    """Synchronous wrapper for batch embedding"""
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            import nest_asyncio
            nest_asyncio.apply()
            return loop.run_until_complete(get_batch_text_embeddings_async(texts, model_name, concurrency, free_tier_delay))
        else:
            return asyncio.run(get_batch_text_embeddings_async(texts, model_name, concurrency, free_tier_delay))
    except Exception:
        return asyncio.run(get_batch_text_embeddings_async(texts, model_name, concurrency, free_tier_delay))

def compute_cosine_similarity(vec1: List[float], vec2: List[float]) -> float:
    """두 벡터 간의 코사인 유사도 계산"""
    v1 = np.array(vec1)
    v2 = np.array(vec2)
    norm1 = np.linalg.norm(v1)
    norm2 = np.linalg.norm(v2)
    if norm1 == 0 or norm2 == 0:
        return 0.0
    return float(np.dot(v1, v2) / (norm1 * norm2))
