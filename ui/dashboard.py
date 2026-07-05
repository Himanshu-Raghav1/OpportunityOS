"""
Main dashboard — renders all opportunity sections and analytics.
Uses native Streamlit components throughout for reliable rendering.
"""
import streamlit as st
import plotly.express as px
import pandas as pd
from typing import List, Dict, Any, Optional
from ui.cards import render_opportunity_card, render_card_grid
from ui.filters import apply_filters


# ── Section helpers ───────────────────────────────────────────────────────────

def filter_by_category(opps: List[Dict], category: str, limit: int) -> List[Dict]:
    result = [o for o in opps if o.get("category") == category]
    return sorted(result, key=lambda x: float(x.get("score", 0)), reverse=True)[:limit]


def filter_closing_soon(opps: List[Dict], limit: int) -> List[Dict]:
    """Opportunities that have a concrete deadline (not TBA/Rolling)."""
    result = []
    for o in opps:
        dl = str(o.get("deadline", "") or "")
        if dl and dl.lower() not in ("tba", "rolling", "ongoing", ""):
            result.append(o)
    return sorted(result, key=lambda x: str(x.get("deadline", "9999")))[:limit]


def filter_recent(opps: List[Dict], limit: int) -> List[Dict]:
    return sorted(opps, key=lambda x: str(x.get("created_at", "")), reverse=True)[:limit]


def top_opps(opps: List[Dict], limit: int) -> List[Dict]:
    return sorted(opps, key=lambda x: float(x.get("score", 0)), reverse=True)[:limit]


# ── Section header ────────────────────────────────────────────────────────────

def section_header(title: str, count: int, color: str = "#8b5cf6"):
    st.markdown(
        f'<div style="display:flex;align-items:center;gap:0.75rem;'
        f'border-bottom:1px solid rgba(255,255,255,0.07);padding-bottom:0.6rem;margin:1.8rem 0 1rem;">'
        f'<span style="font-size:1.15rem;font-weight:700;color:#f0f0f8;">{title}</span>'
        f'<span style="background:{color}22;color:{color};border-radius:100px;'
        f'padding:0.1rem 0.55rem;font-size:0.72rem;font-weight:600;">{count}</span>'
        f'</div>',
        unsafe_allow_html=True
    )


# ── Analytics panel ───────────────────────────────────────────────────────────

def render_analytics(opps: List[Dict]):
    if not opps:
        return

    df = pd.DataFrame(opps)
    df["score"] = pd.to_numeric(df.get("score", 0), errors="coerce").fillna(0)

    tab1, tab2, tab3 = st.tabs(["📊 Categories", "🏆 Score Distribution", "📡 Sources"])

    # ── Tab 1: Category pie ──────────────────────────────────────────────────
    with tab1:
        if "category" in df.columns:
            cat_df = df["category"].value_counts().reset_index()
            cat_df.columns = ["Category", "Count"]
            fig = px.pie(
                cat_df, values="Count", names="Category", hole=0.55,
                color_discrete_sequence=[
                    "#8b5cf6","#3b82f6","#10b981","#f59e0b",
                    "#f43f5e","#06b6d4","#f97316","#34d399","#a78bfa"
                ]
            )
            fig.update_layout(
                paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                font_color="#f0f0f8", margin=dict(t=10,b=10,l=0,r=0),
                legend=dict(bgcolor="rgba(0,0,0,0)", font=dict(color="#8b8ba8"))
            )
            fig.update_traces(textfont_color="#f0f0f8", textfont_size=12)
            st.plotly_chart(fig, width="stretch")

    # ── Tab 2: Score histogram ───────────────────────────────────────────────
    with tab2:
        fig2 = px.histogram(
            df, x="score", nbins=15, color_discrete_sequence=["#8b5cf6"]
        )
        fig2.update_layout(
            paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
            font_color="#f0f0f8",
            xaxis=dict(title="Score (0–100)", gridcolor="rgba(255,255,255,0.05)"),
            yaxis=dict(title="Count", gridcolor="rgba(255,255,255,0.05)"),
            margin=dict(t=10,b=10,l=0,r=0)
        )
        st.plotly_chart(fig2, width="stretch")

    # ── Tab 3: Source bar ────────────────────────────────────────────────────
    with tab3:
        if "source" in df.columns:
            src_df = df["source"].value_counts().reset_index()
            src_df.columns = ["Source", "Count"]
            fig3 = px.bar(
                src_df, x="Source", y="Count",
                color="Count", color_continuous_scale="Purples"
            )
            fig3.update_layout(
                paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                font_color="#f0f0f8",
                xaxis=dict(gridcolor="rgba(255,255,255,0.05)", tickangle=-30),
                yaxis=dict(gridcolor="rgba(255,255,255,0.05)"),
                margin=dict(t=10,b=40,l=0,r=0),
                coloraxis_showscale=False
            )
            st.plotly_chart(fig3, width="stretch")


