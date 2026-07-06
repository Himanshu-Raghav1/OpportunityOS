"""
Agent 5: Classification Agent
──────────────────────────────
Classifies each opportunity into one of 9 categories using:
  1. Rule-based regex keyword matching with word boundaries (fast, deterministic)
  2. LLM batch fallback for ambiguous cases (optimized to prevent 429 rate limits)
"""
from __future__ import annotations
import re
import time
import json
from typing import List, Dict, Tuple, Optional
from core.state import AgentState
from core.models import Opportunity, AgentDecision
from core.llm import get_precise_llm, parse_json_safely, rate_limited_invoke

CATEGORIES = [
    "Hackathon", "Ideathon", "Internship", "Open Source",
    "Fellowship", "Competition", "Research", "Student Program", "Developer Program"
]

# Rule-based regex keyword map (category → compiled regex with word boundaries to check in text)
CATEGORY_RULES: Dict[str, re.Pattern] = {
    "Hackathon": re.compile(
        r"\b(hackathon|hackathons|buildathon|buildathons|codefest|hackfest|hackfests|hack|hacks|datathon|datathons|designathon|designathons|game\s*jam|gamejams)\b",
        re.IGNORECASE
    ),
    "Ideathon": re.compile(
        r"\b(ideathon|ideathons|idea\s+challenge|innovation\s+challenge|idea\s+competition|pitch\s+competition|b-plan|business\s+plan|venture\s+challenge)\b",
        re.IGNORECASE
    ),
    "Internship": re.compile(
        r"\b(internship|internships|intern|interns|co-op|coop|apprentice|apprenticeship|apprenticeships|work\s+placement|job\s+placement)\b",
        re.IGNORECASE
    ),
    "Open Source": re.compile(
        r"\b(gsoc|outreachy|open\s*source|open-source|lfx|osoc|octoberfest|hacktoberfest|mentorship|mentorships|mentee)\b",
        re.IGNORECASE
    ),
    "Fellowship": re.compile(
        r"\b(fellowship|fellowships|fellow|fellows|scholar|scholars|cohort|residency|residencies|scholarship|scholarships)\b",
        re.IGNORECASE
    ),
    "Competition": re.compile(
        r"\b(competition|competitions|contest|contests|kaggle|challenge|challenges|tournament|tournaments|olympiad|olympiads|ctf|capture\s+the\s+flag|hackerrank|codeforces|hackerearth)\b",
        re.IGNORECASE
    ),
    "Research": re.compile(
        r"\b(research|phd|postdoc|paper|papers|professor|academic|thesis|dissertation|journal|journals|symposium|symposiums|lab|laboratory)\b",
        re.IGNORECASE
    ),
    "Student Program": re.compile(
        r"\b(student\s+program|student\s+programs|imagine\s+cup|campus\s+ambassador|student\s+ambassador|student\s+lead|student\s+chapter|gdsc)\b",
        re.IGNORECASE
    ),
    "Developer Program": re.compile(
        r"\b(developer\s+program|developer\s+programs|developer\s+relations|devrel|developer\s+advocate|cloud\s+program|credits|api\s+access|early\s+access|beta\s+program|beta\s+programs)\b",
        re.IGNORECASE
    ),
}


def rule_based_classify(opp: Opportunity) -> Tuple[str, float, str]:
    """
    Returns (category, confidence, reasoning) using regex pattern matching with word boundaries.
    Confidence: 1.0 for strong match, 0.4+ for match, 0.0 for no match.
    """
    text = f"{opp.title} {opp.description} {opp.source}".lower()

    scores: Dict[str, int] = {}
    for cat, pattern in CATEGORY_RULES.items():
        # Find all occurrences of word-boundary matches
        matches = pattern.findall(text)
        if matches:
            scores[cat] = len(matches)

    if not scores:
        return "Competition", 0.0, "No keyword match found — defaulting to Competition"

    best_cat = max(scores, key=scores.get)
    best_score = scores[best_cat]
    confidence = min(1.0, best_score * 0.4)
    reasoning = f"Regex match: '{best_cat}' matched pattern {best_score} time(s) with word boundaries"

    return best_cat, confidence, reasoning


