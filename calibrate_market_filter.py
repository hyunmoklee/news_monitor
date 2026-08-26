import sqlite3
import yaml
import os
import shutil

BASE_DIR = r"d:\1_MyProject\6_NaverNewsCrawler"
config_path = os.path.join(BASE_DIR, "market_filter_config.yaml")
db_path = os.path.join(BASE_DIR, "news_monitor.db")
log_path = os.path.join(BASE_DIR, "calibration_rejected_matches.log")

import sys
sys.path.insert(0, BASE_DIR)
from market_filter.company_dict import get_listed_companies
from market_filter.scoring import calculate_market_score

with open(config_path, "r", encoding="utf-8") as f:
    config = yaml.safe_load(f)

company_list = get_listed_companies()

conn = sqlite3.connect(db_path)
cur = conn.cursor()
cur.execute("SELECT url, title, body, chosen_text, published_at FROM articles ORDER BY rowid ASC LIMIT 100")
rows = cur.fetchall()
conn.close()

print(f"=== 100 Articles Calibration EDA Report ===")
print(f"Total Sample Loaded: {len(rows)} articles\n")

scores = []
with open(log_path, "w", encoding="utf-8") as rej_log:
    for i, r in enumerate(rows):
        u, t, b, ct, pub = r
        body = ct or b or ""
        score, detail = calculate_market_score(t, body, config, company_list, rejected_logger=rej_log)
        scores.append({
            "idx": i+1,
            "title": t,
            "score": score,
            "detail": detail
        })

t1 = config["thresholds"]["T1_company_cutoff"]
t2 = config["thresholds"]["T2_market_cutoff"]

all_scores = [s["score"] for s in scores]
grp_a = [s for s in scores if s["score"] < t1]
grp_b = [s for s in scores if s["score"] > t2]
grp_c = [s for s in scores if t1 <= s["score"] <= t2]

print("="*60)
print("[Score Distribution Summary]")
print(f" - Min Score: {min(all_scores)} pts")
print(f" - Max Score: {max(all_scores)} pts")
print(f" - Avg Score: {sum(all_scores)/len(all_scores):.1f} pts")
print("="*60)

print(f"\n[3-Way Group Allocation (T1={t1}, T2={t2})]")
print(f" * Group A (Company Fixed, Score < {t1}): {len(grp_a)}건 ({len(grp_a)/len(scores)*100:.1f}%)")
print(f" * Group B (Market Fixed, Score > {t2}): {len(grp_b)}건 ({len(grp_b)/len(scores)*100:.1f}%)")
print(f" * Group C (LLM Gray Zone, {t1} <= Score <= {t2}): {len(grp_c)}건 ({len(grp_c)/len(scores)*100:.1f}%)")

target_pass = 15 <= len(grp_c) <= 20
print(f"\n[Group C Target Gate (15% ~ 20%)]: {'PASS' if target_pass else 'NEEDS TUNING'}")

print("\n--- Sample Group A (Company Core News) ---")
for s in grp_a[:3]:
    print(f"  [{s['score']:+3d} pts] {s['title'][:55]}")

print("\n--- Sample Group B (Pure Market News) ---")
for s in grp_b[:3]:
    print(f"  [{s['score']:+3d} pts] {s['title'][:55]}")

print("\n--- Sample Group C (Gray Zone -> LLM Input) ---")
for s in grp_c[:5]:
    print(f"  [{s['score']:+3d} pts] {s['title'][:55]} (F1={s['detail']['F1_score']}, F2={s['detail']['F2_score']}, F3={s['detail']['F3_score']}, F4={s['detail']['F4_score']})")

print(f"\nBoundary rejection diagnostic log written to: {log_path}")


# Copy this script to root as calibrate_market_filter.py
shutil.copyfile(__file__, os.path.join(BASE_DIR, "calibrate_market_filter.py"))
