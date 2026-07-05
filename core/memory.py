"""
Memory manager — SQLite for structured storage, ChromaDB for vector semantic search.
Handles persistence of opportunities, scans, agent decisions, and search history.
"""
from __future__ import annotations
# Bypasses SQLite version limits on Streamlit Cloud (Linux)
try:
    __import__('pysqlite3')
    import sys
    sys.modules['sqlite3'] = sys.modules.pop('pysqlite3')
except ImportError:
    pass

import sqlite3
import json
import os
from datetime import datetime
from pathlib import Path
from typing import List, Optional
from core.models import Opportunity, AgentDecision, ScanMetadata

# ── Paths ────────────────────────────────────────────────────────────────────
DATA_DIR = Path(__file__).parent.parent / "data"
DATA_DIR.mkdir(exist_ok=True)
DB_PATH = DATA_DIR / "opportunityos.db"
CHROMA_PATH = str(DATA_DIR / "chroma_db")


# ── SQLite ────────────────────────────────────────────────────────────────────

def get_db() -> sqlite3.Connection:
    """Returns a SQLite connection with row_factory set."""
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    """Create all tables if they don't exist."""
    conn = get_db()
    cursor = conn.cursor()

    cursor.executescript("""
        CREATE TABLE IF NOT EXISTS opportunities (
            id TEXT PRIMARY KEY,
            title TEXT NOT NULL,
            organization TEXT,
            category TEXT,
            description TEXT,
            deadline TEXT,
            deadline_date TEXT,
            eligibility TEXT,
            rewards TEXT,
            required_skills TEXT,
            location TEXT,
            country TEXT,
            source TEXT,
            url TEXT,
            is_remote INTEGER DEFAULT 1,
            score REAL DEFAULT 0,
            reputation_score REAL DEFAULT 0,
            learning_score REAL DEFAULT 0,
            career_score REAL DEFAULT 0,
            accessibility_score REAL DEFAULT 0,
            ai_insight TEXT,
            why_it_matters TEXT,
            who_should_apply TEXT,
            career_impact INTEGER DEFAULT 5,
            learning_impact INTEGER DEFAULT 5,
            ranking_reasoning TEXT,
            classification_reasoning TEXT,
            created_at TEXT,
            scan_id TEXT,
            is_duplicate INTEGER DEFAULT 0,
            duplicate_of TEXT
        );

        CREATE TABLE IF NOT EXISTS scans (
            scan_id TEXT PRIMARY KEY,
            started_at TEXT,
            completed_at TEXT,
            total_found INTEGER DEFAULT 0,
            total_unique INTEGER DEFAULT 0,
            total_duplicates_removed INTEGER DEFAULT 0,
            sources_searched TEXT,
            status TEXT DEFAULT 'running',
            error TEXT
        );

        CREATE TABLE IF NOT EXISTS agent_logs (
            id TEXT PRIMARY KEY,
            scan_id TEXT,
            agent_name TEXT,
            decision TEXT,
            reasoning TEXT,
            opportunity_id TEXT,
            timestamp TEXT
        );

        CREATE TABLE IF NOT EXISTS search_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            scan_id TEXT,
            source TEXT,
            query TEXT,
            results_count INTEGER,
            timestamp TEXT
        );

        CREATE TABLE IF NOT EXISTS bookmarks (
            opportunity_id TEXT PRIMARY KEY,
            saved_at TEXT
        );

        -- Cleanup stale running scans from previous interrupted runs
        UPDATE scans SET status = 'cancelled' WHERE status = 'running';
    """)
    conn.commit()
    conn.close()


def save_opportunity(opp: Opportunity):
    """Insert or replace an opportunity in SQLite."""
    conn = get_db()
    conn.execute("""
        INSERT OR REPLACE INTO opportunities VALUES (
            :id, :title, :organization, :category, :description, :deadline,
            :deadline_date, :eligibility, :rewards, :required_skills, :location,
            :country, :source, :url, :is_remote, :score, :reputation_score,
            :learning_score, :career_score, :accessibility_score, :ai_insight,
            :why_it_matters, :who_should_apply, :career_impact, :learning_impact,
            :ranking_reasoning, :classification_reasoning, :created_at, :scan_id,
            :is_duplicate, :duplicate_of
        )
    """, {
        **(opp.model_dump() if hasattr(opp, "model_dump") else opp.dict()),
        "required_skills": json.dumps(opp.required_skills),
        "deadline_date": opp.deadline_date.isoformat() if opp.deadline_date else None,
        "created_at": opp.created_at.isoformat(),
        "is_remote": int(opp.is_remote),
        "is_duplicate": int(opp.is_duplicate),
    })
    conn.commit()
    conn.close()


def save_opportunities_bulk(opps: List[Opportunity]):
    """Bulk insert opportunities."""
    for opp in opps:
        save_opportunity(opp)


