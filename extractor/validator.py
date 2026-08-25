# extractor/validator.py
from typing import Dict, Any, Optional

def validate_candidates(
    selector_result: Optional[Dict[str, Any]],
    trafilatura_std: Dict[str, Any],
    trafilatura_prec: Dict[str, Any],
    std_score: int,
    prec_score: int,
    selector_score: int = 0,
    threshold_ratio: float = 0.3,
    high_threshold: int = 85,
    low_threshold: int = 60
) -> Dict[str, Any]:
    """
    Validates candidates between Trafilatura and Site Selector.
    """
    # Determine best Trafilatura candidate
    if prec_score >= std_score and trafilatura_prec.get("success"):
        best_traf_method = "trafilatura_precision"
        best_traf_text = trafilatura_prec.get("text", "")
        best_traf_score = prec_score
    else:
        best_traf_method = "trafilatura_standard"
        best_traf_text = trafilatura_std.get("text", "")
        best_traf_score = std_score

    # Case 1: Site Selector exists
    if selector_result and selector_result.get("success"):
        selector_text = selector_result.get("body", "")
        len_sel = len(selector_text)
        len_traf = len(best_traf_text)
        max_len = max(len_sel, len_traf, 1)
        diff_ratio = abs(len_sel - len_traf) / max_len

        if diff_ratio > threshold_ratio:
            reason = f"Selector vs Trafilatura length mismatch ({round(diff_ratio * 100, 1)}% difference: selector={len_sel} chars, trafilatura={len_traf} chars)"
            return {
                "chosen_method": "site_selector",
                "chosen_text": selector_text,
                "quality_score": selector_score,
                "needs_review": True,
                "mismatch_reason": reason,
                "length_diff_ratio": diff_ratio
            }
        else:
            needs_rev = selector_score < high_threshold
            return {
                "chosen_method": "site_selector",
                "chosen_text": selector_text,
                "quality_score": selector_score,
                "needs_review": needs_rev,
                "mismatch_reason": None,
                "length_diff_ratio": diff_ratio
            }

    # Case 2: No Site Selector (Trafilatura only)
    if not best_traf_text:
        return {
            "chosen_method": "failed",
            "chosen_text": "",
            "quality_score": 0,
            "needs_review": True,
            "mismatch_reason": "All extraction methods returned empty text",
            "length_diff_ratio": 0.0
        }

    # Check if there are critical details from quality scorer (e.g. truncation, paywall)
    # Since we don't have the detail dict directly in the arguments for validation (only score),
    # we rely on the score being dropped. But let's assume if score is 0, it's a hard fail.
    # If score < 85, it's needs_review.
    needs_rev = best_traf_score < high_threshold
    mismatch_reason = None
    if best_traf_score == 0:
         mismatch_reason = "Paywall/Block or Empty extraction"
         needs_rev = True
    elif best_traf_score < low_threshold:
        mismatch_reason = f"Low quality score ({best_traf_score} < {low_threshold})"
    elif needs_rev:
        mismatch_reason = f"Moderate quality score ({best_traf_score} in {low_threshold}~{high_threshold})"

    return {
        "chosen_method": best_traf_method,
        "chosen_text": best_traf_text,
        "quality_score": best_traf_score,
        "needs_review": needs_rev,
        "mismatch_reason": mismatch_reason,
        "length_diff_ratio": 0.0
    }

