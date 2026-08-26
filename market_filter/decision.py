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
    if not api_key:
        api_key = os.getenv("GEMINI_API_KEY", "")
        
    if not api_key:
        return True, "failed"
        
    prompt = (
        f"당신은 금융 뉴스 분석기입니다.\n"
        f"기사 제목: {title}\n"
        f"기사 본문(앞 300자): {lead_300}\n\n"
        f"본 뉴스가 [두산에너빌리티]의 자체 사업/실적/계약/이슈 중심 기사이면 is_market_news: false,\n"
        f"증시 전반이나 다수 종목을 나열한 단순 시황 기사이면 is_market_news: true 로 판정하세요.\n"
        f"반드시 JSON 형식으로만 응답하세요: {{\"is_market_news\": boolean, \"reason\": string}}"
    )
    
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash-lite:generateContent?key={api_key}"
    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"temperature": 0.0, "responseMimeType": "application/json"}
    }
    
    max_retries = config.get("llm", {}).get("max_retries", 3)
    timeout = aiohttp.ClientTimeout(total=config.get("llm", {}).get("timeout_seconds", 15.0))
    
    for attempt in range(max_retries + 1):
        try:
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.post(url, json=payload) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        text_resp = data["candidates"][0]["content"]["parts"][0]["text"]
                        parsed = json.loads(text_resp)
                        is_mkt = bool(parsed.get("is_market_news", True))
                        return is_mkt, "success"
                    elif resp.status >= 500:
                        # Server Error -> Exponential Backoff
                        if attempt < max_retries:
                            await asyncio.sleep(2 ** attempt)
        except Exception:
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

