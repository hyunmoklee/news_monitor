"""
Phase B-3: LLM 장애 알림 헬스체크 배치 (Healthcheck Monitor).
- 최근 24시간 내 llm_status == 'failed' 비율이 5% 초과 시 경고 발생
- SLACK_WEBHOOK_URL 발송 및 시스템 Error 로그 Fallback
"""
import datetime
import json
import logging
import os
import sqlite3
import urllib.request

logging.basicConfig(level=logging.INFO, format='[%(asctime)s] %(levelname)s: %(message)s')

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "news_monitor.db")

def check_llm_health(threshold_ratio: float = 0.05) -> bool:
    if not os.path.exists(DB_PATH):
        logging.error(f"Database not found: {DB_PATH}")
        return False
        
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    
    # 24시간 전 타임스탬프
    day_ago = (datetime.datetime.now() - datetime.timedelta(days=1)).strftime("%Y-%m-%d %H:%M:%S")
    
    cur.execute(
        "SELECT count(*) FROM articles WHERE market_processed_at >= ? AND llm_status IN ('success', 'failed')",
        (day_ago,)
    )
    total_llm_calls = cur.fetchone()[0]
    
    cur.execute(
        "SELECT count(*) FROM articles WHERE market_processed_at >= ? AND llm_status = 'failed'",
        (day_ago,)
    )
    failed_llm_calls = cur.fetchone()[0]
    conn.close()
    
    if total_llm_calls == 0:
        logging.info("Healthcheck: No LLM calls in the past 24 hours. Status Healthy.")
        return True
        
    fail_ratio = failed_llm_calls / total_llm_calls
    logging.info(f"Healthcheck: Total LLM Calls={total_llm_calls}, Failed={failed_llm_calls}, Fail Ratio={fail_ratio*100:.2f}%")
    
    if fail_ratio > threshold_ratio:
        msg = f"[CRITICAL WARNING] LLM Failure Ratio in past 24h is {fail_ratio*100:.2f}% ({failed_llm_calls}/{total_llm_calls}), exceeding threshold of {threshold_ratio*100:.1f}%!"
        logging.error(msg)
        
        # Send Slack Webhook
        webhook_url = os.getenv("SLACK_WEBHOOK_URL", "")
        if webhook_url:
            try:
                alert_text = f":warning: *[News Crawler MLOps Alert]*\\n{msg}"
                payload = json.dumps({"text": alert_text}).encode('utf-8')
                req = urllib.request.Request(webhook_url, data=payload, headers={'Content-Type': 'application/json'})
                urllib.request.urlopen(req, timeout=5)
                logging.info("Successfully sent Slack alert.")
            except Exception as se:
                logging.error(f"Failed to send Slack alert: {se}")
        else:
            logging.warning("SLACK_WEBHOOK_URL is not set. Logged as System Standard Error.")

        return False
        
    logging.info("Healthcheck: LLM Health Status Normal.")
    return True

if __name__ == "__main__":
    check_llm_health()
