# extractor/llm_cleaner.py
import re
import os
import logging
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)

STRICT_CLEANER_PROMPT = """역할: 너는 편집자가 아니라 정제기(cleaner)다.

입력:
[원문 본문 후보 텍스트]
{candidate_text}

지시사항:
1. 입력된 텍스트에서 기사 본문에 해당하지 않는 부분(광고 문구, 관련기사 링크, 추천기사 목록, 기자 바이라인/이메일, 저작권 문구, 무단전재 금지, 네이버 채널 구독 유도, 댓글 안내 등)만 깨끗이 제거하라.
2. 실제 기사 본문에 해당하는 문장은 단 한 글자도 요약, 재작성, 의역, 수정하지 마라. 원문 그대로 유지하라.
3. 기사 본문 문장인지 확신이 없는 문단은 임의로 삭제하지 말고 원문 그대로 남겨두어라.
4. 출력에는 부연 설명, 인사말, 코드 블록(```) 등 어떠한 추가 코멘트도 붙이지 말고 오직 '정제된 본문 텍스트'만 출력하라.
"""

def calculate_jaccard_similarity(text1: str, text2: str) -> float:
    if not text1 or not text2:
        return 0.0
    set1 = set(text1[i:i+2] for i in range(len(text1)-1))
    set2 = set(text2[i:i+2] for i in range(len(text2)-1))
    if not set1 or not set2:
        return 0.0
    intersection = len(set1 & set2)
    union = len(set1 | set2)
    return intersection / union if union > 0 else 0.0

def clean_with_gemini(
    candidate_text: str,
    api_key: Optional[str] = None,
    model_name: str = "gemini-2.5-flash",
    max_change_ratio: float = 0.4
) -> Dict[str, Any]:
    clean_original = (candidate_text or "").strip()
    if not clean_original:
        return {
            "cleaned_text": "",
            "needs_review": True,
            "success": False,
            "reason": "empty_input",
            "tokens_used": 0,
            "cost_usd": 0.0
        }

    from config import get_gemini_client, DEFAULT_GEMINI_MODEL
    model_to_use = model_name or DEFAULT_GEMINI_MODEL
    prompt = STRICT_CLEANER_PROMPT.format(candidate_text=clean_original)

    try:
        if api_key:
            from google import genai
            client = genai.Client(api_key=api_key)
        else:
            client = get_gemini_client()
        
        response = client.models.generate_content(
            model=model_to_use,
            contents=prompt,
        )

        
        cleaned_output = (response.text or "").strip()
        
        if cleaned_output.startswith("```") and cleaned_output.endswith("```"):
            cleaned_output = re.sub(r'^```[a-zA-Z]*\n', '', cleaned_output)
            cleaned_output = re.sub(r'\n```$', '', cleaned_output).strip()

        orig_len = len(clean_original)
        clean_len = len(cleaned_output)
        deletion_ratio = (orig_len - clean_len) / orig_len if orig_len > 0 else 1.0
        jaccard_sim = calculate_jaccard_similarity(clean_original, cleaned_output)

        est_input_tokens = len(prompt) // 2
        est_output_tokens = len(cleaned_output) // 2
        total_tokens = est_input_tokens + est_output_tokens
        cost_usd = (est_input_tokens * 0.075 + est_output_tokens * 0.30) / 1_000_000

        if deletion_ratio > max_change_ratio or jaccard_sim < 0.5:
            logger.warning(f"LLM Cleaner safety triggered: Deletion={round(deletion_ratio*100,1)}%, Jaccard={round(jaccard_sim, 2)}")
            return {
                "cleaned_text": cleaned_output,
                "needs_review": True,
                "safety_triggered": True,
                "reason": f"Excessive modification detected (deletion: {round(deletion_ratio*100, 1)}%, jaccard: {round(jaccard_sim, 2)})",
                "success": True,
                "tokens_used": total_tokens,
                "cost_usd": cost_usd
            }

        return {
            "cleaned_text": cleaned_output,
            "needs_review": False,
            "safety_triggered": False,
            "reason": None,
            "success": True,
            "tokens_used": total_tokens,
            "cost_usd": cost_usd
        }

    except Exception as e:
        logger.error(f"Gemini API invocation error: {e}")
        return {
            "cleaned_text": clean_original,
            "needs_review": True,
            "success": False,
            "reason": f"API error: {e}",
            "tokens_used": 0,
            "cost_usd": 0.0
        }
