"""
Agent 5: Classification Agent
──────────────────────────────
Classifies each opportunity into one of 9 categories using:
  1. Rule-based keyword matching (fast, deterministic)
  2. LLM fallback for ambiguous cases
"""
from __future__ import annotations
import re
from typing import List, Dict, Tuple
from core.state import AgentState
from core.models import Opportunity, AgentDecision
from core.llm import get_precise_llm, parse_json_safely, rate_limited_invoke

CATEGORIES = [
    "Hackathon", "Ideathon", "Internship", "Open Source",
    "Fellowship", "Competition", "Research", "Student Program", "Developer Program"
]

# Rule-based keyword map (category → keywords to check in title/description/source)
CATEGORY_RULES: Dict[str, List[str]] = {
    "Hackathon": ["hackathon", "hack ", "hacks", "devfolio", "mlh", "devpost", "buildathon", "hackfest"],
    "Ideathon": ["ideathon", "idea challenge", "innovation challenge", "idea competition", "pitch"],
    "Internship": ["internship", "intern ", "wellfound", "summer internship", "winter internship", "apprentice"],
    "Open Source": ["gsoc", "outreachy", "open source", "google summer", "open-source", "lfx", "season of docs"],
    "Fellowship": ["fellowship", "fellow ", "scholar", "cohort", "residency"],
    "Competition": ["competition", "contest", "kaggle", "challenge", "tournament", "olympiad"],
    "Research": ["research", "undergraduate research", "phd", "professor", "paper", "publication", "lab"],
    "Student Program": ["student program", "campus", "imagine cup", "microsoft student", "gdsc", "google developer"],
    "Developer Program": ["developer program", "aws", "cloud program", "developer advocate", "beta program"],
}


def rule_based_classify(opp: Opportunity) -> Tuple[str, float, str]:
    """
    Returns (category, confidence, reasoning) using keyword matching.
    Confidence: 1.0 for strong match, 0.6 for weak match, 0.0 for no match.
    """
    text = f"{opp.title} {opp.description} {opp.source}".lower()

    scores: Dict[str, int] = {}
    for cat, keywords in CATEGORY_RULES.items():
        score = sum(1 for kw in keywords if kw in text)
        if score > 0:
            scores[cat] = score

    if not scores:
        return "Competition", 0.0, "No keyword match found — defaulting to Competition"

    best_cat = max(scores, key=scores.get)
    best_score = scores[best_cat]
    confidence = min(1.0, best_score * 0.4)
    reasoning = f"Keyword match: '{best_cat}' matched {best_score} keyword(s) in title/description/source"

    return best_cat, confidence, reasoning


CLASSIFICATION_PROMPT = """You are the Classification Agent. Classify this opportunity.
Title: {title}
Org: {organization}
Desc: {description}
Source: {source}
Rewards: {rewards}

Categories: {categories}

Return ONLY JSON:
{{
  "category": "Category Name",
  "reasoning": "Brief explanation of why this category fits"
}}
"""


def llm_classify_batch(opps: List[Opportunity], llm) -> Dict[str, Tuple[str, str]]:
    """Classify a batch of ambiguous opportunities using LLM."""
    results = {}
    for opp in opps:
        prompt = CLASSIFICATION_PROMPT.format(
            categories=", ".join(CATEGORIES),
            title=opp.title,
            organization=opp.organization,
            description=opp.description[:200],
            source=opp.source,
            rewards=opp.rewards
        )
        try:
            raw = rate_limited_invoke(llm, [("human", prompt)])
            data = parse_json_safely(raw)
            category = data.get("category", "Competition")
            # Validate category
            if category not in CATEGORIES:
                category = "Competition"
            reasoning = data.get("reasoning", "LLM classification")
            results[opp.id] = (category, reasoning)
        except Exception:
            results[opp.id] = ("Competition", "Classification failed — defaulted to Competition")
    return results


def run_classifier(state: AgentState) -> dict:
    """
    Agent 5 node: Classifies all deduplicated opportunities.
    Updates: classified_opportunities, agent_logs, progress_messages
    """
    opps = state.get("deduplicated_opportunities", [])
    scan_id = state["scan_id"]

    if not opps:
        return {
            "classified_opportunities": [],
            "agent_logs": [],
            "progress_messages": ["🏷️  **Classification Agent** — No opportunities to classify"]
        }

    # Step 1: Rule-based classification
    needs_llm: List[Opportunity] = []
    classified: List[Opportunity] = []
    category_counts: Dict[str, int] = {}

    for opp in opps:
        cat, confidence, reasoning = rule_based_classify(opp)
        if confidence >= 0.4:
            opp.category = cat
            opp.classification_reasoning = reasoning
        else:
            needs_llm.append(opp)

        category_counts[cat] = category_counts.get(cat, 0) + 1
        classified.append(opp)

    # Step 2: LLM for ambiguous ones
    if needs_llm:
        llm = get_precise_llm()
        llm_results = llm_classify_batch(needs_llm, llm)
        for opp in needs_llm:
            if opp.id in llm_results:
                cat, reasoning = llm_results[opp.id]
                opp.category = cat
                opp.classification_reasoning = f"LLM: {reasoning}"

    # Build category summary
    cat_summary = ", ".join([f"{k}: {v}" for k, v in sorted(category_counts.items())])

    decision = AgentDecision(
        scan_id=scan_id,
        agent_name="Classification Agent",
        decision=f"Classified {len(classified)} opportunities into {len(category_counts)} categories",
        reasoning=f"Rule-based: {len(classified) - len(needs_llm)} | LLM fallback: {len(needs_llm)}. Distribution: {cat_summary}"
    )

    return {
        "classified_opportunities": classified,
        "agent_logs": [decision],
        "progress_messages": [
            f"🏷️  **Classification Agent** — Done",
            f"   📊 {len(classified)} opportunities classified",
            f"   🤖 {len(needs_llm)} used LLM classification",
            f"   📈 Categories: {cat_summary}"
        ]
    }
