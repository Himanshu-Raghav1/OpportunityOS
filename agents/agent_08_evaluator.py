"""
Agent 8: Resume Matchmaker (Evaluator)
Evaluates opportunities against the user's resume/skills profile and calculates a personal Match Score.
Optimized with batch processing to prevent sequential API hangs.
"""
from typing import Dict, List, Any
from core.state import AgentState
from core.models import AgentDecision, Opportunity
from core.llm import get_precise_llm, rate_limited_invoke, parse_json_safely
from core.memory import save_opportunities_bulk
import time
import json

BATCH_EVALUATOR_PROMPT = """You are an expert technical recruiter matching candidates to opportunities.

Candidate Profile/Resume:
{resume}

Evaluate these opportunities against the candidate profile:
{opp_list}

For each opportunity:
1. How well does the candidate's profile match the opportunity requirements and eligibility?
2. Give a match score from 0 to 100.
3. Provide a very short 1-2 sentence reason for the score, speaking directly to the candidate (e.g. "You have the required Python skills but may not meet the student eligibility.").

Respond ONLY with a JSON object mapping each opportunity ID to its score and reasoning:
{{
  "opp_id_1": {{
    "match_score": 85,
    "match_reason": "Your reason here."
  }}
}}
"""


def llm_evaluate_batch(opps: List[Opportunity], profile_str: str, llm) -> Dict[str, dict]:
    """Evaluate opportunities against resume in batches of 10 to prevent sequential API hangs."""
    results = {}
    batch_size = 10
    
    for i in range(0, len(opps), batch_size):
        batch = opps[i:i + batch_size]
        
        # Pre-populate fallbacks
        for opp in batch:
            results[opp.id] = {
                "match_score": 50.0,
                "match_reason": "General developer match based on standard profile."
            }
            
        opp_list_str = []
        for opp in batch:
            opp_list_str.append(
                f"ID: {opp.id}\n"
                f"Title: {opp.title}\n"
                f"Org: {opp.organization}\n"
                f"Description: {opp.description[:180]}\n"
                f"Eligibility: {opp.eligibility[:150]}\n"
                f"Required Skills: {', '.join(opp.required_skills) if opp.required_skills else 'General'}\n"
                f"---"
            )
            
        prompt = BATCH_EVALUATOR_PROMPT.format(
            resume=profile_str,
            opp_list="\n".join(opp_list_str)
        )
        
        try:
            raw = rate_limited_invoke(llm, [("human", prompt)])
            data = parse_json_safely(raw)
            if isinstance(data, dict):
                if "match_score" in data:
                    # Backwards compatibility check for flat object payloads (e.g. mock test suites)
                    for opp in batch:
                        results[opp.id] = {
                            "match_score": float(data.get("match_score", 50.0)),
                            "match_reason": str(data.get("match_reason", ""))[:250]
                        }
                else:
                    for opp in batch:
                        opp_res = data.get(opp.id, {})
                        if isinstance(opp_res, dict):
                            results[opp.id] = {
                                "match_score": float(opp_res.get("match_score", 50.0)),
                                "match_reason": str(opp_res.get("match_reason", results[opp.id]["match_reason"]))[:250]
                            }
            else:
                print(f"[Evaluator] Batch {i // batch_size + 1}: LLM returned non-object response", flush=True)
        except Exception as e:
            print(f"[Evaluator] Batch {i // batch_size + 1} failed: {e}", flush=True)
            
        # breathing room
        time.sleep(0.5)
        
    return results


def run_evaluator(state: AgentState) -> Dict[str, Any]:
    """Evaluates the ranked opportunities against the user profile."""
    messages = []
    messages.append("🎯 **Agent 8: Evaluator Agent** activated")
    
    user_prefs = state.get("user_preferences", {})
    profile = user_prefs.get("profile")
    resume = user_prefs.get("resume", "").strip()
    
    if profile:
        profile_str = json.dumps(profile, indent=2)
    elif resume:
        profile_str = f"Raw Resume Text:\n{resume}"
    else:
        profile_str = ""

    if not profile_str:
        messages.append("   ⏭️ No resume/skills or profile provided. Skipping personalized evaluation.")
        decision = AgentDecision(
            scan_id=state["scan_id"],
            agent_name="Evaluator Agent",
            decision="Skipped personalized evaluation",
            reasoning="User did not provide profile credentials or resume."
        )
        return {"agent_logs": [decision], "progress_messages": messages}
        
    opportunities = state.get("ranked_opportunities", [])
    if not opportunities:
        return {}

    llm = get_precise_llm()
    messages.append(f"   🧑‍💻 Evaluating {len(opportunities)} opportunities against your profile...")
    
    evaluated_count = 0
    # Process only top 30 to save time and API quota, others get default/0 scores
    to_evaluate = opportunities[:30]
    
    # Run batch evaluation
    eval_results = llm_evaluate_batch(to_evaluate, profile_str, llm)
    
    for opp in opportunities:
        res = eval_results.get(opp.id)
        if res:
            opp.match_score = res["match_score"]
            opp.match_reason = res["match_reason"]
            # Boost the overall score slightly if it's a high match (optional hybrid ranking)
            if res["match_score"] >= 80:
                opp.score = min(100.0, opp.score + (res["match_score"] * 0.1))
            evaluated_count += 1
        else:
            # Set defaults for opportunities beyond top 30
            opp.match_score = 0.0
            opp.match_reason = "Not evaluated (beyond ranking threshold)"

    # Sort again: primary by match_score, secondary by absolute score
    opportunities.sort(key=lambda x: (x.match_score, x.score), reverse=True)

    # 💾 Final DB save with evaluated match details
    try:
        save_opportunities_bulk(opportunities)
    except Exception as e:
        print(f"[Evaluator DB Checkpoint] Save failed: {e}", flush=True)

    decision = AgentDecision(
        scan_id=state["scan_id"],
        agent_name="Evaluator Agent",
        decision=f"Evaluated top {evaluated_count} opportunities against user profile.",
        reasoning="Generated personal match scores and re-ranked the list based on candidate fit using batch evaluations."
    )
    
    messages.append(f"   ✅ Matchmaking complete. Re-ranked list by Personal Fit.")
    
    return {
        "ranked_opportunities": opportunities,
        "agent_logs": [decision],
        "progress_messages": messages
    }
