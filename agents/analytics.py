from __future__ import annotations
import os
from datetime import datetime, timezone
from langchain_ollama import ChatOllama
from langchain_core.messages import SystemMessage, HumanMessage
from schemas.state import WorkflowState, AuditEntry, format_feedback
from config.loader import get_brand_context

_llm = ChatOllama(model=os.getenv("OLLAMA_MODEL", "qwen3:8b"), base_url=os.getenv("OLLAMA_BASE_URL", "http://localhost:11434"), reasoning=True, temperature=0.1)

_BASE_SYSTEM = """\
You are a senior e-commerce data analyst embedded with a small independent brand. \
You turn raw metrics into structured, actionable intelligence.

Core guidelines:
- Lead with a narrative summary before data — one to three sentences that tell the story
- Follow with key findings, root cause analysis, and prioritised recommendations
- Flag any inferred deltas or assumed baselines explicitly — never present guesses as facts
- Keep recommendations actionable within a small-team, independent-brand context
- Match the brand voice exactly as specified in the brand context below
- Address each task with a clearly labelled section heading"""


def analytics_node(state: WorkflowState) -> dict:
    brief = state["task_brief"]
    tasks = state["decomposed_tasks"]
    task_list = "\n".join(f"  • {t}" for t in tasks)

    feedback_block = format_feedback(state.get("review_feedback", ""), state.get("retry_count", 0))

    brand_ctx = get_brand_context("analytics", state.get("brand_name") or "terra_and_clay")
    system_content = f"{_BASE_SYSTEM}\n\n{brand_ctx}" if brand_ctx else _BASE_SYSTEM

    human_parts = [f"Analytics brief:\n{brief}"]
    if feedback_block:
        human_parts.append(feedback_block)
    human_parts += [
        f"Analysis tasks:\n{task_list}",
        "Provide a comprehensive, structured analysis following the brand guidelines above. "
        "Use a clear heading for each section.",
    ]

    response = _llm.invoke([
        SystemMessage(content=system_content),
        HumanMessage(content="\n\n".join(human_parts)),
    ])

    output = response.content.strip()
    brand_name = "branded" if brand_ctx else "unbranded"
    audit = AuditEntry(
        timestamp=datetime.now(timezone.utc).isoformat(),
        from_agent="analytics",
        to_agent="manager",
        action="deliver_output",
        details=f"Generated {len(output)} chars across {len(tasks)} task(s) [{brand_name}]",
    )

    return {
        "specialist_output": output,
        "audit_log": [audit],
    }
