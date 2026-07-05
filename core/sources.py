"""
Opportunity source definitions and metadata.
Defines all sources the Hunter Agent knows about.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import List


@dataclass
class OpportunitySource:
    name: str
    display_name: str
    url: str
    categories: List[str]
    fetch_method: str          # "api" | "rss" | "html" | "llm_synthesis"
    api_endpoint: str = ""
    rss_url: str = ""
    requires_auth: bool = False
    description: str = ""


# All known sources grouped by fetch strategy
SOURCES: List[OpportunitySource] = [

    # ── Live API / RSS Sources ──────────────────────────────────────────────

    OpportunitySource(
        name="mlh",
        display_name="Major League Hacking (MLH)",
        url="https://mlh.io",
        categories=["Hackathon"],
        fetch_method="rss",
        rss_url="https://mlh.io/seasons/2025/events.json",
        description="Official MLH hackathon events"
    ),
    OpportunitySource(
        name="outreachy",
        display_name="Outreachy",
        url="https://www.outreachy.org",
        categories=["Open Source", "Fellowship"],
        fetch_method="html",
        description="Paid open source internships for underrepresented groups"
    ),
    OpportunitySource(
        name="kaggle",
        display_name="Kaggle Competitions",
        url="https://www.kaggle.com/competitions",
        categories=["Competition"],
        fetch_method="api",
        api_endpoint="https://www.kaggle.com/api/v1/competitions/list",
        description="ML/AI competitions with prize money"
    ),
    OpportunitySource(
        name="github",
        display_name="GitHub Hackathons & Open Source",
        url="https://github.com",
        categories=["Hackathon", "Open Source"],
        fetch_method="api",
        api_endpoint="https://api.github.com/search/repositories",
        description="GitHub repos and events tagged with hackathon/gsoc"
    ),
    OpportunitySource(
        name="gsoc",
        display_name="Google Summer of Code Organizations",
        url="https://summerofcode.withgoogle.com/organizations",
        categories=["Open Source"],
        fetch_method="api",
        api_endpoint="https://summerofcode.withgoogle.com/api/program/2025/organizations/",
        description="GSoC 2024/2025 mentoring organizations"
    ),
    OpportunitySource(
        name="devpost",
        display_name="Devpost Hackathons",
        url="https://devpost.com",
        categories=["Hackathon"],
        fetch_method="rss",
        rss_url="https://devpost.com/hackathons.rss",
        description="Global hackathon platform with prize competitions"
    ),
    OpportunitySource(
        name="lfx_mentorship",
        display_name="Linux Foundation LFX Mentorship",
        url="https://mentorship.lfx.linuxfoundation.org",
        categories=["Open Source", "Fellowship"],
        fetch_method="api",
        api_endpoint="https://api.lfx.linuxfoundation.org/v2/mentorship/programs",
        description="Linux Foundation paid mentorship programs"
    ),
    OpportunitySource(
        name="hackernews",
        display_name="HackerNews Opportunities",
        url="https://news.ycombinator.com",
        categories=["Hackathon", "Competition"],
        fetch_method="api",
        api_endpoint="https://hn.algolia.com/api/v1/search",
        description="Tech opportunities and hackathon announcements on HackerNews"
    ),
    OpportunitySource(
        name="tavily_search",
        display_name="Tavily Live Web Search",
        url="https://tavily.com",
        categories=["Hackathon", "Internship", "Open Source", "Fellowship", "Competition"],
        fetch_method="api",
        api_endpoint="https://api.tavily.com/search",
        requires_auth=True,
        description="Real-time web search for opportunities"
    ),
    OpportunitySource(
        name="serpapi_search",
        display_name="SerpAPI Targeted Search",
        url="https://serpapi.com",
        categories=["Hackathon", "Internship", "Open Source", "Fellowship", "Competition"],
        fetch_method="api",
        api_endpoint="https://serpapi.com/search",
        requires_auth=True,
        description="Google search targeting specific platforms"
    ),

    # ── LLM Synthesis Sources (JS-gated or auth-required) ──────────────────

    OpportunitySource(
        name="devfolio",
        display_name="Devfolio",
        url="https://devfolio.co",
        categories=["Hackathon"],
        fetch_method="llm_synthesis",
        description="India's largest hackathon platform"
    ),
    OpportunitySource(
        name="unstop",
        display_name="Unstop",
        url="https://unstop.com",
        categories=["Hackathon", "Competition", "Internship"],
        fetch_method="llm_synthesis",
        description="Student opportunity platform in India"
    ),
    OpportunitySource(
        name="wellfound",
        display_name="Wellfound (AngelList)",
        url="https://wellfound.com",
        categories=["Internship"],
        fetch_method="llm_synthesis",
        description="Startup internships and jobs"
    ),
    OpportunitySource(
        name="gsoc_org",
        display_name="GSoC Organizations (Extended)",
        url="https://summerofcode.withgoogle.com/organizations",
        categories=["Open Source"],
        fetch_method="llm_synthesis",
        description="Extended list of GSoC mentoring organizations with project ideas"
    ),
    OpportunitySource(
        name="microsoft_imagine",
        display_name="Microsoft Imagine Cup",
        url="https://imaginecup.microsoft.com",
        categories=["Competition", "Student Program"],
        fetch_method="llm_synthesis",
        description="Microsoft's flagship student innovation competition"
    ),
    OpportunitySource(
        name="google_developer",
        display_name="Google Developer Student Clubs",
        url="https://developers.google.com/community/gdsc",
        categories=["Developer Program", "Student Program"],
        fetch_method="llm_synthesis",
        description="Google's student developer community programs"
    ),
    OpportunitySource(
        name="aws_programs",
        display_name="AWS Student Programs",
        url="https://aws.amazon.com/education",
        categories=["Developer Program", "Student Program"],
        fetch_method="llm_synthesis",
        description="AWS training, credits, and hackathon programs"
    ),
    OpportunitySource(
        name="research_programs",
        display_name="Research Programs",
        url="https://www.cs.cmu.edu/",
        categories=["Research"],
        fetch_method="llm_synthesis",
        description="University and industry research internship programs"
    ),
    OpportunitySource(
        name="fellowships",
        display_name="Tech Fellowships",
        url="https://fellowships.co",
        categories=["Fellowship"],
        fetch_method="llm_synthesis",
        description="Technology and social impact fellowship programs"
    ),
]


# Convenience maps
SOURCE_BY_NAME = {s.name: s for s in SOURCES}
LIVE_SOURCES = [s for s in SOURCES if s.fetch_method != "llm_synthesis"]
SYNTHESIS_SOURCES = [s for s in SOURCES if s.fetch_method == "llm_synthesis"]
CATEGORIES = [
    "Hackathon", "Ideathon", "Internship", "Open Source",
    "Fellowship", "Competition", "Research", "Student Program", "Developer Program"
]
