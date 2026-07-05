"""
Agent 2: Opportunity Hunter Agent — TURBO EDITION
══════════════════════════════════════════════════
Three-layer intelligence pipeline:

LAYER 1 – LIVE WEB CRAWL (Firecrawl)
  • Scrapes actual opportunity listing pages: Devfolio, Unstop, Devpost, MLH,
    Kaggle, GSoC, Outreachy, LFX, Wellfound, Hackernews
  • Returns clean markdown content for Gemini to extract from

LAYER 2 – LIVE WEB SEARCH (Tavily + SerpAPI)
  • Tavily: 12 semantic web-search queries (advanced mode, 8 results each)
  • SerpAPI: 14 site-targeted google searches
  • Parallel batches → 100-180 snippets total

LAYER 3 – LIVE APIS + LLM SYNTHESIS
  • MLH JSON, GitHub API, GSoC Org API, Devpost RSS, Kaggle API,
    HackerNews Algolia, LFX Mentorship API
  • Gemini LLM synthesis for JS-gated platforms

ALL LAYERS → Gemini 2.5 Flash extracts structured opportunities
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""
from __future__ import annotations
import json
import os
import re
import time
import xml.etree.ElementTree as ET
from datetime import datetime
from typing import List, Dict, Any, Optional
import requests
from concurrent.futures import ThreadPoolExecutor
from core.state import AgentState
from core.models import AgentDecision
from core.llm import get_llm, parse_json_safely, rate_limited_invoke
from core.sources import SOURCES, SOURCE_BY_NAME
from agents.platform_scouts import fetch_devfolio, fetch_unstop
from agents.platform_scouts.deep_link_resolver import resolve_deep_links

# ══════════════════════════════════════════════════════════════════════════════
# UTILITIES
# ══════════════════════════════════════════════════════════════════════════════

def _get(url: str, params: dict = None, headers: dict = None, timeout: int = 15) -> Optional[requests.Response]:
    try:
        resp = requests.get(url, params=params, headers=headers, timeout=timeout)
        if resp.status_code == 200:
            return resp
    except Exception as e:
        print(f"[GET] {url} -> {e}")
    return None


def _post(url: str, json_body: dict = None, timeout: int = 15) -> Optional[requests.Response]:
    try:
        resp = requests.post(url, json=json_body, timeout=timeout)
        if resp.status_code == 200:
            return resp
    except Exception as e:
        print(f"[POST] {url} -> {e}")
    return None


# ══════════════════════════════════════════════════════════════════════════════
# LAYER 1 — FIRECRAWL (web crawl of real pages)
# ══════════════════════════════════════════════════════════════════════════════

# URLs Firecrawl will scrape — these are public listing pages
FIRECRAWL_TARGETS = [
    ("https://devfolio.co/hackathons",               "devfolio"),
    ("https://unstop.com/hackathons",                "unstop"),
    ("https://devpost.com/hackathons",               "devpost"),
    ("https://mlh.io/seasons/2025/events",           "mlh"),
    ("https://www.kaggle.com/competitions",          "kaggle"),
    ("https://summerofcode.withgoogle.com",          "gsoc"),
    ("https://www.outreachy.org",                    "outreachy"),
    ("https://mentorship.lfx.linuxfoundation.org",   "lfx_mentorship"),
    ("https://wellfound.com/jobs?jobType=internship", "wellfound"),
    ("https://unstop.com/fellowships",               "fellowships"),
    ("https://unstop.com/internships",               "internships_unstop"),
    ("https://hackerearth.com/challenges/hackathon/","hackerearth"),
]

FIRECRAWL_EXTRACT_PROMPT = """You are an expert opportunity researcher analyzing a webpage.

Extract ALL opportunities visible on this page. Each opportunity is something a student or developer can apply to.

Page source: {source}
Page URL: {url}

Page content:
{content}

Return ONLY a JSON array. Each item:
{{
  "title": "Exact opportunity name",
  "organization": "Host/company name",
  "description": "2-3 sentence description",
  "deadline": "YYYY-MM-DD or 'Rolling' or 'TBA'",
  "eligibility": "Who can apply",
  "rewards": "Prize/stipend/benefit",
  "required_skills": ["skill1", "skill2"],
  "location": "Remote / City, Country / Hybrid",
  "url": "Direct URL to apply",
  "source": "{source}"
}}

