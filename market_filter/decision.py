"""
Step 3: 3-Way 하이브리드 판정 및 비동기 I/O 분리 (DB Lock 방지) 모듈.
"""
import asyncio
import json
import os
import aiohttp
from typing import Dict, Tuple

def extract_target_context(body: str, aliases: list, max_chars: int = 500) -> str:
    """본문 전체에서 타깃 기업 별칭이 등장하는 문맥 윈도우를 지능적으로 추출 (최대 500자)"""
    if not body:
        return ""
    
    # 별칭이 등장하는 위치 탐색
    matched_pos = -1
    for alias in aliases:
        pos = body.find(alias)
        if pos != -1:
            matched_pos = pos
            break
            
    if matched_pos == -1:
        return body[:max_chars].strip()
        
    start_pos = max(0, matched_pos - 150)
    end_pos = min(len(body), start_pos + max_chars)
    snippet = body[start_pos:end_pos].strip()
    return snippet if len(snippet) >= 100 else body[:max_chars].strip()


async def call_gemini_fallback(
    title: str, 
    lead_300: str, 
    config: Dict,
    full_body: str = None,
    api_key: str = None
) -> Tuple[bool, str]:
    from google.genai import types
    from config import get_gemini_client, DEFAULT_GEMINI_MODEL, GEMINI_THINKING_BUDGET
    
    targets = config.get("targets", {})
    t_name = list(targets.keys())[0] if targets else "타깃 기업"
    t_info = targets.get(t_name, {})
    t_aliases = t_info.get("aliases", [t_name])
    
    context_text = extract_target_context(full_body or lead_300, t_aliases, max_chars=500)

    prompt = (
        f"당신은 금융 뉴스 전문 분류 AI입니다.\n"
        f"대상 기업: [{t_name}] (관련 키워드: {', '.join(t_aliases)})\n\n"
        f"기사 제목: {title}\n"
        f"기사 본문 핵심 문맥: {context_text}\n\n"
        f"【분류 지침】\n"
        f"1. [기업 기사 (is_market_news: false)]:\n"
        f"   - 기사의 주된 화제가 [{t_name}]의 자체 사업, 수주, 실적, 계약, 기술 개발, 설비 투자, 경영 이슈인 경우.\n"
        f"   - 기사 서두/말미에 증시 지수나 타사 주가가 일부 언급되었더라도, 핵심 내용이 [{t_name}]의 고유 비즈니스 호재라면 기업 기사로 분류하세요.\n"
        f"   - 대형 계약/수주/호재 소식으로 인해 주가가 급등했다는 '특징주' 기사도 기업 기사로 인정합니다.\n\n"
        f"2. [시황 기사 (is_market_news: true)]:\n"
        f"   - 코스피/코스닥 지수 시황, 외인/기관/개미 매매 동향, 복수 종목을 단순 나열한 기계적 시세 기사.\n"
        f"   - [{t_name}]의 고유 비즈니스 내용 없이 단순 주가/호가 등락만 1~2줄 나열한 시세봇 기사.\n\n"
        f"반드시 다음 JSON 형식으로만 엄격하게 응답하세요:\n"
        f"{{\n"
        f'  "primary_topic": "기사의 핵심 화제 (1문장 요약)",\n'
        f'  "has_company_business_event": boolean,\n'
        f'  "is_pure_stock_listicle": boolean,\n'
        f'  "reason": "분류 사유",\n'
        f'  "is_market_news": boolean\n'
        f"}}"
    )

    model_name = config.get("llm", {}).get("model", DEFAULT_GEMINI_MODEL)
    max_retries = config.get("llm", {}).get("max_retries", 3)
    thinking_budget = max(512, config.get("llm", {}).get("thinking_budget", GEMINI_THINKING_BUDGET))
    
    try:
        client = get_gemini_client()
    except Exception as e:
        return None, "manual_review_needed"
        
    for attempt in range(max_retries + 1):
        try:
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

