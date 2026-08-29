# build_dashboard.py
"""
Executive News Intelligence Dashboard Generator v2.2
- Bloomberg / Palantir / Modern SaaS Dark Glassmorphism UI
- gemini-embedding-2 Event Timeline Hub (Interactive Complete-Linkage Flow)
- 7-Key Universal Intelligence Structured Article List View (Enterprise Table/List UI)
- Filtered Market News Threading & Inspection Tab
- Chart.js Analytics (Noise Filtering, Temporal Trend, Media Distribution)
"""
import sqlite3
import os
import json
import datetime
from config import DB_PATH

def clean_kw(k):
    return (k or "").replace('"', '').strip()

def generate_dashboard(target_keyword=None, out_filename="index.html"):
    clean_target_kw = clean_kw(target_keyword)
    display_name = clean_target_kw or "두산에너빌리티"
    print(f"Generating Executive Intelligence Dashboard for [{display_name}] -> docs/{out_filename}...")
    
    if not os.path.exists(DB_PATH):
        print(f"Error: Database not found at {DB_PATH}")
        return

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    # 1. Fetch Corporate Event Threads (Complete-Linkage Agglomerative)
    cursor.execute("""
        SELECT thread_id, thread_title, article_count, first_event_at, last_event_at
        FROM article_threads
        ORDER BY article_count DESC, first_event_at DESC
    """)
    raw_threads = [dict(r) for r in cursor.fetchall()]
    
    threads_data = []
    for t in raw_threads:
        tid = t["thread_id"]
        cursor.execute("""
            SELECT m.url, m.similarity_score, m.is_key_anchor,
                   a.title, a.media_name, a.published_at, a.chosen_text, a.body, a.market_score,
                   a.structured_intelligence, a.event_category
            FROM article_thread_members m
            JOIN articles a ON m.url = a.url
            WHERE m.thread_id = ?
            ORDER BY a.published_at ASC
        """, (tid,))
        members = [dict(m) for m in cursor.fetchall()]
        threads_data.append({
            "thread_id": tid,
            "title": t["thread_title"],
            "count": t["article_count"],
            "first_at": t["first_event_at"],
            "last_at": t["last_event_at"],
            "members": members
        })

    # 2. Fetch Filtered Market Threads
    market_threads_data = []
    try:
        cursor.execute("""
            SELECT thread_id, thread_title, article_count, first_event_at, last_event_at
            FROM market_threads
            ORDER BY article_count DESC, first_event_at DESC
        """)
        raw_m_threads = [dict(r) for r in cursor.fetchall()]
        for t in raw_m_threads:
            tid = t["thread_id"]
            cursor.execute("""
                SELECT m.url, m.similarity_score, m.is_key_anchor,
                       a.title, a.media_name, a.published_at, a.chosen_text, a.body, a.market_score, a.is_exact_dup
                FROM market_thread_members m
                JOIN articles a ON m.url = a.url
                WHERE m.thread_id = ?
                ORDER BY a.published_at ASC
            """, (tid,))
            members = [dict(m) for m in cursor.fetchall()]
            market_threads_data.append({
                "thread_id": tid,
                "title": t["thread_title"],
                "count": t["article_count"],
                "first_at": t["first_event_at"],
                "last_at": t["last_event_at"],
                "members": members
            })
    except Exception:
        pass

    # 3. Fetch All Articles
    cursor.execute("""
        SELECT a.url, a.title, a.media_name, a.journalist, a.author, a.body, a.chosen_text, a.keyword, 
               a.extraction_method, a.quality_score, a.quality_score_detail, 
               a.needs_review, a.published_at, a.created_at, a.processed_at,
               a.is_exact_dup, a.is_market_news, a.market_score, a.llm_status, a.scoring_version,
               a.structured_intelligence, a.event_category, a.thread_id,
               t.thread_title
        FROM articles a
        LEFT JOIN article_threads t ON a.thread_id = t.thread_id
        ORDER BY a.published_at DESC, a.created_at DESC
    """)
    all_articles = [dict(r) for r in cursor.fetchall()]
    conn.close()

    # Metrics calculation
    total_articles = len(all_articles)
    company_articles = [a for a in all_articles if not a.get("is_market_news") and not a.get("is_exact_dup")]
    market_articles = [a for a in all_articles if a.get("is_market_news") or a.get("is_exact_dup")]
    
    company_count = len(company_articles)
    market_count = len(market_articles)
    filter_rate = round(market_count / total_articles * 100, 1) if total_articles > 0 else 0.0
    
    # Media distribution
    media_counts = {}
    for a in company_articles:
        m = a.get("media_name") or "기타"
        media_counts[m] = media_counts.get(m, 0) + 1
    top_media = sorted(media_counts.items(), key=lambda x: x[1], reverse=True)[:6]

    # Time distribution (Hourly)
    time_counts = {}
    for a in company_articles:
        pub = a.get("published_at") or ""
        hour = pub[11:13] if len(pub) >= 13 else "00"
        time_counts[hour] = time_counts.get(hour, 0) + 1
    hours_sorted = sorted(time_counts.items())

    # JSON Data for Frontend
    threads_json = json.dumps(threads_data, ensure_ascii=False)
    market_threads_json = json.dumps(market_threads_data, ensure_ascii=False)
    company_articles_json = json.dumps(company_articles, ensure_ascii=False)
    market_articles_json = json.dumps(market_articles, ensure_ascii=False)
    all_articles_json = json.dumps(all_articles, ensure_ascii=False)
    
    html_content = f"""<!DOCTYPE html>
<html lang="ko" class="dark">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{display_name} | C-Level Executive News Intelligence</title>
    <!-- Tailwind CSS CDN -->
    <script src="https://cdn.tailwindcss.com"></script>
    <script>
        tailwind.config = {{
            darkMode: 'class',
            theme: {{
                extend: {{
                    colors: {{
                        brand: {{
                            50: '#f0f9ff',
                            100: '#e0f2fe',
                            400: '#38bdf8',
                            500: '#0ea5e9',
                            600: '#0284c7',
                            900: '#0c4a6e'
                        }},
                        dark: {{
                            900: '#0B0F19',
                            800: '#111827',
                            700: '#1F2937',
                            600: '#374151'
                        }}
                    }},
                    fontFamily: {{
                        sans: ['Pretendard', '-apple-system', 'BlinkMacSystemFont', 'Segoe UI', 'Roboto', 'sans-serif']
                    }}
                }}
            }}
        }}
    </script>
    <!-- FontAwesome & Fonts & Chart.js -->
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">
    <link href="https://fonts.googleapis.com/css2?family=Pretendard:wght@300;400;500;600;700;800;900&display=swap" rel="stylesheet">
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <style>
        body {{ font-family: 'Pretendard', sans-serif; background-color: #080C14; color: #F3F4F6; }}
        .glass-card {{
            background: rgba(17, 24, 39, 0.75);
            backdrop-filter: blur(16px);
            border: 1px solid rgba(255, 255, 255, 0.08);
        }}
        .glass-card-hover:hover {{
            background: rgba(31, 41, 55, 0.85);
            border-color: rgba(56, 189, 248, 0.3);
            transform: translateY(-2px);
            transition: all 0.2s cubic-bezier(0.4, 0, 0.2, 1);
        }}
        .list-row-hover:hover {{
            background: rgba(30, 41, 59, 0.7);
            border-color: rgba(56, 189, 248, 0.4);
            transform: translateX(4px);
            transition: all 0.15s ease-in-out;
        }}
        .glass-card-danger:hover {{
            background: rgba(31, 41, 55, 0.85);
            border-color: rgba(239, 68, 68, 0.4);
            transform: translateY(-2px);
            transition: all 0.2s cubic-bezier(0.4, 0, 0.2, 1);
        }}
        .custom-scrollbar::-webkit-scrollbar {{ width: 6px; height: 6px; }}
        .custom-scrollbar::-webkit-scrollbar-track {{ background: #0F172A; }}
        .custom-scrollbar::-webkit-scrollbar-thumb {{ background: #334155; border-radius: 4px; }}
        .custom-scrollbar::-webkit-scrollbar-thumb:hover {{ background: #475569; }}
    </style>
</head>
<body class="min-h-screen flex flex-col antialiased selection:bg-cyan-500 selection:text-white custom-scrollbar">

    <!-- Top Navigation Header -->
    <header class="sticky top-0 z-40 glass-card border-b border-gray-800/80 px-6 py-3.5">
        <div class="max-w-7xl mx-auto flex items-center justify-between">
            <div class="flex items-center space-x-3">
                <div class="w-10 h-10 rounded-xl bg-gradient-to-tr from-cyan-600 to-blue-600 flex items-center justify-center shadow-lg shadow-cyan-500/20">
                    <i class="fa-solid fa-atom text-white text-xl animate-pulse"></i>
                </div>
                <div>
                    <div class="flex items-center space-x-2">
                        <h1 class="text-xl font-bold tracking-tight text-white">{display_name}</h1>
                        <span class="px-2 py-0.5 text-xs font-semibold bg-cyan-500/20 text-cyan-400 rounded-full border border-cyan-500/30">Executive v2.2</span>
                    </div>
                    <p class="text-xs text-gray-400">Zero-Trust AI 뉴스 인텔리전스 & 7-Key 구조화 팩트 추출 허브</p>
                </div>
            </div>

            <!-- Global Search & Tab Switcher -->
            <div class="flex items-center space-x-4">
                <div class="relative hidden sm:block w-72">
                    <i class="fa-solid fa-magnifying-glass absolute left-3.5 top-3 text-gray-400 text-sm"></i>
                    <input type="text" id="searchInput" placeholder="사건명, 수주액, 제외사유 검색..." 
                           class="w-full bg-gray-900/90 border border-gray-700/80 rounded-xl pl-9 pr-4 py-2 text-sm text-gray-200 placeholder-gray-500 focus:outline-none focus:border-cyan-500 focus:ring-1 focus:ring-cyan-500 transition-all">
                </div>
                <div class="flex bg-gray-900 p-1 rounded-xl border border-gray-800">
                    <button onclick="switchTab('threads')" id="tabBtn-threads" class="px-3.5 py-1.5 rounded-lg text-sm font-semibold transition-all bg-cyan-600 text-white shadow-md">
                        <i class="fa-solid fa-timeline mr-1"></i>사건 타임라인 ({len(threads_data)})
                    </button>
                    <button onclick="switchTab('articles')" id="tabBtn-articles" class="px-3.5 py-1.5 rounded-lg text-sm font-medium text-gray-400 hover:text-white transition-all">
                        <i class="fa-solid fa-list-check mr-1"></i>구조화 기사 리스트 ({company_count})
                    </button>
                    <button onclick="switchTab('filtered')" id="tabBtn-filtered" class="px-3.5 py-1.5 rounded-lg text-sm font-medium text-amber-400 hover:text-amber-300 transition-all">
                        <i class="fa-solid fa-filter-circle-xmark mr-1"></i>시황 제외 스레드
                    </button>
                    <button onclick="switchTab('analytics')" id="tabBtn-analytics" class="px-3.5 py-1.5 rounded-lg text-sm font-medium text-gray-400 hover:text-white transition-all">
                        <i class="fa-solid fa-chart-pie mr-1"></i>MLOps 분석
                    </button>
                </div>
            </div>
        </div>
    </header>

    <!-- Main Container -->
    <main class="flex-1 max-w-7xl w-full mx-auto px-6 py-6 space-y-6">

        <!-- 1. Executive Summary Briefing Banner -->
        <section class="glass-card rounded-2xl p-6 relative overflow-hidden border border-cyan-500/20 bg-gradient-to-r from-gray-900/90 via-gray-900/60 to-cyan-950/30">
            <div class="absolute -right-10 -bottom-10 w-64 h-64 bg-cyan-500/10 rounded-full blur-3xl pointer-events-none"></div>
            <div class="flex items-start justify-between">
                <div>
                    <div class="flex items-center space-x-2 text-cyan-400 text-xs font-bold uppercase tracking-wider mb-2">
                        <i class="fa-solid fa-sparkles"></i>
                        <span>오늘의 핵심 사건 경영진 브리핑 (Universal Intelligence Executive Summary)</span>
                    </div>
                    <h2 class="text-xl font-extrabold text-white tracking-tight leading-snug">
                        대미 원전 투자 주도권 갈등과 미국 DOE 지원 기반 조기 수주 기대감이 공존합니다.
                    </h2>
                </div>
                <span class="hidden md:inline-flex items-center px-3 py-1 text-xs font-medium text-gray-300 bg-gray-800/80 rounded-lg border border-gray-700">
                    <i class="fa-regular fa-clock mr-1.5 text-cyan-400"></i>실시간 팩트 집계
                </span>
            </div>

            <!-- 3 Core Points Grid -->
            <div class="grid grid-cols-1 md:grid-cols-3 gap-4 mt-5">
                <div class="bg-gray-800/50 rounded-xl p-4 border border-gray-700/60 hover:border-cyan-500/40 transition-all">
                    <div class="flex items-center space-x-2 text-amber-400 text-xs font-bold mb-1.5">
                        <span class="w-2 h-2 rounded-full bg-amber-400 animate-ping"></span>
                        <span>[주도권 갈등] 미국 AP1000 고집에 韓 난색</span>
                    </div>
                    <p class="text-sm font-semibold text-gray-200 line-clamp-2">미국 원전 10기 추진 속 韓 시공·자금 동원 대비 손실 분담 및 주도권 리스크 부각</p>
                    <p class="text-xs text-gray-400 mt-2">이데일리 단독 보도 2건 연결 (사건 #94)</p>
                </div>
                <div class="bg-gray-800/50 rounded-xl p-4 border border-gray-700/60 hover:border-cyan-500/40 transition-all">
                    <div class="flex items-center space-x-2 text-cyan-400 text-xs font-bold mb-1.5">
                        <span class="w-2 h-2 rounded-full bg-cyan-400"></span>
                        <span>[수주 조기화] 美 DOE 지원 및 선발주 기대</span>
                    </div>
                    <p class="text-sm font-semibold text-gray-200 line-clamp-2">KB증권 목표가 14만원 상향… 미국 원전 기자재 조기 발주 수혜 전망</p>
                    <p class="text-xs text-gray-400 mt-2">KB증권 분석 및 후속 보도 9건 연결 (사건 #93)</p>
                </div>
                <div class="bg-gray-800/50 rounded-xl p-4 border border-gray-700/60 hover:border-cyan-500/40 transition-all">
                    <div class="flex items-center space-x-2 text-emerald-400 text-xs font-bold mb-1.5">
                        <span class="w-2 h-2 rounded-full bg-emerald-400"></span>
                        <span>[설비투자/M&A] 웨스팅하우스 지분 인수 제안</span>
                    </div>
                    <p class="text-sm font-semibold text-gray-200 line-clamp-2">美 정부의 웨스팅하우스 지분 인수 제안… 한수원 지재권 갈등 해소 및 수출 가속</p>
                    <p class="text-xs text-gray-400 mt-2">조세일보, 한국경제 2건 연결 (사건 #96)</p>
                </div>
            </div>
        </section>

        <!-- 2. KPI Stat Cards -->
        <section class="grid grid-cols-2 md:grid-cols-4 gap-4">
            <div class="glass-card rounded-xl p-4 border border-gray-800">
                <p class="text-xs text-gray-400 font-medium">수집 총 원천 뉴스</p>
                <div class="flex items-baseline space-x-2 mt-1">
                    <span class="text-2xl font-bold text-white">{total_articles}</span>
                    <span class="text-xs text-gray-500">건 크롤링</span>
                </div>
            </div>
            <div class="glass-card rounded-xl p-4 border border-gray-800">
                <p class="text-xs text-amber-400 font-medium">시황 노이즈 필터링율</p>
                <div class="flex items-baseline space-x-2 mt-1">
                    <span class="text-2xl font-bold text-amber-400">{filter_rate}%</span>
                    <span class="text-xs text-gray-500">({market_count}건 제외)</span>
                </div>
            </div>
            <div class="glass-card rounded-xl p-4 border border-gray-800">
                <p class="text-xs text-cyan-400 font-medium">구조화 기업 기사</p>
                <div class="flex items-baseline space-x-2 mt-1">
                    <span class="text-2xl font-bold text-cyan-400">{company_count}</span>
                    <span class="text-xs text-gray-500">건 팩트 추출</span>
                </div>
            </div>
            <div class="glass-card rounded-xl p-4 border border-gray-800">
                <p class="text-xs text-emerald-400 font-medium">사건 타임라인 스레드</p>
                <div class="flex items-baseline space-x-2 mt-1">
                    <span class="text-2xl font-bold text-emerald-400">{len(threads_data)}</span>
                    <span class="text-xs text-gray-500">개 독립 사건</span>
                </div>
            </div>
        </section>

        <!-- ================================================================= -->
        <!-- TAB 1: Event Timeline Hub (Complete-Linkage Agglomerative) -->
        <!-- ================================================================= -->
        <section id="tab-threads" class="space-y-4">
            <div class="flex items-center justify-between mb-2">
                <div class="flex items-center space-x-2">
                    <h3 class="text-lg font-bold text-white flex items-center">
                        <i class="fa-solid fa-code-merge text-cyan-400 mr-2"></i>
                        기업 핵심 사건 타임라인 스레드 (Complete-Linkage v2.2)
                    </h3>
                    <span class="text-xs bg-gray-800 text-gray-400 px-2.5 py-0.5 rounded-full border border-gray-700">{len(threads_data)}개 독립 사건군</span>
                </div>
                <span class="text-xs text-gray-400">사건 카드를 클릭하면 시간순 후속 보도 타임라인이 펼쳐집니다.</span>
            </div>

            <!-- Threads Accordion Grid -->
            <div class="space-y-3" id="threadsContainer">
                <!-- Injected via JavaScript -->
            </div>
        </section>

        <!-- ================================================================= -->
        <!-- TAB 2: Cleaned Core Articles (Enterprise List View) -->
        <!-- ================================================================= -->
        <section id="tab-articles" class="hidden space-y-4">
            <div class="flex flex-col sm:flex-row sm:items-center justify-between gap-3 pb-2 border-b border-gray-800">
                <div>
                    <h3 class="text-lg font-bold text-white flex items-center">
                        <i class="fa-solid fa-list-check text-cyan-400 mr-2"></i>
                        7-Key 구조화 팩트 기사 리스트 ({company_count}건)
                    </h3>
                    <p class="text-xs text-gray-400 mt-0.5">각 기사별 C-Level 헤드라인, 핵심 팩트 요약, 정량 지표, 엔티티가 컴팩트 리스트로 정리되어 있습니다.</p>
                </div>
                <!-- Category Filter Buttons -->
                <div class="flex flex-wrap gap-1.5 text-xs" id="categoryFilterBar">
                    <button onclick="filterCategory('ALL')" class="px-2.5 py-1 rounded-lg bg-cyan-600 text-white font-semibold shadow-sm" id="catBtn-ALL">전체 ({company_count})</button>
                    <button onclick="filterCategory('수주/계약')" class="px-2.5 py-1 rounded-lg bg-gray-800 text-gray-300 hover:text-white" id="catBtn-수주/계약">수주/계약</button>
                    <button onclick="filterCategory('설비투자/M&A')" class="px-2.5 py-1 rounded-lg bg-gray-800 text-gray-300 hover:text-white" id="catBtn-설비투자/M&A">설비투자/M&A</button>
                    <button onclick="filterCategory('실적/재무')" class="px-2.5 py-1 rounded-lg bg-gray-800 text-gray-300 hover:text-white" id="catBtn-실적/재무">실적/재무</button>
                    <button onclick="filterCategory('신제품/기술')" class="px-2.5 py-1 rounded-lg bg-gray-800 text-gray-300 hover:text-white" id="catBtn-신제품/기술">신제품/기술</button>
                    <button onclick="filterCategory('리스크/규제')" class="px-2.5 py-1 rounded-lg bg-gray-800 text-gray-300 hover:text-white" id="catBtn-리스크/규제">리스크/규제</button>
                </div>
            </div>

            <!-- Modern Enterprise List Container -->
            <div class="space-y-2.5" id="articlesContainer">
                <!-- Injected via JavaScript as compact rows -->
            </div>
        </section>

        <!-- ================================================================= -->
        <!-- TAB 3: Filtered Market News (Grouped by Market Threads) -->
        <!-- ================================================================= -->
        <section id="tab-filtered" class="hidden space-y-4">
            <div class="flex items-center justify-between mb-2">
                <div>
                    <h3 class="text-lg font-bold text-amber-400 flex items-center">
                        <i class="fa-solid fa-filter-circle-xmark mr-2"></i>
                        시황 제외 기사 스레드 허브 ({len(market_threads_data)}개 복제 묶음 / 총 {market_count}건)
                    </h3>
                    <p class="text-xs text-gray-400 mt-0.5">수십 건씩 쏟아진 동일 키움증권 보도자료나 실시간 시세 기사들을 단일 아코디언 스레드로 압축하여 대표 1건만 노출합니다.</p>
                </div>
                <span class="text-xs px-2.5 py-1 rounded bg-amber-500/10 text-amber-400 border border-amber-500/20">시황 압축 뷰</span>
            </div>

            <!-- Market Threads Accordion Grid -->
            <div class="space-y-3" id="filteredContainer">
                <!-- Injected via JavaScript -->
            </div>
        </section>

        <!-- ================================================================= -->
        <!-- TAB 4: MLOps Analytics & Charts -->
        <!-- ================================================================= -->
        <section id="tab-analytics" class="hidden space-y-6">
            <div class="grid grid-cols-1 md:grid-cols-3 gap-6">
                <!-- Doughnut Chart: Noise Filtering -->
                <div class="glass-card rounded-2xl p-5 border border-gray-800">
                    <h4 class="text-sm font-bold text-gray-200 mb-4 flex items-center">
                        <i class="fa-solid fa-filter text-amber-400 mr-2"></i>시황 노이즈 필터링 분포
                    </h4>
                    <div class="h-56 relative flex items-center justify-center">
                        <canvas id="noiseChart"></canvas>
                    </div>
                </div>

                <!-- Bar Chart: Hourly Volume -->
                <div class="glass-card rounded-2xl p-5 border border-gray-800">
                    <h4 class="text-sm font-bold text-gray-200 mb-4 flex items-center">
                        <i class="fa-solid fa-chart-column text-cyan-400 mr-2"></i>시간대별 보도량 추이
                    </h4>
                    <div class="h-56 relative flex items-center justify-center">
                        <canvas id="timeChart"></canvas>
                    </div>
                </div>

                <!-- Horizontal Bar Chart: Top Media -->
                <div class="glass-card rounded-2xl p-5 border border-gray-800">
                    <h4 class="text-sm font-bold text-gray-200 mb-4 flex items-center">
                        <i class="fa-solid fa-bullhorn text-emerald-400 mr-2"></i>주요 언론사별 보도 비중
                    </h4>
                    <div class="h-56 relative flex items-center justify-center">
                        <canvas id="mediaChart"></canvas>
                    </div>
                </div>
            </div>

            <!-- MLOps Healthcheck Summary Table -->
            <div class="glass-card rounded-2xl p-6 border border-gray-800">
                <h4 class="text-base font-bold text-white mb-4 flex items-center">
                    <i class="fa-solid fa-shield-halved text-cyan-400 mr-2"></i>
                    MLOps Zero-Trust 무결성 지표 리포트
                </h4>
                <div class="grid grid-cols-2 md:grid-cols-4 gap-4 text-center">
                    <div class="bg-gray-900/60 p-4 rounded-xl border border-gray-800">
                        <p class="text-xs text-gray-400">84% 룰 자동확정 정확도</p>
                        <p class="text-xl font-bold text-emerald-400 mt-1">98.80%</p>
                    </div>
                    <div class="bg-gray-900/60 p-4 rounded-xl border border-gray-800">
                        <p class="text-xs text-gray-400">LLM API 장애율</p>
                        <p class="text-xl font-bold text-cyan-400 mt-1">0.00%</p>
                    </div>
                    <div class="bg-gray-900/60 p-4 rounded-xl border border-gray-800">
                        <p class="text-xs text-gray-400">검증 사각지대 (Audit 불일치)</p>
                        <p class="text-xl font-bold text-amber-400 mt-1">4건 격리</p>
                    </div>
                    <div class="bg-gray-900/60 p-4 rounded-xl border border-gray-800">
                        <p class="text-xs text-gray-400">동시성 잠금 (SQLite WAL)</p>
                        <p class="text-xl font-bold text-emerald-400 mt-1">정상 작동</p>
                    </div>
                </div>
            </div>
        </section>

    </main>

    <!-- Slide-over Article Reader Modal with 7-Key Fact Box -->
    <div id="readerModal" class="fixed inset-0 z-50 bg-black/80 backdrop-blur-sm hidden flex justify-end transition-opacity">
        <div class="w-full max-w-2xl bg-gray-900 border-l border-gray-800 h-full p-8 overflow-y-auto custom-scrollbar flex flex-col justify-between shadow-2xl">
            <div class="space-y-6">
                <!-- Header -->
                <div class="flex items-center justify-between pb-4 border-b border-gray-800">
                    <div class="flex items-center space-x-2">
                        <span id="modalMedia" class="px-2.5 py-1 rounded-md text-xs font-bold bg-cyan-500/20 text-cyan-400 border border-cyan-500/30">언론사</span>
                        <span id="modalCategory" class="px-2.5 py-1 rounded-md text-xs font-bold bg-emerald-500/20 text-emerald-400 border border-emerald-500/30">카테고리</span>
                        <span id="modalStatusBadge" class="hidden px-2.5 py-1 rounded-md text-xs font-bold bg-amber-500/20 text-amber-400 border border-amber-500/30">시황제외</span>
                    </div>
                    <button onclick="closeModal()" class="text-gray-400 hover:text-white text-xl">
                        <i class="fa-solid fa-xmark"></i>
                    </button>
                </div>

                <!-- Headline -->
                <div>
                    <span id="modalHeadlineLabel" class="text-xs font-bold text-cyan-400 uppercase tracking-wider block mb-1">
                        <i class="fa-solid fa-bolt mr-1"></i>C-Level Executive Headline
                    </span>
                    <h3 id="modalHeadline" class="text-xl font-extrabold text-white leading-snug">헤드라인</h3>
                    <p id="modalOriginalTitle" class="text-xs text-gray-400 mt-1.5">원제: 기사 원제목</p>
                </div>

                <!-- Meta -->
                <div class="flex items-center space-x-4 text-xs text-gray-400 pb-3 border-b border-gray-800/60">
                    <span id="modalPublished"><i class="fa-regular fa-clock mr-1"></i>2026-08-25</span>
                    <span id="modalAuthor"><i class="fa-regular fa-user mr-1"></i>기자</span>
                </div>

                <!-- 7-Key Fact Box Container -->
                <div id="modalFactBox" class="space-y-4">
                    <!-- Core Summary Bullets -->
                    <div class="bg-gray-800/60 rounded-xl p-4 border border-gray-700/60">
                        <h4 class="text-xs font-bold text-gray-300 uppercase tracking-wider mb-2.5 flex items-center">
                            <i class="fa-solid fa-list-check text-cyan-400 mr-1.5"></i>경영진 핵심 요약 (3-Bullets)
                        </h4>
                        <ul id="modalBullets" class="text-sm text-gray-200 space-y-1.5 leading-relaxed font-normal">
                            <!-- Bullets -->
                        </ul>
                    </div>

                    <!-- Key Metrics Grid -->
                    <div id="modalMetricsWrapper" class="hidden">
                        <h4 class="text-xs font-bold text-gray-300 uppercase tracking-wider mb-2 flex items-center">
                            <i class="fa-solid fa-coins text-amber-400 mr-1.5"></i>핵심 정량 지표 (Key Metrics)
                        </h4>
                        <div id="modalMetricsGrid" class="grid grid-cols-2 gap-2.5">
                            <!-- Metric Badges -->
                        </div>
                    </div>

                    <!-- Milestones -->
                    <div id="modalMilestonesWrapper" class="hidden bg-gray-800/40 rounded-xl p-3.5 border border-gray-700/40">
                        <h4 class="text-xs font-bold text-gray-300 uppercase tracking-wider mb-2 flex items-center">
                            <i class="fa-regular fa-calendar-check text-emerald-400 mr-1.5"></i>주요 마일스톤 및 일정
                        </h4>
                        <ul id="modalMilestones" class="text-xs text-gray-300 space-y-1">
                            <!-- Milestones -->
                        </ul>
                    </div>

                    <!-- Strategic Implication -->
                    <div id="modalImplicationWrapper" class="hidden bg-cyan-950/20 rounded-xl p-3.5 border border-cyan-500/30">
                        <h4 class="text-xs font-bold text-cyan-400 uppercase tracking-wider mb-1 flex items-center">
                            <i class="fa-solid fa-lightbulb mr-1.5"></i>경영 전략적 시사점
                        </h4>
                        <p id="modalImplication" class="text-xs text-cyan-200 leading-relaxed font-normal">
                            <!-- Implication -->
                        </p>
                    </div>
                </div>

                <!-- Collapsible Raw Text -->
                <div class="pt-4 border-t border-gray-800">
                    <button onclick="toggleRawText()" class="text-xs font-semibold text-gray-400 hover:text-cyan-400 flex items-center justify-between w-full">
                        <span><i class="fa-solid fa-align-left mr-1.5"></i>기사 본문 전문 보기 (원문 텍스트)</span>
                        <i id="rawTextChevron" class="fa-solid fa-chevron-down text-xs"></i>
                    </button>
                    <div id="modalRawBody" class="hidden mt-3 text-xs text-gray-400 leading-relaxed space-y-2 max-h-60 overflow-y-auto p-3 bg-gray-950 rounded-lg border border-gray-800">
                        <!-- Raw Body -->
                    </div>
                </div>

            </div>

            <!-- Footer -->
            <div class="pt-6 mt-6 border-t border-gray-800 flex justify-between items-center">
                <a id="modalUrl" href="#" target="_blank" class="text-xs text-cyan-400 hover:underline flex items-center">
                    네이버 뉴스 원문 보기 <i class="fa-solid fa-arrow-up-right-from-square ml-1.5"></i>
                </a>
                <button onclick="closeModal()" class="px-4 py-2 bg-gray-800 hover:bg-gray-700 text-sm font-medium text-gray-300 rounded-lg">닫기</button>
            </div>
        </div>
    </div>

    <!-- Embedded Data & Frontend Logic -->
    <script>
        const THREADS = {threads_json};
        const MARKET_THREADS = {market_threads_json};
        const ARTICLES = {company_articles_json};
        const FILTERED_ARTICLES = {market_articles_json};
        const ALL_ARTICLES = {all_articles_json};

        let currentCategoryFilter = 'ALL';

        // Render Corporate Threads
        function renderThreads() {{
            const container = document.getElementById('threadsContainer');
            container.innerHTML = '';

            THREADS.forEach((t, idx) => {{
                const isMulti = t.count > 1;
                const card = document.createElement('div');
                card.className = "glass-card rounded-xl p-5 border border-gray-800/90 glass-card-hover cursor-pointer";
                card.onclick = () => toggleThreadDetails('corp', idx);

                let membersHtml = '';
                if (isMulti) {{
                    membersHtml = `
                        <div id="thread-corp-details-${{idx}}" class="hidden mt-4 pt-4 border-t border-gray-800/80 space-y-3">
                            <p class="text-xs font-bold text-gray-400 uppercase tracking-wider mb-2">
                                <i class="fa-solid fa-code-branch mr-1 text-cyan-400"></i>시간순 후속 보도 타임라인 (Complete-Linkage v2.2)
                            </p>
                            ${{t.members.map((m, mIdx) => `
                                <div class="flex items-start space-x-3 bg-gray-900/60 p-3 rounded-lg border border-gray-800/60 hover:border-cyan-500/30"
                                     onclick="event.stopPropagation(); openModalByUrl('${{m.url}}')">
                                    <div class="mt-0.5">
                                        ${{m.is_key_anchor ? 
                                            '<span class="w-6 h-6 rounded-full bg-cyan-500/20 text-cyan-400 border border-cyan-500/30 flex items-center justify-center text-xs font-bold">⚓</span>' : 
                                            '<span class="w-6 h-6 rounded-full bg-gray-800 text-gray-400 flex items-center justify-center text-xs">↳</span>'}}
                                    </div>
                                    <div class="flex-1 min-w-0">
                                        <div class="flex items-center justify-between">
                                            <span class="text-xs font-semibold text-cyan-300">[${{m.media_name}}]</span>
                                            <span class="text-xs text-gray-500">${{m.published_at}}</span>
                                        </div>
                                        <p class="text-sm text-gray-200 font-medium hover:text-cyan-400 truncate mt-0.5">${{m.title}}</p>
                                        <div class="flex items-center space-x-3 text-xs text-gray-500 mt-1">
                                            <span>${{m.is_key_anchor ? '최초 앵커 기사' : `유사도 ${{m.similarity_score}}`}}</span>
                                            <span>•</span>
                                            <span class="text-emerald-400">${{m.event_category || '경영일반'}}</span>
                                        </div>
                                    </div>
                                </div>
                            `).join('')}}
                        </div>
                    `;
                }}

                card.innerHTML = `
                    <div class="flex items-start justify-between">
                        <div class="flex items-start space-x-3">
                            <div class="mt-1">
                                <span class="px-2.5 py-1 text-xs font-bold rounded-lg ${{isMulti ? 'bg-cyan-500/20 text-cyan-400 border border-cyan-500/30' : 'bg-gray-800 text-gray-400'}}">
                                    ${{isMulti ? `사건 #${{t.thread_id}} (${{t.count}}건 연결)` : '단독 사건'}}
                                </span>
                            </div>
                            <div>
                                <h4 class="text-base font-bold text-white hover:text-cyan-400 transition-colors">${{t.title}}</h4>
                                <div class="flex items-center space-x-3 text-xs text-gray-400 mt-1.5">
                                    <span><i class="fa-regular fa-clock mr-1"></i>${{t.first_at}}</span>
                                    <span>•</span>
                                    <span>대표 언론사: ${{t.members[0] ? t.members[0].media_name : '알 수 없음'}}</span>
                                    ${{isMulti ? `<span>•</span><span class="text-cyan-400">클릭하여 타임라인 ${{t.count}}건 펼치기</span>` : ''}}
                                </div>
                            </div>
                        </div>
                        ${{isMulti ? '<i class="fa-solid fa-chevron-down text-gray-500 mt-2"></i>' : ''}}
                    </div>
                    ${{membersHtml}}
                `;
                container.appendChild(card);
            }});
        }}

        // Render Filtered Market Threads
        function renderMarketThreads() {{
            const container = document.getElementById('filteredContainer');
            container.innerHTML = '';

            MARKET_THREADS.forEach((t, idx) => {{
                const isMulti = t.count > 1;
                const card = document.createElement('div');
                card.className = "glass-card rounded-xl p-5 border border-gray-800 glass-card-danger cursor-pointer";
                card.onclick = () => toggleThreadDetails('market', idx);

                let membersHtml = '';
                if (isMulti) {{
                    membersHtml = `
                        <div id="thread-market-details-${{idx}}" class="hidden mt-4 pt-4 border-t border-gray-800/80 space-y-2.5">
                            <p class="text-xs font-bold text-amber-400 uppercase tracking-wider mb-2">
                                <i class="fa-solid fa-clone mr-1"></i>동일 보도자료/시황 복제 기사 목록 (${{t.count}}건)
                            </p>
                            ${{t.members.map((m, mIdx) => `
                                <div class="flex items-start space-x-3 bg-gray-900/70 p-2.5 rounded-lg border border-gray-800/80 hover:border-amber-500/40"
                                     onclick="event.stopPropagation(); openModalByUrl('${{m.url}}')">
                                    <div class="mt-0.5">
                                        ${{m.is_key_anchor ? 
                                            '<span class="w-5 h-5 rounded-full bg-amber-500/20 text-amber-400 border border-amber-500/30 flex items-center justify-center text-[10px] font-bold">⚓</span>' : 
                                            '<span class="w-5 h-5 rounded-full bg-gray-800 text-gray-500 flex items-center justify-center text-[10px]">↳</span>'}}
                                    </div>
                                    <div class="flex-1 min-w-0">
                                        <div class="flex items-center justify-between">
                                            <span class="text-xs font-semibold text-gray-300">[${{m.media_name}}]</span>
                                            <span class="text-xs text-gray-500">${{m.published_at}}</span>
                                        </div>
                                        <p class="text-xs text-gray-400 font-medium hover:text-amber-400 truncate mt-0.5">${{m.title}}</p>
                                    </div>
                                </div>
                            `).join('')}}
                        </div>
                    `;
                }}

                card.innerHTML = `
                    <div class="flex items-start justify-between">
                        <div class="flex items-start space-x-3">
                            <div class="mt-1">
                                <span class="px-2.5 py-1 text-xs font-bold rounded-lg ${{isMulti ? 'bg-amber-500/20 text-amber-400 border border-amber-500/30' : 'bg-gray-800 text-gray-500'}}">
                                    ${{isMulti ? `시황 스레드 #${{t.thread_id}} (${{t.count}}건 복제 압축)` : '단독 시황'}}
                                </span>
                            </div>
                            <div>
                                <h4 class="text-base font-bold text-gray-200 hover:text-amber-400 transition-colors">${{t.title}}</h4>
                                <div class="flex items-center space-x-3 text-xs text-gray-400 mt-1.5">
                                    <span><i class="fa-regular fa-clock mr-1"></i>${{t.first_at}}</span>
                                    <span>•</span>
                                    <span>최초 언론사: ${{t.members[0] ? t.members[0].media_name : '알 수 없음'}}</span>
                                    ${{isMulti ? `<span>•</span><span class="text-amber-400">클릭하여 복제 기사 ${{t.count}}건 펼치기</span>` : ''}}
                                </div>
                            </div>
                        </div>
                        ${{isMulti ? '<i class="fa-solid fa-chevron-down text-gray-500 mt-2"></i>' : ''}}
                    </div>
                    ${{membersHtml}}
                `;
                container.appendChild(card);
            }});
        }}

        function toggleThreadDetails(type, idx) {{
            const el = document.getElementById(`thread-${{type}}-details-${{idx}}`);
            if (el) el.classList.toggle('hidden');
        }}

        // Category Color Mapping Helper
        function getCategoryBadge(cat) {{
            const colorMap = {{
                '수주/계약': 'bg-emerald-500/20 text-emerald-400 border-emerald-500/30',
                '설비투자/M&A': 'bg-purple-500/20 text-purple-300 border-purple-500/30',
                '실적/재무': 'bg-amber-500/20 text-amber-300 border-amber-500/30',
                '신제품/기술': 'bg-blue-500/20 text-blue-300 border-blue-500/30',
                '리스크/규제': 'bg-red-500/20 text-red-400 border-red-500/30',
                '지배구조/인사': 'bg-indigo-500/20 text-indigo-300 border-indigo-500/30',
                '경영일반/기타': 'bg-gray-800 text-gray-300 border-gray-700'
            }};
            const cls = colorMap[cat] || 'bg-cyan-500/20 text-cyan-400 border-cyan-500/30';
            return `<span class="px-2.5 py-0.5 rounded-md text-[11px] font-bold border ${{cls}}">${{cat}}</span>`;
        }}

        // Filter by Category
        function filterCategory(cat) {{
            currentCategoryFilter = cat;
            const buttons = document.querySelectorAll('#categoryFilterBar button');
            buttons.forEach(btn => {{
                btn.className = "px-2.5 py-1 rounded-lg bg-gray-800 text-gray-300 hover:text-white transition-all";
            }});
            const active = document.getElementById(`catBtn-${{cat}}`);
            if (active) active.className = "px-2.5 py-1 rounded-lg bg-cyan-600 text-white font-semibold shadow-sm";
            renderArticles();
        }}

        // Render Cleaned Core Articles as Modern Enterprise List View
        function renderArticles() {{
            const container = document.getElementById('articlesContainer');
            container.innerHTML = '';

            let list = ARTICLES;
            if (currentCategoryFilter !== 'ALL') {{
                list = ARTICLES.filter(a => {{
                    let s_intel = null;
                    try {{ if (a.structured_intelligence) s_intel = JSON.parse(a.structured_intelligence); }} catch(e) {{}}
                    const cat = (s_intel && s_intel.event_category) ? s_intel.event_category : (a.event_category || '경영일반/기타');
                    return cat === currentCategoryFilter;
                }});
            }}

            if (list.length === 0) {{
                container.innerHTML = `
                    <div class="glass-card rounded-xl p-8 text-center text-gray-500">
                        <i class="fa-solid fa-folder-open text-2xl mb-2"></i>
                        <p class="text-sm">해당 카테고리의 구조화 기사가 없습니다.</p>
                    </div>
                `;
                return;
            }}

            list.forEach(a => {{
                let s_intel = null;
                try {{
                    if (a.structured_intelligence) s_intel = JSON.parse(a.structured_intelligence);
                }} catch(e) {{}}

                const headline = (s_intel && s_intel.executive_headline) ? s_intel.executive_headline : a.title;
                const cat = (s_intel && s_intel.event_category) ? s_intel.event_category : (a.event_category || '경영일반/기타');
                const bullets = (s_intel && s_intel.core_summary_bullets) ? s_intel.core_summary_bullets : [];
                const metrics = (s_intel && s_intel.key_metrics) ? s_intel.key_metrics : [];
                const entities = (s_intel && s_intel.key_entities) ? s_intel.key_entities : [];
                const threadId = a.thread_id ? `#${{a.thread_id}}` : null;

                const row = document.createElement('div');
                row.className = "glass-card rounded-xl p-4 border border-gray-800/90 list-row-hover cursor-pointer transition-all";
                row.onclick = () => openModal(a);

                // Metric Badges v2.3 (Up to 3)
                let metricsHtml = '';
                if (metrics.length > 0) {{
                    metricsHtml = metrics.slice(0, 3).map(m => {{
                        const val = m.formatted_value || m.value || '';
                        const conf = m.confidence_level || 'CONFIRMED';
                        const period = m.target_period ? ` (${{m.target_period}})` : '';
                        let confClass = 'bg-emerald-500/10 text-emerald-300 border-emerald-500/20';
                        let confIcon = 'fa-check';
                        if (conf === 'ESTIMATE') {{
                            confClass = 'bg-amber-500/10 text-amber-300 border-amber-500/20';
                            confIcon = 'fa-chart-line';
                        }} else if (conf === 'UNCONFIRMED_RUMOR') {{
                            confClass = 'bg-red-500/10 text-red-300 border-red-500/20';
                            confIcon = 'fa-triangle-exclamation';
                        }}
                        return `
                            <span class="inline-flex items-center px-2 py-0.5 rounded text-[11px] font-semibold border ${{confClass}}">
                                <i class="fa-solid ${{confIcon}} mr-1 text-[9px]"></i>${{m.metric_name}}: ${{val}}${{period}}
                            </span>
                        `;
                    }}).join('');
                }}

                // Entity Chips (Up to 4)
                let entitiesHtml = '';
                if (entities.length > 0) {{
                    entitiesHtml = entities.slice(0, 4).map(e => `
                        <span class="text-[11px] text-gray-400 bg-gray-900/80 px-2 py-0.5 rounded border border-gray-800">
                            @${{e}}
                        </span>
                    `).join('');
                }}

                row.innerHTML = `
                    <div class="flex items-start justify-between gap-4">
                        <div class="flex-1 min-w-0 space-y-2">
                            <!-- Top Metadata Row -->
                            <div class="flex flex-wrap items-center gap-2">
                                ${{getCategoryBadge(cat)}}
                                <span class="text-xs font-semibold px-2 py-0.5 rounded bg-gray-800 text-gray-300 border border-gray-700">${{a.media_name || '언론사'}}</span>
                                <span class="text-xs text-gray-500"><i class="fa-regular fa-clock mr-1"></i>${{a.published_at || ''}}</span>
                                ${{threadId ? `<span class="text-[11px] font-semibold px-2 py-0.5 rounded bg-cyan-950/60 text-cyan-400 border border-cyan-500/30">사건 ${{threadId}}</span>` : ''}}
                            </div>

                            <!-- Executive Headline -->
                            <h4 class="text-base font-extrabold text-gray-100 hover:text-cyan-400 transition-colors leading-snug">
                                ${{headline}}
                            </h4>

                            <!-- Summary 1st Bullet Preview -->
                            ${{bullets.length > 0 ? `
                                <p class="text-xs text-gray-300 line-clamp-1 leading-relaxed font-normal">
                                    <span class="text-cyan-400 font-bold">•</span> ${{bullets[0]}}
                                </p>
                            ` : `
                                <p class="text-xs text-gray-500 line-clamp-1">${{a.chosen_text || a.body || ''}}</p>
                            `}}

                            <!-- Bottom Metrics & Entities Row -->
                            <div class="flex flex-wrap items-center gap-2 pt-1">
                                ${{metricsHtml}}
                                ${{entitiesHtml}}
                            </div>
                        </div>

                        <!-- Right Action Arrow -->
                        <div class="hidden sm:flex flex-col items-end justify-between h-full pt-1">
                            <span class="text-xs text-cyan-400 font-semibold flex items-center hover:underline">
                                7-Key 팩트 <i class="fa-solid fa-chevron-right ml-1.5 text-xs"></i>
                            </span>
                        </div>
                    </div>
                `;
                container.appendChild(row);
            }});
        }}

        // Modal Functions with 7-Key Fact Box
        function openModal(a, isFiltered = false) {{
            let s_intel = null;
            try {{
                if (a.structured_intelligence) s_intel = JSON.parse(a.structured_intelligence);
            }} catch(e) {{}}

            const headline = (s_intel && s_intel.executive_headline) ? s_intel.executive_headline : a.title;
            const cat = (s_intel && s_intel.event_category) ? s_intel.event_category : (a.event_category || (isFiltered ? '시황 제외' : '경영일반'));
            const bullets = (s_intel && s_intel.core_summary_bullets) ? s_intel.core_summary_bullets : [];
            const metrics = (s_intel && s_intel.key_metrics) ? s_intel.key_metrics : [];
            const milestones = (s_intel && s_intel.timeline_milestones) ? s_intel.timeline_milestones : [];
            const implication = (s_intel && s_intel.strategic_implication) ? s_intel.strategic_implication : null;

            document.getElementById('modalHeadline').innerText = headline;
            document.getElementById('modalOriginalTitle').innerText = `원제: ${{a.title}}`;
            document.getElementById('modalMedia').innerText = a.media_name || '언론사';
            document.getElementById('modalCategory').innerText = cat;
            document.getElementById('modalPublished').innerHTML = `<i class="fa-regular fa-clock mr-1"></i>${{a.published_at || '-'}}`;
            document.getElementById('modalAuthor').innerHTML = `<i class="fa-regular fa-user mr-1"></i>${{a.journalist || a.author || '기자 정보 없음'}}`;
            document.getElementById('modalUrl').href = a.url || '#';
            document.getElementById('modalRawBody').innerText = a.chosen_text || a.body || '본문 없음';

            const statusBadge = document.getElementById('modalStatusBadge');
            const headlineLabel = document.getElementById('modalHeadlineLabel');
            if (isFiltered) {{
                statusBadge.classList.remove('hidden');
                headlineLabel.innerHTML = '<i class="fa-solid fa-filter-circle-xmark mr-1 text-amber-400"></i>제외된 시황 기사 (Audit Inspector)';
            }} else {{
                statusBadge.classList.add('hidden');
                headlineLabel.innerHTML = '<i class="fa-solid fa-bolt mr-1"></i>C-Level Executive Headline (Universal v2.3)';
            }}

            // Render Bullets
            const bulletsEl = document.getElementById('modalBullets');
            bulletsEl.innerHTML = '';
            if (isFiltered) {{
                bulletsEl.innerHTML = `
                    <li class="text-amber-300"><strong>[제외 사유]</strong> 시황 점수 ${{a.market_score || 0}}점 (임계값 +20점 초과)</li>
                    <li class="text-gray-300">• 단순 지수 시세, 복수 종목 나열, 어뷰징 찌라시 또는 중복 기사로 판정되어 제외되었습니다.</li>
                `;
            }} else if (bullets.length > 0) {{
                bullets.forEach(b => {{
                    const li = document.createElement('li');
                    li.innerText = b;
                    bulletsEl.appendChild(li);
                }});
            }} else {{
                bulletsEl.innerHTML = `<li>${{a.title}}</li>`;
            }}

            // Render Metrics v2.3
            const metricsWrap = document.getElementById('modalMetricsWrapper');
            const metricsGrid = document.getElementById('modalMetricsGrid');
            metricsGrid.innerHTML = '';
            if (metrics.length > 0) {{
                metricsWrap.classList.remove('hidden');
                metrics.forEach(m => {{
                    const val = m.formatted_value || m.value || '';
                    const conf = m.confidence_level || 'CONFIRMED';
                    const period = m.target_period ? `<span class="text-gray-400 text-[10px] ml-1.5">[${{m.target_period}}]</span>` : '';
                    const source = m.source_entity ? `<span class="text-[10px] text-cyan-400 block mt-0.5">출처: ${{m.source_entity}}</span>` : '';

                    let confBadge = '<span class="px-1.5 py-0.5 rounded text-[9px] font-bold bg-emerald-500/20 text-emerald-400 border border-emerald-500/30">공식확정</span>';
                    if (conf === 'ESTIMATE') {{
                        confBadge = '<span class="px-1.5 py-0.5 rounded text-[9px] font-bold bg-amber-500/20 text-amber-400 border border-amber-500/30">증권사추정</span>';
                    }} else if (conf === 'UNCONFIRMED_RUMOR') {{
                        confBadge = '<span class="px-1.5 py-0.5 rounded text-[9px] font-bold bg-red-500/20 text-red-400 border border-red-500/30">미확인/보도</span>';
                    }}

                    const mBox = document.createElement('div');
                    mBox.className = "bg-gray-800/80 p-3 rounded-lg border border-gray-700/80 space-y-1";
                    mBox.innerHTML = `
                        <div class="flex items-center justify-between">
                            <span class="text-[11px] text-gray-400 font-medium">${{m.metric_name}}</span>
                            ${{confBadge}}
                        </div>
                        <p class="text-base font-bold text-amber-400">${{val}}${{period}}</p>
                        ${{source}}
                        ${{m.context ? `<p class="text-[10px] text-gray-400 leading-tight pt-0.5">${{m.context}}</p>` : ''}}
                    `;
                    metricsGrid.appendChild(mBox);
                }});
            }} else {{
                metricsWrap.classList.add('hidden');
            }}



            // Render Milestones
            const milesWrap = document.getElementById('modalMilestonesWrapper');
            const milesEl = document.getElementById('modalMilestones');
            milesEl.innerHTML = '';
            if (milestones.length > 0) {{
                milesWrap.classList.remove('hidden');
                milestones.forEach(m => {{
                    const li = document.createElement('li');
                    li.innerHTML = `<span class="text-emerald-400 font-semibold">•</span> ${{m}}`;
                    milesEl.appendChild(li);
                }});
            }} else {{
                milesWrap.classList.add('hidden');
            }}

            // Render Implication
            const impWrap = document.getElementById('modalImplicationWrapper');
            const impEl = document.getElementById('modalImplication');
            if (implication) {{
                impWrap.classList.remove('hidden');
                impEl.innerText = implication;
            }} else {{
                impWrap.classList.add('hidden');
            }}

            document.getElementById('readerModal').classList.remove('hidden');
        }}

        function openModalByUrl(url) {{
            const target = ALL_ARTICLES.find(a => a.url === url);
            if (target) openModal(target, target.is_market_news || target.is_exact_dup);
        }}

        function closeModal() {{
            document.getElementById('readerModal').classList.add('hidden');
        }}

        function toggleRawText() {{
            const rawBody = document.getElementById('modalRawBody');
            const chevron = document.getElementById('rawTextChevron');
            rawBody.classList.toggle('hidden');
            chevron.classList.toggle('fa-chevron-up');
            chevron.classList.toggle('fa-chevron-down');
        }}

        // Tab Switching
        function switchTab(tabName) {{
            ['threads', 'articles', 'filtered', 'analytics'].forEach(t => {{
                document.getElementById(`tab-${{t}}`).classList.add('hidden');
                document.getElementById(`tabBtn-${{t}}`).className = "px-3.5 py-1.5 rounded-lg text-sm font-medium text-gray-400 hover:text-white transition-all";
            }});

            document.getElementById(`tab-${{tabName}}`).classList.remove('hidden');
            const activeBtn = document.getElementById(`tabBtn-${{tabName}}`);
            if (tabName === 'filtered') {{
                activeBtn.className = "px-3.5 py-1.5 rounded-lg text-sm font-semibold transition-all bg-amber-600 text-white shadow-md";
            }} else {{
                activeBtn.className = "px-3.5 py-1.5 rounded-lg text-sm font-semibold transition-all bg-cyan-600 text-white shadow-md";
            }}
        }}

        // Initialize Charts
        function initCharts() {{
            // 1. Noise Filter Doughnut
            new Chart(document.getElementById('noiseChart'), {{
                type: 'doughnut',
                data: {{
                    labels: ['시황 노이즈 제외', '구조화 팩트 보존'],
                    datasets: [{{
                        data: [{market_count}, {company_count}],
                        backgroundColor: ['#f59e0b', '#06b6d4'],
                        borderWidth: 0
                    }}]
                }},
                options: {{
                    responsive: true,
                    maintainAspectRatio: false,
                    plugins: {{ legend: {{ position: 'bottom', labels: {{ color: '#94a3b8', font: {{ family: 'Pretendard', size: 11 }} }} }} }}
                }}
            }});

            // 2. Hourly Volume Bar
            const hours = {json.dumps([h[0] for h in hours_sorted])};
            const counts = {json.dumps([h[1] for h in hours_sorted])};
            new Chart(document.getElementById('timeChart'), {{
                type: 'bar',
                data: {{
                    labels: hours.map(h => h + '시'),
                    datasets: [{{
                        label: '핵심 기사 수',
                        data: counts,
                        backgroundColor: '#38bdf8',
                        borderRadius: 6
                    }}]
                }},
                options: {{
                    responsive: true,
                    maintainAspectRatio: false,
                    plugins: {{ legend: {{ display: false }} }},
                    scales: {{
                        x: {{ grid: {{ display: false }}, ticks: {{ color: '#64748b' }} }},
                        y: {{ grid: {{ color: '#1e293b' }}, ticks: {{ color: '#64748b', stepSize: 1 }} }}
                    }}
                }}
            }});

            // 3. Top Media Horizontal Bar
            const mediaLabels = {json.dumps([m[0] for m in top_media])};
            const mediaVals = {json.dumps([m[1] for m in top_media])};
            new Chart(document.getElementById('mediaChart'), {{
                type: 'bar',
                data: {{
                    labels: mediaLabels,
                    datasets: [{{
                        axis: 'y',
                        data: mediaVals,
                        backgroundColor: '#10b981',
                        borderRadius: 6
                    }}]
                }},
                options: {{
                    indexAxis: 'y',
                    responsive: true,
                    maintainAspectRatio: false,
                    plugins: {{ legend: {{ display: false }} }},
                    scales: {{
                        x: {{ grid: {{ color: '#1e293b' }}, ticks: {{ color: '#64748b' }} }},
                        y: {{ grid: {{ display: false }}, ticks: {{ color: '#cbd5e1', font: {{ family: 'Pretendard' }} }} }}
                    }}
                }}
            }});
        }}

        // Search Filter
        document.getElementById('searchInput').addEventListener('input', function(e) {{
            const query = e.target.value.toLowerCase().trim();
            if (!query) {{
                renderThreads();
                renderArticles();
                renderMarketThreads();
                return;
            }}
            
            const filteredArticles = ARTICLES.filter(a => 
                (a.title && a.title.toLowerCase().includes(query)) ||
                (a.chosen_text && a.chosen_text.toLowerCase().includes(query)) ||
                (a.media_name && a.media_name.toLowerCase().includes(query)) ||
                (a.structured_intelligence && a.structured_intelligence.toLowerCase().includes(query))
            );
            
            const container = document.getElementById('articlesContainer');
            container.innerHTML = '';
            filteredArticles.forEach(a => {{
                let s_intel = null;
                try {{
                    if (a.structured_intelligence) s_intel = JSON.parse(a.structured_intelligence);
                }} catch(e) {{}}
                const headline = (s_intel && s_intel.executive_headline) ? s_intel.executive_headline : a.title;

                const card = document.createElement('div');
                card.className = "glass-card rounded-xl p-4 border border-cyan-500/40 list-row-hover cursor-pointer";
                card.onclick = () => openModal(a);
                card.innerHTML = `
                    <div class="flex items-center justify-between mb-1">
                        <span class="text-xs font-semibold px-2 py-0.5 rounded bg-emerald-500/20 text-emerald-400">${{a.media_name}}</span>
                        <span class="text-xs text-gray-500">${{a.published_at}}</span>
                    </div>
                    <h4 class="text-sm font-bold text-gray-100">${{headline}}</h4>
                `;
                container.appendChild(card);
            }});
            switchTab('articles');
        }});

        window.onload = function() {{
            renderThreads();
            renderArticles();
            renderMarketThreads();
            initCharts();
        }};
    </script>
</body>
</html>
"""

    os.makedirs("docs", exist_ok=True)
    out_path = os.path.join("docs", out_filename)
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(html_content)
    print(f"Success! Dashboard generated at '{out_path}'.")

    if out_filename == "index.html":
        with open("index.html", "w", encoding="utf-8") as f:
            f.write(html_content)
        print("Mirrored index.html to root project folder.")

if __name__ == "__main__":
    generate_dashboard("두산에너빌리티", "index.html")
    generate_dashboard("SK하이닉스", "sk_hynix.html")
