"""
Agent 8: Resume Matchmaker (Evaluator)
Evaluates opportunities against the user's resume/skills profile and calculates a personal Match Score.
"""
from typing import Dict, Any
from core.state import AgentState
from core.models import AgentDecision, Opportunity
from core.llm import get_llm, rate_limited_invoke, parse_json_safely
import time
import json

EVALUATOR_PROMPT = """You are an expert technical recruiter matching candidates to opportunities.

Candidate Profile/Resume:
{resume}

Evaluate this opportunity against the candidate profile:
Title: {title}
Organization: {organization}
Description: {description}
Eligibility: {eligibility}
Required Skills: {skills}

1. How well does the candidate's profile match the opportunity requirements and eligibility?
2. Give a match score from 0 to 100.
3. Provide a very short 1-2 sentence reason for the score, speaking directly to the candidate (e.g. "You have the required Python skills but may not meet the student eligibility.").

Respond ONLY with a JSON object:
{{
  "match_score": 85,
  "match_reason": "Your reason here."
}}
"""

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

    llm = get_llm(temperature=0.1) # precise
    messages.append(f"   🧑‍💻 Evaluating {len(opportunities)} opportunities against your profile...")
    
    evaluated_count = 0
    # Process only top 30 to save time and API quota, others get 0 score
    to_evaluate = opportunities[:30]
    
    for opp in to_evaluate:
        prompt = EVALUATOR_PROMPT.format(
            resume=profile_str,
            title=opp.title,
            organization=opp.organization,
            description=opp.description,
            eligibility=opp.eligibility,
            skills=", ".join(opp.required_skills)
        )
        
        raw = rate_limited_invoke(llm, [("human", prompt)])
        if raw:
            data = parse_json_safely(raw)
            if isinstance(data, dict):
                score = float(data.get("match_score", 0))
                opp.match_score = score
                opp.match_reason = data.get("match_reason", "")
                
                # Boost the overall score slightly if it's a high match (optional hybrid ranking)
                if score >= 80:
                    opp.score = min(100.0, opp.score + (score * 0.1))
                
                evaluated_count += 1
        
        # very small delay
        time.sleep(0.1)

    # Sort again: primary by match_score, secondary by absolute score
    opportunities.sort(key=lambda x: (x.match_score, x.score), reverse=True)

    decision = AgentDecision(
        scan_id=state["scan_id"],
        agent_name="Evaluator Agent",
        decision=f"Evaluated top {evaluated_count} opportunities against user profile.",
        reasoning="Generated personal match scores and re-ranked the list based on candidate fit."
    )
    
    messages.append(f"   ✅ Matchmaking complete. Re-ranked list by Personal Fit.")
    
    return {
        "ranked_opportunities": opportunities,
        "agent_logs": [decision],
        "progress_messages": messages
    }
