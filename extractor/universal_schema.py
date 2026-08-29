# extractor/universal_schema.py
"""
Universal Enterprise Intelligence Schema (v2.0)
- Covers any industry (Semiconductor, Heavy Industry, Bio, Tech/Platform, Finance, etc.)
- Strict 7 Fixed Top-Level Keys
- 5W1H + Strategic Impact Mapping
"""
from typing import List, Optional, Literal
from pydantic import BaseModel, Field

class KeyMetricItem(BaseModel):
    metric_name: str = Field(description="지표명 (예: 수주액, 설비투자액, HBM3E 수율, FDA 승인단계, MAU, 당기순이익, 지분율 등)")
    value: str = Field(description="수치 및 단위 (예: 9,300억 원, 95%, 4,200만 명, 26.4조 원, +15.2% 등)")
    context: Optional[str] = Field(default=None, description="지표의 세부 맥락 (예: 전년 동기 대비 58% 증가, 테라파워 공급분 등)")

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
    
    # [5] 동적 정량 지표 목록 (How Much: 어떤 산업 수치든 100% 흡수)
    key_metrics: List[KeyMetricItem] = Field(
        default_factory=list,
        description="기사 내 주요 수치/정량 팩트 목록 (금액, 비율, 기술스펙, 일정 등 없으면 빈 배열 [])"
    )
    
    # [6] 주요 일정 및 마일스톤 (When)
    timeline_milestones: List[str] = Field(
        default_factory=list,
        description="향후 주요 일정 및 날짜 (예: '2026년 4분기 양산', 없으면 빈 배열 [])"
    )
    
    # [7] 경영 전략적 시사점 (So What)
    strategic_implication: Optional[str] = Field(
        default=None,
        description="해당 기업 관점에서의 핵심 전략적 의미와 시사점 (1~2문장)"
    )
