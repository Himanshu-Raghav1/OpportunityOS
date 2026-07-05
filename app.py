"""
OpportunityOS AI — Main Streamlit Application
═════════════════════════════════════════════
Autonomous multi-agent opportunity discovery system powered by Gemini 2.5 Flash.
"""
import streamlit as st
import os
import uuid
import time
from pathlib import Path
from datetime import datetime
import sys
if sys.platform.startswith("win"):
    try:
        sys.stdout.reconfigure(encoding='utf-8')
        sys.stderr.reconfigure(encoding='utf-8')
    except Exception:
        pass

from dotenv import load_dotenv
load_dotenv()

# Streamlit Cloud: inject secrets into os.environ if .env not present
import os
for _k in ["GOOGLE_API_KEY", "SERPAPI_KEY", "TAVILY_API_KEY", "FIRECRAWL_API_KEY"]:
    if not os.getenv(_k):
        try:
            if hasattr(st, "secrets") and _k in st.secrets:
                os.environ[_k] = st.secrets[_k]
        except Exception:
            pass


# Start background scheduler exactly once
@st.cache_resource
def run_bg_scheduler():
    from core.scheduler import start_scheduler
    start_scheduler()

run_bg_scheduler()

# ── Page config (must be first Streamlit call) ────────────────────────────────
st.set_page_config(
    page_title="OpportunityOS AI",
    page_icon="🚀",
    layout="wide",
    initial_sidebar_state="expanded",
    menu_items={
        "Get Help": None,
        "Report a bug": None,
        "About": "OpportunityOS AI — Autonomous Opportunity Discovery Agent"
    }
)

# ── Load custom CSS ───────────────────────────────────────────────────────────
css_path = Path(__file__).parent / "assets" / "style.css"
if css_path.exists():
    with open(css_path) as f:
        st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)

# ── Imports (after page config) ───────────────────────────────────────────────
from core.memory import load_all_opportunities, load_scan_history
from core.models import ScanMetadata
from ui.filters import render_filters, apply_filters
from ui.dashboard import render_dashboard
from ui.reasoning_panel import render_reasoning_panel


# ── Session state initialization ──────────────────────────────────────────────
if "scan_complete" not in st.session_state:
    st.session_state.scan_complete = False
if "last_scan_id" not in st.session_state:
    st.session_state.last_scan_id = None
if "opportunities" not in st.session_state:
    st.session_state.opportunities = []
if "scan_stats" not in st.session_state:
    st.session_state.scan_stats = {}
if "agent_messages" not in st.session_state:
    st.session_state.agent_messages = []
if "user_github" not in st.session_state:
    st.session_state.user_github = ""
if "user_linkedin" not in st.session_state:
    st.session_state.user_linkedin = ""
if "user_profile" not in st.session_state:
    st.session_state.user_profile = None
if "personalize_match" not in st.session_state:
    st.session_state.personalize_match = False


# ── Sidebar ───────────────────────────────────────────────────────────────────
with st.sidebar:
    # Logo / brand
    st.markdown("""
    <div style="text-align:center; padding:1.5rem 0 0.5rem;">
        <div style="font-size:2.5rem;">🚀</div>
        <div style="font-size:1.2rem; font-weight:800; background:linear-gradient(135deg,#8b5cf6,#3b82f6);
                    -webkit-background-clip:text; -webkit-text-fill-color:transparent; margin-top:0.3rem;">
            OpportunityOS AI
        </div>
        <div style="font-size:0.72rem; color:#5a5a72; letter-spacing:0.1em; text-transform:uppercase;">
            Autonomous Discovery Agent
        </div>
    </div>
    """, unsafe_allow_html=True)

    st.markdown("---")

    # Scan button
    scan_clicked = st.button(
        "⚡ Scan Opportunities",
        type="primary",
        use_container_width=True,
        key="scan_btn"
    )

    # Refresh from memory button
    if st.button("🔄 Load Saved Results", use_container_width=True):
        with st.spinner("Loading from memory..."):
            opps = load_all_opportunities()
            if opps:
                st.session_state.opportunities = opps
                st.session_state.scan_stats = {
                    "total": len(opps),
                    "unique": len(opps),
                    "duplicates": 0,
                    "sources": len(set(o.get("source", "") for o in opps))
                }
                st.success(f"✅ Loaded {len(opps)} opportunities from memory")
            else:
                st.info("No saved opportunities found. Run a scan first.")

