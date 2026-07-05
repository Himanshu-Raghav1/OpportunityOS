"""
Devfolio Platform Scout
Uses the Devfolio Search API to fetch live hackathons with direct registration links.
"""
from typing import List, Dict
import requests
import datetime

def fetch_devfolio() -> List[Dict]:
    """Scrapes active and upcoming hackathons directly from Devfolio."""
    results = []
    # Devfolio uses an elasticsearch API backend
    url = "https://api.devfolio.co/api/search/hackathons"
    payload = {
        "filter": {
            "status": ["open", "upcoming"]
        },
        "page": 1,
        "limit": 15
    }
    
    try:
        resp = requests.post(url, json=payload, timeout=15)
        if resp.status_code == 200:
            data = resp.json()
            hits = data.get("hits", {}).get("hits", [])
            for hit in hits:
                source = hit.get("_source", {})
                title = source.get("name", "Devfolio Hackathon")
                slug = source.get("slug", "")
                
                # Direct registration/application link for Devfolio
                apply_url = f"https://{slug}.devfolio.co/" if slug else "https://devfolio.co/hackathons"
                
                desc = source.get("description", "")
                
                # Parse deadlines
                starts_at = source.get("starts_at")
                ends_at = source.get("ends_at")
                deadline = ends_at[:10] if ends_at else (starts_at[:10] if starts_at else "TBA")
                
                results.append({
                    "title": title,
                    "organization": source.get("organizer_name", "Devfolio Host"),
                    "description": desc[:300] + ("..." if len(desc)>300 else ""),
                    "deadline": deadline,
                    "eligibility": "Student/Developer (See application page)",
                    "rewards": "Cash prizes, SWAGs, Devfolio API prizes",
                    "required_skills": ["hackathon", "software development"],
                    "location": source.get("location", "Remote/In-person"),
                    "url": apply_url,
                    "source": "devfolio"
                })
    except Exception as e:
        print(f"[Devfolio Scout] Error: {e}")
        
    return results
