"""
audit/spot_auditor.py
84% 룰 자동확정 구간(Group A: 시황, Group B: 기업)의 침묵하는 오류(Silent Failure)를
탐지하고 모니터링하기 위한 Shadow Spot-Audit 모듈.
"""
import os
import sys
import random
import sqlite3
import asyncio
from typing import Dict, List, Tuple

try:
    sys.stdout.reconfigure(encoding='utf-8')
except Exception:
    pass

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import get_gemini_client, DEFAULT_GEMINI_MODEL, DB_PATH
from market_filter.decision import call_gemini_fallback


def init_audit_tables(db_path: str = DB_PATH):
    """audit_discrepancies 테이블 초기화"""
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS audit_discrepancies (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            audited_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            url TEXT UNIQUE,
            title TEXT,
            rule_group VARCHAR(10),        -- 'GROUP_A' (시황) 또는 'GROUP_B' (기업)
            rule_score INTEGER,            -- F1~F4 합산 룰 스코어
            llm_decision BOOLEAN,          -- LLM의 판단 (True: 시황, False: 기업)
            llm_reason TEXT,               -- LLM의 판단 근거
            status VARCHAR(20) DEFAULT 'open', -- 'open', 'reviewed', 'resolved'
            scoring_version VARCHAR(10)
        )
    """)
    conn.commit()
    conn.close()

async def run_spot_audit(
    sample_rate: float = 0.15,
    db_path: str = DB_PATH,
    config: Dict = None,
    scoring_version: str = "v1.2"
) -> Dict:
    """
    Group A(시황)와 Group B(기업)에서 sample_rate 만큼 무작위 표본을 추출하여
    Gemini 3.7 Flash와 교차 검증을 수행하고 불일치(Discrepancy)를 기록합니다.
    """
    init_audit_tables(db_path)
    if config is None:
        config = {"llm": {"model": DEFAULT_GEMINI_MODEL, "max_retries": 2}}

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    # Group A: 룰 기반 시황 확정 기사 (market_score >= 20, is_market_news = 1, llm_status != 'success')
    cur.execute("""
        SELECT url, title, body, chosen_text, market_score, is_market_news 
        FROM articles 
        WHERE market_score >= 20 AND is_market_news = 1 AND (llm_status IS NULL OR llm_status != 'success')
    """)
    group_a_rows = cur.fetchall()

    # Group B: 룰 기반 기업 확정 기사 (market_score <= -20, is_market_news = 0, llm_status != 'success')
    cur.execute("""
        SELECT url, title, body, chosen_text, market_score, is_market_news 
        FROM articles 
        WHERE market_score <= -20 AND is_market_news = 0 AND (llm_status IS NULL OR llm_status != 'success')
    """)
    group_b_rows = cur.fetchall()
    conn.close()

    # 무작위 샘플링
    sample_a = random.sample(group_a_rows, max(1, int(len(group_a_rows) * sample_rate))) if group_a_rows else []
    sample_b = random.sample(group_b_rows, max(1, int(len(group_b_rows) * sample_rate))) if group_b_rows else []

    total_sampled = len(sample_a) + len(sample_b)
    print(f"\n🔍 [Shadow Spot-Audit] Auditing {total_sampled} articles ({sample_rate*100:.0f}% sample rate)...")
    print(f"  - Group A (Rule Market) Sampled : {len(sample_a)} / {len(group_a_rows)} rows")
    print(f"  - Group B (Rule Company) Sampled: {len(sample_b)} / {len(group_b_rows)} rows")

    discrepancies = []
    matches = 0

    # 1. Group A 감사 (룰은 시황(True)이라고 확정함)
    for r in sample_a:
        title = r["title"]
        lead = (r["body"] or r["chosen_text"] or "")[:300]
        is_mkt, status = await call_gemini_fallback(title, lead, config)
        
        if status == "success":
            # 룰: True, LLM: False 이면 불일치(Rule False Negative: 기업 핵심 기사를 시황으로 버렸을 위험)
            if is_mkt is False:
                discrepancies.append({
                    "url": r["url"],
                    "title": title,
                    "rule_group": "GROUP_A",
                    "rule_score": r["market_score"],
                    "llm_decision": is_mkt,
                    "llm_reason": "LLM judged as Company Core News while Rule classified as Market News (Silent FN Risk)",
                    "scoring_version": scoring_version
                })
            else:
                matches += 1

    # 2. Group B 감사 (룰은 기업(False)이라고 확정함)
    for r in sample_b:
        title = r["title"]
        lead = (r["body"] or r["chosen_text"] or "")[:300]
        is_mkt, status = await call_gemini_fallback(title, lead, config)
        
        if status == "success":
            # 룰: False, LLM: True 이면 불일치(Rule False Positive: 시황 기사가 기업 뉴스로 오염되었을 위험)
            if is_mkt is True:
                discrepancies.append({
                    "url": r["url"],
                    "title": title,
                    "rule_group": "GROUP_B",
                    "rule_score": r["market_score"],
                    "llm_decision": is_mkt,
                    "llm_reason": "LLM judged as Market News while Rule classified as Company Core News (Silent FP Risk)",
                    "scoring_version": scoring_version
                })
            else:
                matches += 1

    # DB에 불일치 항목 적재
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    for d in discrepancies:
        cur.execute("""
            INSERT OR REPLACE INTO audit_discrepancies 
            (audited_at, url, title, rule_group, rule_score, llm_decision, llm_reason, status, scoring_version)
            VALUES (CURRENT_TIMESTAMP, ?, ?, ?, ?, ?, ?, 'open', ?)
        """, (d["url"], d["title"], d["rule_group"], d["rule_score"], d["llm_decision"], d["llm_reason"], d["scoring_version"]))
    conn.commit()
    conn.close()

    valid_audits = matches + len(discrepancies)
    disc_rate = (len(discrepancies) / valid_audits * 100) if valid_audits > 0 else 0.0

    print(f"\n📊 [Spot-Audit Result]")
    print(f"  - Total Audited  : {valid_audits} articles")
    print(f"  - Rule-LLM Match : {matches} articles ({100 - disc_rate:.1f}%)")
    print(f"  - Discrepancies  : {len(discrepancies)} articles ({disc_rate:.1f}%)")

    return {
        "total_sampled": total_sampled,
        "valid_audits": valid_audits,
        "matches": matches,
        "discrepancies_count": len(discrepancies),
        "discrepancy_rate": disc_rate,
        "discrepancies": discrepancies
    }
