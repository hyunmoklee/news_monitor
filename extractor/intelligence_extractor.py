# extractor/intelligence_extractor.py
"""
Single-Pass Enterprise Intelligence Extractor
- Powered by Gemini 3.7 Flash (with thinking_budget=1024, temperature=0.0)
- Extracts UniversalIntelligence Pydantic schema
- Zero-hallucination fact grounding
"""
import os
import json
import logging
from typing import Dict, Any, Optional
from google.genai import types
from config import get_gemini_client, DEFAULT_GEMINI_MODEL
from extractor.universal_schema import UniversalIntelligence

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """당신은 C-Level 경영진 및 기관 투자자를 위한 [금융·산업 뉴스 인텔리전스 수석 분석관]입니다.
주어진 기사 본문을 분석하여 경영진이 5초 만에 핵심 팩트와 비즈니스 영향을 파악할 수 있도록 엄격하게 구조화된 인텔리전스를 추출하세요.

【절대 준수 지침 (Zero-Hallucination & Canonicalization Rules)】
1. [철저한 사실 기반 (Strict Grounding)]:
   - 본문에 명시되지 않은 추측, 루머, 외부 지식은 절대 추가하지 마세요.
   - 금액이나 수치가 본문에 명시되지 않은 경우 key_metrics에 항목을 지어내지 마세요.
   - 향후 일정이 없으면 timeline_milestones를 빈 배열([])로 두세요.
2. [명칭 및 단위 표준화 (Canonicalization)]:
   - 기업명/기관명은 접두사(美, 韓)와 법인형태(社, 주식회사)를 떼고 '공식 표준 약칭'으로 통일하세요. (예: "美 테라파워社" -> "테라파워", "NVIDIA Corp." -> "엔비디아")
   - 금액(억원, 조원, 달러), 비율(%), 용량(MW, GW, GB), 시점(분기, 연도) 단위를 본문 그대로 정확히 기재하세요.
3. [불필요한 미사여구 배제]:
   - "기대에 힘입어", "관심이 모인다" 같은 상투적 수식어를 배제하고, [주어 + 객체 + 수치 + 팩트] 중심으로 작성하세요.
"""

async def extract_intelligence_async(
    title: str,
    body: str,
    target_company: str = "두산에너빌리티"
) -> Dict[str, Any]:
    """
    Extract structured intelligence from article using Gemini 3.7 Flash.
    """
    clean_body = (body or "").strip()
    if not clean_body or len(clean_body) < 50:
        return {
            "success": False,
            "error": "Body too short",
            "intelligence": None
        }

    client = get_gemini_client()
    prompt = f"""[분석 대상 기업]: {target_company}
[기사 제목]: {title}
[기사 본문]:
{clean_body}

위 기사를 정밀 분석하여 지정된 JSON 스키마 규격으로 구조화 인텔리전스를 출력하세요."""

    config = types.GenerateContentConfig(
        system_instruction=SYSTEM_PROMPT,
        temperature=0.0,
        response_mime_type="application/json",
        response_schema=UniversalIntelligence,
        thinking_config=types.ThinkingConfig(thinking_budget=1024)
    )

    try:
        response = await client.aio.models.generate_content(
            model=DEFAULT_GEMINI_MODEL,
            contents=prompt,
            config=config
        )
        
        parsed_json = json.loads(response.text)
        return {
            "success": True,
            "intelligence": parsed_json
        }
    except Exception as e:
        logger.error(f"Failed to extract intelligence for '{title}': {e}")
        return {
            "success": False,
            "error": str(e),
            "intelligence": None
        }