# Render filters (also in sidebar)
filters = render_filters()

with st.sidebar:
    st.markdown("---")
    st.markdown("### 🎯 Personalize Match (Google Hackathon Feature)")
    st.session_state.personalize_match = st.toggle(
        "Enable Personalization",
        value=st.session_state.personalize_match,
        help="Toggle to scrape your profile & resume to match with thousands of opportunities."
    )
    
    if st.session_state.personalize_match:
        st.session_state.user_github = st.text_input(
            "GitHub Username/URL:",
            value=st.session_state.user_github,
            placeholder="e.g. divyanshu-dev"
        )
        st.session_state.user_linkedin = st.text_area(
            "LinkedIn Bio/Experience:",
            value=st.session_state.user_linkedin,
            placeholder="Paste your LinkedIn summary or work experience here...",
            height=100
        )
        uploaded_file = st.file_uploader("Upload PDF Resume:", type=["pdf"])
        if uploaded_file is not None:
            st.session_state.user_resume_bytes = uploaded_file.read()
            st.success("✅ PDF Resume uploaded")
        else:
            st.session_state.user_resume_bytes = None
    else:
        st.session_state.user_resume = st.text_area(
            "Paste your skills, bio, or resume snippet here:",
            value=st.session_state.get("user_resume", ""),
            height=120,
            help="Alternative basic matching: Paste your skills raw text."
        )

# Scan history in sidebar
with st.sidebar:
    st.markdown("---")
    st.markdown("### 📚 Scan History")
    history = load_scan_history(5)
    if history:
        for scan in history:
            status_icon = "✅" if scan.get("status") == "completed" else "⚠️"
            st.markdown(
                f'<div style="font-size:0.75rem; color:#8b8ba8; padding:0.3rem 0; '
                f'border-bottom:1px solid rgba(255,255,255,0.05);">'
                f'{status_icon} {str(scan.get("started_at",""))[:10]} — '
                f'{scan.get("total_unique", 0)} opportunities</div>',
                unsafe_allow_html=True
            )
    else:
        st.markdown('<div style="font-size:0.8rem; color:#5a5a72;">No scans yet</div>', unsafe_allow_html=True)


# ── Main Content Area ─────────────────────────────────────────────────────────

# Hero section
st.markdown("""
<div class="hero-section">
    <div class="hero-badge">🤖 AI-Powered · Multi-Agent · Autonomous</div>
    <div class="hero-title">OpportunityOS AI</div>
    <div class="hero-subtitle">
        Your autonomous AI analyst that discovers, analyzes, and ranks opportunities<br>
        from hackathons, internships, fellowships, open source programs, and more.
    </div>
</div>
""", unsafe_allow_html=True)