def save_scan(scan: ScanMetadata):
    """Insert or update a scan record."""
    conn = get_db()
    conn.execute("""
        INSERT OR REPLACE INTO scans VALUES (
            :scan_id, :started_at, :completed_at, :total_found,
            :total_unique, :total_duplicates_removed, :sources_searched,
            :status, :error
        )
    """, {
        **(scan.model_dump() if hasattr(scan, "model_dump") else scan.dict()),
        "sources_searched": json.dumps(scan.sources_searched),
        "started_at": scan.started_at.isoformat(),
        "completed_at": scan.completed_at.isoformat() if scan.completed_at else None,
    })
    conn.commit()
    conn.close()


def save_agent_decision(decision: AgentDecision):
    """Save an agent decision log entry."""
    conn = get_db()
    conn.execute("""
        INSERT OR REPLACE INTO agent_logs VALUES (
            :id, :scan_id, :agent_name, :decision, :reasoning,
            :opportunity_id, :timestamp
        )
    """, {
        **(decision.model_dump() if hasattr(decision, "model_dump") else decision.dict()),
        "timestamp": decision.timestamp.isoformat(),
    })
    conn.commit()
    conn.close()


def load_all_opportunities(limit: int = 500) -> List[dict]:
    """Load all non-duplicate opportunities ordered by score desc."""
    conn = get_db()
    rows = conn.execute("""
        SELECT * FROM opportunities
        WHERE is_duplicate = 0
        ORDER BY score DESC
        LIMIT ?
    """, (limit,)).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def load_opportunities_by_category(category: str) -> List[dict]:
    conn = get_db()
    rows = conn.execute("""
        SELECT * FROM opportunities
        WHERE category = ? AND is_duplicate = 0
        ORDER BY score DESC
    """, (category,)).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def load_scan_history(limit: int = 20) -> List[dict]:
    conn = get_db()
    rows = conn.execute("""
        SELECT * FROM scans ORDER BY started_at DESC LIMIT ?
    """, (limit,)).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def load_agent_decisions(scan_id: str) -> List[dict]:
    conn = get_db()
    rows = conn.execute("""
        SELECT * FROM agent_logs WHERE scan_id = ? ORDER BY timestamp
    """, (scan_id,)).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_all_opportunity_titles() -> List[str]:
    """Used by deduplication agent for fast title lookup."""
    conn = get_db()
    rows = conn.execute("SELECT id, title, organization FROM opportunities WHERE is_duplicate = 0").fetchall()
    conn.close()
    return [dict(r) for r in rows]


# ── Bookmarks Persistence ─────────────────────────────────────────────────────

def save_bookmark(opportunity_id: str):
    conn = get_db()
    conn.execute("INSERT OR REPLACE INTO bookmarks VALUES (?, ?)", (opportunity_id, datetime.utcnow().isoformat()))
    conn.commit()
    conn.close()


def delete_bookmark(opportunity_id: str):
    conn = get_db()
    conn.execute("DELETE FROM bookmarks WHERE opportunity_id = ?", (opportunity_id,))
    conn.commit()
    conn.close()


def load_bookmarked_opportunity_ids() -> List[str]:
    conn = get_db()
    rows = conn.execute("SELECT opportunity_id FROM bookmarks").fetchall()
    conn.close()
    return [r[0] for r in rows]



# ── ChromaDB ──────────────────────────────────────────────────────────────────

_chroma_client = None
_chroma_collection = None


def get_chroma():
    """Lazy-initialize ChromaDB client and collection."""
    global _chroma_client, _chroma_collection
    if _chroma_client is None:
        try:
            import chromadb
            _chroma_client = chromadb.PersistentClient(path=CHROMA_PATH)
            _chroma_collection = _chroma_client.get_or_create_collection(
                name="opportunities",
                metadata={"hnsw:space": "cosine"}
            )
        except Exception as e:
            print(f"ChromaDB init warning: {e}")
            return None, None
    return _chroma_client, _chroma_collection


def add_to_vector_store(opp: Opportunity):
    """Add an opportunity embedding to ChromaDB for semantic dedup."""
    _, collection = get_chroma()
    if collection is None:
        return
    try:
        text = f"{opp.title} {opp.organization} {opp.description[:200]}"
        collection.upsert(
            documents=[text],
            ids=[opp.id],
            metadatas=[{"category": opp.category, "source": opp.source}]
        )
    except Exception as e:
        print(f"ChromaDB add warning: {e}")


def find_similar_opportunities(text: str, threshold: float = 0.92, n_results: int = 5) -> List[dict]:
    """
    Query ChromaDB for semantically similar opportunities.
    Returns matches above the similarity threshold.
    """
    _, collection = get_chroma()
    if collection is None:
        return []
    try:
        count = collection.count()
        if count == 0:
            return []
        results = collection.query(
            query_texts=[text],
            n_results=min(n_results, count)
        )
        matches = []
        if results and results.get("distances"):
            for i, dist in enumerate(results["distances"][0]):
                similarity = 1 - dist  # cosine distance → similarity
                if similarity >= threshold:
                    matches.append({
                        "id": results["ids"][0][i],
                        "similarity": similarity,
                        "metadata": results["metadatas"][0][i] if results.get("metadatas") else {}
                    })
        return matches
    except Exception as e:
        print(f"ChromaDB query warning: {e}")
        return []


# Initialize DB on import
init_db()
