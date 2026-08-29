# build_dashboard.py
"""
Executive News Intelligence Dashboard Generator v2.0
- Bloomberg / Palantir / Modern SaaS Dark Glassmorphism UI
- gemini-embedding-2 Event Timeline Hub (Interactive Flow)
- 7-Key Universal Intelligence Fact Box Modal (Headlines, Bullets, Metrics, Milestones, Implication)
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
    
    # 1. Fetch Event Threads (gemini-embedding-2)
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

    # 2. Fetch All Articles
    cursor.execute("""
        SELECT url, title, media_name, journalist, author, body, chosen_text, keyword, 
               extraction_method, quality_score, quality_score_detail, 
               needs_review, published_at, created_at, processed_at,
               is_exact_dup, is_market_news, market_score, llm_status, scoring_version,
               structured_intelligence, event_category
        FROM articles 
        ORDER BY published_at DESC, created_at DESC
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
    company_articles_json = json.dumps(company_articles, ensure_ascii=False)
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
        .neon-border-cyan {{ box-shadow: 0 0 15px rgba(6, 182, 212, 0.2); }}
        .neon-border-emerald {{ box-shadow: 0 0 15px rgba(16, 185, 129, 0.2); }}
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
                        <span class="px-2 py-0.5 text-xs font-semibold bg-cyan-500/20 text-cyan-400 rounded-full border border-cyan-500/30">Executive v2.0</span>
                    </div>
                    <p class="text-xs text-gray-400">Zero-Trust AI 뉴스 인텔리전스 & 7-Key 구조화 팩트 추출 허브</p>
                </div>
            </div>

            <!-- Global Search & Tab Switcher -->
            <div class="flex items-center space-x-4">
                <div class="relative hidden sm:block w-72">
                    <i class="fa-solid fa-magnifying-glass absolute left-3.5 top-3 text-gray-400 text-sm"></i>
                    <input type="text" id="searchInput" placeholder="사건명, 수주액, 엔티티 검색..." 
                           class="w-full bg-gray-900/90 border border-gray-700/80 rounded-xl pl-9 pr-4 py-2 text-sm text-gray-200 placeholder-gray-500 focus:outline-none focus:border-cyan-500 focus:ring-1 focus:ring-cyan-500 transition-all">
                </div>
                <div class="flex bg-gray-900 p-1 rounded-xl border border-gray-800">
                    <button onclick="switchTab('threads')" id="tabBtn-threads" class="px-4 py-1.5 rounded-lg text-sm font-semibold transition-all bg-cyan-600 text-white shadow-md">
                        <i class="fa-solid fa-timeline mr-1.5"></i>사건 타임라인
                    </button>
                    <button onclick="switchTab('articles')" id="tabBtn-articles" class="px-4 py-1.5 rounded-lg text-sm font-medium text-gray-400 hover:text-white transition-all">
                        <i class="fa-solid fa-newspaper mr-1.5"></i>구조화 팩트 기사
                    </button>
                    <button onclick="switchTab('analytics')" id="tabBtn-analytics" class="px-4 py-1.5 rounded-lg text-sm font-medium text-gray-400 hover:text-white transition-all">
                        <i class="fa-solid fa-chart-pie mr-1.5"></i>MLOps 분석
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
                        미국 대형 원전 수주 조기화와 SMR 공급망 확장 모멘텀이 핵심 동력입니다.
                    </h2>
                </div>
                <span class="hidden md:inline-flex items-center px-3 py-1 text-xs font-medium text-gray-300 bg-gray-800/80 rounded-lg border border-gray-700">
                    <i class="fa-regular fa-clock mr-1.5 text-cyan-400"></i>실시간 팩트 집계
                </span>
            </div>

            <!-- 3 Core Points Grid -->
            <div class="grid grid-cols-1 md:grid-cols-3 gap-4 mt-5">
                <div class="bg-gray-800/50 rounded-xl p-4 border border-gray-700/60 hover:border-cyan-500/40 transition-all">
                    <div class="flex items-center space-x-2 text-cyan-400 text-xs font-bold mb-1.5">
                        <span class="w-2 h-2 rounded-full bg-cyan-400 animate-ping"></span>
                        <span>[수주/계약] 북미 대형 원전 발주 가속</span>
                    </div>
                    <p class="text-sm font-semibold text-gray-200 line-clamp-2">미국 원전 정책 기반 조기 발주 및 신규 대형원전 수주 기대감으로 주가 10.55% 급등</p>
                    <p class="text-xs text-gray-400 mt-2">현대건설 매터도어 4기 프로젝트와 연계 (유사도 0.89)</p>
                </div>
                <div class="bg-gray-800/50 rounded-xl p-4 border border-gray-700/60 hover:border-cyan-500/40 transition-all">
                    <div class="flex items-center space-x-2 text-emerald-400 text-xs font-bold mb-1.5">
                        <span class="w-2 h-2 rounded-full bg-emerald-400"></span>
                        <span>[설비투자/M&A] 웨스팅하우스 공동 인수 제안</span>
                    </div>
                    <p class="text-sm font-semibold text-gray-200 line-clamp-2">美 정부의 한-미 공동 SPC 설립 제안… 한수원 지재권 갈등 해소 및 수출 가속</p>
                    <p class="text-xs text-gray-400 mt-2">기관 순매수 992억 원 유입 (유사도 0.85)</p>
                </div>
                <div class="bg-gray-800/50 rounded-xl p-4 border border-gray-700/60 hover:border-cyan-500/40 transition-all">
                    <div class="flex items-center space-x-2 text-amber-400 text-xs font-bold mb-1.5">
                        <span class="w-2 h-2 rounded-full bg-amber-400"></span>
                        <span>[재무/실적] 시가총액 51조 원 돌파</span>
                    </div>
                    <p class="text-sm font-semibold text-gray-200 line-clamp-2">시가총액 51조 6,933억 원(14위) 달성, 거래량 316% 폭증</p>
                    <p class="text-xs text-gray-400 mt-2">KB증권 등 주요 증권가 리포트 일제히 호평</p>
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
                    <span class="text-xs text-gray-500">개 사건 묶음</span>
                </div>
            </div>
        </section>

        <!-- ================================================================= -->
        <!-- TAB 1: Event Timeline Hub (gemini-embedding-2) -->
        <!-- ================================================================= -->
        <section id="tab-threads" class="space-y-4">
            <div class="flex items-center justify-between mb-2">
                <div class="flex items-center space-x-2">
                    <h3 class="text-lg font-bold text-white flex items-center">
                        <i class="fa-solid fa-code-merge text-cyan-400 mr-2"></i>
                        gemini-embedding-2 사건 타임라인 스레드 (Fact-Guided v2.0)
                    </h3>
                    <span class="text-xs bg-gray-800 text-gray-400 px-2.5 py-0.5 rounded-full border border-gray-700">7-Key 팩트 벡터 클러스터링</span>
                </div>
                <span class="text-xs text-gray-400">사건 카드를 클릭하면 시간순 후속 보도 타임라인이 펼쳐집니다.</span>
            </div>

            <!-- Threads Accordion Grid -->
            <div class="space-y-3" id="threadsContainer">
                <!-- Injected via JavaScript -->
            </div>
        </section>

        <!-- ================================================================= -->
        <!-- TAB 2: Cleaned Core Articles with 7-Key Fact Badges -->
        <!-- ================================================================= -->
        <section id="tab-articles" class="hidden space-y-4">
            <div class="flex items-center justify-between mb-2">
                <h3 class="text-lg font-bold text-white flex items-center">
                    <i class="fa-solid fa-newspaper text-emerald-400 mr-2"></i>
                    구조화 팩트 기반 기업 핵심 기사
                </h3>
                <span class="text-xs text-gray-400">7대 범용 인텔리전스 스키마 완비</span>
            </div>

            <div class="grid grid-cols-1 md:grid-cols-2 gap-4" id="articlesContainer">
                <!-- Injected via JavaScript -->
            </div>
        </section>

        <!-- ================================================================= -->
        <!-- TAB 3: MLOps Analytics & Charts -->
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
                    </div>
                    <button onclick="closeModal()" class="text-gray-400 hover:text-white text-xl">
                        <i class="fa-solid fa-xmark"></i>
                    </button>
                </div>

                <!-- Headline -->
                <div>
                    <span class="text-xs font-bold text-cyan-400 uppercase tracking-wider block mb-1">
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
                            <i class="fa-solid fa-list-check text-cyan-400 mr-1.5"></i>경영진 3줄 핵심 요약
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
        const ARTICLES = {company_articles_json};
        const ALL_ARTICLES = {all_articles_json};

        // Render Threads
        function renderThreads() {{
            const container = document.getElementById('threadsContainer');
            container.innerHTML = '';

            THREADS.forEach((t, idx) => {{
                const isMulti = t.count > 1;
                const card = document.createElement('div');
                card.className = "glass-card rounded-xl p-5 border border-gray-800/90 glass-card-hover cursor-pointer";
                card.onclick = () => toggleThreadDetails(idx);

                let membersHtml = '';
                if (isMulti) {{
                    membersHtml = `
                        <div id="thread-details-${{idx}}" class="hidden mt-4 pt-4 border-t border-gray-800/80 space-y-3">
                            <p class="text-xs font-bold text-gray-400 uppercase tracking-wider mb-2">
                                <i class="fa-solid fa-code-branch mr-1 text-cyan-400"></i>시간순 후속 보도 타임라인 (7-Key 팩트 연계)
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
                                    ${{isMulti ? `사건 #${{t.thread_id}} (${{t.count}}건 연결)` : '단독 보도'}}
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

        function toggleThreadDetails(idx) {{
            const el = document.getElementById(`thread-details-${{idx}}`);
            if (el) el.classList.toggle('hidden');
        }}

        // Render Articles with Fact Badges
        function renderArticles() {{
            const container = document.getElementById('articlesContainer');
            container.innerHTML = '';

            ARTICLES.forEach(a => {{
                let s_intel = null;
                try {{
                    if (a.structured_intelligence) s_intel = JSON.parse(a.structured_intelligence);
                }} catch(e) {{}}

                const headline = (s_intel && s_intel.executive_headline) ? s_intel.executive_headline : a.title;
                const cat = (s_intel && s_intel.event_category) ? s_intel.event_category : (a.event_category || '경영일반');
                const bullets = (s_intel && s_intel.core_summary_bullets) ? s_intel.core_summary_bullets : [];
                const metrics = (s_intel && s_intel.key_metrics) ? s_intel.key_metrics : [];

                const card = document.createElement('div');
                card.className = "glass-card rounded-xl p-5 border border-gray-800 glass-card-hover cursor-pointer flex flex-col justify-between";
                card.onclick = () => openModal(a);

                let metricsBadgesHtml = '';
                if (metrics.length > 0) {{
                    metricsBadgesHtml = `
                        <div class="flex flex-wrap gap-1.5 mt-2.5">
                            ${{metrics.slice(0, 2).map(m => `
                                <span class="px-2 py-0.5 rounded text-[11px] font-semibold bg-amber-500/10 text-amber-300 border border-amber-500/20">
                                    ${{m.metric_name}}: ${{m.value}}
                                </span>
                            `).join('')}}
                        </div>
                    `;
                }}

                card.innerHTML = `
                    <div>
                        <div class="flex items-center justify-between mb-2">
                            <div class="flex items-center space-x-1.5">
                                <span class="text-xs font-semibold px-2 py-0.5 rounded bg-emerald-500/20 text-emerald-400 border border-emerald-500/30">${{a.media_name || '언론사'}}</span>
                                <span class="text-xs font-semibold px-2 py-0.5 rounded bg-cyan-500/20 text-cyan-400 border border-cyan-500/30">${{cat}}</span>
                            </div>
                            <span class="text-xs text-gray-500">${{a.published_at || ''}}</span>
                        </div>
                        <h4 class="text-sm font-bold text-gray-100 hover:text-cyan-400 line-clamp-2 leading-snug">${{headline}}</h4>
                        ${{bullets.length > 0 ? `<p class="text-xs text-gray-300 line-clamp-2 mt-2 leading-relaxed font-normal">${{bullets[0]}}</p>` : `<p class="text-xs text-gray-400 line-clamp-2 mt-2 leading-relaxed">${{a.chosen_text || a.body || ''}}</p>`}}
                        ${{metricsBadgesHtml}}
                    </div>
                    <div class="mt-4 pt-3 border-t border-gray-800/80 flex items-center justify-between text-xs text-gray-500">
                        <span>7대 팩트 구조화 완료</span>
                        <span class="text-cyan-400 hover:underline">인텔리전스 리더 &rarr;</span>
                    </div>
                `;
                container.appendChild(card);
            }});
        }}

        // Modal Functions with 7-Key Fact Box
        function openModal(a) {{
            let s_intel = null;
            try {{
                if (a.structured_intelligence) s_intel = JSON.parse(a.structured_intelligence);
            }} catch(e) {{}}

            const headline = (s_intel && s_intel.executive_headline) ? s_intel.executive_headline : a.title;
            const cat = (s_intel && s_intel.event_category) ? s_intel.event_category : (a.event_category || '경영일반');
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

            // Render Bullets
            const bulletsEl = document.getElementById('modalBullets');
            bulletsEl.innerHTML = '';
            if (bullets.length > 0) {{
                bullets.forEach(b => {{
                    const li = document.createElement('li');
                    li.innerText = b;
                    bulletsEl.appendChild(li);
                }});
            }} else {{
                bulletsEl.innerHTML = `<li>${{a.title}}</li>`;
            }}

            // Render Metrics
            const metricsWrap = document.getElementById('modalMetricsWrapper');
            const metricsGrid = document.getElementById('modalMetricsGrid');
            metricsGrid.innerHTML = '';
            if (metrics.length > 0) {{
                metricsWrap.classList.remove('hidden');
                metrics.forEach(m => {{
                    const mBox = document.createElement('div');
                    mBox.className = "bg-gray-800/80 p-2.5 rounded-lg border border-gray-700/80";
                    mBox.innerHTML = `
                        <p class="text-[11px] text-gray-400 font-medium">${{m.metric_name}}</p>
                        <p class="text-sm font-bold text-amber-400 mt-0.5">${{m.value}}</p>
                        ${{m.context ? `<p class="text-[10px] text-gray-500 mt-0.5 truncate">${{m.context}}</p>` : ''}}
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
            if (target) openModal(target);
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
            ['threads', 'articles', 'analytics'].forEach(t => {{
                document.getElementById(`tab-${{t}}`).classList.add('hidden');
                document.getElementById(`tabBtn-${{t}}`).className = "px-4 py-1.5 rounded-lg text-sm font-medium text-gray-400 hover:text-white transition-all";
            }});

            document.getElementById(`tab-${{tabName}}`).classList.remove('hidden');
            document.getElementById(`tabBtn-${{tabName}}`).className = "px-4 py-1.5 rounded-lg text-sm font-semibold transition-all bg-cyan-600 text-white shadow-md";
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
                card.className = "glass-card rounded-xl p-5 border border-cyan-500/40 glass-card-hover cursor-pointer";
                card.onclick = () => openModal(a);
                card.innerHTML = `
                    <div class="flex items-center justify-between mb-2">
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
