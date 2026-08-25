# build_dashboard.py
import sqlite3
import os
import json
from config import DB_PATH

def clean_kw(k):
    return (k or "").replace('"', '').strip()

def generate_dashboard(target_keyword=None, out_filename="index.html"):
    clean_target_kw = clean_kw(target_keyword)
    display_name = clean_target_kw or "전체 기업"
    print(f"Generating Comprehensive Dashboard for [{display_name}] -> docs/{out_filename}...")
    
    if not os.path.exists(DB_PATH):
        print(f"Error: Database not found at {DB_PATH}")
        return

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    # 1. Fetch RAWDATA & Extracted Articles
    cursor.execute("""
        SELECT url, title, media_name, journalist, author, body, chosen_text, keyword, 
               raw_html, raw_html_hash, publisher_domain, pipeline_version, 
               extraction_method, quality_score, quality_score_detail, 
               needs_review, mismatch_reason, published_at, created_at, processed_at
        FROM articles 
        ORDER BY published_at DESC, created_at DESC
    """)
    
    raw_articles = []
    extracted_articles = []
    
    for row in cursor.fetchall():
        r_dict = dict(row)
        kw = clean_kw(r_dict.get("keyword"))
        
        if clean_target_kw and clean_target_kw not in kw:
            continue
            
        q_detail = {}
        try:
            q_detail = json.loads(r_dict.get("quality_score_detail") or "{}")
        except Exception:
            pass
            
        score = r_dict.get("quality_score") if r_dict.get("quality_score") is not None else 70
        needs_rev = bool(r_dict.get("needs_review", 0))
        
        item = {
            "url": r_dict.get("url") or "",
            "title": r_dict.get("title") or "",
            "media_name": r_dict.get("media_name") or r_dict.get("publisher_domain") or "알 수 없음",
            "journalist": r_dict.get("journalist") or r_dict.get("author") or "알 수 없음",
            "body": r_dict.get("chosen_text") or r_dict.get("body") or "",
            "raw_body": r_dict.get("body") or "",
            "keyword": kw or "기타",
            "published_at": r_dict.get("published_at") or "-",
            "created_at": r_dict.get("created_at") or "-",
            "pipeline_version": r_dict.get("pipeline_version") or "v1.0.0",
            "extraction_method": r_dict.get("extraction_method") or "legacy_extracted",
            "quality_score": score,
            "quality_score_detail": q_detail,
            "needs_review": needs_rev,
            "mismatch_reason": r_dict.get("mismatch_reason") or ("품질 점수 미달 (85점 미만)" if needs_rev else "정상 추출"),
            "has_raw_html": bool(r_dict.get("raw_html")),
            "raw_html_hash": r_dict.get("raw_html_hash") or "-"
        }
        raw_articles.append(item)
        extracted_articles.append(item)

    raw_total = len(raw_articles)
    extract_total = len(extracted_articles)
    extract_needs_review = sum(1 for a in extracted_articles if a["needs_review"])
    extract_scores = [a["quality_score"] for a in extracted_articles if a["quality_score"] is not None]
    extract_avg_score = round(sum(extract_scores) / len(extract_scores), 1) if extract_scores else 0.0

    # 2. Fetch DATA PREPROCESSING RESULT (processed_articles)
    cursor.execute("""
        SELECT url, title, media_name, journalist, cleaned_body, summary, keyword, category, published_at, processed_at, extra_meta 
        FROM processed_articles 
        ORDER BY 
            CASE 
                WHEN category = 'MASTER' THEN 1 
                WHEN category = 'DUPLICATE' THEN 2 
                ELSE 3 
            END ASC,
            published_at DESC
    """)
    
    processed_articles = []
    global_relevant_count = 0
    solo_focus_count = 0
    proc_master = 0
    proc_dup = 0
    proc_filtered = 0
    
    for row in cursor.fetchall():
        r_dict = dict(row)
        kw = clean_kw(r_dict.get("keyword"))
        
        if clean_target_kw and clean_target_kw not in kw:
            continue
            
        meta = {}
        try:
            meta = json.loads(r_dict.get("extra_meta") or "{}")
        except Exception:
            pass
            
        cat = r_dict.get("category") or "일반"
        if cat == "MASTER": proc_master += 1
        elif cat == "DUPLICATE": proc_dup += 1
        elif cat == "FILTERED": proc_filtered += 1
            
        global_eval = meta.get("global_eval", {})
        is_global = global_eval.get("is_global_relevant", False)
        if is_global:
            global_relevant_count += 1
            
        focus_eval = meta.get("focus_eval", {})
        focus_type = focus_eval.get("focus_type", "PRIMARY_FOCUS")
        if focus_type == "EXCLUSIVE_SOLO":
            solo_focus_count += 1
            
        processed_articles.append({
            "url": r_dict.get("url") or "",
            "title": r_dict.get("title") or "",
            "media_name": r_dict.get("media_name") or "알 수 없음",
            "journalist": r_dict.get("journalist") or "알 수 없음",
            "cleaned_body": r_dict.get("cleaned_body") or "",
            "summary": r_dict.get("summary") or "",
            "keyword": kw or "기타",
            "category": cat,
            "published_at": r_dict.get("published_at") or "-",
            "created_at": r_dict.get("processed_at") or "-",
            "status": meta.get("status", cat),
            "value_score": meta.get("value_score", 0.0),
            "cluster_id": meta.get("cluster_id", "-"),
            "final_decision": meta.get("final_decision", cat),
            "final_reason": meta.get("final_reason", r_dict.get("summary")),
            "global_eval": global_eval,
            "global_score": global_eval.get("global_score", 0),
            "is_global_relevant": is_global,
            "focus_eval": focus_eval,
            "focus_score": focus_eval.get("focus_score", 0),
            "focus_type": focus_type,
            "audit_trail": meta
        })
        
    proc_total = len(processed_articles)
    conn.close()
    
    raw_articles_json = json.dumps(raw_articles, ensure_ascii=False)
    proc_articles_json = json.dumps(processed_articles, ensure_ascii=False)
    extract_articles_json = json.dumps(extracted_articles, ensure_ascii=False)
    
    brand_icon = "fa-microchip" if "SK" in display_name else "fa-bolt-lightning"
    
    html_content = f"""<!DOCTYPE html>
<html lang="ko">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{display_name} 뉴스 모니터링 & 정제 검증 대시보드</title>
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com">
    <link href="https://fonts.googleapis.com/css2?family=Pretendard:wght@300;400;500;600;700;800&display=swap" rel="stylesheet">
    <style>
        :root {{
            --bg-primary: #0f172a;
            --bg-secondary: #1e293b;
            --bg-card: #1e293b;
            --bg-card-hover: #26334d;
            --text-primary: #f8fafc;
            --text-secondary: #94a3b8;
            --text-muted: #64748b;
            --accent: #38bdf8;
            --accent-hover: #0ea5e9;
            --accent-glow: rgba(56, 189, 248, 0.25);
            --proc-accent: #a855f7;
            --extract-accent: #06b6d4;
            --master-color: #10b981;
            --master-bg: rgba(16, 185, 129, 0.15);
            --solo-color: #14b8a6;
            --solo-bg: rgba(20, 184, 166, 0.15);
            --global-color: #3b82f6;
            --global-bg: rgba(59, 130, 246, 0.15);
            --dup-color: #f59e0b;
            --dup-bg: rgba(245, 158, 11, 0.15);
            --filtered-color: #ef4444;
            --filtered-bg: rgba(239, 68, 68, 0.15);
            --border: #334155;
            --radius-sm: 6px;
            --radius-md: 10px;
            --radius-lg: 16px;
        }}

        * {{
            box-sizing: border-box;
            margin: 0;
            padding: 0;
            font-family: 'Pretendard', -apple-system, BlinkMacSystemFont, system-ui, Roboto, sans-serif;
        }}

        body {{
            background-color: var(--bg-primary);
            color: var(--text-primary);
            line-height: 1.6;
            min-height: 100vh;
            display: flex;
            flex-direction: column;
        }}

        header {{
            background: linear-gradient(180deg, rgba(30, 41, 59, 0.98) 0%, rgba(15, 23, 42, 0.98) 100%);
            border-bottom: 1px solid var(--border);
            padding: 1.1rem 2rem;
            backdrop-filter: blur(10px);
            position: sticky;
            top: 0;
            z-index: 100;
        }}

        .header-container {{
            max-width: 1600px;
            margin: 0 auto;
            display: flex;
            justify-content: space-between;
            align-items: center;
            flex-wrap: wrap;
            gap: 1rem;
        }}

        .brand {{
            display: flex;
            align-items: center;
            gap: 0.85rem;
        }}

        .brand-icon {{
            background: linear-gradient(135deg, #38bdf8 0%, #3b82f6 100%);
            color: white;
            width: 42px;
            height: 42px;
            border-radius: var(--radius-md);
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 1.3rem;
            box-shadow: 0 0 18px var(--accent-glow);
        }}

        .brand-text h1 {{
            font-size: 1.25rem;
            font-weight: 800;
            letter-spacing: -0.5px;
        }}

        .brand-text p {{
            font-size: 0.8rem;
            color: var(--text-secondary);
        }}

        .container {{
            max-width: 1600px;
            margin: 1.5rem auto;
            padding: 0 1.5rem;
            flex: 1;
            width: 100%;
        }}

        /* Pipeline Tabs */
        .pipeline-tabs {{
            display: flex;
            gap: 0.75rem;
            margin-bottom: 1.5rem;
            border-bottom: 1px solid var(--border);
            padding-bottom: 0.75rem;
            flex-wrap: wrap;
        }}

        .tab-btn {{
            padding: 0.7rem 1.3rem;
            border-radius: var(--radius-md);
            border: 1px solid var(--border);
            background: var(--bg-card);
            color: var(--text-secondary);
            font-size: 0.92rem;
            font-weight: 700;
            cursor: pointer;
            display: flex;
            align-items: center;
            gap: 0.6rem;
            transition: all 0.2s ease;
        }}

        .tab-btn:hover {{
            background: var(--bg-card-hover);
            color: var(--text-primary);
        }}

        .tab-btn.active {{
            background: linear-gradient(135deg, rgba(56, 189, 248, 0.2) 0%, rgba(168, 85, 247, 0.2) 100%);
            border-color: var(--accent);
            color: var(--text-primary);
            box-shadow: 0 0 15px rgba(56, 189, 248, 0.25);
        }}

        .tab-badge {{
            padding: 0.15rem 0.55rem;
            border-radius: 12px;
            font-size: 0.75rem;
            background: rgba(255,255,255,0.12);
        }}

        /* Summary Grid */
        .summary-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(210px, 1fr));
            gap: 1rem;
            margin-bottom: 1.5rem;
        }}

        .summary-card {{
            background-color: var(--bg-card);
            border: 1px solid var(--border);
            border-radius: var(--radius-lg);
            padding: 1.1rem 1.2rem;
            display: flex;
            align-items: center;
            gap: 0.9rem;
            transition: transform 0.2s ease;
        }}

        .summary-icon {{
            width: 44px;
            height: 44px;
            border-radius: var(--radius-md);
            background: rgba(56, 189, 248, 0.1);
            color: var(--accent);
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 1.25rem;
            flex-shrink: 0;
        }}

        .summary-info .label {{
            font-size: 0.75rem;
            color: var(--text-secondary);
            font-weight: 500;
            margin-bottom: 0.15rem;
        }}

        .summary-info .value {{
            font-size: 1.15rem;
            font-weight: 800;
            color: var(--text-primary);
        }}

        /* Control Panel */
        .control-panel {{
            background-color: var(--bg-card);
            border: 1px solid var(--border);
            border-radius: var(--radius-lg);
            padding: 1rem 1.5rem;
            margin-bottom: 1.5rem;
            display: flex;
            justify-content: space-between;
            align-items: center;
            flex-wrap: wrap;
            gap: 1rem;
        }}

        .search-box {{
            display: flex;
            align-items: center;
            background: rgba(15, 23, 42, 0.7);
            border: 1px solid var(--border);
            border-radius: var(--radius-md);
            padding: 0.5rem 0.9rem;
            width: 340px;
        }}

        .search-box input {{
            background: transparent;
            border: none;
            color: var(--text-primary);
            font-size: 0.88rem;
            outline: none;
            width: 100%;
            margin-left: 0.5rem;
        }}

        .filter-group {{
            display: flex;
            gap: 0.5rem;
            flex-wrap: wrap;
        }}

        .filter-btn {{
            padding: 0.45rem 0.9rem;
            background: rgba(15, 23, 42, 0.7);
            border: 1px solid var(--border);
            border-radius: var(--radius-md);
            color: var(--text-secondary);
            font-size: 0.84rem;
            font-weight: 600;
            cursor: pointer;
            transition: all 0.15s ease;
        }}

        .filter-btn:hover, .filter-btn.active {{
            background: var(--accent);
            color: #0f172a;
            border-color: var(--accent);
            font-weight: 700;
        }}

        /* Card Grid View (Processed Results) */
        .cards-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(460px, 1fr));
            gap: 1.25rem;
        }}

        .article-card {{
            background-color: var(--bg-card);
            border: 1px solid var(--border);
            border-radius: var(--radius-lg);
            padding: 1.35rem;
            display: flex;
            flex-direction: column;
            gap: 0.85rem;
            transition: all 0.2s ease;
        }}

        .article-card:hover {{
            border-color: rgba(56, 189, 248, 0.4);
            transform: translateY(-2px);
            box-shadow: 0 8px 25px rgba(0,0,0,0.3);
        }}

        .card-header {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            flex-wrap: wrap;
            gap: 0.5rem;
        }}

        .cat-badge {{
            padding: 0.25rem 0.65rem;
            border-radius: 6px;
            font-size: 0.78rem;
            font-weight: 800;
            display: inline-flex;
            align-items: center;
            gap: 0.35rem;
        }}
        .cat-master {{ background: var(--master-bg); color: var(--master-color); border: 1px solid rgba(16,185,129,0.35); }}
        .cat-dup {{ background: var(--dup-bg); color: var(--dup-color); border: 1px solid rgba(245,158,11,0.35); }}
        .cat-filtered {{ background: var(--filtered-bg); color: var(--filtered-color); border: 1px solid rgba(239,68,68,0.35); }}

        .card-title {{
            font-size: 1.05rem;
            font-weight: 700;
            line-height: 1.45;
        }}

        .card-title a {{
            color: var(--text-primary);
            text-decoration: none;
            transition: color 0.15s;
        }}

        .card-title a:hover {{
            color: var(--accent);
        }}

        .card-meta {{
            display: flex;
            gap: 0.8rem;
            font-size: 0.82rem;
            color: var(--text-secondary);
            flex-wrap: wrap;
        }}

        .summary-box {{
            background: rgba(15, 23, 42, 0.6);
            border-left: 3px solid var(--accent);
            border-radius: 4px;
            padding: 0.85rem;
            font-size: 0.88rem;
            color: #cbd5e1;
            line-height: 1.6;
        }}

        .body-accordion {{
            margin-top: 0.5rem;
            border-top: 1px solid var(--border);
            padding-top: 0.75rem;
        }}

        .btn-toggle-body {{
            background: transparent;
            border: 1px solid var(--border);
            color: var(--text-secondary);
            padding: 0.4rem 0.8rem;
            border-radius: var(--radius-sm);
            font-size: 0.8rem;
            font-weight: 600;
            cursor: pointer;
            width: 100%;
            display: flex;
            align-items: center;
            justify-content: center;
            gap: 0.4rem;
            transition: all 0.15s;
        }}

        .btn-toggle-body:hover {{
            background: rgba(255,255,255,0.05);
            color: var(--text-primary);
            border-color: var(--accent);
        }}

        .body-full-content {{
            display: none;
            background: rgba(15, 23, 42, 0.8);
            border: 1px solid var(--border);
            border-radius: var(--radius-md);
            padding: 1rem;
            margin-top: 0.6rem;
            font-size: 0.85rem;
            line-height: 1.7;
            max-height: 300px;
            overflow-y: auto;
            white-space: pre-wrap;
            color: #e2e8f0;
        }}

        /* Table (Extraction & Raw) */
        .table-container {{
            background-color: var(--bg-card);
            border: 1px solid var(--border);
            border-radius: var(--radius-lg);
            overflow: hidden;
            box-shadow: 0 4px 20px rgba(0,0,0,0.25);
        }}

        .table-header-title {{
            padding: 1.15rem 1.5rem;
            border-bottom: 1px solid var(--border);
            display: flex;
            justify-content: space-between;
            align-items: center;
        }}

        .table-header-title h2 {{
            font-size: 1.05rem;
            font-weight: 700;
            display: flex;
            align-items: center;
            gap: 0.5rem;
        }}

        .table-responsive {{
            width: 100%;
            overflow-x: auto;
        }}

        table {{
            width: 100%;
            border-collapse: collapse;
            text-align: left;
            table-layout: fixed;
        }}

        th {{
            background-color: rgba(15, 23, 42, 0.8);
            color: var(--text-secondary);
            font-size: 0.78rem;
            font-weight: 600;
            text-transform: uppercase;
            padding: 0.9rem 0.8rem;
            border-bottom: 1px solid var(--border);
            white-space: nowrap;
        }}

        td {{
            padding: 0.85rem 0.8rem;
            border-bottom: 1px solid var(--border);
            font-size: 0.86rem;
            vertical-align: middle;
            overflow: hidden;
            text-overflow: ellipsis;
            white-space: nowrap;
        }}

        tr:hover td {{
            background-color: rgba(255, 255, 255, 0.03);
        }}

        /* Badges */
        .score-badge {{
            padding: 0.2rem 0.6rem;
            border-radius: 14px;
            font-weight: 700;
            font-size: 0.78rem;
            display: inline-flex;
            align-items: center;
            gap: 0.25rem;
        }}
        .score-high {{ background: var(--master-bg); color: var(--master-color); border: 1px solid rgba(16,185,129,0.35); }}
        .score-mid {{ background: var(--dup-bg); color: var(--dup-color); border: 1px solid rgba(245,158,11,0.35); }}
        .score-low {{ background: var(--filtered-bg); color: var(--filtered-color); border: 1px solid rgba(239,68,68,0.35); }}

        .method-badge {{
            padding: 0.2rem 0.55rem;
            border-radius: 6px;
            font-size: 0.75rem;
            font-weight: 600;
            background: rgba(56, 189, 248, 0.15);
            color: var(--accent);
            border: 1px solid rgba(56, 189, 248, 0.3);
        }}

        .review-badge {{
            padding: 0.2rem 0.55rem;
            border-radius: 6px;
            font-size: 0.75rem;
            font-weight: 700;
        }}
        .review-warn {{ background: rgba(239, 68, 68, 0.15); color: #f87171; border: 1px solid rgba(239,68,68,0.3); }}
        .review-clean {{ background: rgba(16, 185, 129, 0.15); color: #34d399; border: 1px solid rgba(16,185,129,0.3); }}

        .btn-detail {{
            background: rgba(56, 189, 248, 0.12);
            border: 1px solid rgba(56, 189, 248, 0.35);
            color: var(--accent);
            padding: 0.35rem 0.8rem;
            border-radius: var(--radius-sm);
            cursor: pointer;
            font-size: 0.8rem;
            font-weight: 700;
            transition: all 0.15s;
            display: inline-flex;
            align-items: center;
            gap: 0.3rem;
        }}
        .btn-detail:hover {{ background: var(--accent); color: #0f172a; }}

        /* Modal */
        .modal-overlay {{
            position: fixed;
            top: 0; left: 0; right: 0; bottom: 0;
            background: rgba(0,0,0,0.8);
            backdrop-filter: blur(6px);
            display: none;
            align-items: center;
            justify-content: center;
            z-index: 1000;
            padding: 1.5rem;
        }}
        .modal-card {{
            background: var(--bg-secondary);
            border: 1px solid var(--border);
            border-radius: var(--radius-lg);
            width: 100%;
            max-width: 950px;
            max-height: 88vh;
            display: flex;
            flex-direction: column;
            box-shadow: 0 15px 50px rgba(0,0,0,0.6);
            overflow: hidden;
        }}
        .modal-header {{
            padding: 1.25rem 1.5rem;
            display: flex;
            justify-content: space-between;
            align-items: flex-start;
            border-bottom: 1px solid var(--border);
            background: rgba(15, 23, 42, 0.6);
        }}
        .modal-body {{
            padding: 1.5rem;
            overflow-y: auto;
            display: grid;
            grid-template-columns: 1fr 1.5fr;
            gap: 1.5rem;
        }}
        @media (max-width: 768px) {{
            .modal-body {{ grid-template-columns: 1fr; }}
            .cards-grid {{ grid-template-columns: 1fr; }}
        }}
        .modal-close {{
            background: transparent;
            border: none;
            color: var(--text-secondary);
            font-size: 1.4rem;
            cursor: pointer;
        }}
        .modal-close:hover {{ color: var(--text-primary); }}
    </style>
</head>
<body>
    <header>
        <div class="header-container">
            <div class="brand">
                <div class="brand-icon">
                    <i class="fa-solid {brand_icon}"></i>
                </div>
                <div class="brand-text">
                    <h1>{display_name} 뉴스 모니터링 & 정제 검증 대시보드</h1>
                    <p>Crawl4AI + Trafilatura Dual Mode + Quality Scoring + Preprocessing Engine (v1.0.0)</p>
                </div>
            </div>
            <div style="display:flex; gap:0.5rem;">
                <a href="index.html" style="padding:0.45rem 0.9rem; border-radius:6px; background:{'rgba(56,189,248,0.2)' if '두산' in display_name else 'rgba(255,255,255,0.05)'}; color:var(--text-primary); text-decoration:none; font-size:0.85rem; font-weight:700; border:1px solid var(--border);">
                    <i class="fa-solid fa-bolt-lightning"></i> 두산에너빌리티
                </a>
                <a href="sk_hynix.html" style="padding:0.45rem 0.9rem; border-radius:6px; background:{'rgba(56,189,248,0.2)' if 'SK' in display_name else 'rgba(255,255,255,0.05)'}; color:var(--text-primary); text-decoration:none; font-size:0.85rem; font-weight:700; border:1px solid var(--border);">
                    <i class="fa-solid fa-microchip"></i> SK하이닉스
                </a>
            </div>
        </div>
    </header>

    <div class="container">
        <!-- Pipeline Switcher Tabs -->
        <div class="pipeline-tabs">
            <button class="tab-btn active" id="tabBtnProcessed" onclick="switchTab('PROCESSED')">
                <i class="fa-solid fa-layer-group" style="color:var(--proc-accent);"></i>
                전처리 & 정밀 분석 결과 (Processed Results)
                <span class="tab-badge" id="procTabBadge">{proc_total}건</span>
            </button>
            <button class="tab-btn" id="tabBtnExtraction" onclick="switchTab('EXTRACTION')">
                <i class="fa-solid fa-wand-magic-sparkles" style="color:var(--extract-accent);"></i>
                본문 추출 & 품질 검증 (Extraction v1.0.0)
                <span class="tab-badge" id="extractTabBadge">{extract_total}건</span>
            </button>
            <button class="tab-btn" id="tabBtnRaw" onclick="switchTab('RAW')">
                <i class="fa-solid fa-database" style="color:var(--accent);"></i>
                원천 수집 데이터 (Raw Data)
                <span class="tab-badge" id="rawTabBadge">{raw_total}건</span>
            </button>
        </div>

        <!-- Summary Grid (Processed) -->
        <div id="processedSummary" class="summary-grid">
            <div class="summary-card">
                <div class="summary-icon" style="background: rgba(168, 85, 247, 0.15); color: var(--proc-accent);">
                    <i class="fa-solid fa-chart-pie"></i>
                </div>
                <div class="summary-info">
                    <div class="label">총 전처리 기사</div>
                    <div class="value">{proc_total} <span style="font-size:0.8rem; font-weight:normal;">건</span></div>
                </div>
            </div>
            <div class="summary-card" style="border-left: 3px solid var(--master-color);">
                <div class="summary-icon" style="background: var(--master-bg); color: var(--master-color);">
                    <i class="fa-solid fa-star"></i>
                </div>
                <div class="summary-info">
                    <div class="label">🌟 MASTER (핵심 기사)</div>
                    <div class="value" style="color: var(--master-color);">{proc_master} <span style="font-size:0.8rem; font-weight:normal;">건</span></div>
                </div>
            </div>
            <div class="summary-card" style="border-left: 3px solid var(--solo-color);">
                <div class="summary-icon" style="background: var(--solo-bg); color: var(--solo-color);">
                    <i class="fa-solid fa-bullseye"></i>
                </div>
                <div class="summary-info">
                    <div class="label">🎯 SOLO (단독 집중 기사)</div>
                    <div class="value" style="color: var(--solo-color);">{solo_focus_count} <span style="font-size:0.8rem; font-weight:normal;">건</span></div>
                </div>
            </div>
            <div class="summary-card" style="border-left: 3px solid var(--global-color);">
                <div class="summary-icon" style="background: var(--global-bg); color: var(--global-color);">
                    <i class="fa-solid fa-globe"></i>
                </div>
                <div class="summary-info">
                    <div class="label">🌐 GLOBAL (해외 투자추천)</div>
                    <div class="value" style="color: #60a5fa;">{global_relevant_count} <span style="font-size:0.8rem; font-weight:normal;">건</span></div>
                </div>
            </div>
            <div class="summary-card">
                <div class="summary-icon" style="background: var(--dup-bg); color: var(--dup-color);">
                    <i class="fa-solid fa-copy"></i>
                </div>
                <div class="summary-info">
                    <div class="label">📑 DUPLICATE (중복 배제)</div>
                    <div class="value" style="color: var(--dup-color);">{proc_dup} <span style="font-size:0.8rem; font-weight:normal;">건</span></div>
                </div>
            </div>
            <div class="summary-card">
                <div class="summary-icon" style="background: var(--filtered-bg); color: var(--filtered-color);">
                    <i class="fa-solid fa-filter-circle-xmark"></i>
                </div>
                <div class="summary-info">
                    <div class="label">🗑️ FILTERED (필터링)</div>
                    <div class="value" style="color: var(--filtered-color);">{proc_filtered} <span style="font-size:0.8rem; font-weight:normal;">건</span></div>
                </div>
            </div>
        </div>

        <!-- Summary Grid (Extraction) -->
        <div id="extractionSummary" class="summary-grid" style="display:none;">
            <div class="summary-card">
                <div class="summary-icon" style="background: rgba(6, 182, 212, 0.15); color: var(--extract-accent);">
                    <i class="fa-solid fa-file-lines"></i>
                </div>
                <div class="summary-info">
                    <div class="label">총 추출 기사 (v1.0.0)</div>
                    <div class="value">{extract_total} <span style="font-size:0.8rem; font-weight:normal; color:var(--text-secondary);">건</span></div>
                </div>
            </div>
            <div class="summary-card" style="border-left: 3px solid var(--master-color);">
                <div class="summary-icon" style="background: var(--master-bg); color: var(--master-color);">
                    <i class="fa-solid fa-gauge-high"></i>
                </div>
                <div class="summary-info">
                    <div class="label">평균 품질 점수 (Quality Score)</div>
                    <div class="value" style="color: var(--master-color);">{extract_avg_score} <span style="font-size:0.8rem; font-weight:normal;">/ 100점</span></div>
                </div>
            </div>
            <div class="summary-card" style="border-left: 3px solid #f87171;">
                <div class="summary-icon" style="background: rgba(239, 68, 68, 0.15); color: #f87171;">
                    <i class="fa-solid fa-triangle-exclamation"></i>
                </div>
                <div class="summary-info">
                    <div class="label">⚠️ 검토 필요 (Needs Review)</div>
                    <div class="value" style="color: #f87171;">{extract_needs_review} <span style="font-size:0.8rem; font-weight:normal;">건</span></div>
                </div>
            </div>
            <div class="summary-card" style="border-left: 3px solid var(--accent);">
                <div class="summary-icon" style="background: rgba(56, 189, 248, 0.1); color: var(--accent);">
                    <i class="fa-solid fa-code-compare"></i>
                </div>
                <div class="summary-info">
                    <div class="label">이중 추출 엔진</div>
                    <div class="value" style="font-size:0.95rem; color:var(--accent);">Trafilatura + Selector</div>
                </div>
            </div>
        </div>

        <!-- Control Panel -->
        <div class="control-panel">
            <div class="search-box">
                <i class="fa-solid fa-magnifying-glass" style="color: var(--text-muted);"></i>
                <input type="text" id="searchInput" placeholder="제목, 언론사, 기자, 핵심 내용 검색..." oninput="handleSearch()">
            </div>
            <div class="filter-group" id="procFilterGroup">
                <button class="filter-btn active" onclick="setProcFilter('ALL')">전체보기</button>
                <button class="filter-btn" onclick="setProcFilter('MASTER')">🌟 MASTER 핵심</button>
                <button class="filter-btn" onclick="setProcFilter('SOLO')">🎯 SOLO 집중</button>
                <button class="filter-btn" onclick="setProcFilter('GLOBAL')">🌐 GLOBAL</button>
                <button class="filter-btn" onclick="setProcFilter('DUPLICATE')">📑 DUPLICATE</button>
                <button class="filter-btn" onclick="setProcFilter('FILTERED')">🗑️ FILTERED</button>
            </div>
            <div class="filter-group" id="extractFilterGroup" style="display:none;">
                <button class="filter-btn active" onclick="setExtractFilter('ALL')">전체보기</button>
                <button class="filter-btn" onclick="setExtractFilter('NEEDS_REVIEW')">⚠️ 검토 필요만</button>
                <button class="filter-btn" onclick="setExtractFilter('CLEAN')">✓ 정상 추출만</button>
                <button class="filter-btn" onclick="setExtractFilter('TRAF')">Trafilatura</button>
                <button class="filter-btn" onclick="setExtractFilter('SELECTOR')">Site Selector</button>
            </div>
        </div>

        <!-- Section 1: Processed Cards Grid -->
        <div id="processedSection">
            <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:1rem;">
                <h2 style="font-size:1.1rem; font-weight:700;"><i class="fa-solid fa-sparkles" style="color:var(--proc-accent);"></i> 전처리 기사 분석 결과물</h2>
                <span class="tab-badge" id="procCountBadge">총 0건</span>
            </div>
            <div class="cards-grid" id="cardsGrid"></div>
        </div>

        <!-- Section 2: Extraction Table -->
        <div id="extractionSection" style="display:none;">
            <div class="table-container">
                <div class="table-header-title">
                    <h2>
                        <i class="fa-solid fa-wand-magic-sparkles" style="color: var(--extract-accent);"></i>
                        본문 추출 결과 및 품질 점수 검증 목록 (v1.0.0)
                    </h2>
                    <span class="tab-badge" id="extractCountBadge">총 0건</span>
                </div>
                <div class="table-responsive">
                    <table>
                        <thead>
                            <tr>
                                <th style="width: 50px; text-align: center;">No.</th>
                                <th style="width: 32%;">기사 제목 (Title)</th>
                                <th style="width: 110px; text-align: center;">언론사</th>
                                <th style="width: 130px; text-align: center;">추출 엔진</th>
                                <th style="width: 90px; text-align: center;">품질 점수</th>
                                <th style="width: 100px; text-align: center;">검토 상태</th>
                                <th style="width: 22%;">검토 / 불일치 요약</th>
                                <th style="width: 80px; text-align: center;">본문길이</th>
                                <th style="width: 90px; text-align: center;">결과물</th>
                            </tr>
                        </thead>
                        <tbody id="extractTableBody"></tbody>
                    </table>
                </div>
            </div>
        </div>

        <!-- Section 3: Raw Table -->
        <div id="rawSection" style="display:none;">
            <div class="table-container">
                <div class="table-header-title">
                    <h2><i class="fa-solid fa-database" style="color: var(--accent);"></i> 원천 수집 데이터 (Raw Articles)</h2>
                    <span class="tab-badge" id="rawCountBadge">총 0건</span>
                </div>
                <div class="table-responsive">
                    <table>
                        <thead>
                            <tr>
                                <th style="width: 50px; text-align: center;">No.</th>
                                <th>기사 제목</th>
                                <th style="width: 120px; text-align: center;">언론사</th>
                                <th style="width: 100px; text-align: center;">기자</th>
                                <th>본문 미리보기</th>
                                <th style="width: 140px; text-align: center;">발행일시</th>
                            </tr>
                        </thead>
                        <tbody id="rawTableBody"></tbody>
                    </table>
                </div>
            </div>
        </div>
    </div>

    <!-- Modal for Extracted Article Full Inspection -->
    <div class="modal-overlay" id="detailModal" onclick="if(event.target===this) closeModal()">
        <div class="modal-card">
            <div class="modal-header">
                <div style="max-width: 85%;">
                    <h3 id="modalTitle" style="font-size:1.15rem; font-weight:700; margin-bottom:0.35rem; line-height:1.4;">기사 세부 정보</h3>
                    <p id="modalMeta" style="font-size:0.82rem; color:var(--text-secondary);"></p>
                </div>
                <button class="modal-close" onclick="closeModal()"><i class="fa-solid fa-xmark"></i></button>
            </div>
            <div class="modal-body">
                <div>
                    <h4 style="color:var(--accent); font-size:0.95rem; margin-bottom:0.75rem; display:flex; align-items:center; gap:0.4rem;">
                        <i class="fa-solid fa-chart-simple"></i> Quality Score Breakdown
                    </h4>
                    <div id="modalScoreBox" style="background:rgba(15,23,42,0.6); padding:1rem; border-radius:8px; border:1px solid var(--border);"></div>
                    
                    <h4 style="color:var(--text-primary); font-size:0.95rem; margin-top:1.25rem; margin-bottom:0.5rem;">
                        <i class="fa-solid fa-circle-info"></i> 검증 메타데이터
                    </h4>
                    <div id="modalValidationBox" style="background:rgba(15,23,42,0.6); padding:1rem; border-radius:8px; font-size:0.83rem; line-height:1.6; border:1px solid var(--border); color:var(--text-secondary);"></div>
                </div>
                <div>
                    <h4 style="color:var(--master-color); font-size:0.95rem; margin-bottom:0.75rem; display:flex; align-items:center; justify-content:space-between;">
                        <span><i class="fa-solid fa-file-lines"></i> 추출된 기사 본문 전문 (Clean Body)</span>
                        <span id="modalCharCount" style="font-size:0.78rem; font-weight:normal; color:var(--text-secondary);"></span>
                    </h4>
                    <div id="modalContentBox" style="background:rgba(15,23,42,0.85); padding:1.2rem; border-radius:8px; border:1px solid var(--border); font-size:0.88rem; line-height:1.75; white-space:pre-wrap; max-height:450px; overflow-y:auto; color:#f1f5f9;"></div>
                </div>
            </div>
        </div>
    </div>

    <script>
        const rawArticles = {raw_articles_json};
        const procArticles = {proc_articles_json};
        const extractArticles = {extract_articles_json};

        let currentTab = 'PROCESSED';
        let procFilter = 'ALL';
        let extractFilter = 'ALL';
        let searchQuery = '';
        let currentExtractList = [];

        function switchTab(tab) {{
            currentTab = tab;
            document.getElementById('tabBtnProcessed').classList.toggle('active', tab === 'PROCESSED');
            document.getElementById('tabBtnExtraction').classList.toggle('active', tab === 'EXTRACTION');
            document.getElementById('tabBtnRaw').classList.toggle('active', tab === 'RAW');

            document.getElementById('processedSummary').style.display = tab === 'PROCESSED' ? 'grid' : 'none';
            document.getElementById('extractionSummary').style.display = tab === 'EXTRACTION' ? 'grid' : 'none';

            document.getElementById('procFilterGroup').style.display = tab === 'PROCESSED' ? 'flex' : 'none';
            document.getElementById('extractFilterGroup').style.display = tab === 'EXTRACTION' ? 'flex' : 'none';

            document.getElementById('processedSection').style.display = tab === 'PROCESSED' ? 'block' : 'none';
            document.getElementById('extractionSection').style.display = tab === 'EXTRACTION' ? 'block' : 'none';
            document.getElementById('rawSection').style.display = tab === 'RAW' ? 'block' : 'none';

            renderView();
        }}

        function setProcFilter(f) {{
            procFilter = f;
            document.querySelectorAll('#procFilterGroup .filter-btn').forEach(btn => {{
                btn.classList.toggle('active', 
                    (f === 'ALL' && btn.innerText.includes('전체')) ||
                    (f === 'MASTER' && btn.innerText.includes('MASTER')) ||
                    (f === 'SOLO' && btn.innerText.includes('SOLO')) ||
                    (f === 'GLOBAL' && btn.innerText.includes('GLOBAL')) ||
                    (f === 'DUPLICATE' && btn.innerText.includes('DUPLICATE')) ||
                    (f === 'FILTERED' && btn.innerText.includes('FILTERED'))
                );
            }});
            renderProcessedCards();
        }}

        function setExtractFilter(f) {{
            extractFilter = f;
            document.querySelectorAll('#extractFilterGroup .filter-btn').forEach(btn => {{
                btn.classList.toggle('active', 
                    (f === 'ALL' && btn.innerText.includes('전체')) ||
                    (f === 'NEEDS_REVIEW' && btn.innerText.includes('검토 필요')) ||
                    (f === 'CLEAN' && btn.innerText.includes('정상')) ||
                    (f === 'TRAF' && btn.innerText.includes('Trafilatura')) ||
                    (f === 'SELECTOR' && btn.innerText.includes('Selector'))
                );
            }});
            renderExtractionTable();
        }}

        function handleSearch() {{
            searchQuery = document.getElementById('searchInput').value.trim().toLowerCase();
            renderView();
        }}

        function renderView() {{
            if (currentTab === 'PROCESSED') renderProcessedCards();
            else if (currentTab === 'EXTRACTION') renderExtractionTable();
            else renderRawTable();
        }}

        function renderProcessedCards() {{
            const grid = document.getElementById('cardsGrid');
            grid.innerHTML = '';

            let list = procArticles;

            if (procFilter !== 'ALL') {{
                if (procFilter === 'MASTER') list = list.filter(a => a.category === 'MASTER');
                else if (procFilter === 'DUPLICATE') list = list.filter(a => a.category === 'DUPLICATE');
                else if (procFilter === 'FILTERED') list = list.filter(a => a.category === 'FILTERED');
                else if (procFilter === 'SOLO') list = list.filter(a => a.focus_type === 'EXCLUSIVE_SOLO');
                else if (procFilter === 'GLOBAL') list = list.filter(a => a.is_global_relevant);
            }}

            if (searchQuery) {{
                list = list.filter(a => 
                    (a.title && a.title.toLowerCase().includes(searchQuery)) ||
                    (a.media_name && a.media_name.toLowerCase().includes(searchQuery)) ||
                    (a.summary && a.summary.toLowerCase().includes(searchQuery)) ||
                    (a.cleaned_body && a.cleaned_body.toLowerCase().includes(searchQuery))
                );
            }}

            document.getElementById('procCountBadge').innerText = `총 ${{list.length}}건`;

            list.forEach((item, idx) => {{
                const card = document.createElement('div');
                card.className = 'article-card';

                const cat = item.category || 'MASTER';
                const catClass = cat === 'MASTER' ? 'cat-master' : (cat === 'DUPLICATE' ? 'cat-dup' : 'cat-filtered');
                const catIcon = cat === 'MASTER' ? 'fa-star' : (cat === 'DUPLICATE' ? 'fa-copy' : 'fa-filter');

                let tagsHtml = '';
                if (item.focus_type === 'EXCLUSIVE_SOLO') {{
                    tagsHtml += '<span style="padding:0.15rem 0.5rem; border-radius:4px; font-size:0.72rem; font-weight:700; background:var(--solo-bg); color:var(--solo-color); border:1px solid rgba(20,184,166,0.3);">🎯 SOLO 단독</span> ';
                }}
                if (item.is_global_relevant) {{
                    tagsHtml += '<span style="padding:0.15rem 0.5rem; border-radius:4px; font-size:0.72rem; font-weight:700; background:var(--global-bg); color:#60a5fa; border:1px solid rgba(59,130,246,0.3);">🌐 GLOBAL 투자</span> ';
                }}

                card.innerHTML = `
                    <div class="card-header">
                        <div style="display:flex; align-items:center; gap:0.5rem;">
                            <span class="cat-badge ${{catClass}}"><i class="fa-solid ${{catIcon}}"></i> ${{cat}}</span>
                            ${{tagsHtml}}
                        </div>
                        <span style="font-size:0.8rem; color:var(--text-muted);">${{item.published_at}}</span>
                    </div>
                    <div class="card-title">
                        <a href="${{item.url}}" target="_blank">${{item.title}}</a>
                    </div>
                    <div class="card-meta">
                        <span><i class="fa-regular fa-newspaper"></i> ${{item.media_name}}</span>
                        <span><i class="fa-regular fa-user"></i> ${{item.journalist}}</span>
                        <span><i class="fa-solid fa-chart-line"></i> 가치점수: <strong>${{item.value_score || 0}}</strong></span>
                    </div>
                    <div class="summary-box">
                        <strong style="color:var(--accent); display:block; margin-bottom:0.25rem;"><i class="fa-solid fa-robot"></i> AI 핵심 요약 & 전처리 사유:</strong>
                        ${{item.summary || item.final_reason || '요약 정보 없음'}}
                    </div>
                    <div class="body-accordion">
                        <button class="btn-toggle-body" onclick="toggleBody('body_${{idx}}', this)">
                            <i class="fa-solid fa-chevron-down"></i> 정제된 기사 본문 전체 보기
                        </button>
                        <div class="body-full-content" id="body_${{idx}}">${{item.cleaned_body || '본문 없음'}}</div>
                    </div>
                `;
                grid.appendChild(card);
            }});
        }}

        function toggleBody(id, btn) {{
            const box = document.getElementById(id);
            const isShown = box.style.display === 'block';
            box.style.display = isShown ? 'none' : 'block';
            btn.innerHTML = isShown 
                ? '<i class="fa-solid fa-chevron-down"></i> 정제된 기사 본문 전체 보기' 
                : '<i class="fa-solid fa-chevron-up"></i> 기사 본문 접기';
        }}

        function renderExtractionTable() {{
            const tbody = document.getElementById('extractTableBody');
            tbody.innerHTML = '';

            let list = extractArticles;

            if (extractFilter !== 'ALL') {{
                if (extractFilter === 'NEEDS_REVIEW') list = list.filter(a => a.needs_review);
                else if (extractFilter === 'CLEAN') list = list.filter(a => !a.needs_review);
                else if (extractFilter === 'TRAF') list = list.filter(a => a.extraction_method && a.extraction_method.includes('trafilatura'));
                else if (extractFilter === 'SELECTOR') list = list.filter(a => a.extraction_method === 'site_selector');
            }}

            if (searchQuery) {{
                list = list.filter(a => 
                    (a.title && a.title.toLowerCase().includes(searchQuery)) ||
                    (a.media_name && a.media_name.toLowerCase().includes(searchQuery)) ||
                    (a.journalist && a.journalist.toLowerCase().includes(searchQuery)) ||
                    (a.mismatch_reason && a.mismatch_reason.toLowerCase().includes(searchQuery))
                );
            }}

            currentExtractList = list;
            document.getElementById('extractCountBadge').innerText = `총 ${{list.length}}건`;

            list.forEach((item, idx) => {{
                const tr = document.createElement('tr');
                const score = item.quality_score || 0;
                const scoreClass = score >= 85 ? 'score-high' : (score >= 60 ? 'score-mid' : 'score-low');
                const reviewBadge = item.needs_review 
                    ? '<span class="review-badge review-warn"><i class="fa-solid fa-triangle-exclamation"></i> 검토필요</span>'
                    : '<span class="review-badge review-clean"><i class="fa-solid fa-check"></i> Clean</span>';

                tr.innerHTML = `
                    <td style="text-align: center; color: var(--text-muted);">${{idx + 1}}</td>
                    <td><a href="${{item.url}}" target="_blank" style="color: var(--text-primary); text-decoration: none; font-weight: 600;">${{item.title}}</a></td>
                    <td style="text-align: center; color: var(--text-secondary);">${{item.media_name}}</td>
                    <td style="text-align: center;"><span class="method-badge">${{item.extraction_method || 'N/A'}}</span></td>
                    <td style="text-align: center;"><span class="score-badge ${{scoreClass}}">${{score}}점</span></td>
                    <td style="text-align: center;">${{reviewBadge}}</td>
                    <td style="color: ${{item.needs_review ? '#fca5a5' : '#94a3b8'}};">${{item.mismatch_reason || '-'}}</td>
                    <td style="text-align: center; color: var(--text-secondary);">${{(item.body || '').length}}자</td>
                    <td style="text-align: center;"><button class="btn-detail" onclick="openExtractModal(${{idx}})"><i class="fa-solid fa-magnifying-glass"></i> 보기</button></td>
                `;
                tbody.appendChild(tr);
            }});
        }}

        function renderRawTable() {{
            const tbody = document.getElementById('rawTableBody');
            tbody.innerHTML = '';

            let list = rawArticles;
            if (searchQuery) {{
                list = list.filter(a => 
                    (a.title && a.title.toLowerCase().includes(searchQuery)) ||
                    (a.media_name && a.media_name.toLowerCase().includes(searchQuery)) ||
                    (a.journalist && a.journalist.toLowerCase().includes(searchQuery))
                );
            }}

            document.getElementById('rawCountBadge').innerText = `총 ${{list.length}}건`;

            list.forEach((item, idx) => {{
                const tr = document.createElement('tr');
                tr.innerHTML = `
                    <td style="text-align: center; color: var(--text-muted);">${{idx + 1}}</td>
                    <td><a href="${{item.url}}" target="_blank" style="color: var(--text-primary); text-decoration: none; font-weight: 600;">${{item.title}}</a></td>
                    <td style="text-align: center;">${{item.media_name}}</td>
                    <td style="text-align: center;">${{item.journalist}}</td>
                    <td style="font-size:0.82rem; color: var(--text-secondary);">${{(item.raw_body || item.body || '').slice(0, 80)}}...</td>
                    <td style="text-align: center; font-size:0.8rem;">${{item.published_at}}</td>
                `;
                tbody.appendChild(tr);
            }});
        }}

        function openExtractModal(idx) {{
            const item = currentExtractList[idx];
            if (!item) return;

            document.getElementById('modalTitle').innerText = item.title;
            document.getElementById('modalMeta').innerText = `언론사: ${{item.media_name}} | 기자: ${{item.journalist}} | 추출 엔진: ${{item.extraction_method}} | 총 ${{item.body ? item.body.length : 0}}자`;
            document.getElementById('modalCharCount').innerText = `${{(item.body || '').length}} 글자`;

            let scoreHtml = '<ul style="list-style:none; font-size:0.85rem; line-height:1.8;">';
            const detail = item.quality_score_detail || {{}};
            if (Object.keys(detail).length === 0) {{
                scoreHtml += '<li>기본 텍스트 품질 점수: <strong>' + (item.quality_score || 0) + '점</strong></li>';
            }} else {{
                for (const [k, v] of Object.entries(detail)) {{
                    scoreHtml += `<li style="display:flex; justify-content:space-between; border-bottom:1px dashed rgba(255,255,255,0.08); padding:0.2rem 0;"><span style="color:var(--text-secondary);">${{k}}</span> <strong>${{v}}</strong></li>`;
                }}
            }}
            scoreHtml += '</ul>';
            document.getElementById('modalScoreBox').innerHTML = scoreHtml;

            let valHtml = `
                <div><strong>품질 점수:</strong> <span style="color:var(--accent); font-weight:700;">${{item.quality_score || 0}}점</span></div>
                <div><strong>검토 필요 여부:</strong> ${{item.needs_review ? '<span style="color:#f87171; font-weight:700;">⚠️ 검토 필요</span>' : '<span style="color:#34d399; font-weight:700;">✓ Clean</span>'}}</div>
                <div style="margin-top:0.35rem;"><strong>검토 / 불일치 사유:</strong> ${{item.mismatch_reason || '-'}}</div>
                <div style="margin-top:0.35rem; font-family:monospace; font-size:0.75rem; word-break:break-all;"><strong>Raw HTML Hash:</strong> ${{item.raw_html_hash || '-'}}</div>
            `;
            document.getElementById('modalValidationBox').innerHTML = valHtml;

            document.getElementById('modalContentBox').innerText = item.body || '추출된 본문이 없습니다.';
            document.getElementById('detailModal').style.display = 'flex';
        }}

        function closeModal() {{
            document.getElementById('detailModal').style.display = 'none';
        }}

        // Initialize
        renderView();
    </script>
</body>
</html>
"""

    os.makedirs("docs", exist_ok=True)
    out_path = os.path.join("docs", out_filename)
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(html_content)
    print(f"Success! Dashboard generated at '{out_path}'.")

    # If building index.html, also mirror it to root directory for convenient local serving
    if out_filename == "index.html":
        with open("index.html", "w", encoding="utf-8") as f:
            f.write(html_content)
        print("Mirrored index.html to root project folder.")

if __name__ == "__main__":
    generate_dashboard("두산에너빌리티", "index.html")
    generate_dashboard("SK하이닉스", "sk_hynix.html")
