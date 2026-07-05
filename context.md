# OpportunityOS AI — Project Context

## Vision
An autonomous AI Agent that continuously discovers, analyzes, ranks, and explains opportunities (hackathons, internships, open source programs, fellowships, research) across the internet — replacing hours of manual searching with a single click.

## Architecture Overview

```
User clicks "Scan Opportunities"
         │
         ▼
┌─────────────────────────────────────────────┐
│           LangGraph Agent Pipeline          │
│                                             │
│  [1] Planner → [2] Hunter → [3] Extractor  │
│       → [4] Deduplicator → [5] Classifier  │
│       → [6] Intelligence → [7] Ranker      │
└─────────────────────────────────────────────┘
         │
         ▼
┌────────────────────────┐   ┌───────────────────┐
│  SQLite (structured)   │   │  ChromaDB (vector) │
│  - opportunities table │   │  - semantic dedup  │
│  - scans table         │   │  - similarity      │
│  - agent_logs table    │   └───────────────────┘
│  - search_history      │
└────────────────────────┘
         │
         ▼
┌────────────────────────────────────────────────┐
│           Streamlit Dashboard                  │
│  - Real-time agent progress                    │
│  - Opportunity cards with AI insights          │
│  - Reasoning panel                             │
│  - Filters and sections                        │
└────────────────────────────────────────────────┘
```

## Technology Stack
| Component        | Technology               |
|-----------------|--------------------------|
| Frontend        | Streamlit                |
| LLM             | Gemini 2.5 Flash         |
| Agent Framework | LangGraph                |
| Memory          | SQLite + ChromaDB        |
| Data Processing | Pandas                   |
| Visualization   | Plotly                   |
| Web Fetching    | requests + BeautifulSoup |
| Config          | python-dotenv            |

## Agent Descriptions

### Agent 1: Search Planning Agent
- **Role**: Master strategist. Given the current date and user context, creates a prioritized search plan.
- **Input**: User preferences (optional), current date
- **Output**: `SearchPlan` with source list, query strings, and rationale
- **LLM prompt style**: Chain-of-thought planning

### Agent 2: Opportunity Hunter Agent
- **Role**: Data gatherer. Executes the search plan.
- **Strategy**:
  - GitHub: GitHub API (public repos tagged hackathon/gsoc)
  - MLH: RSS feed parsing
  - Kaggle: Public competitions API
  - Outreachy/GSOC: HTML parsing of public pages
  - LinkedIn/Devfolio/Unstop: Gemini LLM synthesis from training knowledge
- **Output**: Raw opportunity list (unstructured/semi-structured)

### Agent 3: Information Extraction Agent
- **Role**: Data normalizer. Extracts structured fields from raw text.
- **Fields extracted**: title, organization, category, deadline, eligibility, rewards, skills, location, source, url
- **Output**: `List[Opportunity]` (Pydantic models)

### Agent 4: Deduplication Agent
- **Role**: Data cleaner. Detects and merges duplicate opportunities.
- **Method**: ChromaDB cosine similarity on title+org embeddings, threshold 0.92
- **Output**: Unique opportunity set

### Agent 5: Classification Agent
- **Role**: Categorizer. Labels each opportunity into one of 9 types.
- **Categories**: Hackathon, Ideathon, Internship, Open Source, Fellowship, Competition, Research, Student Program, Developer Program
- **Method**: Rule-based regex + LLM fallback

### Agent 6: Opportunity Intelligence Agent
- **Role**: Insight generator. Produces human-readable analysis per opportunity.
- **Output per opp**: what it is, why it matters, who should apply, career impact (1-10), learning impact (1-10)

### Agent 7: Ranking Agent
- **Role**: Scorer. Assigns a 0-100 score to each opportunity.
- **Factors**: Reputation, Learning Value, Career Value, Accessibility, Prize/Stipend, Technical Relevance, Deadline Urgency, Community Impact
- **Output**: Ranked opportunity list with reasoning

## Data Flow
```
raw_text → Extractor → Opportunity(unclassified, unscored)
         → Deduplicator → unique set
         → Classifier → categorized
         → Intelligence → with ai_insight
         → Ranker → scored + ranked
         → SQLite + ChromaDB → persisted
         → Streamlit → displayed
```

## Known Limitations (MVP)
1. LinkedIn, Devfolio, Unstop use LLM-synthesized data (no live scraping — blocked by JS/CAPTCHA)
2. No user authentication — single-user local deployment
3. No scheduled background scanning (on-demand only in MVP)
4. Opportunity deadlines may be approximate for LLM-synthesized entries

## Design Decisions
- **LangGraph over raw LangChain**: LangGraph provides proper state management and streaming for agent pipelines
- **SQLite over PostgreSQL**: Zero-infrastructure setup for MVP local deployment
- **ChromaDB for dedup**: Semantic similarity catches near-duplicates that exact-match misses (e.g., same hackathon listed on Devfolio and Unstop with slightly different titles)
- **Hybrid data strategy**: Combines live API data + LLM synthesis to ensure the app always returns results even with no external API keys

## Environment Variables
```
GOOGLE_API_KEY=           # Required — Gemini 2.5 Flash
SERPAPI_KEY=              # Optional — SerpAPI for live search
TAVILY_API_KEY=           # Optional — Tavily for live search
```

## Future Roadmap (Post-MVP)
1. Scheduled background scans (APScheduler)
2. Email/Telegram notifications for new opportunities
3. User profiles and personalized ranking
4. Application tracking (applied/saved/rejected)
5. Browser extension for one-click opportunity saving
6. Real web scraping with Playwright + proxy rotation

## Follow-Up Sessions Context
- All opportunity data persists in `data/opportunityos.db`
- ChromaDB vectors in `data/chroma_db/`
- Agent logs visible in Reasoning Panel and stored in `agent_logs` table
- Scan history in `scans` table
- Re-scanning deduplicates against all prior scans
