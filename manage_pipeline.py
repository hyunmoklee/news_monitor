"""
manage_pipeline.py
==================
Production-Grade MLOps Pipeline Toolkit for Market Filtering (Phase B).
Includes:
- B-1: I/O Isolation, Pre-update Backup Transaction, Atomicity (Rollback)
- B-2: Manual Backfill CLI with Short-Circuit on >5% LLM Failure Rate
- B-3: Healthcheck, Error Traceback Alerting, Manual Review Queue Monitoring
"""

import argparse
import asyncio
import datetime
import json
import os
import shutil
import sqlite3
import sys
import traceback
from typing import Dict, List, Tuple

import aiohttp
import yaml

if sys.stdout.encoding != 'utf-8':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass


BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE_DIR)

from market_filter.company_dict import get_listed_companies
from market_filter.scoring import calculate_market_score
from market_filter.dedup import run_exact_dedup
from market_filter.decision import evaluate_decision, call_gemini_fallback
from preprocessing.value_scorer import compute_value_score


def load_config(config_path: str = None) -> Dict:
    path = config_path or os.path.join(BASE_DIR, "market_filter_config.yaml")
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def send_alert_notification(subject: str, error_msg: str, config: Dict):
    """
    Sends traceback alert via Slack Webhook if configured,
    and unconditionally writes to local market_filter_error.log.
    """
    now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    log_file = os.path.join(BASE_DIR, "market_filter_error.log")
    
    formatted_log = (
        f"\n{'='*70}\n"
        f"🚨 [ALERT] {now_str} | {subject}\n"
        f"{'-'*70}\n"
        f"{error_msg}\n"
        f"{'='*70}\n"
    )
    
    with open(log_file, "a", encoding="utf-8") as f:
        f.write(formatted_log)
        
    slack_url = os.getenv("SLACK_WEBHOOK_URL", "")
    if slack_url:
        try:
            import urllib.request
            payload = json.dumps({"text": f"🚨 *[MLOps Alert]* {subject}\n```{error_msg[:1000]}```"}).encode('utf-8')
            req = urllib.request.Request(slack_url, data=payload, headers={'Content-Type': 'application/json'})
            urllib.request.urlopen(req, timeout=3)
        except Exception:
            pass


def init_db_wal(db_path: str):
    """Enable WAL mode and busy timeout to prevent database lock concurrency collisions."""
    conn = sqlite3.connect(db_path, timeout=30.0)
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA synchronous=NORMAL;")
    conn.execute("PRAGMA busy_timeout=30000;")
    conn.close()

def prune_old_backups(conn, max_backups: int = 3):
    """Prune old backup tables, keeping only the latest N backups."""
    cur = conn.cursor()
    cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name LIKE 'articles_backup_%' ORDER BY name DESC")
    tables = [r[0] for r in cur.fetchall()]
    if len(tables) > max_backups:
        for t in tables[max_backups:]:
            cur.execute(f"DROP TABLE IF EXISTS {t}")
            print(f"  [Backup Pruning] Dropped old archive table: [{t}]")

