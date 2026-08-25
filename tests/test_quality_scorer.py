# tests/test_quality_scorer.py
import pytest
from extractor.quality_scorer import calculate_quality_score, load_scoring_config

SAMPLE_GOOD_ARTICLE = """
두산에너빌리티가 체코 신규 원전 건설 사업의 주계약 체결을 앞두고 핵심 주기기 제작 준비에 본격 착수했다.
이번 사업에서 두산에너빌리티는 증기발생기, 터빈 등 핵심 1차 계통 원전 기자재 공급을 전담하게 된다.

원전 업계에 따르면 체코 정부는 한국수력원자력을 우선협상대상자로 선정한 이후 세부 계약 협상을 순조롭게 이어가고 있다.
두산에너빌리티는 창원공장의 생산 설비를 사전 점검하고 고품질 기자재 제작을 위한 전담 태스크포스를 구성했다.

회사 관계자는 "체코 원전 프로젝트는 한국형 원전의 우수한 기술력과 시공 능력을 세계 시장에 입증하는 계기가 될 것"이라며
"철저한 품질 관리와 기한 내 납품을 통해 국가적 원전 수출 프로젝트의 성공을 적극 뒷받침하겠다"고 밝혔다.
"""

SAMPLE_NOISY_ARTICLE = """
[스폰서 광고] 지금 가입하면 50% 할인 혜택!
관련기사: 많이 본 뉴스 TOP 10
무단전재 및 재배포 금지. 저작권자 © 뉴스
구독하기 댓글 0개
"""

def test_quality_scorer_good_article():
    score, detail = calculate_quality_score(
        text=SAMPLE_GOOD_ARTICLE,
        title="두산에너빌리티, 체코 원전 주기기 제작 본격 착수",
        html="<article><div class='article-body'>content</div></article>"
    )
    assert score >= 85
    assert detail["reasonable_length"] > 0
    assert detail["paragraph_count"] > 0
    assert detail["korean_char_signal"] > 0
    assert detail["boilerplate_penalty"] == 0

def test_quality_scorer_noisy_article():
    score, detail = calculate_quality_score(
        text=SAMPLE_NOISY_ARTICLE,
        title="두산에너빌리티 소식",
        html="<div>ads</div>"
    )
    assert score < 60
    assert detail["boilerplate_penalty"] < 0
    assert detail["boilerplate_hits"] > 0

def test_quality_scorer_empty_text():
    score, detail = calculate_quality_score(text="", title="", html="")
    assert score == 0