Today: {date}
Rules:
- Only real opportunities (hackathons, internships, fellowships, competitions, open source programs)
- Return [] if page has no opportunity listings (e.g., error page, login wall)
- Extract ALL visible items, up to 25
"""


def fetch_firecrawl_page(url: str, source: str, fc_app) -> List[Dict]:
    """Crawl a single URL with Firecrawl and extract opportunities using Gemini."""
    try:
        result = fc_app.scrape_url(url, formats=["markdown"], timeout=20000)
        content = ""
        if isinstance(result, dict):
            content = result.get("markdown", result.get("content", ""))
        elif hasattr(result, "markdown"):
            content = result.markdown or ""
        elif hasattr(result, "content"):
            content = result.content or ""

        if not content or len(content.strip()) < 100:
            return None

        # Truncate to 6000 chars (Gemini context window friendly)
        content = content[:6000]
        return content, source, url
    except Exception as e:
        print(f"[Firecrawl] {url} -> {e}")
        return None


def extract_from_firecrawl_content(content: str, source: str, url: str, llm) -> List[Dict]:
    """Use Gemini to extract structured opportunities from Firecrawl markdown."""
    prompt = FIRECRAWL_EXTRACT_PROMPT.format(
        source=source,
        url=url,
        content=content,
        date=datetime.utcnow().strftime("%Y-%m-%d"),
    )
    raw = rate_limited_invoke(llm, [("human", prompt)])
    if raw:
        data = parse_json_safely(raw)
        if isinstance(data, list):
            for item in data:
                if "source" not in item or not item["source"]:
                    item["source"] = source
            return [d for d in data if d.get("title")]
    return []


def run_firecrawl_layer(llm) -> tuple[List[Dict], List[str], List[str]]:
    """Run Firecrawl on all target URLs, extract opportunities via Gemini."""
    fc_key = os.getenv("FIRECRAWL_API_KEY", "").strip()
    if not fc_key:
        return [], [], ["   ℹ️  Firecrawl: No API key set (add FIRECRAWL_API_KEY to .env)"]

    try:
        from firecrawl import FirecrawlApp
        fc_app = FirecrawlApp(api_key=fc_key)
    except ImportError:
        return [], [], ["   ⚠️  Firecrawl: firecrawl-py not installed (pip install firecrawl-py)"]

    all_opps: List[Dict] = []
    sources_used: List[str] = []
    messages = [f"   🔥 Firecrawl: Crawling {len(FIRECRAWL_TARGETS)} opportunity pages..."]

    for url, source in FIRECRAWL_TARGETS:
        result = fetch_firecrawl_page(url, source, fc_app)
        if result is None:
            messages.append(f"   ⚠️  Firecrawl/{source}: crawl failed or login wall")
            continue
        content, src, page_url = result
        opps = extract_from_firecrawl_content(content, src, page_url, llm)
        if opps:
            all_opps.extend(opps)
            sources_used.append(source)
            messages.append(f"   ✅ Firecrawl/{source}: {len(opps)} opportunities extracted")
        else:
            messages.append(f"   ⚠️  Firecrawl/{source}: no opportunities found (login wall?)")
        time.sleep(0.5)

    messages.append(f"   📦 Firecrawl total: {len(all_opps)} opportunities from {len(sources_used)} pages")
    return all_opps, sources_used, messages


# ══════════════════════════════════════════════════════════════════════════════
# LAYER 2 — TAVILY + SERPAPI (web search → Gemini extraction)
# ══════════════════════════════════════════════════════════════════════════════

TAVILY_QUERIES = [
    "hackathon 2025 2026 open registration students developers",
    "open source internship stipend program 2025 apply",
    "technology fellowship program 2025 students stipend",
    "Google Summer of Code 2025 accepted organizations",
    "MLH hackathon season 2025 upcoming events schedule",
    "Kaggle machine learning competition 2025 prize money",
    "research internship undergraduate summer 2025 application",
    "developer cloud program student credits 2025 AWS Azure",
    "Outreachy internship 2025 application deadline",
    "LFX mentorship Linux Foundation 2025 open projects",
    "Microsoft Imagine Cup 2025 competition registration",
    "GitHub externship fellowship paid program 2025",
]

SERPAPI_QUERIES = [
    "site:devfolio.co hackathon 2025 open registration",
    "site:unstop.com competition OR hackathon 2025",
    "site:devpost.com hackathon open submissions",
    "site:mlh.io hackathon events 2025",
    "site:kaggle.com/competitions active prize",
    "Google STEP internship 2025 apply students",
    "Microsoft Imagine Cup 2025 registration open",
    "Outreachy internship 2025 deadline apply",
    "site:wellfound.com startup internship 2025",
    "GSoC 2025 accepted organizations project ideas",
    "student fellowship tech stipend 2025 apply",
    "HackerEarth hackathon 2025 open registration prize",
    "site:hackerearth.com hackathons active 2025",
    "open source program stipend 2025 beginner friendly",
]

SNIPPET_EXTRACTION_PROMPT = """You are an expert opportunity researcher. Extract ALL real, current opportunities from these web search snippets.

