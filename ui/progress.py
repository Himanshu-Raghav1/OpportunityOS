"""
Real-time agent progress display component.
Shows each agent's status with animated indicators.
"""
import streamlit as st
from typing import List


AGENT_STEPS = [
    ("🧠", "Search Planning Agent",         "Creating search strategy..."),
    ("🔍", "Opportunity Hunter Agent",       "Scanning sources across the web..."),
    ("📋", "Information Extraction Agent",   "Extracting structured data..."),
    ("🔄", "Deduplication Agent",            "Removing duplicate entries..."),
    ("🏷️",  "Classification Agent",          "Categorizing opportunities..."),
    ("💡", "Opportunity Intelligence Agent", "Generating AI insights..."),
    ("🏆", "Ranking Agent",                  "Scoring and ranking all opportunities..."),
]


def render_progress(current_step: int, messages: List[str]):
    """
    Renders the real-time agent progress panel.
    current_step: 0-7 (0 = not started, 7 = done)
    messages: accumulated progress messages
    """
    st.markdown("### 🤖 Agent Execution Pipeline")

    progress_val = min(current_step / len(AGENT_STEPS), 1.0)
    st.progress(progress_val)

    for i, (emoji, name, desc) in enumerate(AGENT_STEPS):
        if i < current_step:
            status = "✅"
            css = ""
        elif i == current_step:
            status = "⚡"
            css = "active"
        else:
            status = "⏳"
            css = ""

        st.markdown(
            f'<div class="agent-log {css}">'
            f'{status} <strong>{emoji} {name}</strong><br>'
            f'<span style="padding-left:1.5rem;">{desc}</span>'
            f'</div>',
            unsafe_allow_html=True
        )

    # Recent log messages
    if messages:
        with st.expander("📜 Live Agent Logs", expanded=True):
            log_text = "\n".join(messages[-20:])  # Show last 20
            st.markdown(
                f'<div style="font-family: JetBrains Mono, monospace; font-size: 0.8rem; '
                f'color: #8b8ba8; line-height: 1.8;">{log_text}</div>',
                unsafe_allow_html=True
            )
