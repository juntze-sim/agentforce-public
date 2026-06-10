from __future__ import annotations
import os
from datetime import datetime, timezone
from langchain_ollama import ChatOllama
from langchain_core.messages import SystemMessage, HumanMessage
from schemas.state import WorkflowState, AuditEntry, format_metadata, format_feedback
from config.loader import get_brand_context
from tools.order_lookup import extract_order_ids, lookup_order, format_order_context

_llm = ChatOllama(model=os.getenv("OLLAMA_MODEL", "qwen3:8b"), base_url=os.getenv("OLLAMA_BASE_URL", "http://localhost:11434"), reasoning=False, temperature=0.2)

_BASE_SYSTEM = """\
You are an expert e-commerce customer support specialist. You handle customer \
inquiries, draft policy documentation, and create FAQ content.

Core guidelines:
- Acknowledge feelings before facts — never lead with policy
- Provide complete, actionable answers with clear next steps
- Offer no more than two resolution paths to avoid overwhelming the customer
- Match the brand voice exactly as specified in the brand context below
- Address each task with a clearly labelled section heading
- When order data is provided, use the exact values given — never invent tracking \
numbers, carrier names, delivery dates, or item details"""


def _resolve_orders(brief: str) -> tuple[list[dict], list[str]]:
    """Look up any order IDs mentioned in the brief. Returns (found_orders, missing_ids)."""
    ids = extract_order_ids(brief)
    found, missing = [], []
    for oid in ids:
        order = lookup_order(oid)
        if order:
            found.append(order)
        else:
            missing.append(oid)
    return found, missing


def support_node(state: WorkflowState) -> dict:
    brief = state["task_brief"]
    tasks = state["decomposed_tasks"]
    task_list = "\n".join(f"  • {t}" for t in tasks)
    meta_block = format_metadata(state.get("product_metadata"))
    feedback_block = format_feedback(state.get("review_feedback", ""), state.get("retry_count", 0))

    brand_ctx = get_brand_context("support", state.get("brand_name") or "terra_and_clay")
    system_content = f"{_BASE_SYSTEM}\n\n{brand_ctx}" if brand_ctx else _BASE_SYSTEM

    # Tool call: resolve any order numbers found in the brief
    found_orders, missing_ids = _resolve_orders(brief)
    order_block = format_order_context(found_orders)

    human_parts = [f"Support request / brief:\n{brief}"]
    if order_block:
        human_parts.append(order_block)
    if missing_ids:
        human_parts.append(
            f"Note: order(s) {', '.join('#' + i for i in missing_ids)} were not found in the system."
        )
    if feedback_block:
        human_parts.append(feedback_block)
    if meta_block:
        human_parts.append(meta_block)
    human_parts += [
        f"Tasks to address:\n{task_list}",
        "Provide complete, customer-ready responses following the brand guidelines above. "
        "Use a clear heading for each section.",
    ]

    response = _llm.invoke([
        SystemMessage(content=system_content),
        HumanMessage(content="\n\n".join(human_parts)),
    ])

    output = response.content.strip()
    brand_label = "branded" if brand_ctx else "unbranded"
    orders_label = f"orders_resolved={len(found_orders)}" if found_orders else "no_orders"
    audit = AuditEntry(
        timestamp=datetime.now(timezone.utc).isoformat(),
        from_agent="support",
        to_agent="manager",
        action="deliver_output",
        details=f"Generated {len(output)} chars across {len(tasks)} task(s) [{brand_label}] [{orders_label}]",
    )

    return {
        "specialist_output": output,
        "audit_log": [audit],
    }
