"""
Agent 6: Opportunity Intelligence Agent
────────────────────────────────────────
Generates deep AI insights for each opportunity using Gemini/Groq:
  - What it is (clear summary)
  - Why it matters
  - Who should apply
  - Career impact score (1–10)
  - Learning impact score (1–10)
Optimized with batch processing to prevent API hangs and timeouts.
"""
from __future__ import annotations
import json
import time
from typing import List, Dict, Tuple
from core.state import AgentState
from core.models import Opportunity, AgentDecision
from core.llm import get_creative_llm, parse_json_safely, rate_limited_invoke
from core.memory import save_opportunities_bulk

BATCH_INTELLIGENCE_PROMPT = """You are an expert career counselor and opportunity analyst for students and developers.

Analyze these opportunities and provide rich, actionable insights.

Opportunities to analyze:
{opp_list}

Return ONLY a valid JSON object mapping each opportunity ID to its details:
{{
  "opp_id_1": {{
    "ai_insight": "2-3 sentence punchy summary of this opportunity. Start with what makes it special.",
    "why_it_matters": "Why this opportunity is significant — impact on career, skills, or community",
    "who_should_apply": "Specific profile of ideal applicant — year, skills, goals",
    "career_impact": 8,
    "learning_impact": 7
  }}
}}

Scoring guidelines (1-10):
- career_impact: Does it add prestige to a resume? Lead to jobs/networks? High = top company internship/GSoC. Low = small local competition.
- learning_impact: How much will the applicant learn? High = mentorship + new skills. Low = just submitting a project.
"""


def llm_enrich_batch(opps: List[Opportunity], llm) -> Dict[str, dict]:
    """Enrich opportunities in batches of 10 to save API calls and prevent network timeouts."""
    results = {}
    batch_size = 10
    
    for i in range(0, len(opps), batch_size):
        batch = opps[i:i + batch_size]
        
        # Pre-populate fallbacks
        for opp in batch:
            results[opp.id] = {
                "ai_insight": f"A {opp.category} opportunity from {opp.organization}. Check the link for full details.",
                "why_it_matters": f"Provides exposure and learning in the {opp.category} domain.",
                "who_should_apply": f"Developers with interest in: {', '.join(opp.required_skills) if opp.required_skills else 'software engineering'}.",
                "career_impact": 5,
                "learning_impact": 5
            }
            
        opp_list_str = []
        for opp in batch:
            opp_list_str.append(
                f"ID: {opp.id}\n"
                f"Title: {opp.title}\n"
                f"Org: {opp.organization}\n"
                f"Category: {opp.category}\n"
                f"Desc: {opp.description[:180]}\n"
                f"Deadline: {opp.deadline or 'TBA'}\n"
                f"Eligibility: {opp.eligibility[:150]}\n"
                f"Rewards: {opp.rewards[:150]}\n"
                f"Location: {opp.location}\n"
                f"Skills: {', '.join(opp.required_skills[:4]) if opp.required_skills else 'General'}\n"
                f"---"
            )
            
        prompt = BATCH_INTELLIGENCE_PROMPT.format(
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
                            "ai_insight": str(opp_res.get("ai_insight", results[opp.id]["ai_insight"]))[:500],
                            "why_it_matters": str(opp_res.get("why_it_matters", results[opp.id]["why_it_matters"]))[:400],
                            "who_should_apply": str(opp_res.get("who_should_apply", results[opp.id]["who_should_apply"]))[:300],
                            "career_impact": min(10, max(1, int(opp_res.get("career_impact", 5)))),
                            "learning_impact": min(10, max(1, int(opp_res.get("learning_impact", 5))))
                        }
            else:
                print(f"[Intelligence] Batch {i // batch_size + 1}: LLM returned non-object response", flush=True)
        except Exception as e:
            print(f"[Intelligence] Batch {i // batch_size + 1} failed: {e}", flush=True)
            
        # breathing room
        time.sleep(0.5)
        
    return results


def run_intelligence(state: AgentState) -> dict:
    """
    Agent 6 node: Generates AI insights for each classified opportunity.
    Updates: enriched_opportunities, agent_logs, progress_messages
    """
    opps = state.get("classified_opportunities", [])
    scan_id = state["scan_id"]

    if not opps:
        return {
            "enriched_opportunities": [],
            "agent_logs": [],
            "progress_messages": ["🧠 **Intelligence Agent** — No opportunities to enrich"]
        }

    llm = get_creative_llm()
    
    # Enrich in batch
    enrich_results = llm_enrich_batch(opps, llm)
    
    enriched: List[Opportunity] = []
    failed = 0

    for opp in opps:
        res = enrich_results.get(opp.id)
        if res:
            opp.ai_insight = res["ai_insight"]
            opp.why_it_matters = res["why_it_matters"]
            opp.who_should_apply = res["who_should_apply"]
            opp.career_impact = res["career_impact"]
            opp.learning_impact = res["learning_impact"]
            if "fallback" in res["ai_insight"].lower() or "full details" in res["ai_insight"].lower():
                failed += 1
        else:
            opp.ai_insight = f"A {opp.category} opportunity from {opp.organization}. Check the link for full details."
            opp.career_impact = 5
            opp.learning_impact = 5
            failed += 1
            
        enriched.append(opp)

    decision = AgentDecision(
        scan_id=scan_id,
        agent_name="Opportunity Intelligence Agent",
        decision=f"Generated AI insights for {len(enriched) - failed} of {len(enriched)} opportunities",
        reasoning=f"Used batch LLM processing (size=10) with creative temperature (0.7). {failed} items resolved to fallback templates."
    )

    # 💾 Intermediate DB checkpoint saving:
    try:
        save_opportunities_bulk(enriched)
    except Exception as e:
        print(f"[Intelligence DB Checkpoint] Save failed: {e}", flush=True)

    avg_career = sum(o.career_impact for o in enriched) / max(len(enriched), 1)
    avg_learn = sum(o.learning_impact for o in enriched) / max(len(enriched), 1)

    return {
        "enriched_opportunities": enriched,
        "agent_logs": [decision],
        "progress_messages": [
            f"🧠 **Opportunity Intelligence Agent** — Done",
            f"   ✅ {len(enriched) - failed} opportunities enriched with AI insights",
            f"   📊 Avg Career Impact: {avg_career:.1f}/10 | Avg Learning Impact: {avg_learn:.1f}/10",
            f"   ⚠️  {failed} used fallback templates due to rate-limit triggers"
        ]
    }
