from __future__ import annotations
from langgraph.graph import StateGraph, START, END
from schemas.state import WorkflowState
from agents.manager import manager_decompose, manager_review, retry_prep
from agents.copywriter import copywriter_node
from agents.support import support_node
from agents.analytics import analytics_node


def _route_to_specialist(state: WorkflowState) -> str:
    task_type = state.get("task_type", "copywriting")
    if task_type == "support":
        return "support"
    if task_type == "analytics":
        return "analytics"
    return "copywriter"


def _route_after_review(state: WorkflowState) -> str:
    status = state.get("review_status", "human_review")
    if status == "auto_approve":
        return "auto_approve"
    if status == "sample_review":
        return "sample_review"
    # score < 50: retry if budget remains, otherwise escalate
    if state.get("retry_count", 0) < 2:
        return "retry"
    return "human_review"


def build_graph() -> StateGraph:
    builder = StateGraph(WorkflowState)

    builder.add_node("manager_decompose", manager_decompose)
    builder.add_node("copywriter", copywriter_node)
    builder.add_node("support", support_node)
    builder.add_node("analytics", analytics_node)
    builder.add_node("manager_review", manager_review)
    builder.add_node("retry_prep", retry_prep)

    builder.add_edge(START, "manager_decompose")

    # Initial dispatch: manager → specialist
    builder.add_conditional_edges(
        "manager_decompose",
        _route_to_specialist,
        {"copywriter": "copywriter", "support": "support", "analytics": "analytics"},
    )

    # All specialists feed into review
    builder.add_edge("copywriter", "manager_review")
    builder.add_edge("support", "manager_review")
    builder.add_edge("analytics", "manager_review")

    # Review exit: approve/sample → done; low score → retry or escalate
    builder.add_conditional_edges(
        "manager_review",
        _route_after_review,
        {
            "auto_approve": END,
            "sample_review": END,
            "retry": "retry_prep",
            "human_review": END,
        },
    )

    # Retry dispatch: increment counter, then back to the same specialist
    builder.add_conditional_edges(
        "retry_prep",
        _route_to_specialist,
        {"copywriter": "copywriter", "support": "support", "analytics": "analytics"},
    )

    return builder.compile()
