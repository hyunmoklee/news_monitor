import sqlite3
import json
import sys

try:
    sys.stdout.reconfigure(encoding='utf-8')
except:
    pass

conn = sqlite3.connect("news_monitor.db")
conn.row_factory = sqlite3.Row
cur = conn.cursor()

cur.execute("""
    SELECT a.url, a.title, a.media_name, a.published_at, a.structured_intelligence, a.event_category, a.thread_id,
           t.thread_title
    FROM articles a
    LEFT JOIN article_threads t ON a.thread_id = t.thread_id
    WHERE a.is_market_news = 0 AND (a.is_exact_dup = 0 OR a.is_exact_dup IS NULL)
    ORDER BY a.thread_id, a.published_at ASC
""")
rows = cur.fetchall()
conn.close()

facts_summary = []
for r in rows:
    intel = json.loads(r["structured_intelligence"]) if r["structured_intelligence"] else {}
    facts_summary.append({
        "thread_id": r["thread_id"],
        "thread_title": r["thread_title"],
        "headline": intel.get("executive_headline", r["title"]),
        "category": intel.get("event_category", r["event_category"]),
        "bullets": intel.get("core_summary_bullets", []),
        "metrics": intel.get("key_metrics", []),
        "milestones": intel.get("timeline_milestones", []),
        "implication": intel.get("strategic_implication", ""),
        "entities": intel.get("key_entities", [])
    })

print(f"Loaded {len(facts_summary)} structured intelligence facts.")
with open("extracted_facts_for_report.json", "w", encoding="utf-8") as f:
    json.dump(facts_summary, f, ensure_ascii=False, indent=2)
print("Saved to extracted_facts_for_report.json")