# ── Run Agent Pipeline ────────────────────────────────────────────────────────
if scan_clicked:
    scan_id = str(uuid.uuid4())
    st.session_state.last_scan_id = scan_id
    st.session_state.agent_messages = []

    scan_meta = ScanMetadata(scan_id=scan_id)

    # ── Handle Profile Synthesis (Personalize Match) ─────────────────────────
    profile = None
    if st.session_state.personalize_match:
        with st.status("🧠 Synthesizing Personal Profile...", expanded=True) as status:
            st.write("🔗 Fetching GitHub profile and repositories...")
            st.write("📄 Extracting text from PDF resume...")
            st.write("🤖 Running Gemini profiler...")
            
            from core.profile_extractor import synthesize_profile
            profile = synthesize_profile(
                github_user=st.session_state.user_github,
                linkedin_text=st.session_state.user_linkedin,
                resume_bytes=st.session_state.get("user_resume_bytes")
            )
            st.session_state.user_profile = profile
            status.update(label="✅ User Profile Synthesized!", state="complete")
            
        st.info(f"**Extracted Skills:** {', '.join(profile.get('skills', []))}")
        st.info(f"**Experience Level:** {profile.get('experience_level', 'Unknown')}")

    # Build initial state
    initial_state = {
        "scan_id": scan_id,
        "user_preferences": {
            "resume": st.session_state.get("user_resume", ""),
            "profile": st.session_state.get("user_profile") if st.session_state.personalize_match else None
        },
        "search_plan": None,
        "raw_opportunities": [],
        "extracted_opportunities": [],
        "deduplicated_opportunities": [],
        "duplicates_removed": 0,
        "classified_opportunities": [],
        "enriched_opportunities": [],
        "ranked_opportunities": [],
        "agent_logs": [],
        "hunter_context": {},
        "scan_metadata": scan_meta,
        "progress_messages": [],
        "errors": []
    }

    # ── Agent execution with live progress UI ─────────────────────────────
    progress_container = st.empty()

    AGENT_STEPS = [
        ("🧠", "Search Planning Agent",          "Creating optimal search strategy...", "Planning"),
        ("🔥", "Hunter: Firecrawl Crawl",        "Scraping live opportunity pages...", "Firecrawl"),
        ("🌐", "Hunter: Web Search",             "Tavily + SerpAPI discovery...", "Tavily/Serp"),
        ("📡", "Hunter: Live APIs",              "Fetching MLH, GitHub, GSoC, etc...", "Live APIs"),
        ("🔗", "Hunter: Finalize",               "LLM synthesis + link resolution...", "Synthesis"),
        ("📋", "Information Extraction Agent",   "Extracting & normalizing data...", "Extract"),
        ("🔄", "Deduplication Agent",            "Detecting & removing duplicates...", "Dedupe"),
        ("🏷️",  "Classification Agent",          "Categorizing opportunities...", "Classify"),
        ("💡", "Opportunity Intelligence Agent", "Generating AI insights...", "Enrich"),
        ("🏆", "Ranking Agent",                  "Scoring & ranking all opportunities...", "Rank"),
        ("🎯", "Evaluator Agent",                "Matching opportunities to your resume...", "Match"),
    ]

    def render_live_progress(current: int, messages: list):
        """Render animated progress in the container."""
        with progress_container.container():
            st.markdown("## 🤖 Agent Pipeline — Live Execution")
            st.progress(min(current / len(AGENT_STEPS), 1.0))
            st.markdown("")

            cols = st.columns(len(AGENT_STEPS))
            for i, (emoji, name, _, short_label) in enumerate(AGENT_STEPS):
                with cols[i]:
                    if i < current:
                        st.markdown(f'<div style="text-align:center;font-size:1.5rem;">✅</div>'
                                   f'<div style="text-align:center;font-size:0.65rem;color:#10b981;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;">{short_label}</div>',
                                   unsafe_allow_html=True)
                    elif i == current:
                        st.markdown(f'<div style="text-align:center;font-size:1.5rem;" class="pulse">⚡</div>'
                                   f'<div style="text-align:center;font-size:0.65rem;color:#8b5cf6;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;">{short_label}</div>',
                                   unsafe_allow_html=True)
                    else:
                        st.markdown(f'<div style="text-align:center;font-size:1.5rem;opacity:0.3;">{emoji}</div>'
                                   f'<div style="text-align:center;font-size:0.65rem;color:#5a5a72;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;">{short_label}</div>',
                                   unsafe_allow_html=True)

            st.markdown("---")
            # Live log — plain text in a code block, no HTML f-string issues
            if messages:
                log_text = "\n".join(messages[-15:])
                st.code(log_text, language=None)

    try:
        from agents.graph import get_graph

        render_live_progress(0, ["🚀 Initializing OpportunityOS AI..."])
        time.sleep(0.3)

        # ── Run pipeline step by step using stream ────────────────────────
        graph = get_graph()
        current_step = 0
        all_messages = ["🚀 OpportunityOS AI Agent Pipeline started"]
        final_state = None

        for event in graph.stream(initial_state):
            # event = {node_name: state_updates}
            for node_name, updates in event.items():
                step_messages = updates.get("progress_messages", [])
                all_messages.extend(step_messages)
                st.session_state.agent_messages.extend(step_messages)
                current_step += 1
                render_live_progress(current_step, all_messages)
                time.sleep(0.1)
                final_state = updates

        # ── Pipeline complete ─────────────────────────────────────────────
        render_live_progress(len(AGENT_STEPS), all_messages + ["✅ All agents completed successfully!"])
        time.sleep(0.5)
        progress_container.empty()

        # Load results from the final state or memory
        ranked = []
        if final_state and final_state.get("ranked_opportunities"):
            ranked = [o.model_dump() if hasattr(o, "model_dump") else (o.dict() if hasattr(o, "dict") else o) for o in final_state["ranked_opportunities"]]
        else:
            ranked = load_all_opportunities()

        st.session_state.opportunities = ranked
        st.session_state.scan_complete = True
        st.session_state.scan_stats = {
            "total": initial_state.get("scan_metadata", scan_meta).total_found if hasattr(scan_meta, "total_found") else len(ranked),
            "unique": len(ranked),
            "duplicates": initial_state.get("duplicates_removed", 0),
            "sources": len(set(o.get("source", "") for o in ranked))
        }

        st.balloons()
        st.success(f"✅ Scan complete! Discovered **{len(ranked)} unique opportunities** across multiple platforms.")

    except Exception as e:
        progress_container.empty()
        st.error(f"⚠️ Agent pipeline error: {str(e)}")
        st.info("💡 Make sure your GOOGLE_API_KEY is set in the .env file")
        import traceback
        with st.expander("Error Details"):
            st.code(traceback.format_exc())