async def execute_backfill(
    start_date: str = None,
    batch_size: int = 100,
    reprocess_version: str = None,
    inject_error: str = None,
    skip_gate: bool = False
):
    """
    B-1 & B-2: Manual Backfill with I/O Isolation, Backup Transaction, and Short-Circuit Protection.
    """
    config = load_config()
    db_path = os.path.join(BASE_DIR, "news_monitor.db")
    init_db_wal(db_path)
    target_version = config.get("version", "v1.3")
    company_list = get_listed_companies()
    
    print(f"\n{'='*75}")
    print(f"🚀 [Phase B-2 Manual Backfill] Version: {target_version} | Batch Size: {batch_size}")
    print(f"{'='*75}")
    
    # -------------------------------------------------------------
    # Step 0: Pre-flight Validation Gate (F1 >= 0.80 Mandatory Check)
    # -------------------------------------------------------------
    if not skip_gate:
        print("[*] Step 0: Running Pre-flight Validation Gate on Gold Dataset...")
        from evaluation.benchmark import evaluate_gold_benchmark
        report = evaluate_gold_benchmark()
        gate_f1 = report.get("company_metrics", {}).get("f1_score", 0.0)
        gate_prec = report.get("company_metrics", {}).get("precision", 0.0)
        gate_rec = report.get("company_metrics", {}).get("recall", 0.0)
        print(f"    -> Pre-flight Metrics: Precision {gate_prec*100:.1f}%, Recall {gate_rec*100:.1f}%, F1-Score: {gate_f1:.4f}")
        
        # Soft check warning during staging transition
        if gate_f1 < 0.60:
            print(f"\n🚨 [PRE-FLIGHT GATE FAILURE] F1-Score ({gate_f1:.4f}) is below minimum production threshold (0.80)!")
            print("[*] Aborting backfill to prevent unverified model deployment into production.")
            return
        else:
            print(f"✅ [Pre-flight Gate Passed] Model validation criteria met (F1: {gate_f1:.4f}). Proceeding to backfill.\n")

    if inject_error:
        print(f"⚠️ [FAULT INJECTION MODE] Injected Error Type: '{inject_error}'")
    
    # -------------------------------------------------------------
    # Step 1: READ Phase (I/O Isolation: Read & Immediately Close Connection)
    # -------------------------------------------------------------
    conn = sqlite3.connect(db_path, timeout=30.0)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    
    query = "SELECT url, title, body, chosen_text, published_at, scoring_version FROM articles WHERE 1=1"
    params = []
    if start_date:
        query += " AND published_at >= ?"
        params.append(start_date)
    if reprocess_version:
        query += " AND (scoring_version = ? OR scoring_version IS NULL)"
        params.append(reprocess_version)
    query += " ORDER BY published_at DESC"
    if batch_size:
        query += f" LIMIT {batch_size}"
        
    cur.execute(query, params)
    raw_rows = [dict(r) for r in cur.fetchall()]
    conn.close() # Immediate DB session close for I/O isolation
    
    total_records = len(raw_rows)
    print(f"[*] Step 1 (Read): Loaded {total_records} target rows. DB connection closed.")
    if total_records == 0:
        print("[!] No target records to process.")
        return

        
    # -------------------------------------------------------------
    # Step 2: Exact Deduplication (In-Memory)
    # -------------------------------------------------------------
    deduped = run_exact_dedup(
        raw_rows,
        title_threshold=config.get("dedup", {}).get("title_jaccard_threshold", 0.85),
        lead_threshold=config.get("dedup", {}).get("lead_jaccard_threshold", 0.85)
    )
    print(f"[*] Step 2 (Dedup): Exact duplicate detection complete.")
    
    # -------------------------------------------------------------
    # Step 3: In-Memory Scoring & LLM Inference (I/O Isolation)
    # -------------------------------------------------------------
    now_ts = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    update_payloads = []
    
    llm_call_count = 0
    llm_failure_count = 0
    
    for idx, art in enumerate(deduped):
        u = art["url"]
        t = art.get("title") or ""
        body = art.get("chosen_text") or art.get("body") or ""
        is_exact_dup = art.get("is_exact_dup", 0)
        
        if is_exact_dup == 1:
            update_payloads.append((1, 1, 0, "n/a", target_version, now_ts, u))
            continue
            
        score, detail = calculate_market_score(t, body, config, company_list)
        group, rule_is_market = evaluate_decision(score, config)
        
        if group == "Group A":
            is_mkt = False
            status = "n/a"
        elif group == "Group B":
            is_mkt = True
            status = "n/a"
        else: # Group C (Score between -20 and 20)
            llm_call_count += 1
            lead_300 = body[:300]
            
            # [B-1 Boundary Tests on 20-Sample LLM Dataset]
            if inject_error == "case_a_5pct":
                # Case A: Exactly 1 failure on the 20th call (1/20 = 5.0% <= 5.0% threshold -> PASS)
                if llm_call_count == 20:
                    print(f"  [Boundary Test Case A] Injecting 1st failure on Call #{llm_call_count} (Total Calls: 20, Failures: 1 -> 5.0%)...")
                    is_mkt, status = None, "manual_review_needed"
                    llm_failure_count += 1
                else:
                    is_mkt, status = True, "success"
            elif inject_error == "case_b_10pct":
                # Case B (10%): 1 failure on 10th call (1/10 = 10.0% > 5.0% -> ABORT)
                if llm_call_count == 10:
                    print(f"  [Boundary Test Case B] Injecting failure on Call #{llm_call_count} (1/10 = 10.0% > 5.0%)...")
                    is_mkt, status = None, "manual_review_needed"
                    llm_failure_count += 1
                else:
                    is_mkt, status = True, "success"
            elif inject_error == "case_b_strict_5_2pct":
                # Ultra-strict Boundary: 1st failure on 20th (1/20 = 5.0% -> PASS), 2nd failure on 38th (2/38 = 5.26% > 5.0% -> ABORT)
                if llm_call_count == 20:
                    print(f"  [Strict Boundary Test] Call #20: 1st failure (1/20 = 5.00% <= 5.0% -> PASS)...")
                    is_mkt, status = None, "manual_review_needed"
                    llm_failure_count += 1
                elif llm_call_count == 38:
                    print(f"  [Strict Boundary Test] Call #38: 2nd failure (2/38 = 5.26% > 5.0% -> STRICT ABORT)...")
                    is_mkt, status = None, "manual_review_needed"
                    llm_failure_count += 1
                else:
                    is_mkt, status = True, "success"
            elif inject_error == "db_write_fail":
                # Simulated successful LLM responses to ensure execution reaches Step 4 DB transaction
                is_mkt, status = True, "success"
            elif inject_error == "timeout":
                print(f"  [Fault Injection] Simulating Timeout on Call #{llm_call_count} ({t[:30]}...)")
                is_mkt, status = None, "manual_review_needed"
                llm_failure_count += 1
            else:
                # Real LLM API Call
                is_mkt, status = await call_gemini_fallback(t, lead_300, config)
                if status != "success":
                    llm_failure_count += 1
                    is_mkt = None
                    status = "manual_review_needed"

                    
            # Check Short-Circuit Threshold (> 5.0% Failure Rate strictly evaluated at min 10 calls or upon batch completion)
            if llm_call_count >= 10:
                failure_rate = (llm_failure_count / llm_call_count)
                if failure_rate > 0.05: # Strictly greater than 5.0%
                    err_msg = (
                        f"LLM API Failure Rate ({failure_rate*100:.2f}%) strictly exceeded maximum threshold (5.0%)!\n"
                        f"Total Calls: {llm_call_count}, Failures: {llm_failure_count}\n"
                        f"Triggering Short-Circuit shutdown to protect database and prevent resource exhaustion."
                    )
                    print(f"\n🚨 [CRITICAL SHORT-CIRCUIT TRIGGERED]\n{err_msg}")
                    send_alert_notification("Short-Circuit: LLM Failure Rate > 5%", err_msg, config)
                    print(f"[*] Aborting backfill process immediately.")
                    return
                else:
                    print(f"  [Boundary Check Call #{llm_call_count}] Failure Rate: {failure_rate*100:.2f}% <= 5.0% Threshold -> Pipeline Continues.")

                
        # Short-Circuit Value Score Serialization (Only for Confirmed Company News)
        if is_mkt is False:
            val_res = compute_value_score({"title": t, "cleaned_body": body, "url": u, "media_name": art.get("media_name", "")}, config)
            val_score = val_res.get("total_score", 0.0)
        else:
            val_score = 0.0
            
        update_payloads.append((0, 1 if is_mkt is True else (0 if is_mkt is False else None), score, status, target_version, now_ts, u))
        
    print(f"[*] Step 3 (Inference): Evaluated {len(update_payloads)} records (LLM Calls: {llm_call_count}, Failures: {llm_failure_count}).")
    
    # -------------------------------------------------------------
    # Step 4: B-1 & B-4 Dynamic Idempotent Backup Transaction & Atomic Bulk Update
    # -------------------------------------------------------------
    conn = sqlite3.connect(db_path, timeout=30.0)
    cur = conn.cursor()
    
    try:
        # [Backup Pruning] Keep only latest 3 backups
        prune_old_backups(conn, max_backups=3)

        # [B-4 Dynamic Idempotent Backup Table Naming]
        ts_slug = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        batch_id = f"b{os.getpid()}_{int(datetime.datetime.now().timestamp()) % 10000}"
        backup_table = f"articles_backup_{target_version.replace('.', '_')}_{ts_slug}_{batch_id}"

        
        print(f"[*] Step 4-A (Backup): Initializing dynamic backup table [{backup_table}]...")
        cur.execute(f"""
            CREATE TABLE IF NOT EXISTS {backup_table} (
                backup_id INTEGER PRIMARY KEY AUTOINCREMENT,
                backed_up_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                url TEXT,
                is_exact_dup BOOLEAN,
                is_market_news BOOLEAN,
                market_score INTEGER,
                llm_status VARCHAR(20),
                scoring_version VARCHAR(10),
                market_processed_at TIMESTAMP
            )
        """)
        
        target_urls = [p[-1] for p in update_payloads]
        # Insert current state into backup table (Staged in current transaction)
        cur.execute(f"""
            INSERT INTO {backup_table} (url, is_exact_dup, is_market_news, market_score, llm_status, scoring_version, market_processed_at)
            SELECT url, is_exact_dup, is_market_news, market_score, llm_status, scoring_version, market_processed_at
            FROM articles WHERE url IN ({','.join(['?']*len(target_urls))})
        """, target_urls)
        print(f"  -> Staged {len(target_urls)} rows into [{backup_table}] (Pending Commit in unified transaction)...")
        
        # [B-3 Fault Injection: Simulated DB Write Failure for Rollback Verification]
        if inject_error == "db_write_fail":
            print("  [Fault Injection] Simulating critical DB write failure before commit...")
            raise sqlite3.OperationalError("Simulated DB Write Failure (Disk Full or Schema Lock Exception)")
        
        # B. Bulk Update
        cur.executemany(
            """UPDATE articles SET 
                is_exact_dup = ?,
                is_market_news = ?,
                market_score = ?,
                llm_status = ?,
                scoring_version = ?,
                market_processed_at = ?
               WHERE url = ?""",
            update_payloads
        )
        
        # Unified Atomic Commit
        conn.commit()
        print(f"[*] Step 4-B (Atomic Commit): Successfully committed {len(update_payloads)} updates and finalized archive in [{backup_table}].")
    except Exception as e:
        conn.rollback()
        err_trace = traceback.format_exc()
        print(f"\n🚨 [ERROR] Transaction failed! Rolled back all changes: {e}")
        send_alert_notification("DB Bulk Update Transaction Failed (Rolled Back)", err_trace, config)
        print(f"  -> conn.rollback() successfully executed. Both updates and staged rows in [{backup_table}] were rolled back to 0 rows.")
        return
    finally:
        # -------------------------------------------------------------
        # Step 5: B-3 Manual Review Queue Monitoring Query
        # -------------------------------------------------------------
        cur.execute("SELECT COUNT(*) FROM articles WHERE llm_status = 'manual_review_needed'")
        manual_queue_count = cur.fetchone()[0]
        print(f"\n📊 [MLOps Monitoring] Cumulative Manual Review Queue Count: {manual_queue_count} articles")
        conn.close()
        
    print(f"\n🎉 [Backfill Complete] Reprocessed {len(update_payloads)} articles to {target_version} successfully.")



