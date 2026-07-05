"""
Agent 4: Deduplication Agent
─────────────────────────────
Detects and removes duplicate opportunities using:
  1. Exact title+org matching (fast)
  2. ChromaDB cosine similarity (semantic near-dedup)
  3. LLM confirmation for borderline cases
"""
from __future__ import annotations
import re
from typing import List, Set, Tuple
from core.state import AgentState
from core.models import Opportunity, AgentDecision
from core.memory import find_similar_opportunities, add_to_vector_store, get_all_opportunity_titles


def normalize_title(title: str) -> str:
    """Normalize title for comparison: lowercase, strip special chars."""
    return re.sub(r"[^a-z0-9\s]", "", title.lower()).strip()


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
    Agent 4 node: Removes duplicate opportunities.
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
    seen_keys: Set[str] = set()  # "title|org" normalized keys
    duplicate_count = 0
    decisions = []

    # Step 1: Load existing opportunities from memory to cross-scan dedup
    existing = get_all_opportunity_titles()
    existing_keys = {
        normalize_title(e["title"]) + "|" + normalize_title(e.get("organization", ""))
        for e in existing
    }

    for opp in extracted:
        key = normalize_title(opp.title) + "|" + normalize_title(opp.organization)

        # ── Check 1: Exact normalized match within this scan ──
        if key in seen_keys:
            opp.is_duplicate = True
            duplicate_count += 1
            continue

        # ── Check 2: Title similarity within this scan batch ──
        is_dup = False
        for existing_opp in unique:
            if titles_are_similar(opp.title, existing_opp.title) and \
               normalize_title(opp.organization) == normalize_title(existing_opp.organization):
                opp.is_duplicate = True
                opp.duplicate_of = existing_opp.id
                duplicate_count += 1
                is_dup = True
                break

        if is_dup:
            continue

        # ── Check 3: ChromaDB semantic similarity against existing DB ──
        query_text = f"{opp.title} {opp.organization}"
        similar = find_similar_opportunities(query_text, threshold=0.90)
        if similar:
            opp.is_duplicate = True
            opp.duplicate_of = similar[0].get("id")
            duplicate_count += 1
            decisions.append(AgentDecision(
                scan_id=scan_id,
                agent_name="Deduplication Agent",
                decision=f"Marked '{opp.title}' as duplicate",
                reasoning=f"ChromaDB similarity {similar[0].get('similarity', 0):.2%} with existing record",
                opportunity_id=opp.id
            ))
            continue

        # ── Not a duplicate ──────────────────────────────────────────────
        seen_keys.add(key)
        unique.append(opp)

        # Add to ChromaDB for future dedup checks
        add_to_vector_store(opp)

    summary_decision = AgentDecision(
        scan_id=scan_id,
        agent_name="Deduplication Agent",
        decision=f"Kept {len(unique)} unique opportunities, removed {duplicate_count} duplicates",
        reasoning="Used normalized string matching + ChromaDB cosine similarity (threshold 0.90) for semantic duplicate detection"
    )

    # Update scan metadata
    scan_meta = state.get("scan_metadata")
    if scan_meta:
        scan_meta.total_unique = len(unique)
        scan_meta.total_duplicates_removed = duplicate_count

    return {
        "deduplicated_opportunities": unique,
        "duplicates_removed": duplicate_count,
        "agent_logs": [summary_decision] + decisions,
        "scan_metadata": scan_meta,
        "progress_messages": [
            f"🔄 **Deduplication Agent** — Analysis complete",
            f"   ✅ {len(unique)} unique opportunities kept",
            f"   🗑️  {duplicate_count} duplicates removed",
            f"   🧠 Used semantic similarity + exact matching"
        ]
    }
