"""
Opportunity Card rendering — uses a single consolidated HTML block per card.
All card content is assembled into one string and rendered via st.markdown().
This prevents Streamlit from splitting the parent div and breaking the layout.
"""
import streamlit as st
from typing import List, Dict, Any
import json
from core.memory import save_bookmark, delete_bookmark, load_bookmarked_opportunity_ids


CATEGORY_EMOJI = {
    "Hackathon":         "⚡",
    "Ideathon":          "💡",
    "Internship":        "💼",
    "Open Source":       "🌐",
    "Fellowship":        "🎓",
    "Competition":       "🏆",
    "Research":          "🔬",
    "Student Program":   "🎒",
    "Developer Program": "⚙️",
}

CATEGORY_COLORS = {
    "Hackathon":         "#8b5cf6",
    "Ideathon":          "#a78bfa",
    "Internship":        "#10b981",
    "Open Source":       "#3b82f6",
    "Fellowship":        "#f59e0b",
    "Competition":       "#f43f5e",
    "Research":          "#06b6d4",
    "Student Program":   "#f97316",
    "Developer Program": "#34d399",
}


def _score_color(score: float) -> str:
    if score >= 80:   return "#10b981"
    elif score >= 60: return "#8b5cf6"
    elif score >= 40: return "#f59e0b"
    else:             return "#f43f5e"


def _parse_skills(skills_raw) -> list:
    if isinstance(skills_raw, str):
        try:
            parsed = json.loads(skills_raw)
            return parsed if isinstance(parsed, list) else [skills_raw]
        except Exception:
            return [s.strip() for s in skills_raw.split(",") if s.strip()]
    return list(skills_raw) if skills_raw else []


