from __future__ import annotations
import json
import os
import re
from datetime import datetime, timezone
from langchain_ollama import ChatOllama
from langchain_core.messages import SystemMessage, HumanMessage
from schemas.state import WorkflowState, AuditEntry
from config.loader import get_brand_review_criteria

_llm = ChatOllama(model=os.getenv("OLLAMA_MODEL", "qwen3:8b"), base_url=os.getenv("OLLAMA_BASE_URL", "http://localhost:11434"), reasoning=True, temperature=0.1)

_DECOMPOSE_SYSTEM = """\
You are an e-commerce operations manager. Analyze the task brief and respond with valid JSON only — no markdown, no explanation outside the JSON.

Classify task_type as exactly one of:
  copywriting — product descriptions, marketing copy, ad content, listings, promotional content
  support     — customer inquiries, FAQs, return/refund policies, order issues, complaints
  analytics   — data analysis, metrics, KPIs, sales trends, forecasting, performance summaries,
                weekly/monthly reports, conversion analysis, revenue breakdowns, any task that
                involves interpreting numbers or generating business intelligence from data

When the brief contains quantitative data (orders, revenue, conversion rates, units sold,
ticket counts, resolution rates, etc.) and asks to summarise, report, or generate insights
from it — always classify as analytics, even if the word "summary" or "report" is used.

Decompose into 2–4 specific, actionable subtasks.

Respond with this exact JSON structure:
{
  "task_type": "copywriting",
  "decomposed_tasks": ["task 1", "task 2"],
  "reasoning": "one-line explanation"
}"""

_REVIEW_SYSTEM_BASE = """\
You are a quality assurance manager for an e-commerce platform. Review the specialist output and assign a confidence score from 0 to 100 using the rubric below.

SCORING RUBRIC (allocate points across these four dimensions):
  Content completeness (0–25 pts) : Are all subtasks addressed fully? No missing sections?
  Accuracy & specificity  (0–25 pts) : Are facts, figures, and claims correct and precise?
  Actionability           (0–25 pts) : Can the output be used immediately, or does it need heavy editing?
  Brand alignment         (0–25 pts) : Does it match the brand voice, vocabulary, and formatting rules?{brand_criteria}

FINAL SCORE THRESHOLDS:
  85–100 → auto_approve   (excellent across all dimensions, ready to publish)
  50–84  → sample_review  (acceptable, minor gaps in one or more dimensions)
  0–49   → human_review   (significant issues, needs rework before use)

Respond with valid JSON only:
{{
  "confidence_score": 82,
  "review_status": "sample_review",
  "feedback": "one or two sentence assessment citing specific strengths and gaps"
}}"""


def _build_review_system(brand_name: str = "terra_and_clay") -> str:
    brand_criteria = get_brand_review_criteria(brand_name)
    insert = f"\n{brand_criteria}" if brand_criteria else ""
    return _REVIEW_SYSTEM_BASE.format(brand_criteria=insert)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _audit(from_agent: str, to_agent: str, action: str, details: str) -> AuditEntry:
    return AuditEntry(
        timestamp=_now(),
        from_agent=from_agent,
        to_agent=to_agent,
        action=action,
        details=details,
    )


def _parse_json(text: str) -> dict:
    # Strip <think>…</think> blocks that reasoning mode may include
    text = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL)
    # Strip markdown fences
    text = re.sub(r"```(?:json)?\s*", "", text).strip().rstrip("`").strip()
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if match:
        return json.loads(match.group())
    return json.loads(text)


def manager_decompose(state: WorkflowState) -> dict:
    brief = state["task_brief"]

    response = _llm.invoke([
        SystemMessage(content=_DECOMPOSE_SYSTEM),
        HumanMessage(content=f"Task brief: {brief}"),
    ])

    parsed = _parse_json(response.content)
    task_type = parsed.get("task_type", "copywriting")
    decomposed = parsed.get("decomposed_tasks", [brief])
    reasoning = parsed.get("reasoning", "")

    audit = _audit(
        from_agent="user",
        to_agent="manager",
        action="decompose",
        details=f"type={task_type} | tasks={len(decomposed)} | {reasoning[:120]}",
    )

    return {
        "task_type": task_type,
        "decomposed_tasks": decomposed,
        "specialist_output": "",
        "confidence_score": 0,
        "review_status": "pending",
        "review_feedback": "",
        "retry_count": 0,
        "audit_log": [audit],
    }


def manager_review(state: WorkflowState) -> dict:
    task_type = state["task_type"]
    tasks = state["decomposed_tasks"]
    output = state["specialist_output"]

    response = _llm.invoke([
        SystemMessage(content=_build_review_system(state.get("brand_name") or "terra_and_clay")),
        HumanMessage(content=(
            f"Task type: {task_type}\n"
            f"Original subtasks: {json.dumps(tasks)}\n\n"
            f"Specialist output:\n{output}"
        )),
    ])

    parsed = _parse_json(response.content)
    score = max(0, min(100, int(parsed.get("confidence_score", 50))))

    # Enforce thresholds regardless of LLM label
    if score >= 85:
        status = "auto_approve"
    elif score >= 50:
        status = "sample_review"
    else:
        status = "human_review"

    feedback = parsed.get("feedback", "")

    audit = _audit(
        from_agent="manager",
        to_agent="output",
        action="review",
        details=f"score={score} | status={status} | {feedback[:140]}",
    )

    return {
        "confidence_score": score,
        "review_status": status,
        "review_feedback": feedback,
        "audit_log": [audit],
    }


def retry_prep(state: WorkflowState) -> dict:
    count = state.get("retry_count", 0) + 1
    feedback = state.get("review_feedback", "")
    task_type = state.get("task_type", "specialist")

    audit = _audit(
        from_agent="manager",
        to_agent=task_type,
        action="retry",
        details=f"attempt {count}/3 | routing back with feedback: {feedback[:120]}",
    )
    return {"retry_count": count, "audit_log": [audit]}
