import json
import sys

try:
    sys.stdout.reconfigure(encoding='utf-8')
except:
    pass

with open("extracted_facts_for_report.json", "r", encoding="utf-8") as f:
    facts = json.load(f)

md_lines = []
md_lines.append("# 📊 두산에너빌리티(034020.KS) 7-Key 구조화 팩트 인텔리전스 전수 보고서 (24건)")
md_lines.append("\n> **데이터 소스**: Zero-Trust AI 뉴스 인텔리전스 파이프라인 v2.2")
md_lines.append(f"> **추출 일시**: 2026-08-30 | **분석 대상**: 기업 핵심 기사 총 {len(facts)}건\n")
md_lines.append("---\n")

current_thread_id = None

for idx, item in enumerate(facts, 1):
    tid = item.get("thread_id")
    t_title = item.get("thread_title")
    
    if tid != current_thread_id:
        current_thread_id = tid
        md_lines.append(f"## 🧵 사건 스레드 #{current_thread_id}: {t_title}\n")
    
    md_lines.append(f"### [{idx:02d}] {item.get('headline')}\n")
    md_lines.append(f"- **카테고리**: `{item.get('category')}`")
    md_lines.append(f"- **소속 사건**: `사건 #{tid}`")
    
    # Entities
    entities = item.get("entities", [])
    if entities:
        ent_str = ", ".join([f"`{e}`" for e in entities])
        md_lines.append(f"- **핵심 엔티티**: {ent_str}")
    
    # 3-Bullets
    md_lines.append("\n#### 📋 3줄 핵심 팩트 요약 (Core Summary)")
    bullets = item.get("bullets", [])
    if bullets:
        for b in bullets:
            md_lines.append(f"- {b}")
    else:
        md_lines.append("- 요약 정보 없음")
        
    # Key Metrics
    metrics = item.get("metrics", [])
    if metrics:
        md_lines.append("\n#### 💰 핵심 정량 지표 (Key Metrics)")
        md_lines.append("| 지표명 | 수치 / 단위 | 세부 맥락 및 산출 근거 |")
        md_lines.append("| :--- | :---: | :--- |")
        for m in metrics:
            m_name = m.get("metric_name", "-")
            val = m.get("value", "-")
            ctx = m.get("context", "-")
            md_lines.append(f"| **{m_name}** | `{val}` | {ctx} |")
            
    # Milestones
    milestones = item.get("milestones", [])
    if milestones:
        md_lines.append("\n#### ⏱️ 주요 마일스톤 및 일정 (Timeline Milestones)")
        for ms in milestones:
            md_lines.append(f"- {ms}")
            
    # Strategic Implication
    implication = item.get("implication", "")
    if implication:
        md_lines.append("\n#### 💡 전략적 시사점 (Strategic Implication)")
        md_lines.append(f"> {implication}")
        
    md_lines.append("\n---\n")

output_md = "\n".join(md_lines)

with open("structured_facts_full_export.md", "w", encoding="utf-8") as f:
    f.write(output_md)

print("Saved full structured facts markdown export to structured_facts_full_export.md")