Search results:
{snippets}

Today's date: {date}

Return ONLY a JSON array. Each item must have:
[
  {{
    "title": "Exact opportunity name",
    "organization": "Hosting organization/company",
    "description": "2-3 sentence description",
    "deadline": "YYYY-MM-DD or 'Rolling' or 'TBA'",
    "eligibility": "Who can apply",
    "rewards": "Prize, stipend, or benefit",
    "required_skills": ["skill1", "skill2"],
    "location": "Remote / City, Country / Hybrid",
    "url": "https://actual-url.com",
    "source": "platform name"
  }}
]

Critical rules:
- ONLY extract real opportunities (hackathons, internships, fellowships, competitions, open-source programs)
- Do NOT include news articles, blog posts, or general info pages
- Deadlines must be 2025 or 2026
- If URL is a search result page, use the destination site URL
- Return [] if no real opportunities found
- Extract as many as possible, up to 30 per batch
"""


def fetch_tavily(plan_queries: List[str]) -> List[Dict]:
    """Tavily advanced search — returns raw snippets concurrently."""
    api_key = os.getenv("TAVILY_API_KEY", "").strip()
    if not api_key or "your_" in api_key.lower():
        return []

    queries = plan_queries[:4] + TAVILY_QUERIES
    queries = list(dict.fromkeys(q for q in queries if q.strip()))[:14]

    snippets: List[Dict] = []
    
    def _worker(query: str) -> List[Dict]:
        results = []
        resp = _post("https://api.tavily.com/search", {
            "api_key": api_key,
            "query": query,
            "search_depth": "advanced",
            "include_answer": True,
            "include_raw_content": False,
            "max_results": 8,
        })
        if resp:
            try:
                for item in resp.json().get("results", []):
                    results.append({
                        "title": item.get("title", ""),
                        "content": item.get("content", "")[:250],
                        "url": item.get("url", ""),
                        "_src": "tavily",
                    })
            except Exception:
                pass
        return results

    # Execute queries concurrently (max 5 threads)
    with ThreadPoolExecutor(max_workers=5) as executor:
        futures = [executor.submit(_worker, q) for q in queries]
        for fut in futures:
            try:
                snippets.extend(fut.result(timeout=45))
            except TimeoutError:
                print("[Tavily] Query worker timed out after 45s", flush=True)
            except Exception as e:
                print(f"[Tavily] Query worker error: {e}", flush=True)

    return snippets


def fetch_serpapi(plan_queries: List[str]) -> List[Dict]:
    """SerpAPI targeted Google search — returns raw snippets concurrently."""
    api_key = os.getenv("SERPAPI_KEY", "").strip()
    if not api_key or "your_" in api_key.lower():
        return []

    queries = SERPAPI_QUERIES + plan_queries[:4]
    queries = list(dict.fromkeys(q for q in queries if q.strip()))[:16]

    snippets: List[Dict] = []

    def _worker(query: str) -> List[Dict]:
        results = []
        resp = _get("https://serpapi.com/search", params={
            "api_key": api_key,
            "q": query,
            "engine": "google",
            "num": 15,
            "gl": "us",
            "hl": "en",
        })
        if resp:
            try:
                for item in resp.json().get("organic_results", []):
                    results.append({
                        "title": item.get("title", ""),
                        "content": item.get("snippet", "")[:250],
                        "url": item.get("link", ""),
                        "_src": "serpapi",
                    })
            except Exception:
                pass
        return results

    # Execute queries concurrently (max 5 threads)
    with ThreadPoolExecutor(max_workers=5) as executor:
        futures = [executor.submit(_worker, q) for q in queries]
        for fut in futures:
            try:
                snippets.extend(fut.result(timeout=45))
            except TimeoutError:
                print("[SerpAPI] Query worker timed out after 45s", flush=True)
            except Exception as e:
                print(f"[SerpAPI] Query worker error: {e}", flush=True)

    return snippets


def extract_from_snippets(snippets: List[Dict], llm) -> List[Dict]:
    """Batch-extract structured opportunities from search snippets via Gemini.
    Uses small batches (5) to prevent rate limits and socket hangs on slow networks.
    """
    if not snippets:
        return []
    all_results: List[Dict] = []
    batch_size = 5  # small batch = fast uploads & no socket hangs
    for i in range(0, len(snippets), batch_size):
        batch = snippets[i:i + batch_size]
        formatted = "\n\n".join(
            f"[{j+1}] Title: {s.get('title','')}\nURL: {s.get('url','')}\nSnippet: {s.get('content','')}"
            for j, s in enumerate(batch)
        )
        prompt = SNIPPET_EXTRACTION_PROMPT.format(
            snippets=formatted,
            date=datetime.utcnow().strftime("%Y-%m-%d"),
        )
        raw = rate_limited_invoke(llm, [("human", prompt)])
        if raw:
            data = parse_json_safely(raw)
            if isinstance(data, list):
                all_results.extend(data)
            elif data:
                print(f"[Hunter] Snippet batch {i // batch_size + 1}: JSON parse returned non-list", flush=True)
        else:
            print(f"[Hunter] Snippet batch {i // batch_size + 1}: empty LLM response", flush=True)
        time.sleep(1.0)  # extra breathing room between batches
    return [r for r in all_results if r.get("title")]


# ══════════════════════════════════════════════════════════════════════════════
# LAYER 3 — LIVE APIS + LLM SYNTHESIS
# ══════════════════════════════════════════════════════════════════════════════

def fetch_mlh() -> List[Dict]:
    results = []
    for season in ["2025", "2026"]:
        resp = _get(f"https://mlh.io/seasons/{season}/events.json")
        if resp:
            try:
                for ev in resp.json()[:100]:
                    results.append({
                        "title": ev.get("name", "MLH Hackathon"),
                        "organization": "Major League Hacking",
                        "description": f"Official MLH hackathon: {ev.get('name', '')}. Build projects, win prizes, and network with developers worldwide.",
                        "deadline": ev.get("start_date", "TBA"),
                        "eligibility": "Students and recent graduates worldwide",
                        "rewards": "Prizes, MLH swag, GitHub credits, digital tools",
                        "required_skills": ["programming", "problem-solving", "teamwork"],
                        "location": ev.get("location", "Remote"),
                        "url": ev.get("url", "https://mlh.io"),
                        "source": "mlh",
                    })
            except Exception:
                pass
    return results


def fetch_github() -> List[Dict]:
    results = []
    headers = {"Accept": "application/vnd.github.v3+json", "User-Agent": "OpportunityOS/1.0"}
    for query, per_page in [
        ("topic:hackathon topic:2025 sort:updated", 80),
        ("topic:hackathon topic:2026 sort:updated", 50),
        ("topic:gsoc topic:open-source sort:updated", 50),
        ("mlh-fellowship OR github-externship sort:updated", 30),
        ("topic:fellowship topic:2025 sort:updated", 40),
    ]:
        resp = _get("https://api.github.com/search/repositories",
                    params={"q": query, "per_page": per_page}, headers=headers)
        if resp:
            try:
                for repo in resp.json().get("items", []):
                    results.append({
                        "title": repo.get("name", "").replace("-", " ").title(),
                        "organization": repo.get("owner", {}).get("login", "GitHub"),
                        "description": repo.get("description") or "Open source hackathon/program on GitHub.",
                        "deadline": "Rolling",
                        "eligibility": "Open source contributors, developers",
                        "rewards": "Open source experience, community recognition",
                        "required_skills": (repo.get("topics", []) or ["programming"])[:5],
                        "location": "Remote",
                        "url": repo.get("html_url", "https://github.com"),
                        "source": "github",
                    })
            except Exception:
                pass
        time.sleep(0.25)
    return results


def fetch_gsoc_orgs() -> List[Dict]:
    results = []
    for year in [2024, 2025]:
        resp = _get(f"https://summerofcode.withgoogle.com/api/program/{year}/organizations/")
        if resp:
            try:
                raw = resp.json()
                orgs = raw if isinstance(raw, list) else raw.get("results", raw.get("organizations", []))
                for org in orgs[:150]:
                    name = org.get("name") or org.get("org_name", "")
                    desc = org.get("description") or org.get("tagline", "")
                    techs = org.get("technologies") or org.get("tech_tags", [])
                    if isinstance(techs, str):
                        techs = [t.strip() for t in techs.split(",")]
                    url = org.get("website") or org.get("url") or "https://summerofcode.withgoogle.com"
                    results.append({
                        "title": f"GSoC {year} — {name}",
                        "organization": name or "GSoC Organization",
                        "description": f"{(desc or '')[:200]} Google Summer of Code {year} mentoring organization.",
                        "deadline": f"April {year}",
                        "eligibility": "Students 18+, open source beginners welcome",
                        "rewards": "$1,500–$6,600 stipend from Google",
                        "required_skills": (techs or ["open source", "programming"])[:5],
                        "location": "Remote",
                        "url": url,
                        "source": "gsoc",
                    })
            except Exception as e:
                print(f"[GSoC {year}] {e}")
        time.sleep(0.3)
    return results


def fetch_outreachy() -> List[Dict]:
    base = {
        "title": "Outreachy Internship Program",
        "organization": "Outreachy",
        "description": "Paid, remote 3-month internships in open source for people underrepresented in tech. Outreachy provides a $7,000 stipend and direct mentorship from open source contributors.",
        "deadline": "Rolling — visit website for current round dates",
        "eligibility": "Underrepresented groups in tech; all skill levels welcome",
        "rewards": "$7,000 stipend over 3 months",
        "required_skills": ["open source", "programming", "documentation"],
        "location": "Remote",
        "url": "https://www.outreachy.org",
        "source": "outreachy",
    }
    try:
        from bs4 import BeautifulSoup
        resp = _get("https://www.outreachy.org/apply/", timeout=10)
        if resp:
            soup = BeautifulSoup(resp.text, "html.parser")
            date_el = soup.find(class_=re.compile(r"date|deadline", re.I))
            if date_el:
                base["deadline"] = date_el.get_text(strip=True)[:80]
    except Exception:
        pass
    return [base]


def fetch_devpost_rss() -> List[Dict]:
    results = []
    for feed_url in ["https://devpost.com/hackathons.rss"]:
        resp = _get(feed_url, timeout=12)
        if resp:
            try:
                root = ET.fromstring(resp.content)
                channel = root.find("channel")
                if channel is not None:
                    for item in channel.findall("item")[:25]:
                        title = getattr(item.find("title"), "text", "") or ""
                        url = getattr(item.find("link"), "text", "") or ""
                        desc_raw = getattr(item.find("description"), "text", "") or ""
                        desc = re.sub(r"<[^>]+>", " ", desc_raw).strip()[:300]
                        pub = getattr(item.find("pubDate"), "text", "TBA") or "TBA"
                        if title:
                            results.append({
                                "title": title.strip(),
                                "organization": "Devpost",
                                "description": desc or f"Devpost hackathon: {title}",
                                "deadline": pub[:50],
                                "eligibility": "Open to developers worldwide",
                                "rewards": "See Devpost listing",
                                "required_skills": ["programming", "web development"],
                                "location": "Remote",
                                "url": url.strip() or "https://devpost.com",
                                "source": "devpost",
                            })
            except Exception as e:
                print(f"[Devpost RSS] {e}")
    return results


def fetch_kaggle() -> List[Dict]:
    results = []
    resp = _get(
        "https://www.kaggle.com/api/v1/competitions/list",
        params={"sortBy": "prize", "status": "active", "pageSize": 100},
        headers={"Accept": "application/json"},
        timeout=12,
    )
    if resp:
        try:
            data = resp.json()
            comps = data if isinstance(data, list) else data.get("competitions", [])
            for c in comps[:100]:
                title = c.get("title") or c.get("name", "")
                reward = c.get("reward", c.get("rewardType", ""))
                if isinstance(reward, (int, float)):
                    reward = f"${reward:,.0f}"
                deadline = str(c.get("deadline", "TBA") or "TBA")[:10]
                slug = c.get("ref") or c.get("url", "")
                url = (f"https://www.kaggle.com/competitions/{slug}"
                       if slug and not slug.startswith("http") else slug or "https://www.kaggle.com/competitions")
                results.append({
                    "title": title,
                    "organization": "Kaggle",
                    "description": (c.get("description") or f"Kaggle data science competition: {title}")[:300],
                    "deadline": deadline,
                    "eligibility": "Open to all; ML practitioners, data scientists",
                    "rewards": str(reward) or "Kaggle points and medals",
                    "required_skills": ["machine learning", "python", "data analysis"],
                    "location": "Remote",
                    "url": url,
                    "source": "kaggle",
                })
        except Exception as e:
            print(f"[Kaggle] {e}")
    return results


def fetch_hackernews() -> List[Dict]:
    results = []
    searches = [
        "hackathon 2025",
        "fellowship stipend 2025",
        "open source internship 2025",
        "competition prize developers 2025",
    ]
    for q in searches:
        resp = _get(
            "https://hn.algolia.com/api/v1/search",
            params={"query": q, "tags": "story", "numericFilters": "created_at_i>1700000000", "hitsPerPage": 30},
            timeout=10,
        )
        if resp:
            for hit in resp.json().get("hits", [])[:30]:
                title = hit.get("title", "")
                hn_url = hit.get("url") or f"https://news.ycombinator.com/item?id={hit.get('objectID', '')}"
                if title and len(title) > 15:
                    results.append({
                        "title": title,
                        "organization": "HackerNews",
                        "description": f"HackerNews community post: {title}",
                        "deadline": "See link",
                        "eligibility": "Developers and tech enthusiasts",
                        "rewards": "Community recognition, networking",
                        "required_skills": ["programming"],
                        "location": "Remote",
                        "url": hn_url,
                        "source": "hackernews",
                    })
        time.sleep(0.2)
    return results


def fetch_lfx() -> List[Dict]:
    results = []
    resp = _get(
        "https://api.lfx.linuxfoundation.org/v2/mentorship/programs",
        params={"orderby": "name", "status": "active", "size": 100},
        timeout=12,
    )
    if resp:
        try:
            data = resp.json()
            programs = data if isinstance(data, list) else data.get("Data", data.get("data", []))
            for p in programs[:100]:
                name = p.get("Name") or p.get("name", "")
                desc = p.get("Description") or p.get("description", "")
                url = p.get("URL") or p.get("url") or "https://mentorship.lfx.linuxfoundation.org"
                results.append({
                    "title": name or "LFX Mentorship Program",
                    "organization": "Linux Foundation",
                    "description": (desc[:300] if desc else "LFX paid mentorship — work on Linux Foundation open source projects with expert mentors."),
                    "deadline": "Rolling — check site",
                    "eligibility": "Students and early-career developers",
                    "rewards": "$1,500–$3,000 stipend per term",
                    "required_skills": ["open source", "Linux", "programming"],
                    "location": "Remote",
                    "url": url,
                    "source": "lfx_mentorship",
                })
        except Exception as e:
            print(f"[LFX] {e}")
    return results


MEGA_SYNTHESIS_PROMPT = """You are an expert opportunity researcher. Generate a comprehensive list of REAL, CURRENT student and developer opportunities from ALL of these platforms:

