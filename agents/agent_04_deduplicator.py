"""
Agent 4: Deduplication Agent
─────────────────────────────
Detects and removes duplicate opportunities using:
  1. Exact title+org matching (fast, deterministic)
  2. Local Cosine Similarity index on word frequencies (100% thread-safe, fast, no DB locks)
"""
from __future__ import annotations
import re
import math
from collections import Counter
from typing import List, Set, Tuple
from core.state import AgentState
from core.models import Opportunity, AgentDecision
from core.memory import get_all_opportunity_titles


def normalize_title(title: str) -> str:
    """Normalize title for comparison: lowercase, strip special chars."""
    return re.sub(r"[^a-z0-9\s]", "", title.lower()).strip()


def get_cosine_similarity(text1: str, text2: str) -> float:
    """Calculate Cosine Similarity of two texts using word frequencies (pure Python)."""
    words1 = re.sub(r"[^a-z0-9\s]", "", text1.lower()).split()
    words2 = re.sub(r"[^a-z0-9\s]", "", text2.lower()).split()
    
    if not words1 or not words2:
        return 0.0
        
    vec1 = Counter(words1)
    vec2 = Counter(words2)
    
    intersection = set(vec1.keys()) & set(vec2.keys())
    numerator = sum(vec1[x] * vec2[x] for x in intersection)
    
    sum1 = sum(vec1[x] ** 2 for x in vec1.keys())
    sum2 = sum(vec2[x] ** 2 for x in vec2.keys())
    denominator = math.sqrt(sum1) * math.sqrt(sum2)
    
    if not denominator:
        return 0.0
    return float(numerator) / denominator


def titles_are_similar(t1: str, t2: str) -> bool:
    """Simple Jaccard similarity on word sets."""
    w1 = set(normalize_title(t1).split())
    w2 = set(normalize_title(t2).split())
    if not w1 or not w2:
        return False
    intersection = w1 & w2
    union = w1 | w2
    return len(intersection) / len(union) > 0.7


def run_deduplicator(state: AgentState) -> dict:
    """
    Agent 4 node: Removes duplicate opportunities using local Cosine Similarity.
    Updates: deduplicated_opportunities, duplicates_removed, agent_logs, progress_messages
    """
    extracted = state.get("extracted_opportunities", [])
    scan_id = state["scan_id"]

    if not extracted:
        return {
            "deduplicated_opportunities": [],
            "duplicates_removed": 0,
            "agent_logs": [],
            "progress_messages": ["🔄 **Deduplication Agent** — No opportunities to deduplicate"]
        }

    unique: List[Opportunity] = []
    seen_keys: Set[str] = set()  # "title|org" normalized keys within this scan
    duplicate_count = 0
    decisions = []

    # Step 1: Load existing opportunities from SQLite memory to cross-scan dedup
    existing = get_all_opportunity_titles()
    
    # Pre-build a set of normalized keys for existing database records to perform O(1) checks
    existing_keys_map = {}
    for e in existing:
        k = normalize_title(e["title"]) + "|" + normalize_title(e.get("organization", ""))
        existing_keys_map[k] = e["id"]

    for opp in extracted:
        key = normalize_title(opp.title) + "|" + normalize_title(opp.organization)

        # ── Check 1: Exact normalized match within this current scan batch ──
        if key in seen_keys:
            opp.is_duplicate = True
            duplicate_count += 1
            continue

        # ── Check 2: Exact normalized match against existing DB records ──
        if key in existing_keys_map:
            opp.is_duplicate = True
            opp.duplicate_of = existing_keys_map[key]
            duplicate_count += 1
            continue

        # ── Check 3: Cosine similarity within current scan batch (semantic near-dedup) ──
        is_dup = False
        for existing_opp in unique:
            sim = get_cosine_similarity(opp.title, existing_opp.title)
            # If titles are highly similar and organization matches
            if sim >= 0.85 and normalize_title(opp.organization) == normalize_title(existing_opp.organization):
                opp.is_duplicate = True
                opp.duplicate_of = existing_opp.id
                duplicate_count += 1
                is_dup = True
                break
        
        if is_dup:
            continue

        # ── Check 4: Cosine similarity against existing DB records ──
        for ex in existing:
            sim = get_cosine_similarity(opp.title, ex["title"])
            if sim >= 0.85 and normalize_title(opp.organization) == normalize_title(ex.get("organization", "")):
                opp.is_duplicate = True
                opp.duplicate_of = ex["id"]
                duplicate_count += 1
                is_dup = True
                decisions.append(AgentDecision(
                    scan_id=scan_id,
                    agent_name="Deduplication Agent",
                    decision=f"Marked '{opp.title}' as duplicate",
                    reasoning=f"Local Cosine similarity {sim:.2%} with existing record '{ex['title']}'",
                    opportunity_id=opp.id
                ))
                break
        
        if is_dup:
            continue

        # ── Not a duplicate ──────────────────────────────────────────────
        seen_keys.add(key)
        unique.append(opp)

        # Bypassed ChromaDB writes to ensure sub-millisecond thread safety
        pass

    summary_decision = AgentDecision(
        scan_id=scan_id,
        agent_name="Deduplication Agent",
        decision=f"Kept {len(unique)} unique opportunities, removed {duplicate_count} duplicates",
        reasoning="Used local word frequency Cosine Similarity (threshold 0.85) for semantic duplicate detection"
    )

    # Update scan metadata
    scan_meta = state.get("scan_metadata")
    if scan_meta:
        scan_meta.total_unique = len(unique)
        scan_meta.total_duplicates_removed = duplicate_count

    # 💾 Intermediate DB checkpoint saving:
    from core.memory import save_opportunities_bulk
    try:
        save_opportunities_bulk(unique)
    except Exception as e:
        print(f"[Deduplicator DB Checkpoint] Save failed: {e}", flush=True)

    return {
        "deduplicated_opportunities": unique,
        "duplicates_removed": duplicate_count,
        "agent_logs": [summary_decision] + decisions,
        "scan_metadata": scan_meta,
        "progress_messages": [
            f"🔄 **Deduplication Agent** — Done",
            f"   ✅ {len(unique)} unique opportunities kept",
            f"   🗑️  {duplicate_count} duplicates removed",
            f"   🧠 Used local Cosine Similarity matching"
        ]
    }
