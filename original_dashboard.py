# build_dashboard.py
import os
import sqlite3
import json
from datetime import datetime
from config import DB_PATH

def get_articles_data():
    """Fetches articles and keyword statistics from the database."""
    if not os.path.exists(DB_PATH):
        return [], [], "N/A"
        
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    try:
        # Fetch all articles ordered by created_at DESC
        cursor.execute("""
            SELECT url, title, media_name, journalist, body, keyword, created_at 
            FROM articles 
            ORDER BY created_at DESC
        """)
        articles = [dict(row) for row in cursor.fetchall()]
        
        # Fetch statistics
        cursor.execute("SELECT keyword, COUNT(*) as count FROM articles GROUP BY keyword")
        stats = {row['keyword']: row['count'] for row in cursor.fetchall()}
        
        # Get latest crawl time
        cursor.execute("SELECT MAX(created_at) FROM articles")
        latest_crawl = cursor.fetchone()[0]
        if latest_crawl:
            # Parse ISO format and make it human readable
            try:
                dt = datetime.fromisoformat(latest_crawl)
                latest_crawl_str = dt.strftime("%Y-%m-%d %H:%M:%S")
            except Exception:
                latest_crawl_str = latest_crawl
        else:
            latest_crawl_str = "N/A"
            
        return articles, stats, latest_crawl_str
    except sqlite3.OperationalError as e:
        print(f"Database error: {e}")
        return [], {}, "N/A"
    finally:
        conn.close()

