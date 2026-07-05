"""
Agent Reasoning Panel — shows decision trail for each agent.
"""
import streamlit as st
from typing import List, Dict, Any
from core.memory import load_agent_decisions


def render_reasoning_panel(scan_id: str):
    """Render the full agent reasoning trail for a scan."""
    decisions = load_agent_decisions(scan_id)
    if not decisions:
        st.info("Run a scan to see agent reasoning.")
        return

    st.markdown("### 🧠 Agent Decision Trail")
    st.markdown("*Here's how each AI agent analyzed and processed the opportunities:*")

    agent_colors = {
        "Search Planning Agent":        "#8b5cf6",
        "Opportunity Hunter Agent":     "#3b82f6",
        "Information Extraction Agent": "#06b6d4",
        "Deduplication Agent":          "#10b981",
        "Classification Agent":         "#f59e0b",
        "Opportunity Intelligence Agent": "#f97316",
        "Ranking Agent":                "#f43f5e",
    }

    for dec in decisions:
        agent_name = dec.get("agent_name", "Unknown Agent")
        color = agent_colors.get(agent_name, "#8b8ba8")

        st.markdown(f"""
        <div class="reasoning-block" style="border-color: {color}33; margin-bottom: 1rem;">
            <div style="display:flex; align-items:center; gap:0.5rem; margin-bottom:0.5rem;">
                <div style="width:8px;height:8px;border-radius:50%;background:{color};"></div>
                <div class="reasoning-agent" style="color:{color};">{agent_name}</div>
                <div style="font-size:0.7rem; color:#5a5a72; margin-left:auto;">{dec.get('timestamp','')[:19]}</div>
            </div>
            <div style="font-weight:600; font-size:0.88rem; color:#f0f0f8; margin-bottom:0.3rem;">
                {dec.get('decision','')}
            </div>
            <div class="reasoning-text">{dec.get('reasoning','')}</div>
        </div>
        """, unsafe_allow_html=True)
