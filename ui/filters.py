"""
Filter sidebar component.
Provides category, deadline, remote, country, and skill-level filters.
"""
import streamlit as st
from typing import List, Dict, Any
import json


ALL_CATEGORIES = [
    "All", "Hackathon", "Ideathon", "Internship", "Open Source",
    "Fellowship", "Competition", "Research", "Student Program", "Developer Program"
]

ALL_COUNTRIES = [
    "Global", "India", "USA", "UK", "Canada", "Germany",
    "Australia", "Europe", "Asia", "Remote"
]

SKILL_LEVELS = ["All", "Beginner", "Intermediate", "Advanced"]


def render_filters() -> Dict[str, Any]:
    """
    Renders the filter sidebar and returns current filter state.
    Returns a dict of active filters.
    """
    with st.sidebar:
        st.markdown("---")
        st.markdown("### 🎛️ Filters")

        # Category filter
        categories = st.multiselect(
            "📂 Category",
            options=ALL_CATEGORIES[1:],
            default=[],
            placeholder="All categories"
        )

        # Remote filter
        remote_only = st.toggle("🌐 Remote Only", value=False)

        # Country filter
        country = st.selectbox(
            "🌍 Country / Region",
            options=ALL_COUNTRIES,
            index=0
        )

        # Score filter
        min_score = st.slider(
            "⭐ Minimum Score",
            min_value=0,
            max_value=100,
            value=0,
            step=5
        )

        # Deadline filter
        upcoming_only = st.toggle("⏰ Upcoming Deadlines Only", value=False)

        # Rewards filter
        has_prize = st.toggle("🏅 Has Prize/Stipend", value=False)

        # Sort order
        sort_by = st.selectbox(
            "📊 Sort By",
            options=["Score (High→Low)", "Deadline (Soonest)", "Launching Date (Newest)", "Career Impact", "Learning Impact"],
            index=0
        )

        st.markdown("---")
        st.markdown("### 📊 Quick Stats")
        if "scan_stats" in st.session_state:
            stats = st.session_state.scan_stats
            col1, col2 = st.columns(2)
            with col1:
                st.metric("Found", stats.get("total", 0))
                st.metric("Sources", stats.get("sources", 0))
            with col2:
                st.metric("Unique", stats.get("unique", 0))
                st.metric("Removed", stats.get("duplicates", 0))

    return {
        "categories": categories,
        "remote_only": remote_only,
        "country": country if country != "Global" else None,
        "min_score": min_score,
        "upcoming_only": upcoming_only,
        "has_prize": has_prize,
        "sort_by": sort_by
    }


def apply_filters(opps: List[Dict], filters: Dict) -> List[Dict]:
    """Apply active filters to opportunity list."""
    result = opps.copy()

    # Category filter
    if filters.get("categories"):
        result = [o for o in result if o.get("category") in filters["categories"]]

    # Remote filter
    if filters.get("remote_only"):
        result = [o for o in result if o.get("is_remote", False) or
                  "remote" in str(o.get("location", "")).lower()]

    # Country filter
    if filters.get("country"):
        country = filters["country"].lower()
        result = [o for o in result
                  if country in str(o.get("country", "")).lower() or
                  country in str(o.get("location", "")).lower() or
                  str(o.get("country", "")).lower() == "global"]

    # Score filter
    min_score = filters.get("min_score", 0)
    if min_score > 0:
        result = [o for o in result if float(o.get("score", 0)) >= min_score]

    # Upcoming Deadlines filter
    if filters.get("upcoming_only"):
        import datetime
        from dateutil import parser
        
        now = datetime.datetime.now()
        filtered_result = []
        for o in result:
            deadline = str(o.get("deadline", "TBA")).lower()
            if deadline in ("tba", "rolling", "ongoing", "open"):
                filtered_result.append(o)
                continue
            
            try:
                # Try to parse the deadline.
                dt = parser.parse(deadline, fuzzy=True)
                if dt >= now:
                    filtered_result.append(o)
            except Exception:
                # If we can't parse it, keep it.
                filtered_result.append(o)
        result = filtered_result

    # Prize filter
    if filters.get("has_prize"):
        result = [o for o in result
                  if any(kw in str(o.get("rewards", "")).lower()
                        for kw in ["$", "stipend", "paid", "prize", "cash"])]

    # Sort
    sort_by = filters.get("sort_by", "Score (High→Low)")
    if sort_by == "Score (High→Low)":
        result.sort(key=lambda x: float(x.get("score", 0)), reverse=True)
    elif sort_by == "Deadline (Soonest)":
        result.sort(key=lambda x: str(x.get("deadline", "9999")))
    elif sort_by == "Launching Date (Newest)":
        result.sort(key=lambda x: str(x.get("created_at", "")), reverse=True)
    elif sort_by == "Career Impact":
        result.sort(key=lambda x: int(x.get("career_impact", 0)), reverse=True)
    elif sort_by == "Learning Impact":
        result.sort(key=lambda x: int(x.get("learning_impact", 0)), reverse=True)

    return result
