"""
Agent 1: Search Planning Agent
─────────────────────────────
Uses Gemini to analyze the current date and opportunity landscape,
then creates a prioritized, structured search plan for all downstream agents.
"""
from __future__ import annotations
import json
from datetime import datetime
from core.state import AgentState
from core.models import SearchPlan, AgentDecision
from core.llm import get_llm, parse_json_safely, rate_limited_invoke
from core.sources import SOURCES, CATEGORIES
import uuid


PLANNER_PROMPT = """You are the Search Planning Agent for OpportunityOS AI — an autonomous opportunity discovery system.

Today's date: {date}

Your mission is to create an optimal search plan to discover the most relevant, timely, and valuable opportunities for students and developers.

Available sources: {sources}

Opportunity categories: {categories}

Create a comprehensive search plan. Return ONLY valid JSON in this exact format:
{{
  "sources": ["list", "of", "source", "names", "to", "search"],
  "queries": ["search query 1", "search query 2", "search query 3"],
  "priorities": ["highest priority category", "second priority", "third priority"],
  "rationale": "Detailed explanation of why this plan was chosen, what timing factors matter (e.g., deadlines approaching), and what opportunities are likely most valuable right now",
  "estimated_count": 45
}}

Guidelines:
- Include ALL 15 sources in the search plan
- Prioritize hackathons and open source programs as they have specific deadlines
- Consider that it's {month} — mention any seasonal opportunities (summer programs, etc.)
- Create 5-8 diverse search queries
- Estimated count should be realistic: 40-80 opportunities
"""


def run_planner(state: AgentState) -> dict:
    """
    Agent 1 node: Creates the search execution plan.
    Updates: search_plan, agent_logs, progress_messages
    """
    llm = get_llm(temperature=0.4)
    now = datetime.utcnow()
    source_names = [s.name for s in SOURCES]

    prompt = PLANNER_PROMPT.format(
        date=now.strftime("%Y-%m-%d"),
        month=now.strftime("%B %Y"),
        sources=", ".join(source_names),
        categories=", ".join(CATEGORIES)
    )

    try:
        raw = rate_limited_invoke(llm, [("human", prompt)])
        plan_data = parse_json_safely(raw)

        plan = SearchPlan(
            sources=plan_data.get("sources", source_names),
            queries=plan_data.get("queries", ["student opportunities 2025", "hackathon 2025"]),
            priorities=plan_data.get("priorities", ["Hackathon", "Open Source", "Internship"]),
            rationale=plan_data.get("rationale", "Standard opportunity search"),
            estimated_count=plan_data.get("estimated_count", 50)
        )
    except Exception as e:
        # Fallback plan on LLM failure
        plan = SearchPlan(
            sources=source_names,
            queries=["hackathon 2025", "student internship", "open source program", "fellowship 2025"],
            priorities=["Hackathon", "Open Source", "Internship"],
            rationale="Fallback plan: comprehensive search across all sources",
            estimated_count=50
        )

    decision = AgentDecision(
        scan_id=state["scan_id"],
        agent_name="Search Planning Agent",
        decision=f"Created search plan targeting {len(plan.sources)} sources",
        reasoning=plan.rationale
    )

    return {
        "search_plan": plan,
        "agent_logs": [decision],
        "progress_messages": [
            f"🧠 **Search Planning Agent** — Plan created",
            f"   📋 Targeting {len(plan.sources)} sources",
            f"   🎯 Priority categories: {', '.join(plan.priorities[:3])}",
            f"   📊 Estimated ~{plan.estimated_count} opportunities"
        ]
    }