# ── Stats Banner ──────────────────────────────────────────────────────────────
opps = st.session_state.opportunities
if opps:
    avg_score = sum(float(o.get('score', 0)) for o in opps) / max(len(opps), 1)
    remote_count = len([o for o in opps if o.get('is_remote')])
    col1, col2, col3, col4, col5 = st.columns(5)
    with col1:
        st.metric("🎯 Opportunities", len(opps))
    with col2:
        st.metric("📂 Categories", len(set(o.get('category', '') for o in opps)))
    with col3:
        st.metric("🌐 Remote", remote_count)
    with col4:
        st.metric("📡 Sources", len(set(o.get('source', '') for o in opps)))
    with col5:
        st.metric("⭐ Avg Score", f"{avg_score:.0f}/100")
    st.markdown("")


# ── Main Tabs: Dashboard | Reasoning | History | Scheduler Logs ─────────────
main_tab1, main_tab2, main_tab3, main_tab4 = st.tabs([
    "🏠 Dashboard", 
    "🧠 Agent Reasoning", 
    "📚 History", 
    "📡 Scheduled Scan Logs"
])

with main_tab1:
    render_dashboard(opps, filters)

with main_tab2:
    if st.session_state.last_scan_id:
        render_reasoning_panel(st.session_state.last_scan_id)
    else:
        st.markdown("<br>", unsafe_allow_html=True)
        c1, c2, c3 = st.columns([1, 2, 1])
        with c2:
            st.markdown("### 🧠 Agent Reasoning Panel")
            st.info("Run a scan first to see how each AI agent thinks and makes decisions.")

with main_tab3:
    st.markdown("### 📚 Scan History")
    history = load_scan_history(20)
    if history:
        import pandas as pd
        df_hist = pd.DataFrame(history)
        display_cols = ["scan_id", "started_at", "status", "total_unique", "total_duplicates_removed", "sources_searched"]
        available = [c for c in display_cols if c in df_hist.columns]
        st.dataframe(
            df_hist[available].rename(columns={
                "scan_id": "Scan ID", "started_at": "Started", "status": "Status",
                "total_unique": "Unique Opps", "total_duplicates_removed": "Dupes Removed",
                "sources_searched": "Sources"
            }),
            use_container_width=True
        )
    else:
        st.info("No scan history yet. Click 'Scan Opportunities' to begin.")

    # Full opportunity table
    if opps:
        st.markdown("### 📋 All Opportunities (Data Table)")
        import pandas as pd
        df = pd.DataFrame(opps)
        show_cols = ["title", "organization", "category", "score", "deadline", "location", "source"]
        available = [c for c in show_cols if c in df.columns]
        st.dataframe(
            df[available].rename(columns={
                "title": "Title", "organization": "Org", "category": "Category",
                "score": "Score", "deadline": "Deadline", "location": "Location",
                "source": "Source"
            }).sort_values("Score", ascending=False) if "score" in df.columns else df[available],
            use_container_width=True,
            height=400
        )

with main_tab4:
    st.markdown("### 📡 Live Background Scheduler Logs")
    st.caption("This tab displays live stdout messages from the background agent executing 3x daily runs.")
    
    # Read live scheduler logs
    from pathlib import Path
    log_file = Path(__file__).parent / "logs" / "background_scan.log"
    if log_file.exists():
        try:
            with open(log_file, "r", encoding="utf-8") as f:
                log_data = f.readlines()
            
            # Display last 100 log lines in a terminal look-alike
            st.code("".join(log_data[-100:]), language="log")
        except Exception as e:
            st.error(f"Error reading log file: {e}")
    else:
        st.info("No background scheduled runs have executed yet. The scheduler loop runs check every 10 minutes.")
