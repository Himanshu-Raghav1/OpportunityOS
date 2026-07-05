"""
Deep Link Resolver
Takes surface-level URLs (from search snippets or general scrapes) and uses Firecrawl
to visit the page, parse the DOM, and extract the direct "Apply Now" or "Register" link.
"""
import os
import re
from typing import List, Dict
import time

# Regex patterns that strongly suggest an application button or link
APPLY_PATTERNS = re.compile(r'(apply|register|sign up|join|submit|participate)', re.IGNORECASE)

def resolve_deep_links(opportunities: List[Dict], fc_app=None, llm=None) -> List[Dict]:
    """
    Given a list of opportunity dicts, attempts to resolve their surface URLs
    into direct application URLs using Firecrawl.
    
    If fc_app is None, tries to instantiate it.
    """
    if not fc_app:
        fc_key = os.getenv("FIRECRAWL_API_KEY", "").strip()
        if not fc_key:
            print("[DeepLinkResolver] No Firecrawl API key. Skipping resolution.")
            return opportunities
        try:
            from firecrawl import FirecrawlApp
            fc_app = FirecrawlApp(api_key=fc_key)
        except ImportError:
            print("[DeepLinkResolver] firecrawl-py not installed.")
            return opportunities

    resolved = []
    print(f"[DeepLinkResolver] Resolving direct links for {len(opportunities)} opportunities...")
    
    for opp in opportunities:
        url = opp.get("url", "")
        # Skip if already looks like a direct link or if not a standard URL
        if not url or url.startswith("/") or "apply" in url.lower() or "register" in url.lower():
            resolved.append(opp)
            continue
            
        try:
            # We use Firecrawl to scrape the page and ask for structured data (the apply link)
            # Or we can just get the HTML/markdown and use the LLM to find the application link
            result = fc_app.scrape_url(url, formats=["markdown", "links"], timeout=15000)
            links = []
            if isinstance(result, dict):
                links = result.get("links", [])
            elif hasattr(result, "links"):
                links = result.links or []
            
            # Find a link that contains apply/register/etc in its text or URL
            best_link = url
            if links:
                for link in links:
                    if APPLY_PATTERNS.search(link):
                        # Ensure it's a valid absolute URL
                        if link.startswith("http"):
                            best_link = link
                            break
            
            # Update the opportunity URL
            opp["url"] = best_link
            
        except Exception as e:
            print(f"[DeepLinkResolver] Failed to resolve {url}: {e}")
        
        resolved.append(opp)
        time.sleep(0.5) # Rate limiting
        
    return resolved
