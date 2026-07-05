"""
Profile Extraper & Synthesizer
Fetches user data from GitHub, LinkedIn text, and Resume PDFs, then synthesizes them
using Gemini into a structured developer/student skill profile.
"""
from __future__ import annotations
import requests
import json
from pypdf import PdfReader
from io import BytesIO
from core.llm import get_llm, rate_limited_invoke, parse_json_safely

PROFILE_SYNTHESIS_PROMPT = """You are an expert developer profiler.
Analyze the following raw data points about a candidate (GitHub profile, LinkedIn bio, and Resume text).
Synthesize them into a single, clean JSON structure representing their profile.

GitHub Data:
{github_data}

LinkedIn Info:
{linkedin_text}

Resume Text:
{resume_text}

Return ONLY a JSON object:
{{
  "name": "Candidate Name or 'Anonymous'",
  "skills": ["list", "of", "programming", "languages", "frameworks", "tools", "libraries"],
  "experience_level": "Beginner / Intermediate / Advanced",
  "domains": ["Web Development", "Machine Learning", "Mobile Apps", "Blockchain", "DevOps", "etc."],
  "bio_summary": "2-3 sentence overview of their technical background, projects, and strengths.",
  "location": "Candidate location or Remote preferred"
}}
"""

def extract_pdf_text(pdf_bytes: bytes) -> str:
    """Extract text from PDF file bytes."""
    try:
        reader = PdfReader(BytesIO(pdf_bytes))
        text_parts = []
        for page in reader.pages:
            t = page.extract_text()
            if t:
                text_parts.append(t)
        return "\n".join(text_parts)
    except Exception as e:
        print(f"[Profile Extractor] PDF extraction error: {e}")
        return ""

def fetch_github_profile(username: str) -> dict:
    """Fetch GitHub profile data and repository details."""
    username = username.strip().split('/')[-1] # extract username from url if full link is passed
    if not username:
        return {}
        
    headers = {"User-Agent": "OpportunityOS-AI-Agent"}
    
    # 1. Fetch user profile
    user_url = f"https://api.github.com/users/{username}"
    user_data = {}
    try:
        r = requests.get(user_url, headers=headers, timeout=10)
        if r.status_code == 200:
            ud = r.json()
            user_data = {
                "login": ud.get("login"),
                "name": ud.get("name"),
                "bio": ud.get("bio"),
                "public_repos": ud.get("public_repos"),
                "followers": ud.get("followers")
            }
    except Exception as e:
        print(f"[Profile Extractor] GitHub profile fetch error: {e}")

    # 2. Fetch user repositories (up to 30 sorted by updated)
    repos_url = f"https://api.github.com/users/{username}/repos?sort=updated&per_page=30"
    repos_data = []
    try:
        r = requests.get(repos_url, headers=headers, timeout=10)
        if r.status_code == 200:
            for repo in r.json():
                repos_data.append({
                    "name": repo.get("name"),
                    "description": repo.get("description"),
                    "language": repo.get("language"),
                    "stars": repo.get("stargazers_count"),
                    "topics": repo.get("topics", [])
                })
    except Exception as e:
        print(f"[Profile Extractor] GitHub repos fetch error: {e}")

    return {
        "user": user_data,
        "repositories": repos_data
    }

def synthesize_profile(github_user: str = "", linkedin_text: str = "", resume_bytes: bytes = None) -> dict:
    """
    Synthesize all inputs into a single developer profile using Gemini.
    """
    github_data = {}
    if github_user:
        github_data = fetch_github_profile(github_user)
        
    resume_text = ""
    if resume_bytes:
        resume_text = extract_pdf_text(resume_bytes)

    # Use LLM to synthesize
    llm = get_llm(temperature=0.2)
    prompt = PROFILE_SYNTHESIS_PROMPT.format(
        github_data=json.dumps(github_data, indent=2) if github_data else "No GitHub data",
        linkedin_text=linkedin_text if linkedin_text.strip() else "No LinkedIn data",
        resume_text=resume_text if resume_text.strip() else "No Resume data"
    )

    raw = rate_limited_invoke(llm, [("human", prompt)])
    if raw:
        profile = parse_json_safely(raw)
        if isinstance(profile, dict):
            return profile

    # Fallback default empty profile
    return {
        "name": "Anonymous",
        "skills": [],
        "experience_level": "Intermediate",
        "domains": [],
        "bio_summary": "Profile evaluation skipped or failed to parse.",
        "location": "Remote"
    }
