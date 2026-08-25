# config.py
import os

# NAVER API HUB Credentials
NAVER_CLIENT_ID = os.getenv("NAVER_CLIENT_ID", "oioijo7rek")
NAVER_CLIENT_SECRET = os.getenv("NAVER_CLIENT_SECRET", "EheJe6HadgzG72bpfla3E2Wt6tYawnDDEKOaFLBt")
NAVER_NEWS_API_URL = "https://naverapihub.apigw.ntruss.com/search/v1/news"

# Keywords to monitor in news search
KEYWORDS = [
    '"두산에너빌리티"'
]


# Max search results to fetch per keyword
SEARCH_LIMIT = 5

# Search sort order: 'date' (latest first) or 'sim' (relevance)
SEARCH_SORT = "date"

# Local SQLite database path
DB_PATH = "news_monitor.db"

# Directory where daily news reports will be saved
REPORT_DIR = "."

# Pipeline Version (SemVer tracking for reproducibility)
PIPELINE_VERSION = "v1.0.0"

# Extraction & Scoring Configuration Paths
SCORING_CONFIG_PATH = os.getenv("SCORING_CONFIG_PATH", "scoring_config.yaml")
PUBLISHER_RULES_PATH = os.getenv("PUBLISHER_RULES_PATH", "publisher_rules.yaml")
HARD_CASES_DIR = os.getenv("HARD_CASES_DIR", "hard_cases")

# Gemini LLM Cleaner Configuration
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
DEFAULT_GEMINI_MODEL = os.getenv("DEFAULT_GEMINI_MODEL", "gemini-2.5-flash")