Platforms to cover:
{platforms_list}

Today: {date}

Generate 6-8 opportunities PER PLATFORM listed above. Base them on REAL programs that exist.

Return ONLY a JSON array. Each item:
{{
  "title": "Opportunity Title",
  "organization": "Organization Name",
  "description": "2-3 sentence description",
  "deadline": "YYYY-MM-DD or 'Rolling' or 'TBA'",
  "eligibility": "Who can apply",
  "rewards": "Prize money, stipend, certificate (include amounts where known)",
  "required_skills": ["skill1", "skill2"],
  "location": "Remote / City, Country / Hybrid",
  "url": "https://real-platform-url.com/opportunity",
  "source": "platform_name"
}}

Requirements:
- MUST cover all platforms listed
- Include real rewards amounts (e.g. "$7,000 stipend", "$100,000 prize pool", "$1,500/month")
- Deadlines in 2025 or 2026
- Include India-specific opportunities where relevant (Devfolio, Unstop)
- Include variety: beginner to advanced, local and global
- Return 15-25 total opportunities (quality over quantity)
"""


def synthesize_llm_mega(platforms: list, llm) -> List[Dict]:
    """
    ONE LLM call to synthesize opportunities for ALL platforms at once.
    Massively reduces API quota usage vs calling per-platform.
    """
    platform_lines = []
    for src_name in platforms:
        src = SOURCE_BY_NAME.get(src_name)
        if src:
            platform_lines.append(f"- {src.display_name} ({src.url}) [source_field: '{src_name}']")

    prompt = MEGA_SYNTHESIS_PROMPT.format(
        platforms_list="\n".join(platform_lines),
        date=datetime.utcnow().strftime("%Y-%m-%d"),
    )
    raw = rate_limited_invoke(llm, [("human", prompt)], max_retries=4)
    if raw:
        data = parse_json_safely(raw)
        if isinstance(data, list):
            return [d for d in data if d.get("title")]
    return []


# ══════════════════════════════════════════════════════════════════════════════
# HUNTER HELPERS + SUB-NODES (streamed via LangGraph for live UI progress)
# ══════════════════════════════════════════════════════════════════════════════

def _sources_from_state(state: AgentState) -> List[str]:
    scan_meta = state.get("scan_metadata")
    if scan_meta and scan_meta.sources_searched:
        return list(scan_meta.sources_searched)
    return []


def _update_scan_progress(state: AgentState, all_raw: List[Dict], sources: List[str]):
    scan_meta = state.get("scan_metadata")
    if scan_meta:
        scan_meta.sources_searched = sorted(set(sources))
        scan_meta.total_found = len(all_raw)
    return scan_meta


def _plan_queries(state: AgentState) -> List[str]:
    plan = state.get("search_plan")
    return plan.queries if plan and plan.queries else []


def run_hunter_firecrawl(state: AgentState) -> dict:
    """Layer 1: Firecrawl page scraping."""
    llm = get_llm(temperature=0.4)
    messages = [
        "🔍 **Opportunity Hunter Agent — TURBO EDITION**",
        "   Activating 3-layer intelligence pipeline...",
        "\n   🔥 **LAYER 1: Firecrawl Web Crawl**",
    ]
    print("[HUNTER] Starting Layer 1: Firecrawl web crawl...", flush=True)

    fc_opps, fc_sources, fc_msgs = run_firecrawl_layer(llm)
    messages.extend(fc_msgs)

    all_raw = list(state.get("raw_opportunities", []))
    all_raw.extend(fc_opps)
    sources = _sources_from_state(state)
    sources.extend(fc_sources)
    scan_meta = _update_scan_progress(state, all_raw, sources)

    ctx = dict(state.get("hunter_context") or {})
    ctx["fc_count"] = len(fc_opps)

    return {
        "raw_opportunities": all_raw,
        "hunter_context": ctx,
        "progress_messages": messages,
        "scan_metadata": scan_meta,
    }


def run_hunter_web_search(state: AgentState) -> dict:
    """Layer 2: Tavily + SerpAPI search and Gemini extraction."""
    llm = get_llm(temperature=0.4)
    plan_queries = _plan_queries(state)
    messages = ["\n   🌐 **LAYER 2: Tavily + SerpAPI Web Search**"]
    print("[HUNTER] Starting Layer 2: Tavily + SerpAPI web search...", flush=True)

    messages.append("   🔎 Tavily: Running semantic queries...")
    tavily_snippets = fetch_tavily(plan_queries)
    sources = _sources_from_state(state)
    if tavily_snippets:
        messages.append(f"   ✅ Tavily: {len(tavily_snippets)} search snippets fetched")
        sources.append("tavily_search")
    else:
        messages.append("   ℹ️  Tavily: key missing or quota exceeded")

    messages.append("   🔎 SerpAPI: Running site-targeted queries...")
    serp_snippets = fetch_serpapi(plan_queries)
    if serp_snippets:
        messages.append(f"   ✅ SerpAPI: {len(serp_snippets)} search snippets fetched")
        sources.append("serpapi_search")
    else:
        messages.append("   ℹ️  SerpAPI: key missing or quota exceeded")

    all_raw = list(state.get("raw_opportunities", []))
    all_snippets = (tavily_snippets + serp_snippets)[:15]
    if all_snippets:
        messages.append(f"   🤖 Gemini extracting from {len(all_snippets)} snippets...")
        web_extracted = extract_from_snippets(all_snippets, llm)
        if web_extracted:
            all_raw.extend(web_extracted)
            messages.append(f"   ✅ Search extraction: {len(web_extracted)} opportunities extracted")
        else:
            messages.append("   ⚠️  Search extraction: Gemini found no clear opportunities in snippets")

    ctx = dict(state.get("hunter_context") or {})
    ctx["tavily_snippets"] = len(tavily_snippets)
    ctx["serp_snippets"] = len(serp_snippets)

    scan_meta = _update_scan_progress(state, all_raw, sources)
    return {
        "raw_opportunities": all_raw,
        "hunter_context": ctx,
        "progress_messages": messages,
        "scan_metadata": scan_meta,
    }


def run_hunter_live_apis(state: AgentState) -> dict:
    """Layer 3: Live APIs and platform scouts."""
    messages = ["\n   📡 **LAYER 3: Live APIs + Platform Scouts**"]
    print("[HUNTER] Starting Layer 3: Live APIs fetching...", flush=True)

    all_raw = list(state.get("raw_opportunities", []))
    sources = _sources_from_state(state)
    ctx = dict(state.get("hunter_context") or {})

    mlh = fetch_mlh()
    if mlh:
        all_raw.extend(mlh)
        sources.append("mlh")
        messages.append(f"   ✅ MLH: {len(mlh)} hackathons (2025+2026)")
    else:
        messages.append("   MLH feed down -- will cover via LLM synthesis")
    ctx["mlh_ok"] = bool(mlh)

    gh = fetch_github()
    if gh:
        all_raw.extend(gh)
        sources.append("github")
        messages.append(f"   ✅ GitHub API: {len(gh)} repos")
    ctx["gh_count"] = len(gh)

    gsoc = fetch_gsoc_orgs()
    if gsoc:
        all_raw.extend(gsoc)
        sources.append("gsoc")
        messages.append(f"   ✅ GSoC API: {len(gsoc)} orgs")
    else:
        messages.append("   GSoC API down -- will cover via LLM synthesis")
    ctx["gsoc_ok"] = bool(gsoc)

    out = fetch_outreachy()
    all_raw.extend(out)
    sources.append("outreachy")
    messages.append(f"   ✅ Outreachy: {len(out)} program(s)")

    dp = fetch_devpost_rss()
    if dp:
        all_raw.extend(dp)
        sources.append("devpost")
        messages.append(f"   ✅ Devpost RSS: {len(dp)} hackathons")
    else:
        messages.append("   Devpost RSS down -- will cover via LLM synthesis")
    ctx["devpost_ok"] = bool(dp)

    kag = fetch_kaggle()
    if kag:
        all_raw.extend(kag)
        sources.append("kaggle")
        messages.append(f"   ✅ Kaggle API: {len(kag)} competitions")
    else:
        messages.append("   Kaggle API down -- will cover via LLM synthesis")
    ctx["kaggle_ok"] = bool(kag)

    hn = fetch_hackernews()
    if hn:
        all_raw.extend(hn)
        sources.append("hackernews")
        messages.append(f"   ✅ HackerNews: {len(hn)} posts")

    lfx = fetch_lfx()
    if lfx:
        all_raw.extend(lfx)
        sources.append("lfx_mentorship")
        messages.append(f"   ✅ LFX Mentorship: {len(lfx)} programs")

    uns = fetch_unstop()
    if uns:
        all_raw.extend(uns)
        sources.append("unstop")
        messages.append(f"   ✅ Unstop Scout: {len(uns)} opportunities")

    devf = fetch_devfolio()
    if devf:
        all_raw.extend(devf)
        sources.append("devfolio")
        messages.append(f"   ✅ Devfolio Scout: {len(devf)} hackathons")

    scan_meta = _update_scan_progress(state, all_raw, sources)
    return {
        "raw_opportunities": all_raw,
        "hunter_context": ctx,
        "progress_messages": messages,
        "scan_metadata": scan_meta,
    }


def run_hunter_finalize(state: AgentState) -> dict:
    """Layer 4: LLM synthesis fallback, deep link resolution, and summary."""
    llm = get_llm(temperature=0.4)
    ctx = dict(state.get("hunter_context") or {})
    all_raw = list(state.get("raw_opportunities", []))
    sources = _sources_from_state(state)
    messages: List[str] = []

    synth_platforms = [
        "wellfound", "microsoft_imagine",
        "google_developer", "aws_programs", "research_programs",
        "fellowships", "gsoc_org",
    ]
    if not ctx.get("mlh_ok"):
        synth_platforms.append("mlh")
    if not ctx.get("gsoc_ok"):
        synth_platforms.append("github_gsoc")
    if not ctx.get("devpost_ok"):
        synth_platforms.append("devpost")
    if not ctx.get("kaggle_ok"):
        synth_platforms.append("kaggle")

    messages.append(f"   LLM mega-synthesis for {len(synth_platforms)} platforms...")
    synth_results = synthesize_llm_mega(synth_platforms, llm)
    if synth_results:
        all_raw.extend(synth_results)
        sources.extend([p for p in synth_platforms if p not in sources])
        messages.append(f"   ✅ LLM synthesis: {len(synth_results)} opportunities")
    else:
        messages.append("   ⚠️  LLM synthesis: rate limited or failed -- try again later")

    messages.append("\n   🔗 **LAYER 4: Deep Link Resolution**")
    needs_resolution = [
        o for o in all_raw
        if "apply" not in o.get("url", "").lower() and "register" not in o.get("url", "").lower()
    ]
    if needs_resolution:
        subset = needs_resolution[:10]
        messages.append(f"   Resolving {len(subset)} surface links...")
        resolved = resolve_deep_links(subset)
        for r_opp in resolved:
            for i, opp in enumerate(all_raw):
                if opp.get("title") == r_opp.get("title") and opp.get("organization") == r_opp.get("organization"):
                    all_raw[i] = r_opp
        messages.append("   ✅ Deep link resolution complete.")

    unique_sources = sorted(set(sources))
    messages.append(
        f"\n   📊 **HUNT COMPLETE**: {len(all_raw)} raw opportunities "
        f"from {len(unique_sources)} sources"
    )
    messages.append(f"   🗂️  Sources: {', '.join(unique_sources)}")

    decision = AgentDecision(
        scan_id=state["scan_id"],
        agent_name="Opportunity Hunter Agent",
        decision=f"Collected {len(all_raw)} raw opportunities from {len(unique_sources)} sources",
        reasoning=(
            f"Firecrawl ({ctx.get('fc_count', 0)}) + "
            f"Tavily ({ctx.get('tavily_snippets', 0)} snippets) + "
            f"SerpAPI ({ctx.get('serp_snippets', 0)} snippets) + "
            f"Live APIs + LLM synthesis. Sources: {len(unique_sources)}"
        ),
    )

    scan_meta = _update_scan_progress(state, all_raw, unique_sources)
    return {
        "raw_opportunities": all_raw,
        "agent_logs": [decision],
        "progress_messages": messages,
        "scan_metadata": scan_meta,
    }


def run_hunter(state: AgentState) -> dict:
    """Legacy single-node hunter — runs all layers sequentially."""
    state = {**state, **run_hunter_firecrawl(state)}
    state = {**state, **run_hunter_web_search(state)}
    state = {**state, **run_hunter_live_apis(state)}
    return run_hunter_finalize(state)
