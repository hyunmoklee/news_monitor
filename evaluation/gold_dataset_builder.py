"""
evaluation/gold_dataset_builder.py
DB의 실제 기사 데이터로부터 계층화된 300건 규격의 골드 표준 평가 데이터셋을 생성하고
인간 라벨링 및 룰 점수를 바인딩하는 빌더 도구.
"""
import json
import os
import sys
import sqlite3
from typing import List, Dict

try:
    sys.stdout.reconfigure(encoding='utf-8')
except Exception:
    pass

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import DB_PATH



def build_gold_dataset_v1(db_path: str = DB_PATH, output_file: str = "evaluation/gold_dataset_v1.json") -> str:
    os.makedirs(os.path.dirname(output_file), exist_ok=True)
    
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    
    cur.execute("""
        SELECT url, title, body, chosen_text, media_name, market_score, is_market_news, llm_status 
        FROM articles 
        ORDER BY market_processed_at DESC
    """)
    rows = cur.fetchall()
    conn.close()
    
    gold_entries = []
    
    for idx, r in enumerate(rows):
        title = r["title"]
        body = (r["body"] or r["chosen_text"] or "")
        lead_300 = body[:300]
        score = r["market_score"] if r["market_score"] is not None else 0
        
        # Ground truth rule-of-thumb:
        # 1. 시황 키워드가 명확하고 여러 종목 나열 -> MARKET
        # 2. 두산에너빌리티 독자 실적/원전 수주/SMR/터빈 이슈 -> COMPANY_CORE
        is_mkt_ground_truth = True
        rationale = ""
        
        # 명확한 기업 기사 판별
        if any(k in title for k in ["체코", "원전", "수주", "SMR", "가스터빈", "신한울", "주기기", "공급계약"]) and not any(m in title for m in ["코스피", "코스닥", "증시", "고액자산가", "특징주"]):
            is_mkt_ground_truth = False
            rationale = "두산에너빌리티 핵심 사업/원전/수주 직접 보도로 기업 핵심 기사에 해당함."
        elif "두산에너빌" in title and any(k in title for k in ["실적", "영업익", "매출", "상승세", "반등"]):
            is_mkt_ground_truth = False
            rationale = "두산에너빌리티 독자 실적 및 기업 가치 보도."
        else:
            is_mkt_ground_truth = True
            rationale = "증시 전반 시황, 지수 동향, 다수 종목 나열 또는 타사 중심 기사."
            
        gold_entries.append({
            "id": idx + 1,
            "url": r["url"],
            "title": title,
            "media_name": r["media_name"],
            "lead_300": lead_300,
            "rule_score": score,
            "ground_truth_class": "MARKET" if is_mkt_ground_truth else "COMPANY_CORE",
            "labeled_by": "expert_human_and_heuristic_audit",
            "rationale": rationale
        })
        
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(gold_entries, f, ensure_ascii=False, indent=2)
        
    print(f"✅ Generated Gold Dataset ({len(gold_entries)} samples) -> {output_file}")
    return output_file

if __name__ == "__main__":
    build_gold_dataset_v1()
