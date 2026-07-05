"""
Core data models for OpportunityOS AI.
All opportunity data is validated through these Pydantic schemas.
"""
from __future__ import annotations
from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, Field
import uuid


class Opportunity(BaseModel):
    """Full opportunity record — produced and enriched through the agent pipeline."""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    title: str
    organization: str
    category: str = "Unknown"          # Set by Classification Agent
    description: str = ""
    deadline: Optional[str] = None     # ISO date string or human-readable
    deadline_date: Optional[datetime] = None
    eligibility: str = ""
    rewards: str = ""                  # Prize, stipend, certificate
    required_skills: List[str] = Field(default_factory=list)
    location: str = "Remote"
    country: str = "Global"
    source: str = ""                   # Platform name
    url: str = ""
    is_remote: bool = True

    # Set by Ranking Agent
    score: float = 0.0                 # 0–100
    reputation_score: float = 0.0
    learning_score: float = 0.0
    career_score: float = 0.0
    accessibility_score: float = 0.0

    # Set by Intelligence Agent
    ai_insight: str = ""
    why_it_matters: str = ""
    who_should_apply: str = ""
    career_impact: int = 5             # 1–10
    learning_impact: int = 5          # 1–10

    # Set by agents
    ranking_reasoning: str = ""
    classification_reasoning: str = ""

    # Set by Evaluator Agent
    match_score: float = 0.0
    match_reason: str = ""

    # Metadata
    created_at: datetime = Field(default_factory=datetime.utcnow)
    scan_id: str = ""
    is_duplicate: bool = False
    duplicate_of: Optional[str] = None

    class Config:
        json_encoders = {datetime: lambda v: v.isoformat()}


class SearchPlan(BaseModel):
    """Output of the Search Planning Agent."""
    plan_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    sources: List[str]                 # List of source names to search
    queries: List[str]                 # Search queries to use
    priorities: List[str]             # Priority categories
    rationale: str                     # Why this plan was chosen
    estimated_count: int = 50
    created_at: datetime = Field(default_factory=datetime.utcnow)


class AgentDecision(BaseModel):
    """Records a decision made by any agent — stored for the Reasoning Panel."""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    scan_id: str
    agent_name: str
    decision: str
    reasoning: str
    opportunity_id: Optional[str] = None
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class ScanMetadata(BaseModel):
    """Metadata about a single scan run."""
    scan_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    started_at: datetime = Field(default_factory=datetime.utcnow)
    completed_at: Optional[datetime] = None
    total_found: int = 0
    total_unique: int = 0
    total_duplicates_removed: int = 0
    sources_searched: List[str] = Field(default_factory=list)
    status: str = "running"            # running | completed | failed
    error: Optional[str] = None
