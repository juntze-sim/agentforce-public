from __future__ import annotations
import os
from datetime import datetime, timezone
from langchain_ollama import ChatOllama
from langchain_core.messages import SystemMessage, HumanMessage
from schemas.state import WorkflowState, AuditEntry, format_metadata, format_feedback
from config.loader import get_brand_context

_llm = ChatOllama(model=os.getenv("OLLAMA_MODEL", "qwen3:8b"), base_url=os.getenv("OLLAMA_BASE_URL", "http://localhost:11434"), reasoning=False, temperature=0.3)

_BASE_SYSTEM = """\
You are a professional e-commerce copywriter. Your job is to create compelling, \
conversion-optimized content that feels authentic to the brand.

Core guidelines:
- Lead with sensory experience and emotional resonance before features
- Write in flowing prose — avoid bullet lists inside product descriptions
- Match the brand voice exactly as specified in the brand context below
- Address each task with a clearly labelled section heading
- Stay within the formatting rules provided"""


def copywriter_node(state: WorkflowState) -> dict:
    brief = state["task_brief"]
    tasks = state["decomposed_tasks"]
    task_list = "\n".join(f"  • {t}" for t in tasks)
    meta_block = format_metadata(state.get("product_metadata"))
    feedback_block = format_feedback(state.get("review_feedback", ""), state.get("retry_count", 0))

    brand_ctx = get_brand_context("copywriting", state.get("brand_name") or "terra_and_clay")
    system_content = f"{_BASE_SYSTEM}\n\n{brand_ctx}" if brand_ctx else _BASE_SYSTEM

    human_parts = [f"Original brief:\n{brief}"]
    if feedback_block:
        human_parts.append(feedback_block)
    if meta_block:
        human_parts.append(meta_block)
    human_parts += [
        f"Tasks to complete:\n{task_list}",
        "Produce polished copy for each task following the brand guidelines above. "
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
        from_agent="copywriter",
        to_agent="manager",
        action="deliver_output",
        details=f"Generated {len(output)} chars across {len(tasks)} task(s) [{brand_name}]",
    )

    return {
        "specialist_output": output,
        "audit_log": [audit],
    }
