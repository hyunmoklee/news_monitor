"""
Step 3: 3-Way 하이브리드 판정 및 비동기 I/O 분리 (DB Lock 방지) 모듈.
"""
import asyncio
import json
import os
import aiohttp
from typing import Dict, Tuple

async def call_gemini_fallback(
    title: str, 
    lead_300: str, 
    config: Dict,
    api_key: str = None
) -> Tuple[bool, str]:
    from google.genai import types

    from config import get_gemini_client, DEFAULT_GEMINI_MODEL, GEMINI_THINKING_BUDGET
    
    prompt = (
        f"당신은 금융 뉴스 분석기입니다.\n"
        f"기사 제목: {title}\n"
        f"기사 본문(앞 300자): {lead_300}\n\n"
        f"본 뉴스가 [두산에너빌리티]의 자체 사업/실적/계약/이슈 중심 기사이면 is_market_news: false,\n"
        f"증시 전반이나 다수 종목을 나열한 단순 시황 기사이면 is_market_news: true 로 판정하세요.\n"
        f"반드시 JSON 형식으로만 응답하세요: {{\"is_market_news\": boolean, \"reason\": string}}"
    )
    
    model_name = config.get("llm", {}).get("model", DEFAULT_GEMINI_MODEL)
    max_retries = config.get("llm", {}).get("max_retries", 3)
    thinking_budget = config.get("llm", {}).get("thinking_budget", GEMINI_THINKING_BUDGET)
    
    try:
        client = get_gemini_client()
    except Exception as e:
        return None, "manual_review_needed"
        
    for attempt in range(max_retries + 1):
        try:
            # google-genai async call with thinking config
            gen_config = types.GenerateContentConfig(
                temperature=0.0,
                response_mime_type="application/json",
                thinking_config=types.ThinkingConfig(thinking_budget=thinking_budget)
            )
            response = await client.aio.models.generate_content(
                model=model_name,
                contents=prompt,
                config=gen_config
            )

            
            text_resp = (response.text or "").strip()
            parsed = json.loads(text_resp)
            is_mkt = bool(parsed.get("is_market_news", True))
            return is_mkt, "success"
        except Exception as e:
            if attempt < max_retries:
                await asyncio.sleep(2 ** attempt)
                
    # [State Transition: v1.2 New Policy]
    # Scrap old fallback (is_market_news=True). Replace with manual review queue.
    return None, "manual_review_needed"


def evaluate_decision(
    market_score: int, 
    config: Dict
) -> Tuple[str, bool]:
    t1 = config.get("thresholds", {}).get("T1_company_cutoff", -20)
    t2 = config.get("thresholds", {}).get("T2_market_cutoff", 20)
    
    if market_score < t1:
        return "Group A", False  # 기업 기사 확정 (Company Core)
    elif market_score > t2:
        return "Group B", True   # 시황 기사 확정 (Pure Market)
    else:
        return "Group C", None   # 회색지대 (Rule 미판정 -> LLM 위임 / Pending)

