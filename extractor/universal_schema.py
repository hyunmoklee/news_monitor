# extractor/universal_schema.py
"""
Universal Enterprise Intelligence Schema (v2.3)
- Covers any industry (Semiconductor, Heavy Industry, Bio, Tech/Platform, Finance, etc.)
- Strict 7 Fixed Top-Level Keys + Quantitative Standardization
- 3-Tier Fact Verification Level (CONFIRMED / ESTIMATE / UNCONFIRMED_RUMOR)
- Temporal Guardrail (Standardized target_period & reference_date)
"""
from typing import List, Optional, Literal
from pydantic import BaseModel, Field

class KeyMetricItem(BaseModel):
    metric_name: str = Field(
        description="지표명 (예: 목표주가, 연간매출전망, 연간영업익전망, 공장가동률, 신규원전수량, 수주목표 등)"
    )
    raw_numeric_value: Optional[float] = Field(
        default=None,
        description="정량 수치값 (숫자만 추출, 예: 140000, 19.0, 1.2, 80.0, 10.55, 10.0 등. 단위가 억원/조원이면 해당 단위 기준 실수)"
    )
    unit: str = Field(
        default="",
        description="수치 단위 (예: 원, KRW, %, 억원, 조원, MW, GW, 기, 시간, 주)"
    )
    formatted_value: str = Field(
        description="가독성 서식 표기 (예: 140,000원, +10.55%, 19조 원, 1조 2,000억 원, 80.0%, 10기)"
    )
    target_period: Optional[str] = Field(
        default=None,
        description="대상 시점/기간 (예: 2026E, 2026년 상반기, 2029년, 2030년대 중반. 과거 연도 오타는 실질 대상 기간으로 정규화)"
    )
    confidence_level: Literal["CONFIRMED", "ESTIMATE", "UNCONFIRMED_RUMOR"] = Field(
        default="CONFIRMED",
        description="팩트 신뢰도 등급: CONFIRMED(정부/기업 공식발표·공시·실적), ESTIMATE(증권사 추정치·목표가·가이던스), UNCONFIRMED_RUMOR(막후 협상·풍문·공식부인·단독보도)"
    )
    source_entity: Optional[str] = Field(
        default=None,
        description="수치 출처 기관/발행처 (예: KB증권, 한국투자증권, 금융감독원, 미국 에너지부)"
    )
    context: Optional[str] = Field(
        default=None,
        description="지표의 세부 맥락 및 비고 (예: 전년 대비 58.2% 증가, 전일 종가 대비 +91.8% 상승여력)"
    )

class UniversalIntelligence(BaseModel):
    # [1] C-Level 헤드라인 (Who + What)
    executive_headline: str = Field(
        description="C-Level 경영진용 1줄 핵심 헤드라인 (수식어 배제, 팩트 중심 35자 내외)"
    )
    
    # [2] 경영진 3줄 요약 (Why + How)
    core_summary_bullets: List[str] = Field(
        description="경영진 보고용 2~3줄 핵심 요약 불릿 (각 문장에 번호 매김, 예: '1. ...', '2. ...')"
    )
    
    # [3] 8대 표준 비즈니스 카테고리
    event_category: Literal[
        "수주/계약",
        "실적/재무",
        "신제품/기술",
        "인허가/승인",
        "설비투자/M&A",
        "리스크/규제",
        "지배구조/인사",
        "경영일반/기타"
    ] = Field(description="기사의 8대 표준 비즈니스 사건 유형 분류")
    
    # [4] 핵심 관련 주체 (Entities: Who)
    key_entities: List[str] = Field(
        default_factory=list,
        description="기사에 등장하는 주요 관련 기업/기관명 (표준 명칭으로 정규화, 없으면 빈 배열 [])"
    )
    
    # [5] 동적 정량 지표 목록 (How Much: 표준화된 정량 지표)
    key_metrics: List[KeyMetricItem] = Field(
        default_factory=list,
        description="기사 내 주요 수치/정량 팩트 목록 (금액, 비율, 기술스펙, 목표가 등 없으면 빈 배열 [])"
    )
    
    # [6] 주요 일정 및 마일스톤 (When)
    timeline_milestones: List[str] = Field(
        default_factory=list,
        description="향후 주요 일정 및 날짜 (예: '2026년 4분기 양산', '2029년 준공', 없으면 빈 배열 [])"
    )
    
    # [7] 경영 전략적 시사점 (So What)
    strategic_implication: Optional[str] = Field(
        default=None,
        description="해당 기업 관점에서의 핵심 전략적 의미와 시사점 (1~2문장)"
    )
    
    # [Metadata] 시점 앵커링
    reference_date: str = Field(
        default="2026-08-25",
        description="인텔리전스 추출 기준 시점"
    )
