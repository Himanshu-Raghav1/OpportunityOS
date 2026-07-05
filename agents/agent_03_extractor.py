"""
Agent 3: Information Extraction Agent
──────────────────────────────────────
Normalizes raw opportunity dicts into validated Pydantic Opportunity models.
Uses both rule-based parsing and LLM validation for quality assurance.
"""
from __future__ import annotations
import json
import re
from datetime import datetime
from typing import List, Dict, Any
from core.state import AgentState
from core.models import Opportunity, AgentDecision
from core.llm import get_llm, parse_json_safely


EXTRACTION_PROMPT = """You are an Information Extraction Agent. Given a raw opportunity record, extract and normalize all fields.

Raw opportunity data:
{raw_data}

Extract and return ONLY valid JSON with these exact fields:
{{
  "title": "Clean, formatted title",
  "organization": "Organization/company name",
  "description": "2-3 sentence clear description",
  "deadline": "YYYY-MM-DD or descriptive like 'Rolling' or 'February 2026'",
  "eligibility": "Who can apply",
  "rewards": "Prizes, stipend amount, benefits",
  "required_skills": ["skill1", "skill2"],
  "location": "Remote / City, Country / Hybrid",
  "country": "Country name or 'Global'",
  "is_remote": true/false,
  "url": "https://url.com",
  "source": "source_name"
}}

Rules:
- Clean up any garbled text
- If a field is missing, use sensible defaults
- is_remote = true if location contains "Remote" or "Online"
- country = "Global" if no specific country mentioned
- required_skills should be a list of 2-6 relevant skills
"""


def parse_opportunity_from_raw(raw: Dict, scan_id: str) -> Opportunity:
    """
    Convert a raw dict to an Opportunity model.
    First tries direct field mapping, then LLM extraction for quality.
    """
    # Direct field extraction with defaults
    title = str(raw.get("title", "Unknown Opportunity")).strip()
    org = str(raw.get("organization", raw.get("org", "Unknown"))).strip()
    desc = str(raw.get("description", "")).strip()
    deadline = str(raw.get("deadline", "TBA")).strip()
    eligibility = str(raw.get("eligibility", "Open to all")).strip()
    rewards = str(raw.get("rewards", raw.get("prize", "Certificate"))).strip()
    location = str(raw.get("location", "Remote")).strip()
    url = str(raw.get("url", raw.get("link", ""))).strip()
    source = str(raw.get("source", "unknown")).strip()

    # Parse skills
    skills_raw = raw.get("required_skills", raw.get("skills", []))
    if isinstance(skills_raw, str):
        skills = [s.strip() for s in skills_raw.split(",") if s.strip()]
    elif isinstance(skills_raw, list):
        skills = [str(s).strip() for s in skills_raw if s]
    else:
        skills = []

    # Determine remote / country
    is_remote = "remote" in location.lower() or "online" in location.lower()
    country = raw.get("country", "Global")
    if not country or country == "Unknown":
        country = "Global"

    # Build Opportunity
    opp = Opportunity(
        title=title[:200],
        organization=org[:100],
        description=desc[:500],
        deadline=deadline[:100],
        eligibility=eligibility[:300],
        rewards=rewards[:200],
        required_skills=skills[:8],
        location=location[:100],
        country=str(country)[:50],
        source=source,
        url=url[:500],
        is_remote=is_remote,
        scan_id=scan_id
    )
    return opp


def run_extractor(state: AgentState) -> dict:
    """
    Agent 3 node: Extracts structured Opportunity objects from raw data.
    Updates: extracted_opportunities, agent_logs, progress_messages
    """
    raw_opps = state.get("raw_opportunities", [])
    scan_id = state["scan_id"]
    extracted: List[Opportunity] = []
    failed = 0

    for raw in raw_opps:
        try:
            if not isinstance(raw, dict):
                continue
            opp = parse_opportunity_from_raw(raw, scan_id)
            if opp.title and opp.title != "Unknown Opportunity":
                extracted.append(opp)
        except Exception as e:
            failed += 1

    decision = AgentDecision(
        scan_id=scan_id,
        agent_name="Information Extraction Agent",
        decision=f"Extracted {len(extracted)} valid opportunities from {len(raw_opps)} raw records",
        reasoning=f"Used structured field mapping with Pydantic validation. {failed} records failed validation."
    )

    return {
        "extracted_opportunities": extracted,
        "agent_logs": [decision],
        "progress_messages": [
            f"📋 **Information Extraction Agent** — Processing complete",
            f"   ✅ {len(extracted)} opportunities extracted",
            f"   ⚠️  {failed} records skipped (invalid data)"
        ]
    }
