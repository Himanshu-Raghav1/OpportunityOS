"""
Agent 7: Ranking Agent
───────────────────────
Scores each opportunity on a 0-100 scale using weighted factors:
  - Reputation (org prestige)      : 20%
  - Learning Value                  : 15%
  - Career Value                    : 20%
  - Accessibility (no barrier)      : 15%
  - Prize/Stipend Value             : 10%
  - Technical Relevance             : 10%
  - Deadline Urgency                : 5%
  - Community Impact                : 5%

Uses rule-based scoring + LLM batch reasoning for efficiency and transparency.
"""
from __future__ import annotations
import re
import time
from datetime import datetime
from typing import List, Dict, Any
from core.state import AgentState
from core.models import Opportunity, AgentDecision
from core.llm import get_precise_llm, parse_json_safely, rate_limited_invoke

# Org reputation presets (manually curated, normalized 0-10)
REPUTATION_MAP: Dict[str, float] = {
    "google": 10.0, "microsoft": 9.5, "amazon": 9.0, "aws": 9.0,
    "meta": 9.0, "apple": 9.0, "netflix": 8.5, "openai": 9.5,
    "outreachy": 8.5, "mlh": 8.0, "gsoc": 9.5, "kaggle": 8.5,
    "devpost": 7.0, "devfolio": 7.5, "unstop": 7.0,
    "github": 9.0, "linux foundation": 8.5, "mozilla": 8.0,
    "mit": 9.5, "stanford": 9.5, "cmu": 9.0, "iit": 8.5,
    "wellfound": 7.5, "angellist": 7.5,
}

PRIZE_PATTERNS = [
    (r"\$[\d,]+k|\$[\d,]{4,}", 10.0),   # $10k+ prizes
    (r"\$[\d,]{3}", 7.0),               # $100-$999
    (r"stipend|paid|salary", 8.0),
    (r"certificate|swag|goodies", 3.0),
    (r"internship offer|ppo|pre-placement", 9.0),
]


def score_reputation(opp: Opportunity) -> float:
    """Score 0-10 based on known organization prestige."""
    org_lower = opp.organization.lower()
    for key, score in REPUTATION_MAP.items():
        if key in org_lower:
            return score
    return 5.0


def score_prize(opp: Opportunity) -> float:
    """Score 0-10 based on reward value."""
    rewards_lower = opp.rewards.lower()
    for pattern, score in PRIZE_PATTERNS:
        if re.search(pattern, rewards_lower, re.IGNORECASE):
            return score
    if rewards_lower and rewards_lower != "certificate":
        return 4.0
    return 2.0


def score_accessibility(opp: Opportunity) -> float:
    """Score 0-10: higher = more accessible (open to beginners, global, remote)."""
    score = 5.0
    elig_lower = opp.eligibility.lower()
    if "open to all" in elig_lower or "everyone" in elig_lower:
        score += 2.0
    if "no experience" in elig_lower or "beginner" in elig_lower:
        score += 1.5
    if opp.is_remote:
        score += 1.5
    if "global" in opp.country.lower():
        score += 1.0
    if "experience required" in elig_lower or "senior" in elig_lower:
        score -= 2.0
    return min(10.0, max(0.0, score))


def score_deadline_urgency(opp: Opportunity) -> float:
    """Score 0-10: higher = deadline approaching soon (more urgent = more relevant now)."""
    if not opp.deadline or opp.deadline.lower() in ("tba", "rolling", "ongoing"):
        return 5.0
    try:
        for fmt in ["%Y-%m-%d", "%d %B %Y", "%B %Y", "%Y"]:
            try:
                deadline_dt = datetime.strptime(opp.deadline[:10], fmt)
                days_left = (deadline_dt - datetime.utcnow()).days
                if days_left < 0:
                    return 1.0
                elif days_left <= 7:
                    return 10.0
                elif days_left <= 30:
                    return 8.0
                elif days_left <= 90:
                    return 6.0
                else:
                    return 4.0
            except ValueError:
                continue
    except Exception:
        pass
    return 5.0


def compute_rule_based_score(opp: Opportunity) -> float:
    """Compute weighted composite score using rule-based factors."""
    reputation = score_reputation(opp)
    learning = opp.learning_impact
    career = opp.career_impact
    accessibility = score_accessibility(opp)
    prize = score_prize(opp)
    technical = min(10.0, len(opp.required_skills) * 1.5 + 3)
    urgency = score_deadline_urgency(opp)
    community = 6.0

    weighted = (
        reputation   * 0.20 +
        learning     * 0.15 +
        career       * 0.20 +
        accessibility * 0.15 +
        prize        * 0.10 +
        technical    * 0.10 +
        urgency      * 0.05 +
        community    * 0.05
    )
    return round(weighted * 10, 1)


BATCH_RANKING_PROMPT = """You are an expert at evaluating tech and student opportunities.

Score these opportunities on a scale of 0-100 and explain your reasoning.

Opportunities:
{opp_list}

Return ONLY valid JSON mapping each opportunity ID to its score and reasoning:
{{
  "opp_id_1": {{
    "score": 75,
    "reasoning": "Brief explanation of why this score was assigned — 2-3 specific points"
  }}
}}
"""