BATCH_CLASSIFICATION_PROMPT = """You are the Classification Agent. Classify these opportunities into one of these categories:
Categories: {categories}

Opportunities to classify:
{opp_list}

Return ONLY a JSON object mapping each opportunity ID to its category and reasoning:
{{
  "id_1": {{
    "category": "Category Name",
    "reasoning": "Brief explanation of why this category fits."
  }}
}}
"""


def llm_classify_batch(opps: List[Opportunity], llm) -> Dict[str, Tuple[str, str]]:
    """Classify opportunities in batches of 15 to save API calls and speed up execution."""
    results = {}
    batch_size = 15
    
    for i in range(0, len(opps), batch_size):
        batch = opps[i:i + batch_size]
        
        # Pre-populate fallbacks
        for opp in batch:
            results[opp.id] = ("Competition", "LLM skipped this ID or failed")
            
        opp_list_str = []
        for opp in batch:
            opp_list_str.append(
                f"ID: {opp.id}\n"
                f"Title: {opp.title}\n"
                f"Org: {opp.organization}\n"
                f"Desc: {opp.description[:180]}\n"
                f"Source: {opp.source}\n"
                f"Rewards: {opp.rewards}\n"
                f"---"
            )
            
        prompt = BATCH_CLASSIFICATION_PROMPT.format(
            categories=", ".join(CATEGORIES),
            opp_list="\n".join(opp_list_str)
        )
        
        try:
            raw = rate_limited_invoke(llm, [("human", prompt)])
            data = parse_json_safely(raw)
            if isinstance(data, dict):
                for opp in batch:
                    opp_res = data.get(opp.id, {})
                    if isinstance(opp_res, dict):
                        category = opp_res.get("category", "Competition")
                        if category not in CATEGORIES:
                            category = "Competition"
                        reasoning = opp_res.get("reasoning", "LLM classification")
                        results[opp.id] = (category, reasoning)
            else:
                print(f"[Classifier] Batch {i // batch_size + 1}: LLM returned non-object response", flush=True)
        except Exception as e:
            print(f"[Classifier] Batch {i // batch_size + 1} failed: {e}", flush=True)
            
        # breathing room between batches
        time.sleep(0.5)
        
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

    # Step 1: Rule-based classification with regex word boundaries
    needs_llm: List[Opportunity] = []
    classified: List[Opportunity] = []
    category_counts: Dict[str, int] = {}

    for opp in opps:
        cat, confidence, reasoning = rule_based_classify(opp)
        if confidence >= 0.4:
            opp.category = cat
            opp.classification_reasoning = reasoning
            category_counts[cat] = category_counts.get(cat, 0) + 1
        else:
            needs_llm.append(opp)
        classified.append(opp)

    # Step 2: LLM for ambiguous ones using high-efficiency batch classification
    if needs_llm:
        llm = get_precise_llm()
        llm_results = llm_classify_batch(needs_llm, llm)
        for opp in needs_llm:
            if opp.id in llm_results:
                cat, reasoning = llm_results[opp.id]
                opp.category = cat
                opp.classification_reasoning = f"LLM: {reasoning}"
                category_counts[cat] = category_counts.get(cat, 0) + 1

    # Build category summary
    cat_summary = ", ".join([f"{k}: {v}" for k, v in sorted(category_counts.items())])

    decision = AgentDecision(
        scan_id=scan_id,
        agent_name="Classification Agent",
        decision=f"Classified {len(classified)} opportunities into {len(category_counts)} categories",
        reasoning=f"Rule-based: {len(classified) - len(needs_llm)} | LLM fallback: {len(needs_llm)} (in batches of 15). Distribution: {cat_summary}"
    )

    return {
        "classified_opportunities": classified,
        "agent_logs": [decision],
        "progress_messages": [
            f"🏷️  **Classification Agent** — Done",
            f"   📊 {len(classified)} opportunities classified",
            f"   🤖 {len(needs_llm)} used batch LLM classification",
            f"   📈 Categories: {cat_summary}"
        ]
    }
