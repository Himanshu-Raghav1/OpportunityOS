"""
LangGraph StateGraph — wires all agents into the pipeline.
Hunter is split into 4 sub-nodes for live streaming progress in the UI.
"""
from __future__ import annotations
from langgraph.graph import StateGraph, END
from core.state import AgentState
from agents.agent_01_planner import run_planner
from agents.agent_02_hunter import (
    run_hunter_firecrawl,
    run_hunter_web_search,
    run_hunter_live_apis,
    run_hunter_finalize,
)
from agents.agent_03_extractor import run_extractor
from agents.agent_04_deduplicator import run_deduplicator
from agents.agent_05_classifier import run_classifier
from agents.agent_06_intelligence import run_intelligence
from agents.agent_07_ranker import run_ranker
from agents.agent_08_evaluator import run_evaluator


def build_graph() -> StateGraph:
    """Build and compile the OpportunityOS multi-agent graph."""
    graph = StateGraph(AgentState)

    graph.add_node("planner",           run_planner)
    graph.add_node("hunter_firecrawl",  run_hunter_firecrawl)
    graph.add_node("hunter_web_search", run_hunter_web_search)
    graph.add_node("hunter_live_apis",  run_hunter_live_apis)
    graph.add_node("hunter_finalize",   run_hunter_finalize)
    graph.add_node("extractor",         run_extractor)
    graph.add_node("deduplicator",      run_deduplicator)
    graph.add_node("classifier",        run_classifier)
    graph.add_node("intelligence",      run_intelligence)
    graph.add_node("ranker",            run_ranker)
    graph.add_node("evaluator",         run_evaluator)

    graph.set_entry_point("planner")
    graph.add_edge("planner",           "hunter_firecrawl")
    graph.add_edge("hunter_firecrawl",  "hunter_web_search")
    graph.add_edge("hunter_web_search", "hunter_live_apis")
    graph.add_edge("hunter_live_apis",  "hunter_finalize")
    graph.add_edge("hunter_finalize",   "extractor")
    graph.add_edge("extractor",         "deduplicator")
    graph.add_edge("deduplicator",      "classifier")
    graph.add_edge("classifier",        "intelligence")
    graph.add_edge("intelligence",      "ranker")
    graph.add_edge("ranker",            "evaluator")
    graph.add_edge("evaluator",         END)

    return graph.compile()


_graph = None


def get_graph():
    global _graph
    if _graph is None:
        _graph = build_graph()
    return _graph