def _esc(text: str) -> str:
    """Escape < > & in user-provided strings before embedding in HTML."""
    return str(text).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def render_opportunity_card(opp: Dict[str, Any], show_reasoning: bool = False):
    """
    Render a single opportunity card as ONE consolidated HTML block.
    Avoids split st.markdown() calls that let Streamlit break card structure.
    """
    score       = float(opp.get("score", 0))
    category    = str(opp.get("category", "Competition"))
    cat_emoji   = CATEGORY_EMOJI.get(category, "📌")
    cat_color   = CATEGORY_COLORS.get(category, "#8b5cf6")
    sc_color    = _score_color(score)
    title       = _esc(opp.get("title", "Unknown Opportunity"))
    org         = _esc(opp.get("organization", "Unknown"))
    deadline    = _esc(opp.get("deadline", "TBA") or "TBA")
    location    = _esc(opp.get("location", "Remote") or "Remote")
    rewards     = _esc(opp.get("rewards", "") or "")
    country     = _esc(opp.get("country", "Global") or "Global")
    source      = _esc(opp.get("source", "") or "").upper()
    url         = str(opp.get("url", "") or "")
    if not url.startswith("http"):
        url = "#"
    insight     = _esc((opp.get("ai_insight") or opp.get("description") or "")[:280])
    skills      = _parse_skills(opp.get("required_skills", []))
    career_i    = int(opp.get("career_impact", 5))
    learning_i  = int(opp.get("learning_impact", 5))
    is_remote   = bool(opp.get("is_remote", True))
    loc_icon    = "🌐" if is_remote else "📍"
    score_int   = int(score)
    
    match_score = float(opp.get("match_score", 0))
    match_reason = str(opp.get("match_reason", ""))

    # ── Skill tags ──────────────────────────────────────────────────────────
    skill_tags_html = ""
    for sk in skills[:6]:
        skill_tags_html += (
            f'<code style="background:rgba(255,255,255,0.04);border:1px solid rgba(255,255,255,0.1);'
            f'border-radius:4px;padding:0.1rem 0.45rem;font-size:0.71rem;color:#8b8ba8;margin:0.1rem;">'
            f'{_esc(sk)}</code>'
        )

    # ── Reward pill (optional) ───────────────────────────────────────────────
    pill_style = (
        "display:inline-block;background:rgba(255,255,255,0.05);"
        "border:1px solid rgba(255,255,255,0.1);border-radius:100px;"
        "padding:0.18rem 0.65rem;font-size:0.74rem;color:#8b8ba8;margin:0.1rem 0.1rem 0 0;"
    )
    reward_pill = (
        f'<span style="{pill_style}">🏅 {rewards[:45]}</span>' if rewards else ""
    )
    country_pill = (
        f'<span style="{pill_style}">🌍 {country[:25]}</span>'
        if country and country.lower() != "global" else ""
    )

    # ── Apply button ─────────────────────────────────────────────────────────
    if url and url != "#":
        apply_btn = (
            f'<a href="{url}" target="_blank" style="'
            f'background:linear-gradient(135deg,#8b5cf6,#3b82f6);color:#fff;'
            f'border-radius:8px;padding:0.42rem 1.1rem;font-size:0.82rem;font-weight:700;'
            f'text-decoration:none;display:inline-block;white-space:nowrap;">'
            f'Apply Now →</a>'
        )
    else:
        apply_btn = '<span style="font-size:0.78rem;color:#5a5a72;">No link</span>'

    # ── Impact mini-stats ─────────────────────────────────────────────────
    impact_html = (
        f'<span style="font-size:1.05rem;font-weight:800;color:#8b5cf6;">{career_i}'
        f'<span style="font-size:0.58rem;color:#5a5a72;">/10</span></span>'
        f'<span style="font-size:0.6rem;color:#5a5a72;display:block;text-transform:uppercase;letter-spacing:.07em;">Career</span>'
    )
    learn_html = (
        f'<span style="font-size:1.05rem;font-weight:800;color:#3b82f6;">{learning_i}'
        f'<span style="font-size:0.58rem;color:#5a5a72;">/10</span></span>'
        f'<span style="font-size:0.6rem;color:#5a5a72;display:block;text-transform:uppercase;letter-spacing:.07em;">Learning</span>'
    )

    # ── Consolidated card HTML ────────────────────────────────────────────────
    card_html = f"""
<div class="opp-card" style="border-top: 3px solid {cat_color};">
  <div style="display:flex;align-items:flex-start;justify-content:space-between;gap:0.5rem;margin-bottom:0.5rem;">
    <div style="flex:1;min-width:0;">
      <span style="background:{cat_color}22;color:{cat_color};border:1px solid {cat_color}44;border-radius:100px;padding:0.18rem 0.75rem;font-size:0.71rem;font-weight:700;letter-spacing:.05em;text-transform:uppercase;display:inline-block;margin-bottom:0.45rem;">{cat_emoji} {_esc(category)}</span>
      <div style="font-size:1.02rem;font-weight:700;color:#f0f0f8;line-height:1.35;margin-bottom:0.2rem;">{title}</div>
      <div style="font-size:0.85rem;font-weight:600;color:{cat_color};">🏢 {org}</div>
    </div>
    <div style="text-align:right;flex-shrink:0;padding-top:0.15rem;">
      <div style="display:flex; gap:1rem; align-items:center;">
          {f'<div style="text-align:center;"><div style="font-size:1.9rem;font-weight:900;color:#06b6d4;line-height:1;">{int(match_score)}<span style="font-size:1rem">%</span></div><div style="font-size:0.58rem;color:#5a5a72;text-transform:uppercase;letter-spacing:.08em;">MATCH</div></div>' if match_score > 0 else ''}
          <div style="text-align:center;">
              <div style="font-size:1.9rem;font-weight:900;color:{sc_color};line-height:1;">{score_int}</div>
              <div style="font-size:0.58rem;color:#5a5a72;text-transform:uppercase;letter-spacing:.08em;">SCORE</div>
          </div>
      </div>
    </div>
  </div>
  <div style="margin:0.4rem 0 0.5rem;">
    <span style="{pill_style}">📅 {deadline}</span>
    <span style="{pill_style}">{loc_icon} {location[:35]}</span>
    {reward_pill}
    {country_pill}
  </div>
  {'<div style="font-size:0.84rem;color:#8b8ba8;line-height:1.65;border-left:2px solid ' + cat_color + ';padding-left:0.75rem;margin:0.5rem 0;">' + insight + ('...' if len(insight) >= 280 else '') + '</div>' if insight else ''}
  {f'<div style="font-size:0.84rem;color:#06b6d4;font-weight:600;background:rgba(6,182,212,0.1);border-radius:6px;padding:0.5rem;margin:0.5rem 0;">✨ <strong>Match Reason:</strong> {match_reason}</div>' if match_reason else ''}
  {'<div style="display:flex;flex-wrap:wrap;gap:0.25rem;margin:0.35rem 0;">' + skill_tags_html + '</div>' if skill_tags_html else ''}
  <div style="display:flex;align-items:center;justify-content:space-between;margin-top:0.7rem;">
    <div style="display:flex;gap:1.4rem;align-items:center;">
      <div style="text-align:center;">{impact_html}</div>
      <div style="text-align:center;">{learn_html}</div>
      <div style="font-size:0.67rem;color:#5a5a72;text-transform:uppercase;letter-spacing:.06em;">{source}</div>
    </div>
    <div>{apply_btn}</div>
  </div>
</div>
"""
    # Remove all leading whitespace to prevent Streamlit from rendering code blocks
    card_html = "\n".join(line.strip() for line in card_html.split("\n") if line.strip())

    st.markdown(card_html, unsafe_allow_html=True)

    # ── Action Buttons (Streamlit Native beneath Card HTML) ───────────────────
    if "bookmarked_ids" not in st.session_state:
        st.session_state.bookmarked_ids = set(load_bookmarked_opportunity_ids())

    opp_id = opp.get("id")
    is_saved = opp_id in st.session_state.bookmarked_ids
    btn_label = "❤️ Saved" if is_saved else "🖤 Save to Board"
    
    col_btn1, col_btn2, col_btn3 = st.columns([1.5, 1.5, 3])
    with col_btn1:
        if st.button(btn_label, key=f"save_{opp_id}_{opp.get('title')[:20]}"):
            if is_saved:
                delete_bookmark(opp_id)
                st.session_state.bookmarked_ids.remove(opp_id)
            else:
                save_bookmark(opp_id)
                st.session_state.bookmarked_ids.add(opp_id)
            st.rerun()

    # ── Reasoning expander (native Streamlit, outside HTML) ───────────────────
    if show_reasoning:
        ranking_r = str(opp.get("ranking_reasoning", "") or "")
        class_r   = str(opp.get("classification_reasoning", "") or "")
        why       = str(opp.get("why_it_matters", "") or "")
        who       = str(opp.get("who_should_apply", "") or "")
        if ranking_r or class_r or why or who:
            with st.expander("🔍 Agent Reasoning & Analysis"):
                if ranking_r:
                    st.markdown("**🏆 Ranking Agent**")
                    st.caption(ranking_r)
                if class_r:
                    st.markdown("**🏷️ Classification Agent**")
                    st.caption(class_r)
                if why:
                    st.markdown("**💡 Why It Matters**")
                    st.info(why)
                if who:
                    st.markdown("**👤 Who Should Apply**")
                    st.success(who)


def render_card_grid(opps: List[Dict], cols: int = 2, show_reasoning: bool = False):
    """Render a responsive grid of opportunity cards."""
    if not opps:
        st.info("No opportunities in this category yet. Run a scan to discover opportunities!")
        return

    if cols == 1:
        for opp in opps:
            render_opportunity_card(opp, show_reasoning)
    else:
        columns = st.columns(cols)
        for i, opp in enumerate(opps):
            with columns[i % cols]:
                render_opportunity_card(opp, show_reasoning)
