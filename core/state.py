"""
LangGraph shared state for the OpportunityOS multi-agent pipeline.
Every agent reads from and writes to this state.
"""
from __future__ import annotations
from typing import TypedDict, List, Optional, Annotated
import operator
from core.models import Opportunity, SearchPlan, AgentDecision, ScanMetadata


def merge_lists(a: list, b: list) -> list:
    """Reducer that appends new items to the list."""
    return a + b


class AgentState(TypedDict):
    """Shared state passed through the LangGraph pipeline."""

    # Input / control
    scan_id: str
    user_preferences: dict                    # Optional user filter prefs

    # Agent 1 output
    search_plan: Optional[SearchPlan]

    # Agent 2 output
    raw_opportunities: List[dict]             # Unstructured raw data

    # Agent 3 output
    extracted_opportunities: List[Opportunity]

    # Agent 4 output
    deduplicated_opportunities: List[Opportunity]
    duplicates_removed: int

    # Agent 5 output
    classified_opportunities: List[Opportunity]

    # Agent 6 output
    enriched_opportunities: List[Opportunity]

    # Agent 7 output (final)
    ranked_opportunities: List[Opportunity]

    # Cross-agent logs (append-only)
    agent_logs: Annotated[List[AgentDecision], merge_lists]

    # Hunter sub-node context (stats passed between hunter layers)
    hunter_context: dict

    # Scan metadata
    scan_metadata: Optional[ScanMetadata]

    # Real-time progress messages (append-only)
    progress_messages: Annotated[List[str], merge_lists]

    # Error tracking
    errors: Annotated[List[str], merge_lists]

    # Hunter sub-pipeline scratch stats (snippet counts, etc.)
    hunter_stats: dict