def generate_html(articles, stats, latest_crawl):
    """Generates the HTML dashboard content with premium dark theme and glassmorphism."""
    # List of unique keywords
    keywords = sorted(list(set(article['keyword'] for article in articles)))
    
    # Calculate statistics
    total_articles = len(articles)
    
    # Build dynamic cards for statistics
    stats_html = ""
    for kw in keywords:
        count = stats.get(kw, 0)
        stats_html += f"""
        <div class="stats-card">
            <div class="stats-label">{kw}</div>
            <div class="stats-value">{count}</div>
        </div>
        """
        
    # Serialize articles for JS usage
    articles_json = json.dumps(articles, ensure_ascii=False)
    
    # Keyword colors map for JavaScript
    keyword_colors = {
        "인공지능": "violet",
        "KB금융": "emerald",
        "크롤링": "amber"
    }
    keyword_colors_json = json.dumps(keyword_colors, ensure_ascii=False)
    
    # Render static fallback cards (SEO/Fast-load friendly)
    fallback_cards_html = ""
    for article in articles[:9]:  # first 9 articles
        kw = article['keyword']
        color_class = keyword_colors.get(kw, "slate")
        preview = article['body'][:200].replace('\n', ' ') + "..."
        
        # Human readable date
        try:
            date_str = datetime.fromisoformat(article['created_at']).strftime("%Y-%m-%d")
        except Exception:
            date_str = article['created_at'][:10]
            
        fallback_cards_html += f"""
        <div class="article-card active" data-keyword="{kw}">
            <div class="card-header">
                <span class="badge badge-{color_class}">{kw}</span>
                <span class="card-date">{date_str}</span>
            </div>
            <h3 class="card-title">
                <a href="{article['url']}" target="_blank">{article['title']}</a>
            </h3>
            <div class="card-meta">
                <span>📰 {article['media_name']}</span>
                <span>✍️ {article['journalist']}</span>
            </div>
            <p class="card-body">{preview}</p>
        </div>
        """

    html_template = f"""<!DOCTYPE html>
<html lang="ko">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>AI & Finance News Dashboard</title>
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@300;400;500;600;700&family=Noto+Sans+KR:wght@300;400;500;700&display=swap" rel="stylesheet">
    <style>
        :root {{
            --bg-dark: #090d16;
            --bg-card: rgba(22, 28, 45, 0.4);
            --bg-card-hover: rgba(30, 41, 59, 0.6);
            --border-glow: rgba(99, 102, 241, 0.15);
            --border-glow-hover: rgba(99, 102, 241, 0.3);
            --text-primary: #f8fafc;
            --text-secondary: #94a3b8;
            --accent-violet: #8b5cf6;
            --accent-emerald: #10b981;
            --accent-amber: #f59e0b;
            --accent-slate: #64748b;
        }}

        * {{
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }}

        body {{
            background-color: var(--bg-dark);
            background-image: 
                radial-gradient(at 0% 0%, rgba(99, 102, 241, 0.1) 0px, transparent 50%),
                radial-gradient(at 100% 0%, rgba(16, 185, 129, 0.05) 0px, transparent 50%),
                radial-gradient(at 50% 100%, rgba(245, 158, 11, 0.05) 0px, transparent 50%);
            background-attachment: fixed;
            color: var(--text-primary);
            font-family: 'Plus Jakarta Sans', 'Noto Sans KR', sans-serif;
            min-height: 100vh;
            line-height: 1.6;
        }}

        .container {{
            max-width: 1280px;
            margin: 0 auto;
            padding: 2.5rem 1.5rem;
        }}

        /* Header section */
        header {{
            display: flex;
            flex-direction: column;
            gap: 1.5rem;
            margin-bottom: 3.5rem;
            border-bottom: 1px solid rgba(255, 255, 255, 0.05);
            padding-bottom: 2rem;
        }}

        .header-title-area {{
            display: flex;
            justify-content: space-between;
            align-items: flex-start;
            flex-wrap: wrap;
            gap: 1.5rem;
        }}

        .title-container h1 {{
            font-size: 2.5rem;
            font-weight: 700;
            background: linear-gradient(135deg, #fff 30%, #a5b4fc 100%);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            letter-spacing: -0.03em;
            margin-bottom: 0.5rem;
        }}

        .title-container p {{
            color: var(--text-secondary);
            font-size: 1.05rem;
        }}

        .status-badge {{
            background: rgba(99, 102, 241, 0.1);
            border: 1px solid rgba(99, 102, 241, 0.2);
            padding: 0.5rem 1rem;
            border-radius: 9999px;
            font-size: 0.875rem;
            color: #c7d2fe;
            display: flex;
            align-items: center;
            gap: 0.5rem;
            backdrop-filter: blur(10px);
        }}

        .pulse-dot {{
            width: 8px;
            height: 8px;
            background-color: var(--accent-emerald);
            border-radius: 50%;
            display: inline-block;
            box-shadow: 0 0 0 0 rgba(16, 185, 129, 0.7);
            animation: pulse 2s infinite;
        }}

        @keyframes pulse {{
            0% {{
                transform: scale(0.95);
                box-shadow: 0 0 0 0 rgba(16, 185, 129, 0.7);
            }}
            70% {{
                transform: scale(1);
                box-shadow: 0 0 0 8px rgba(16, 185, 129, 0);
            }}
            100% {{
                transform: scale(0.95);
                box-shadow: 0 0 0 0 rgba(16, 185, 129, 0);
            }}
        }}

        /* Stats dashboard section */
        .stats-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 1.25rem;
        }}

        .stats-card {{
            background: var(--bg-card);
            border: 1px solid var(--border-glow);
            border-radius: 16px;
            padding: 1.25rem;
            backdrop-filter: blur(12px);
            transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
        }}

        .stats-card:hover {{
            border-color: var(--border-glow-hover);
            transform: translateY(-2px);
            box-shadow: 0 10px 20px -10px rgba(99, 102, 241, 0.2);
        }}

        .stats-label {{
            color: var(--text-secondary);
            font-size: 0.875rem;
            font-weight: 500;
            margin-bottom: 0.25rem;
        }}

        .stats-value {{
            font-size: 2rem;
            font-weight: 700;
            color: var(--text-primary);
        }}

        /* Filter Controls */
        .controls-row {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            flex-wrap: wrap;
            gap: 1.5rem;
            margin-bottom: 2.5rem;
        }}

        .tabs {{
            display: flex;
            gap: 0.5rem;
            background: rgba(15, 23, 42, 0.6);
            padding: 0.375rem;
            border-radius: 12px;
            border: 1px solid rgba(255, 255, 255, 0.05);
            backdrop-filter: blur(8px);
        }}

        .tab-btn {{
            background: transparent;
            border: none;
            color: var(--text-secondary);
            padding: 0.625rem 1.25rem;
            border-radius: 8px;
            font-size: 0.95rem;
            font-weight: 500;
            cursor: pointer;
            transition: all 0.2s ease;
        }}

        .tab-btn:hover {{
            color: var(--text-primary);
        }}

        .tab-btn.active {{
            background: var(--accent-violet);
            color: #fff;
            box-shadow: 0 4px 12px rgba(139, 92, 246, 0.3);
        }}

        .search-container {{
            position: relative;
            min-width: 300px;
            max-width: 400px;
            flex-grow: 1;
        }}

        .search-input {{
            width: 100%;
            background: rgba(15, 23, 42, 0.6);
            border: 1px solid rgba(255, 255, 255, 0.08);
            border-radius: 12px;
            padding: 0.75rem 1rem 0.75rem 2.75rem;
            color: var(--text-primary);
            font-family: inherit;
            font-size: 0.95rem;
            transition: all 0.3s ease;
        }}

        .search-input:focus {{
            outline: none;
            border-color: var(--accent-violet);
            box-shadow: 0 0 0 3px rgba(139, 92, 246, 0.15);
            background: rgba(15, 23, 42, 0.8);
        }}

        .search-icon {{
            position: absolute;
            left: 1rem;
            top: 50%;
            transform: translateY(-50%);
            color: var(--text-secondary);
            pointer-events: none;
        }}

        /* Article grid & Cards */
        .articles-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(380px, 1fr));
            gap: 1.75rem;
            transition: all 0.3s ease;
        }}

        @media (max-width: 640px) {{
            .articles-grid {{
                grid-template-columns: 1fr;
            }}
            .search-container {{
                min-width: 100%;
            }}
        }}

        .article-card {{
            background: var(--bg-card);
            border: 1px solid var(--border-glow);
            border-radius: 20px;
            padding: 1.75rem;
            display: flex;
            flex-direction: column;
            gap: 1.25rem;
            backdrop-filter: blur(12px);
            transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
            opacity: 0;
            transform: scale(0.96);
            display: none;
        }}

        .article-card.active {{
            display: flex;
            opacity: 1;
            transform: scale(1);
        }}

        .article-card:hover {{
            border-color: var(--border-glow-hover);
            transform: translateY(-5px);
            box-shadow: 
                0 20px 25px -5px rgba(0, 0, 0, 0.3),
                0 0 30px rgba(99, 102, 241, 0.1);
        }}

        .card-header {{
            display: flex;
            justify-content: space-between;
            align-items: center;
        }}

        .badge {{
            padding: 0.25rem 0.75rem;
            border-radius: 9999px;
            font-size: 0.75rem;
            font-weight: 600;
            text-transform: uppercase;
            letter-spacing: 0.05em;
        }}

        .badge-violet {{
            background: rgba(139, 92, 246, 0.15);
            color: #c084fc;
            border: 1px solid rgba(139, 92, 246, 0.25);
        }}

        .badge-emerald {{
            background: rgba(16, 185, 129, 0.15);
            color: #34d399;
            border: 1px solid rgba(16, 185, 129, 0.25);
        }}

        .badge-amber {{
            background: rgba(245, 158, 11, 0.15);
            color: #fbbf24;
            border: 1px solid rgba(245, 158, 11, 0.25);
        }}

        .badge-slate {{
            background: rgba(100, 116, 139, 0.15);
            color: #cbd5e1;
            border: 1px solid rgba(100, 116, 139, 0.25);
        }}

        .card-date {{
            font-size: 0.85rem;
            color: var(--text-secondary);
            font-weight: 500;
        }}

        .card-title {{
            font-size: 1.25rem;
            font-weight: 600;
            line-height: 1.4;
        }}

        .card-title a {{
            color: var(--text-primary);
            text-decoration: none;
            transition: color 0.2s ease;
        }}

        .card-title a:hover {{
            color: #a5b4fc;
        }}

        .card-meta {{
            display: flex;
            gap: 1rem;
            font-size: 0.85rem;
            color: var(--text-secondary);
            border-top: 1px solid rgba(255, 255, 255, 0.04);
            border-bottom: 1px solid rgba(255, 255, 255, 0.04);
            padding: 0.5rem 0;
        }}

        .card-body {{
            color: var(--text-secondary);
            font-size: 0.95rem;
            display: -webkit-box;
            -webkit-line-clamp: 4;
            -webkit-box-orient: vertical;
            overflow: hidden;
            text-overflow: ellipsis;
        }}

        .card-footer {{
            margin-top: auto;
            display: flex;
            justify-content: flex-end;
        }}

        .more-btn {{
            background: rgba(255, 255, 255, 0.05);
            border: 1px solid rgba(255, 255, 255, 0.08);
            color: #c7d2fe;
            padding: 0.5rem 1rem;
            border-radius: 8px;
            font-size: 0.85rem;
            font-weight: 500;
            cursor: pointer;
            transition: all 0.2s ease;
        }}

        .more-btn:hover {{
            background: rgba(99, 102, 241, 0.15);
            border-color: rgba(99, 102, 241, 0.3);
            color: #fff;
        }}

        /* Empty State */
        .empty-state {{
            grid-column: 1 / -1;
            text-align: center;
            padding: 5rem 2rem;
            background: var(--bg-card);
            border: 1px dashed var(--border-glow);
            border-radius: 20px;
            display: none;
        }}

        .empty-state.active {{
            display: block;
        }}

        .empty-state h3 {{
            font-size: 1.5rem;
            margin-bottom: 0.5rem;
            color: var(--text-primary);
        }}

        .empty-state p {{
            color: var(--text-secondary);
        }}

        /* Modal styling */
        .modal-overlay {{
            position: fixed;
            top: 0;
            left: 0;
            right: 0;
            bottom: 0;
            background: rgba(15, 23, 42, 0.85);
            backdrop-filter: blur(8px);
            display: flex;
            justify-content: center;
            align-items: center;
            z-index: 1000;
            opacity: 0;
            pointer-events: none;
            transition: all 0.3s ease;
            padding: 1.5rem;
        }}

        .modal-overlay.active {{
            opacity: 1;
            pointer-events: auto;
        }}

        .modal-container {{
            background: #111827;
            border: 1px solid rgba(255, 255, 255, 0.1);
            border-radius: 24px;
            max-width: 720px;
            width: 100%;
            max-height: 80vh;
            display: flex;
            flex-direction: column;
            box-shadow: 0 25px 50px -12px rgba(0, 0, 0, 0.5);
            transform: scale(0.95);
            transition: all 0.3s cubic-bezier(0.34, 1.56, 0.64, 1);
        }}

        .modal-overlay.active .modal-container {{
            transform: scale(1);
        }}

        .modal-header {{
            padding: 1.75rem;
            border-bottom: 1px solid rgba(255, 255, 255, 0.05);
            display: flex;
            justify-content: space-between;
            align-items: flex-start;
            gap: 1.5rem;
        }}

        .modal-title {{
            font-size: 1.35rem;
            font-weight: 700;
            line-height: 1.4;
        }}

        .close-btn {{
            background: rgba(255, 255, 255, 0.05);
            border: 1px solid rgba(255, 255, 255, 0.1);
            color: var(--text-secondary);
            width: 36px;
            height: 36px;
            border-radius: 50%;
            display: flex;
            align-items: center;
            justify-content: center;
            cursor: pointer;
            transition: all 0.2s ease;
            flex-shrink: 0;
        }}

        .close-btn:hover {{
            background: rgba(239, 68, 68, 0.15);
            border-color: rgba(239, 68, 68, 0.3);
            color: #ef4444;
        }}

        .modal-content {{
            padding: 1.75rem;
            overflow-y: auto;
            font-size: 1.05rem;
            color: #cbd5e1;
            line-height: 1.7;
            white-space: pre-line; /* preserves paragraph breaks */
        }}

        .modal-meta {{
            padding: 1rem 1.75rem;
            background: rgba(255, 255, 255, 0.02);
            border-top: 1px solid rgba(255, 255, 255, 0.05);
            border-bottom-left-radius: 24px;
            border-bottom-right-radius: 24px;
            display: flex;
            justify-content: space-between;
            align-items: center;
            font-size: 0.9rem;
            color: var(--text-secondary);
        }}

        .visit-link {{
            color: #8b5cf6;
            text-decoration: none;
            font-weight: 600;
            display: flex;
            align-items: center;
            gap: 0.25rem;
        }}

        .visit-link:hover {{
            text-decoration: underline;
            color: #a5b4fc;
        }}
    </style>
</head>
<body>
    <div class="container">
        <header>
            <div class="header-title-area">
                <div class="title-container">
                    <h1>Daily News Dashboard</h1>
                    <p>인공지능, KB금융, 크롤링 관련 최신 뉴스를 정밀 모니터링합니다.</p>
                </div>
                <div class="status-badge">
                    <span class="pulse-dot"></span>
                    <span>최신 동기화 완료: {latest_crawl}</span>
                </div>
            </div>
            
            <div class="stats-grid">
                <div class="stats-card">
                    <div class="stats-label">전체 수집 뉴스</div>
                    <div class="stats-value">{total_articles}</div>
                </div>
                {stats_html}
            </div>
        </header>

        <div class="controls-row">
            <div class="tabs" id="keyword-tabs">
                <button class="tab-btn active" data-tab="all">전체</button>
                {" ".join(f'<button class="tab-btn" data-tab="{kw}">{kw}</button>' for kw in keywords)}
            </div>
            
            <div class="search-container">
                <svg class="search-icon" xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="11" cy="11" r="8"></circle><line x1="21" y1="21" x2="16.65" y2="16.65"></line></svg>
                <input type="text" id="search-bar" class="search-input" placeholder="뉴스 제목, 본문, 매체, 기자를 검색하세요...">
            </div>
        </div>

        <main class="articles-grid" id="articles-container">
            {fallback_cards_html}
            
            <div class="empty-state" id="empty-state">
                <h3>검색 결과가 없습니다.</h3>
                <p>다른 검색어 또는 필터를 시도해보세요.</p>
            </div>
        </main>
    </div>

    <!-- Modal for viewing full body -->
    <div class="modal-overlay" id="detail-modal">
        <div class="modal-container">
            <div class="modal-header">
                <div class="modal-title" id="modal-title">기사 제목</div>
                <button class="close-btn" id="modal-close">&times;</button>
            </div>
            <div class="modal-content" id="modal-body">
                본문 내용
            </div>
            <div class="modal-meta">
                <div id="modal-author">매체명 | 기자명</div>
                <a href="#" target="_blank" class="visit-link" id="modal-link">
                    원문 보러가기 ↗
                </a>
            </div>
        </div>
    </div>

    <script>
        // Data injected from Python
        const articles = {articles_json};
        const keywordColors = {keyword_colors_json};
        
        let currentFilter = 'all';
        let searchQuery = '';

        // DOM elements
        const container = document.getElementById('articles-container');
        const searchInput = document.getElementById('search-bar');
        const tabContainer = document.getElementById('keyword-tabs');
        const emptyState = document.getElementById('empty-state');
        
        // Modal elements
        const modal = document.getElementById('detail-modal');
        const modalTitle = document.getElementById('modal-title');
        const modalBody = document.getElementById('modal-body');
        const modalAuthor = document.getElementById('modal-author');
        const modalLink = document.getElementById('modal-link');
        const modalClose = document.getElementById('modal-close');

        // Initialize dashboard
        function init() {{
            renderArticles();
            setupEventListeners();
        }}

        // Format ISO Date to readable format
        const defFormatDate = (isoString) => {{
            try {{
                const date = new Date(isoString);
                if (isNaN(date.getTime())) return isoString.substring(0, 10);
                const year = date.getFullYear();
                const month = String(date.getMonth() + 1).padStart(2, '0');
                const day = String(date.getDate()).padStart(2, '0');
                return `${{year}}-${{month}}-${{day}}`;
            }} catch(e) {{
                return isoString.substring(0, 10);
            }}
        }}

        // Render articles list dynamically
        function renderArticles() {{
            // Filter data
            const filtered = articles.filter(article => {{
                const matchesTab = currentFilter === 'all' || article.keyword === currentFilter;
                
                const s = searchQuery.toLowerCase();
                const matchesSearch = !s || 
                    article.title.toLowerCase().includes(s) || 
                    article.body.toLowerCase().includes(s) || 
                    article.media_name.toLowerCase().includes(s) || 
                    article.journalist.toLowerCase().includes(s);
                
                return matchesTab && matchesSearch;
            }});

            // Clear container (keep empty state element)
            const cardElements = container.querySelectorAll('.article-card');
            cardElements.forEach(el => el.remove());

            if (filtered.length === 0) {{
                emptyState.classList.add('active');
            }} else {{
                emptyState.classList.remove('active');
                
                filtered.forEach((article, index) => {{
                    const card = document.createElement('div');
                    const colorClass = keywordColors[article.keyword] || 'slate';
                    const formattedDate = defFormatDate(article.created_at);
                    const bodyPreview = article.body.substring(0, 200).replace(/\\n/g, ' ') + '...';
                    
                    card.className = 'article-card active';
                    card.setAttribute('data-keyword', article.keyword);
                    card.style.animationDelay = `${{index * 0.05}}s`; // Staggered entry animation
                    
                    card.innerHTML = `
                        <div class="card-header">
                            <span class="badge badge-${{colorClass}}">${{article.keyword}}</span>
                            <span class="card-date">${{formattedDate}}</span>
                        </div>
                        <h3 class="card-title">
                            <a href="${{article.url}}" target="_blank">${{escapeHtml(article.title)}}</a>
                        </h3>
                        <div class="card-meta">
                            <span>📰 ${{escapeHtml(article.media_name)}}</span>
                            <span>✍️ ${{escapeHtml(article.journalist)}}</span>
                        </div>
                        <p class="card-body">${{escapeHtml(bodyPreview)}}</p>
                        <div class="card-footer">
                            <button class="more-btn">더 보기</button>
                        </div>
                    `;
                    
                    // Add details click handler
                    card.querySelector('.more-btn').addEventListener('click', () => {{
                        openModal(article);
                    }});
                    
                    // Insert before emptyState
                    container.insertBefore(card, emptyState);
                }});
            }}
        }}

        // Helper to escape HTML characters
        function escapeHtml(text) {{
            const map = {{
                '&': '&amp;',
                '<': '&lt;',
                '>': '&gt;',
                '"': '&quot;',
                "'": '&#039;'
            }};
            return text.replace(/[&<>"']/g, function(m) {{ return map[m]; }});
        }}

        // Setup event listeners
        function setupEventListeners() {{
            // Search Input
            searchInput.addEventListener('input', (e) => {{
                searchQuery = e.target.value;
                renderArticles();
            }});

            // Keyword Tabs
            tabContainer.addEventListener('click', (e) => {{
                if (e.target.classList.contains('tab-btn')) {{
                    // Update active class
                    tabContainer.querySelectorAll('.tab-btn').forEach(btn => btn.classList.remove('active'));
                    e.target.classList.add('active');
                    
                    currentFilter = e.target.getAttribute('data-tab');
                    renderArticles();
                }}
            }});

            // Modal Close Handlers
            modalClose.addEventListener('click', closeModal);
            modal.addEventListener('click', (e) => {{
                if (e.target === modal) closeModal();
            }});
            
            // ESC key to close modal
            document.addEventListener('keydown', (e) => {{
                if (e.key === 'Escape' && modal.classList.contains('active')) {{
                    closeModal();
                }}
            }});
        }}

        // Modal actions
        function openModal(article) {{
            modalTitle.textContent = article.title;
            modalBody.textContent = article.body;
            modalAuthor.textContent = `📰 ${{article.media_name}} | ✍️ ${{article.journalist}} (${{defFormatDate(article.created_at)}})`;
            modalLink.href = article.url;
            
            modal.classList.add('active');
            document.body.style.overflow = 'hidden'; // Lock background scroll
        }}

        function closeModal() {{
            modal.classList.remove('active');
            document.body.style.overflow = ''; // Unlock scroll
        }}

        // Run setup
        init();
    </script>
</body>
</html>
"""
    return html_template

def main():
    print("Generating Web Dashboard...")
    articles, stats, latest_crawl = get_articles_data()
    
    if not articles:
        print("Warning: No articles found in the database. Creating dashboard with empty state.")
        
    # Ensure docs directory exists
    os.makedirs("docs", exist_ok=True)
    
    html_content = generate_html(articles, stats, latest_crawl)
    
    output_path = os.path.join("docs", "index.html")
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(html_content)
        
    print(f"Success! Dashboard generated at '{output_path}' ({len(articles)} articles).")

if __name__ == "__main__":
    main()
