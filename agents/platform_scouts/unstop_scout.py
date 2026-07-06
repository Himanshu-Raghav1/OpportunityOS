"""
Unstop Platform Scout
Uses Firecrawl to extract direct opportunity registration links.
"""
import os
from typing import List, Dict
import datetime
from core.llm import rate_limited_invoke, parse_json_safely, get_llm

UNSTOP_EXTRACT_PROMPT = """Extract a list of hackathons and competitions from this scraped Unstop markdown.
For each opportunity, find the DIRECT registration/application URL (usually starts with https://unstop.com/hackathons/ or https://unstop.com/competitions/).

Today: {date}

Return ONLY a JSON array. Each item:
{{
  "title": "Opportunity Title",
  "organization": "Host Organization",
  "description": "Short description",
  "deadline": "YYYY-MM-DD or TBA",
  "eligibility": "Who can apply",
  "rewards": "Prizes",
  "required_skills": ["skill1"],
  "location": "Remote or City",
  "url": "https://unstop.com/exact-registration-link",
  "source": "unstop"
}}

Markdown Content:
{content}
"""

def fetch_unstop() -> List[Dict]:
    """Scrapes Unstop via Firecrawl to get direct registration links."""
    from firecrawl import FirecrawlApp
    
    api_key = os.getenv("FIRECRAWL_API_KEY")
    if not api_key:
        print("[Unstop Scout] Firecrawl API key missing.")
        return []
        
    fc_app = FirecrawlApp(api_key=api_key)
    llm = get_llm()
    results = []
    
    targets = [
        "https://unstop.com/hackathons",
        "https://unstop.com/competitions"
    ]
    
    for url in targets:
        try:
            res = fc_app.scrape_url(url, formats=["markdown"], timeout=20)
            content = ""
            if isinstance(res, dict):
                content = res.get("markdown", res.get("content", ""))
            elif hasattr(res, "markdown"):
                content = res.markdown or ""
            
            if not content:
                continue
                
            content = content[:6000] # Limit for LLM
            prompt = UNSTOP_EXTRACT_PROMPT.format(
                date=datetime.datetime.utcnow().strftime("%Y-%m-%d"),
                content=content
            )
            
            raw = rate_limited_invoke(llm, [("human", prompt)])
            if raw:
                data = parse_json_safely(raw)
                if isinstance(data, list):
                    for d in data:
                        # Ensure the URL is an actual direct link if possible
                        if "url" in d and d["url"].startswith("http"):
                            results.append(d)
        except Exception as e:
            print(f"[Unstop Scout] Error on {url}: {e}")
            
    return results
