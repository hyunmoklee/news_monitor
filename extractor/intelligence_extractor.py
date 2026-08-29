# extractor/intelligence_extractor.py
"""
Single-Pass Enterprise Intelligence Extractor v2.3
- Powered by Gemini 3.7 Flash (with thinking_budget=1024, temperature=0.0)
- Extracts UniversalIntelligence v2.3 Pydantic schema
- Zero-hallucination fact grounding & Temporal Guardrail
- 3-Tier Verification Level (CONFIRMED / ESTIMATE / UNCONFIRMED_RUMOR)
- Quantitative Standardization (raw_numeric_value + unit)
"""
import os
import json
import logging
from typing import Dict, Any, Optional
from google.genai import types
from config import get_gemini_client, DEFAULT_GEMINI_MODEL, CURRENT_REFERENCE_DATE
from extractor.universal_schema import UniversalIntelligence

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = f"""당신은 C-Level 경영진 및 글로벌 기관 투자자를 위한 [금융·산업 뉴스 인텔리전스 수석 분석관]입니다.
현재 기사 수집 및 분석 기준 시점은 [{CURRENT_REFERENCE_DATE} (2026년 8월)]입니다.
주어진 기사 본문을 분석하여 경영진이 5초 만에 핵심 팩트와 정량 지표, 비즈니스 영향을 파악할 수 있도록 엄격하게 구조화된 인텔리전스를 추출하세요.

【절대 준수 지침 (Zero-Hallucination & Standardization Rules)】
1. [철저한 사실 기반 (Strict Grounding)]:
   - 본문에 명시되지 않은 추측, 루머, 외부 지식은 절대 추가하지 마세요.
   - 금액이나 수치가 본문에 명시되지 않은 경우 key_metrics에 항목을 지어내지 마세요.
   - 향후 일정이 없으면 timeline_milestones를 빈 배열([])로 두세요.

2. [시점 기준 앵커링 & 과거 연도 오타 보정 (Temporal Guardrail)]:
   - 현재 기준 연도는 [2026년]입니다.
   - 언론사 기자가 과거 기사 템플릿을 재활용하여 "올해(2024년) 실적", "2024년 하반기 전망" 등으로 잘못 표기한 경우, key_metrics의 target_period는 실질 대상 기간(예: "2026E", "2026년 상반기")으로 정규화하고, context에 원문 표기 내용을 기록하세요.

3. [3단계 팩트 신뢰도 등급화 (Verification Level)]:
   - `CONFIRMED`: 정부 부처/공공기관 공식 발표, 기업 공시(DART), 확정 체결 계약, 실측 가동률 등 공식 확인 팩트.
   - `ESTIMATE`: 증권사 리서치 리포트 목표주가, 연간 실적 추정치, 기업 자체 가이던스.
   - `UNCONFIRMED_RUMOR`: 막후 협상 단독 보도, 익명 취재원 인용, 정부 부인 보도, 미확인 풍문.

4. [정량 수치 정규화 (Quantitative Standardization)]:
   - key_metrics의 raw_numeric_value에는 순수 숫자값(float/int)만 기재하세요. (예: 14만원 -> 140000, 19조원 -> 19.0, 80.0% -> 80.0, 10기 -> 10.0)
   - unit에는 단위를 명시하세요. (예: "원", "조원", "억원", "%", "MW", "기", "시간")
   - formatted_value에는 가독성 좋은 표준 서식을 기재하세요. (예: "140,000원", "19조 원", "80.0%", "10기")

5. [명칭 및 단위 표준화]:
   - 기업명/기관명은 접두사(美, 韓)와 법인형태(社, 주식회사)를 떼고 '공식 표준 약칭'으로 통일하세요. (예: "美 테라파워社" -> "테라파워", "KB증권사" -> "KB증권")
"""

async def extract_intelligence_async(
    title: str,
    body: str,
    target_company: str = "두산에너빌리티",
    reference_date: str = CURRENT_REFERENCE_DATE
) -> Dict[str, Any]:
    """
    Extract structured intelligence from article using Gemini 3.7 Flash with schema v2.3.
    """
    clean_body = (body or "").strip()
    if not clean_body or len(clean_body) < 50:
        return {
            "success": False,
            "error": "Body too short",
            "intelligence": None
        }

    client = get_gemini_client()
    prompt = f"""[분석 기준 시점]: {reference_date} (Current Year: 2026)
[분석 대상 기업]: {target_company}
[기사 제목]: {title}
[기사 본문]:
{clean_body}

위 기사를 정밀 분석하여 지정된 UniversalIntelligence v2.3 JSON 규격으로 구조화 인텔리전스를 출력하세요."""

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
        parsed_json["reference_date"] = reference_date
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
