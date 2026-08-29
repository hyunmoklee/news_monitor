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

md_out = []
md_out.append("# 📦 7-Key Universal Intelligence 원본 추출 JSON 데이터 (전체 24건)\n")

for idx, r in enumerate(rows, 1):
    raw_json_str = r["structured_intelligence"] or "{}"
    parsed = json.loads(raw_json_str)
    pretty_json = json.dumps(parsed, ensure_ascii=False, indent=2)
    
    md_out.append(f"## [{idx:02d}] {r['title']}")
    md_out.append(f"- **언론사**: `{r['media_name']}` | **발행시각**: `{r['published_at']}` | **사건**: `#{r['thread_id']} ({r['thread_title']})`")
    md_out.append("```json")
    md_out.append(pretty_json)
    md_out.append("```\n")

full_raw_md = "\n".join(md_out)

with open("raw_extracted_intelligence.md", "w", encoding="utf-8") as f:
    f.write(full_raw_md)

print("Generated raw_extracted_intelligence.md")