# ── Empty state ───────────────────────────────────────────────────────────────

def render_empty_state():
    st.markdown("<br>", unsafe_allow_html=True)
    c1, c2, c3 = st.columns([1, 2, 1])
    with c2:
        st.markdown(
            '<div style="text-align:center;padding:3rem 1rem;">'
            '<div style="font-size:4rem;margin-bottom:1rem;">🤖</div>'
            '<h3 style="color:#8b8ba8;font-weight:700;">No opportunities yet</h3>'
            '<p style="color:#5a5a72;font-size:0.95rem;">Click <strong style="color:#8b5cf6;">⚡ Scan Opportunities</strong>'
            ' in the sidebar to launch the AI agent pipeline.</p>'
            '</div>',
            unsafe_allow_html=True
        )


# ── Main dashboard ────────────────────────────────────────────────────────────

def render_dashboard(opps: List[Dict], filters: Dict):
    """Render the complete opportunity dashboard as a social media feed."""

    if not opps:
        render_empty_state()
        return

    # Apply sidebar filters
    filtered = apply_filters(opps, filters)

    # Search bar filter at dashboard level
    search_query = st.text_input(
        "🔍 Search opportunities, skills, hosts...",
        placeholder="Try 'Python', 'Google', 'Hackathon'...",
        key="feed_search"
    )
    if search_query:
        q = search_query.lower()
        filtered = [
            o for o in filtered 
            if q in o.get("title", "").lower() or
               q in o.get("organization", "").lower() or
               any(q in sk.lower() for sk in o.get("required_skills", []))
        ]

    # Create the 3-column Social Feed Layout
    col_left, col_mid, col_right = st.columns([1, 2.2, 1.2], gap="large")

    # ──────────────────────────────────────────────────────────────────────────
    # LEFT COLUMN: User Profile & Bookmarks
    # ──────────────────────────────────────────────────────────────────────────
    with col_left:
        st.markdown("### 🧑‍💻 My Dashboard")
        
        # User profile summary card
        profile = st.session_state.get("user_profile")
        if st.session_state.get("personalize_match") and profile:
            st.markdown(
                f'<div style="background:#16161e;border:1px solid rgba(255,255,255,0.08);'
                f'border-radius:12px;padding:1rem;margin-bottom:1.5rem;">'
                f'<div style="font-size:0.75rem;color:#06b6d4;font-weight:700;text-transform:uppercase;letter-spacing:0.05em;">Personalized Candidate</div>'
                f'<div style="font-size:1.1rem;font-weight:800;color:#f0f0f8;margin-top:0.2rem;">Divyanshu</div>'
                f'<div style="font-size:0.8rem;color:#8b8ba8;margin-top:0.4rem;">💼 Experience: <strong>{profile.get("experience_level", "Unknown")}</strong></div>'
                f'<div style="font-size:0.8rem;color:#8b8ba8;margin-top:0.2rem;">🎯 Interests: <strong>{", ".join(profile.get("interests", [])[:3])}</strong></div>'
                f'</div>',
                unsafe_allow_html=True
            )
        else:
            st.markdown(
                '<div style="background:#16161e;border:1px solid rgba(255,255,255,0.05);'
                'border-radius:12px;padding:1rem;margin-bottom:1.5rem;text-align:center;">'
                '<div style="font-size:1.5rem;margin-bottom:0.3rem;">🚀</div>'
                '<div style="font-size:0.85rem;color:#5a5a72;">Enable "Personalize Match" in the sidebar to sync your skills.</div>'
                '</div>',
                unsafe_allow_html=True
            )

        # Saved opportunities widget
        st.markdown("#### ❤️ Bookmarked Board")
        bookmarked_ids = st.session_state.get("bookmarked_ids", set())
        saved_opps = [o for o in opps if o.get("id") in bookmarked_ids]
        
        if saved_opps:
            for s_opp in saved_opps[:8]:
                st.markdown(
                    f'<div style="background:rgba(255,255,255,0.02);border:1px solid rgba(255,255,255,0.05);'
                    f'border-radius:8px;padding:0.6rem;margin-bottom:0.5rem;font-size:0.8rem;">'
                    f'<div style="font-weight:700;color:#f0f0f8;"><a href="{s_opp.get("url", "#")}" target="_blank" style="color:inherit;text-decoration:none;">{s_opp.get("title")[:30]}...</a></div>'
                    f'<div style="color:#8b5cf6;font-size:0.72rem;">🏢 {s_opp.get("organization")}</div>'
                    f'</div>',
                    unsafe_allow_html=True
                )
        else:
            st.caption("No bookmarked items yet. Tap 'Save to Board' on any opportunity card.")

    # ──────────────────────────────────────────────────────────────────────────
    # MIDDLE COLUMN: Social Feed & Tags
    # ──────────────────────────────────────────────────────────────────────────
    with col_mid:
        # Category pills
        categories = ["🔥 All", "⚡ Hackathons", "💼 Internships", "🌐 Open Source", "🎓 Fellowships", "⏰ Closing Soon"]
        
        # We can implement tag selection via streamlit button row
        cols = st.columns(len(categories))
        selected_tag = st.session_state.get("feed_tag", "🔥 All")
        
        for i, cat in enumerate(categories):
            with cols[i]:
                is_selected = selected_tag == cat
                btn_type = "primary" if is_selected else "secondary"
                if st.button(cat, key=f"pill_{cat}", type=btn_type, use_container_width=True):
                    st.session_state.feed_tag = cat
                    st.rerun()

        st.markdown("<br>", unsafe_allow_html=True)
        
        # Apply pills filter
        feed_tag = st.session_state.get("feed_tag", "🔥 All")
        tag_filtered = filtered.copy()
        
        if feed_tag == "⚡ Hackathons":
            tag_filtered = [o for o in tag_filtered if o.get("category") == "Hackathon"]
        elif feed_tag == "💼 Internships":
            tag_filtered = [o for o in tag_filtered if o.get("category") == "Internship"]
        elif feed_tag == "🌐 Open Source":
            tag_filtered = [o for o in tag_filtered if o.get("category") == "Open Source"]
        elif feed_tag == "🎓 Fellowships":
            tag_filtered = [o for o in tag_filtered if o.get("category") == "Fellowship"]
        elif feed_tag == "⏰ Closing Soon":
            tag_filtered = filter_closing_soon(tag_filtered, 50)

        # Render Feed
        st.markdown(f"### {feed_tag} Feed ({len(tag_filtered)})")
        if tag_filtered:
            for opp in tag_filtered:
                render_opportunity_card(opp, show_reasoning=True)
        else:
            st.info("No matching opportunities in this feed query. Adjust filters in the sidebar or search query.")

    # ──────────────────────────────────────────────────────────────────────────
    # RIGHT COLUMN: Mini Analytics & Trending
    # ──────────────────────────────────────────────────────────────────────────
    with col_right:
        st.markdown("### 📊 Feed Analytics")
        
        # Compact stats
        st.markdown(
            f'<div style="background:#16161e;border:1px solid rgba(255,255,255,0.08);'
            f'border-radius:12px;padding:1rem;margin-bottom:1rem;">'
            f'<div style="font-size:0.75rem;color:#8b8ba8;text-transform:uppercase;">Scraped Opportunities</div>'
            f'<div style="font-size:1.8rem;font-weight:800;color:#8b5cf6;">{len(opps)}</div>'
            f'</div>',
            unsafe_allow_html=True
        )

        # Plotly chart in expandable container
        with st.expander("📂 Category Breakdowns", expanded=True):
            render_analytics(filtered)

        # Trending hosts list
        st.markdown("#### ⚡ Trending Hosts")
        if filtered:
            df = pd.DataFrame(filtered)
            if "organization" in df.columns:
                top_orgs = df["organization"].value_counts().head(5)
                for org_name, count in top_orgs.items():
                    st.markdown(
                        f'<div style="display:flex;justify-content:space-between;padding:0.4rem 0;'
                        f'border-bottom:1px solid rgba(255,255,255,0.05);font-size:0.8rem;">'
                        f'<span style="color:#f0f0f8;font-weight:600;">{org_name}</span>'
                        f'<span style="color:#8b8ba8;">{count} posts</span>'
                        f'</div>',
                        unsafe_allow_html=True
                    )

