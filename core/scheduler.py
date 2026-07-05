"""
Background Scheduler
Runs the Opportunity OS agent discovery pipeline 3 times a day (every 8 hours) in a background thread.
Logs progress to 'logs/background_scan.log' and avoids duplicate runs using SQLite state tracking.
"""
from __future__ import annotations
import threading
import time
import os
import sys
import uuid
import datetime
from pathlib import Path
from core.memory import get_db
from agents.graph import get_graph
from core.models import ScanMetadata

LOGS_DIR = Path(__file__).parent.parent / "logs"
LOGS_DIR.mkdir(exist_ok=True)
LOG_FILE = LOGS_DIR / "background_scan.log"

def log_message(text: str):
    """Log to file and print to console."""
    timestamp = datetime.datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
    formatted = f"[{timestamp}] {text}"
    try:
        print(formatted)
    except UnicodeEncodeError:
        # Fallback for Windows consoles that don't support UTF-8 print
        try:
            print(formatted.encode(sys.stdout.encoding, errors='replace').decode(sys.stdout.encoding))
        except Exception:
            print(formatted.encode('ascii', errors='replace').decode('ascii'))
    try:
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(formatted + "\n")
    except Exception as e:
        print(f"Failed to write to scheduler log: {e}")

def get_last_run_time() -> datetime.datetime | None:
    """Retrieve the last completed background run time from SQLite."""
    conn = get_db()
    try:
        row = conn.execute(
            "SELECT completed_at FROM scans WHERE status = 'completed' AND scan_id LIKE 'bg-%' ORDER BY completed_at DESC LIMIT 1"
        ).fetchone()
        if row and row["completed_at"]:
            return datetime.datetime.fromisoformat(row["completed_at"])
    except Exception as e:
        log_message(f"Error checking last run time: {e}")
    finally:
        conn.close()
    return None

def run_pipeline_sync():
    """Run the multi-agent graph synchronously for background search."""
    scan_id = f"bg-{uuid.uuid4()}"
    log_message(f"Starting scheduled background scan: {scan_id}")
    
    scan_meta = ScanMetadata(scan_id=scan_id, status="running")
    
    # Save running scan metadata
    from core.memory import save_scan
    save_scan(scan_meta)
    
    initial_state = {
        "scan_id": scan_id,
        "user_preferences": {"resume": ""}, # Run a general scan for global matching
        "search_plan": None,
        "raw_opportunities": [],
        "extracted_opportunities": [],
        "deduplicated_opportunities": [],
        "duplicates_removed": 0,
        "classified_opportunities": [],
        "enriched_opportunities": [],
        "ranked_opportunities": [],
        "agent_logs": [],
        "hunter_context": {},
        "scan_metadata": scan_meta,
        "progress_messages": [],
        "errors": []
    }
    
    try:
        graph = get_graph()
        # Stream the nodes so we can write log messages as they complete
        for event in graph.stream(initial_state):
            for node_name, updates in event.items():
                node_messages = updates.get("progress_messages", [])
                for msg in node_messages:
                    log_message(f"[{node_name.upper()}] {msg}")
                final_state = updates
                
        # Bulk save discovered opportunities to SQLite
        from core.memory import save_opportunities_bulk, save_agent_decision
        if "ranked_opportunities" in final_state and final_state["ranked_opportunities"]:
            save_opportunities_bulk(final_state["ranked_opportunities"])
            log_message(f"Successfully saved {len(final_state['ranked_opportunities'])} opportunities from background scan.")
            
        # Log agent decisions
        if "agent_logs" in final_state:
            for log in final_state["agent_logs"]:
                save_agent_decision(log)
                
        # Mark scan completed
        scan_meta.status = "completed"
        scan_meta.completed_at = datetime.datetime.utcnow()
        scan_meta.total_found = final_state.get("scan_metadata").total_found if final_state.get("scan_metadata") else len(final_state.get("ranked_opportunities", []))
        scan_meta.total_unique = len(final_state.get("ranked_opportunities", []))
        scan_meta.total_duplicates_removed = final_state.get("duplicates_removed", 0)
        save_scan(scan_meta)
        log_message("Background scan completed successfully.")
        
    except Exception as e:
        log_message(f"ERROR: Background scan failed: {e}")
        scan_meta.status = "failed"
        scan_meta.error = str(e)
        scan_meta.completed_at = datetime.datetime.utcnow()
        save_scan(scan_meta)

def is_any_scan_running() -> bool:
    """Check if any manual or background scan is currently in progress."""
    conn = get_db()
    try:
        row = conn.execute("SELECT COUNT(*) as count FROM scans WHERE status = 'running'").fetchone()
        return (row["count"] > 0) if row else False
    except Exception:
        return False
    finally:
        conn.close()

def scheduler_loop():
    """Infinite loop checking if 8 hours have elapsed since the last completed run."""
    log_message("Background Scheduler Thread Started.")
    
    # Wait 15 seconds on startup before running checks to let Streamlit UI load
    time.sleep(15)
    
    while True:
        try:
            if is_any_scan_running():
                log_message("Another scan is already running. Postponing background scan...")
                time.sleep(60)
                continue

            last_run = get_last_run_time()
            now = datetime.datetime.utcnow()
            
            # 8 hours = 28800 seconds
            time_diff = (now - last_run).total_seconds() if last_run else 9999999
            
            if time_diff >= 28800:
                log_message(f"It has been {time_diff/3600:.1f} hours since last scan. Initiating run...")
                run_pipeline_sync()
            else:
                hours_left = (28800 - time_diff) / 3600
                log_message(f"Next background run in {hours_left:.1f} hours.")
                
        except Exception as e:
            log_message(f"Scheduler loop error: {e}")
            
        # Sleep for 10 minutes before checking again
        time.sleep(600)

_scheduler_thread = None
_scheduler_lock = threading.Lock()

def start_scheduler():
    """Start the background scheduler thread if not already running."""
    global _scheduler_thread
    with _scheduler_lock:
        if _scheduler_thread is not None and _scheduler_thread.is_alive():
            return
        _scheduler_thread = threading.Thread(target=scheduler_loop, daemon=True, name="OpportunityOS-Scheduler")
        _scheduler_thread.start()
        log_message("Background scheduler thread spawned.")