def llm_rank_batch(opps: List[Opportunity], llm) -> Dict[str, dict]:
    """Rank opportunities in batches of 15 to save API calls and prevent network timeouts."""
    results = {}
    batch_size = 15
    
    for i in range(0, len(opps), batch_size):
        batch = opps[i:i + batch_size]
        
        # Pre-populate fallbacks
        for opp in batch:
            results[opp.id] = {
                "score": compute_rule_based_score(opp),
                "reasoning": f"Rule-based: Reputation {score_reputation(opp)*10:.0f}/100, Career {opp.career_impact*10:.0f}/100"
            }
            
        opp_list_str = []
        for opp in batch:
            opp_list_str.append(
                f"ID: {opp.id}\n"
                f"Title: {opp.title}\n"
                f"Org: {opp.organization}\n"
                f"Category: {opp.category}\n"
                f"Desc: {opp.description[:180]}\n"
                f"Rewards: {opp.rewards[:150]}\n"
                f"Eligibility: {opp.eligibility[:150]}\n"
                f"Career Impact Score: {opp.career_impact}/10\n"
                f"Learning Impact Score: {opp.learning_impact}/10\n"
                f"Location: {opp.location}\n"
                f"---"
            )
            
        prompt = BATCH_RANKING_PROMPT.format(
            opp_list="\n".join(opp_list_str)
        )
        
        try:
            raw = rate_limited_invoke(llm, [("human", prompt)])
            data = parse_json_safely(raw)
            if isinstance(data, dict):
                for opp in batch:
                    opp_res = data.get(opp.id, {})
                    if isinstance(opp_res, dict):
                        results[opp.id] = {
                            "score": float(opp_res.get("score", results[opp.id]["score"])),
                            "reasoning": str(opp_res.get("reasoning", results[opp.id]["reasoning"]))[:300]
                        }
            else:
                print(f"[Ranker] Batch {i // batch_size + 1}: LLM returned non-object response", flush=True)
        except Exception as e:
            print(f"[Ranker] Batch {i // batch_size + 1} failed: {e}", flush=True)
            
        time.sleep(0.5)
        
    return results


def run_ranker(state: AgentState) -> dict:
    """
    Agent 7 node: Ranks all opportunities with scores and reasoning.
    Updates: ranked_opportunities, scan_metadata, agent_logs, progress_messages
    """
    opps = state.get("enriched_opportunities", [])
    scan_id = state["scan_id"]

    if not opps:
        return {
            "ranked_opportunities": [],
            "agent_logs": [],
            "progress_messages": ["🏆 **Ranking Agent** — No opportunities to rank"]
        }

    llm = get_precise_llm()
    
    # Run batch ranking
    rank_results = llm_rank_batch(opps, llm)
    
    ranked: List[Opportunity] = []
    for opp in opps:
        # Load rule-based details for transparency metrics
        opp.reputation_score = score_reputation(opp) * 10
        opp.learning_score = opp.learning_impact * 10
        opp.career_score = opp.career_impact * 10
        opp.accessibility_score = score_accessibility(opp) * 10

        res = rank_results.get(opp.id)
        if res:
            # Blend rule-based (60%) + LLM (40%)
            rule_score = compute_rule_based_score(opp)
            final_score = round(rule_score * 0.6 + res["score"] * 0.4, 1)
            opp.score = min(100.0, max(0.0, final_score))
            opp.ranking_reasoning = res["reasoning"]
        else:
            opp.score = compute_rule_based_score(opp)
            opp.ranking_reasoning = f"Rule-based fallback: Reputation {opp.reputation_score:.0f}/100"

        ranked.append(opp)

    # Sort by score descending
    ranked.sort(key=lambda o: o.score, reverse=True)

    # 💾 Intermediate DB checkpoint saving:
    from core.memory import save_opportunities_bulk
    try:
        save_opportunities_bulk(ranked)
    except Exception as e:
        print(f"[Ranker DB Checkpoint] Save failed: {e}", flush=True)

    # Update scan metadata
    scan_meta = state.get("scan_metadata")
    if scan_meta:
        scan_meta.total_unique = len(ranked)
        scan_meta.completed_at = datetime.utcnow()
        scan_meta.status = "completed"
        from core.memory import save_scan
        try:
            save_scan(scan_meta)
        except Exception:
            pass

    top3 = [f"{o.title} ({o.score:.0f})" for o in ranked[:3]]
    decision = AgentDecision(
        scan_id=scan_id,
        agent_name="Ranking Agent",
        decision=f"Ranked {len(ranked)} opportunities. Top 3: {', '.join(top3)}",
        reasoning="Used weighted rule formula blended with batch LLM evaluation (40%)"
    )

    return {
        "ranked_opportunities": ranked,
        "scan_metadata": scan_meta,
        "agent_logs": [decision],
        "progress_messages": [
            f"🏆 **Ranking Agent** — Scoring complete",
            f"   📊 {len(ranked)} opportunities ranked",
            f"   🥇 Top opportunity: {ranked[0].title if ranked else 'N/A'} ({ranked[0].score:.0f}/100)" if ranked else "   🥇 No opportunities ranked",
            f"   📈 Score range: {ranked[-1].score:.0f} – {ranked[0].score:.0f}"
        ]
    }