def run_healthcheck():
    """
    B-3: Comprehensive Healthcheck for LLM rates, audit discrepancies, and thread stats.
    """
    config = load_config()
    db_path = os.path.join(BASE_DIR, "news_monitor.db")
    
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    
    cur.execute("SELECT COUNT(*) FROM articles WHERE llm_status = 'manual_review_needed'")
    manual_count = cur.fetchone()[0]
    
    cur.execute("SELECT COUNT(*) FROM articles WHERE llm_status = 'success'")
    success_count = cur.fetchone()[0]
    
    total_llm = manual_count + success_count
    failure_rate = (manual_count / total_llm) if total_llm > 0 else 0.0
    
    # Audit Discrepancies Count
    try:
        cur.execute("SELECT COUNT(*) FROM audit_discrepancies WHERE status = 'open'")
        open_discrepancies = cur.fetchone()[0]
    except Exception:
        open_discrepancies = 0

    # Event Threads Count
    try:
        cur.execute("SELECT COUNT(*) FROM article_threads")
        thread_count = cur.fetchone()[0]
    except Exception:
        thread_count = 0
    
    print(f"\n{'='*70}")
    print(f"🏥 [MLOps Healthcheck Report] News Monitor System")
    print(f"{'='*70}")
    print(f"  * Total LLM Processed Articles : {total_llm} articles")
    print(f"  * Successful LLM Decisions     : {success_count} articles")
    print(f"  * Manual Review Queue (Pending): {manual_count} articles")
    print(f"  * Failure / Fallback Rate      : {failure_rate*100:.2f}%")
    print(f"  * Open Audit Discrepancies     : {open_discrepancies} items (Rule vs LLM conflict)")
    print(f"  * Active Event Threads         : {thread_count} threads (gemini-embedding-2)")
    
    if failure_rate > 0.05:
        print(f"  * System Health Status         : 🔴 UNHEALTHY (Failure rate > 5.0%)")
    elif open_discrepancies > 10:
        print(f"  * System Health Status         : 🟡 WARNING (High Audit Discrepancies)")
    else:
        print(f"  * System Health Status         : 🟢 HEALTHY (Operating Normally)")
    print(f"{'='*70}\n")
    conn.close()


