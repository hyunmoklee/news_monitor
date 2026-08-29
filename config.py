# config.py
import os
from dotenv import load_dotenv

# Load environment variables from .env
load_dotenv()

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

USE_VERTEX_AI = os.getenv("USE_VERTEX_AI", "false").lower() == "true"
VERTEX_PROJECT_ID = os.getenv("VERTEX_PROJECT_ID", "project-0d54bb31-d75f-4758-830")
VERTEX_LOCATION = os.getenv("VERTEX_LOCATION", "global")
DEFAULT_GEMINI_MODEL = os.getenv("GEMINI_MODEL", os.getenv("DEFAULT_GEMINI_MODEL", "gemini-3.7-flash"))
GEMINI_THINKING_BUDGET = int(os.getenv("GEMINI_THINKING_BUDGET", "0"))



def get_gemini_client():
    """
    Returns a configured google-genai Client supporting either
    Google Cloud Vertex AI (GCP Credit via ADC) or direct Gemini API Key.
    """
    from google import genai
    if USE_VERTEX_AI:
        return genai.Client(
            vertexai=True,
            project=VERTEX_PROJECT_ID,
            location=VERTEX_LOCATION
        )
    else:
        key = GEMINI_API_KEY or os.getenv("GEMINI_API_KEY", "")
        return genai.Client(api_key=key)


