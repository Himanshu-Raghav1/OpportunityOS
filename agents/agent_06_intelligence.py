"""
Agent 6: Opportunity Intelligence Agent
────────────────────────────────────────
Generates deep AI insights for each opportunity using Gemini:
  - What it is (clear summary)
  - Why it matters
  - Who should apply
  - Career impact score (1–10)
  - Learning impact score (1–10)
"""
from __future__ import annotations
import json
from typing import List
from core.state import AgentState
from core.models import Opportunity, AgentDecision
from core.llm import get_creative_llm, parse_json_safely, rate_limited_invoke


INTELLIGENCE_PROMPT = """You are an expert career counselor and opportunity analyst for students and developers.

Analyze this opportunity and provide rich, actionable insights.

Opportunity Details:
- Title: {title}
- Organization: {organization}
- Category: {category}
- Description: {description}
- Deadline: {deadline}
- Eligibility: {eligibility}
- Rewards: {rewards}
- Location: {location}
- Required Skills: {skills}

Return ONLY valid JSON with these exact fields:
{{
  "ai_insight": "2-3 sentence punchy summary of this opportunity. Start with what makes it special.",
  "why_it_matters": "Why this opportunity is significant — impact on career, skills, or community",
  "who_should_apply": "Specific profile of ideal applicant — year, skills, goals",
  "career_impact": 8,
  "learning_impact": 7
}}

Scoring guidelines (1-10):
- career_impact: Does it add prestige to a resume? Lead to jobs/networks? High = top company internship/GSoC. Low = small local competition.
- learning_impact: How much will the applicant learn? High = mentorship + new skills. Low = just submitting a project.

Be specific, enthusiastic, and genuinely helpful. Avoid generic advice.
"""


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
    enriched: List[Opportunity] = []
    failed = 0

    for opp in opps:
        prompt = INTELLIGENCE_PROMPT.format(
            title=opp.title,
            organization=opp.organization,
            category=opp.category,
            description=opp.description[:300],
            deadline=opp.deadline or "TBA",
            eligibility=opp.eligibility[:200],
            rewards=opp.rewards[:200],
            location=opp.location,
            skills=", ".join(opp.required_skills[:5]) if opp.required_skills else "General"
        )

        try:
            raw = rate_limited_invoke(llm, [("human", prompt)])
            data = parse_json_safely(raw)

            if isinstance(data, dict):
                opp.ai_insight = str(data.get("ai_insight", ""))[:500]
                opp.why_it_matters = str(data.get("why_it_matters", ""))[:400]
                opp.who_should_apply = str(data.get("who_should_apply", ""))[:300]
                opp.career_impact = min(10, max(1, int(data.get("career_impact", 5))))
                opp.learning_impact = min(10, max(1, int(data.get("learning_impact", 5))))
            else:
                opp.ai_insight = f"Excellent opportunity from {opp.organization} in the {opp.category} space."
                opp.career_impact = 6
                opp.learning_impact = 6

        except Exception as e:
            failed += 1
            opp.ai_insight = f"A {opp.category} opportunity from {opp.organization}. Check the link for full details."
            opp.career_impact = 5
            opp.learning_impact = 5

        enriched.append(opp)

    decision = AgentDecision(
        scan_id=scan_id,
        agent_name="Opportunity Intelligence Agent",
        decision=f"Generated AI insights for {len(enriched) - failed} of {len(enriched)} opportunities",
        reasoning=f"Used Gemini with high creativity (temp=0.7) for nuanced, specific insights. {failed} fell back to templates."
    )

    avg_career = sum(o.career_impact for o in enriched) / max(len(enriched), 1)
    avg_learn = sum(o.learning_impact for o in enriched) / max(len(enriched), 1)

    return {
        "enriched_opportunities": enriched,
        "agent_logs": [decision],
        "progress_messages": [
            f"🧠 **Opportunity Intelligence Agent** — Insights generated",
            f"   ✅ {len(enriched) - failed} opportunities enriched with AI insights",
            f"   📊 Avg Career Impact: {avg_career:.1f}/10 | Avg Learning Impact: {avg_learn:.1f}/10",
            f"   ⚠️  {failed} used fallback templates"
        ]
    }