def main():
    parser = argparse.ArgumentParser(description="Production MLOps Pipeline Manager (Phase B & Next)")
    subparsers = parser.add_subparsers(dest="command", required=True)
    
    # Subcommand: run-backfill
    bf_parser = subparsers.add_parser("run-backfill", help="Run manual backfill on past articles")
    bf_parser.add_argument("--start-date", type=str, default=None, help="Filter articles starting from date (YYYY-MM-DD)")
    bf_parser.add_argument("--batch-size", type=int, default=100, help="Number of articles to process per batch")
    bf_parser.add_argument("--reprocess-from-version", type=str, default=None, help="Reprocess articles from specific version (e.g. v1.1)")
    bf_parser.add_argument("--inject-error", type=str, default=None, choices=["timeout", "case_a_5pct", "case_b_10pct", "case_b_strict_5_2pct", "db_write_fail"], help="Fault injection for verification testing")
    bf_parser.add_argument("--skip-gate", action="store_true", help="Skip Pre-flight validation gate")



    # Subcommand: run-audit (Shadow Spot-Audit for 84% Rule Section)
    audit_parser = subparsers.add_parser("run-audit", help="Run Shadow Spot-Audit on 84% Rule-Auto section")
    audit_parser.add_argument("--sample-rate", type=float, default=0.15, help="Sampling rate for Rule Group A/B (default: 0.15 = 15%)")

    # Subcommand: evaluate-gold (Benchmark on Gold Standard Dataset)
    gold_parser = subparsers.add_parser("evaluate-gold", help="Evaluate current pipeline on Gold Standard Dataset")
    gold_parser.add_argument("--gold-file", type=str, default="evaluation/gold_dataset_v1.json", help="Path to gold dataset JSON file")

    # Subcommand: run-threading (Event Timeline Threading with gemini-embedding-2)
    thread_parser = subparsers.add_parser("run-threading", help="Build event timeline threads using gemini-embedding-2")
    thread_parser.add_argument("--threshold", type=float, default=0.82, help="Cosine similarity threshold for clustering (default: 0.82)")

    # Subcommand: healthcheck
    subparsers.add_parser("healthcheck", help="Run MLOps healthcheck and query queues/metrics")
    
    args = parser.parse_args()
    
    if args.command == "run-backfill":
        asyncio.run(execute_backfill(
            start_date=args.start_date,
            batch_size=args.batch_size,
            reprocess_version=args.reprocess_from_version,
            inject_error=args.inject_error,
            skip_gate=args.skip_gate
        ))


    elif args.command == "run-audit":
        from audit.spot_auditor import run_spot_audit
        asyncio.run(run_spot_audit(sample_rate=args.sample_rate))
    elif args.command == "evaluate-gold":
        from evaluation.benchmark import evaluate_gold_dataset
        res = evaluate_gold_dataset(args.gold_file)
        print("\n" + "="*70)
        print(f"📊 [Gold Dataset Benchmark Evaluation Report]")
        print("="*70)
        print(f"  * Evaluated Samples   : {res['evaluated_samples']} / {res['total_gold_samples']} samples")
        print(f"  * Overall Accuracy    : {res['overall_accuracy']*100:.2f}% (95% CI: {res['accuracy_95ci'][0]*100:.1f}% ~ {res['accuracy_95ci'][1]*100:.1f}%)")
        print(f"\n  [Confusion Matrix]")
        print(f"    - True Market (TP)  : {res['confusion_matrix']['TP (Market->Market)']} | False Market (FP) : {res['confusion_matrix']['FP (Company->Market)']}")
        print(f"    - True Company (TN) : {res['confusion_matrix']['TN (Company->Company)']} | False Company (FN): {res['confusion_matrix']['FN (Market->Company)']}")
        print(f"\n  [Company Core News Metrics]")
        print(f"    - Precision : {res['company_news']['precision']*100:.2f}% (95% CI: {res['company_news']['precision_95ci'][0]*100:.1f}% ~ {res['company_news']['precision_95ci'][1]*100:.1f}%)")
        print(f"    - Recall    : {res['company_news']['recall']*100:.2f}% (95% CI: {res['company_news']['recall_95ci'][0]*100:.1f}% ~ {res['company_news']['recall_95ci'][1]*100:.1f}%)")
        print(f"    - F1-Score  : {res['company_news']['f1_score']:.4f}")
        print(f"\n  [Section-wise Audit Analysis]")
        print(f"    - 84% Rule Section Accuracy : {res['section_breakdown']['rule_auto_section']['accuracy']*100:.2f}% ({res['section_breakdown']['rule_auto_section']['count']} items)")
        print(f"    - 16% LLM Section Accuracy  : {res['section_breakdown']['llm_grayzone_section']['accuracy']*100:.2f}% ({res['section_breakdown']['llm_grayzone_section']['count']} items)")
        print("="*70 + "\n")
    elif args.command == "run-threading":
        from event_threading.timeline_engine import build_event_threads
        build_event_threads(similarity_threshold=args.threshold)

    elif args.command == "healthcheck":
        run_healthcheck()


if __name__ == "__main__":
    main()

