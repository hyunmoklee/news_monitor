# tests/test_validator.py
import pytest
from extractor.validator import validate_candidates

def test_validator_consistent():
    std = {"text": "두산에너빌리티 원전 수주 본문입니다. " * 20, "success": True}
    prec = {"text": "두산에너빌리티 원전 수주 본문입니다. " * 20, "success": True}
    sel = {"body": "두산에너빌리티 원전 수주 본문입니다. " * 20, "success": True}
    
    result = validate_candidates(
        selector_result=sel,
        trafilatura_std=std,
        trafilatura_prec=prec,
        std_score=90,
        prec_score=90,
        selector_score=90,
        threshold_ratio=0.3
    )
    assert result["chosen_method"] == "site_selector"
    assert result["needs_review"] is False
    assert result["mismatch_reason"] is None

def test_validator_mismatch_detected():
    std = {"text": "두산에너빌리티 원전 수주 본문입니다. " * 50, "success": True}
    prec = {"text": "두산에너빌리티 원전 수주 본문입니다. " * 50, "success": True}
    sel = {"body": "짧은 텍스트", "success": True}
    
    result = validate_candidates(
        selector_result=sel,
        trafilatura_std=std,
        trafilatura_prec=prec,
        std_score=88,
        prec_score=88,
        selector_score=40,
        threshold_ratio=0.3
    )
    assert result["needs_review"] is True
    assert "length mismatch" in result["mismatch_reason"]
