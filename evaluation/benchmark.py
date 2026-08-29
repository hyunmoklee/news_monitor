"""
evaluation/benchmark.py
골드 표준 평가셋(Gold Dataset) 기반의 정량적 통계 벤치마크 및 95% 신뢰구간 산출 모듈.
"""
import json
import math
import os
import sys
import sqlite3
from typing import Dict, List, Tuple

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import DB_PATH


def calculate_wilson_interval(p: float, n: int, confidence: float = 0.95) -> Tuple[float, float]:
    """Wilson Score 신뢰구간 계산 (소표본 및 극단값에 대해 정규근사보다 정확)"""
    if n == 0:
        return 0.0, 0.0
    z = 1.96 if confidence == 0.95 else 2.576 # 95% vs 99%
    denominator = 1 + z**2 / n
    centre_adjusted_probability = p + z**2 / (2 * n)
    adjusted_std_dev = math.sqrt((p * (1 - p) + z**2 / (4 * n)) / n)
    lower_bound = (centre_adjusted_probability - z * adjusted_std_dev) / denominator
    upper_bound = (centre_adjusted_probability + z * adjusted_std_dev) / denominator
    return max(0.0, lower_bound), min(1.0, upper_bound)

def evaluate_gold_dataset(
    gold_file_path: str,
    db_path: str = DB_PATH
) -> Dict:
    """
    골드셋과 DB 내의 현재 파이프라인 예측 결과(is_market_news)를 대조하여
    정밀 통계 지표를 계산합니다.
    """
    if not os.path.exists(gold_file_path):
        raise FileNotFoundError(f"Gold dataset file not found: {gold_file_path}")

    with open(gold_file_path, "r", encoding="utf-8") as f:
        gold_data = json.load(f)

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    cur.execute("SELECT url, is_market_news, market_score, llm_status, scoring_version FROM articles")
    db_articles = {r["url"]: r for r in cur.fetchall()}
    conn.close()

    tp = 0 # True Market (Actual Market, Pred Market)
    fp = 0 # False Market (Actual Company, Pred Market)
    tn = 0 # True Company (Actual Company, Pred Company)
    fn = 0 # False Company (Actual Market, Pred Company)
    
    rule_evaluated = 0
    rule_correct = 0
    llm_evaluated = 0
    llm_correct = 0
    
    matched_items = 0
    unmatched_items = 0

    for item in gold_data:
        url = item.get("url")
        actual_label = item.get("ground_truth_class") # "MARKET" 또는 "COMPANY_CORE"
        actual_is_mkt = (actual_label == "MARKET")

        pred_row = db_articles.get(url)
        if not pred_row:
            unmatched_items += 1
            continue

        matched_items += 1
        pred_is_mkt = bool(pred_row["is_market_news"])
        is_llm_judged = (pred_row["llm_status"] == "success")

        # Confusion Matrix
        if actual_is_mkt and pred_is_mkt:
            tp += 1
        elif not actual_is_mkt and pred_is_mkt:
            fp += 1
        elif not actual_is_mkt and not pred_is_mkt:
            tn += 1
        elif actual_is_mkt and not pred_is_mkt:
            fn += 1

        # Section-wise breakdown
        if is_llm_judged:
            llm_evaluated += 1
            if actual_is_mkt == pred_is_mkt:
                llm_correct += 1
        else:
            rule_evaluated += 1
            if actual_is_mkt == pred_is_mkt:
                rule_correct += 1

    total = tp + fp + tn + fn
    accuracy = (tp + tn) / total if total > 0 else 0.0
    
    # Metrics for Company Core News (Class = Negative / False)
    company_total_actual = tn + fp
    company_precision = tn / (tn + fn) if (tn + fn) > 0 else 0.0
    company_recall = tn / company_total_actual if company_total_actual > 0 else 0.0
    company_f1 = (2 * company_precision * company_recall / (company_precision + company_recall)) if (company_precision + company_recall) > 0 else 0.0

    # Metrics for Market News (Class = Positive / True)
    market_total_actual = tp + fn
    market_precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
    market_recall = tp / market_total_actual if market_total_actual > 0 else 0.0
    market_f1 = (2 * market_precision * market_recall / (market_precision + market_recall)) if (market_precision + market_recall) > 0 else 0.0

    # Confidence Intervals (95%)
    acc_ci_low, acc_ci_high = calculate_wilson_interval(accuracy, total)
    comp_prec_ci_low, comp_prec_ci_high = calculate_wilson_interval(company_precision, tn + fn)
    comp_rec_ci_low, comp_rec_ci_high = calculate_wilson_interval(company_recall, company_total_actual)

    rule_acc = rule_correct / rule_evaluated if rule_evaluated > 0 else 0.0
    llm_acc = llm_correct / llm_evaluated if llm_evaluated > 0 else 0.0

    report = {
        "total_gold_samples": len(gold_data),
        "evaluated_samples": total,
        "unmatched_samples": unmatched_items,
        "confusion_matrix": {
            "TP (Market->Market)": tp,
            "FP (Company->Market)": fp,
            "TN (Company->Company)": tn,
            "FN (Market->Company)": fn
        },
        "overall_accuracy": accuracy,
        "accuracy_95ci": (acc_ci_low, acc_ci_high),
        "company_news": {
            "precision": company_precision,
            "precision_95ci": (comp_prec_ci_low, comp_prec_ci_high),
            "recall": company_recall,
            "recall_95ci": (comp_rec_ci_low, comp_rec_ci_high),
            "f1_score": company_f1
        },
        "market_news": {
            "precision": market_precision,
            "recall": market_recall,
            "f1_score": market_f1
        },
        "section_breakdown": {
            "rule_auto_section": {
                "count": rule_evaluated,
                "accuracy": rule_acc
            },
            "llm_grayzone_section": {
                "count": llm_evaluated,
                "accuracy": llm_acc
            }
        }
    }

    return report
