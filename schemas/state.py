from __future__ import annotations
from typing import TypedDict, Annotated, List, Optional
from operator import add


def format_feedback(review_feedback: str, retry_count: int) -> str:
    """Render the manager's review feedback as a revision-request block for agents."""
    if not review_feedback or retry_count == 0:
        return ""
    attempt = retry_count + 1
    return (
        f"REVISION REQUEST — attempt {attempt} of 3:\n"
        f"Your previous submission scored below the quality threshold.\n"
        f"Manager feedback: {review_feedback}\n"
        f"Address these specific issues. Do not repeat the same mistakes."
    )


def format_metadata(metadata: dict | None) -> str:
    """Render product_metadata as a structured prompt block for agents."""
    if not metadata:
        return ""
    lines = [
        "Product metadata (authoritative — use these values precisely, do not re-parse the brief):"
    ]
    for key, value in metadata.items():
        if isinstance(value, list):
            lines.append(f"  {key}:")
            lines.extend(f"    - {item}" for item in value)
        else:
            lines.append(f"  {key}: {value}")
    return "\n".join(lines)


class AuditEntry(TypedDict):
    timestamp: str
    from_agent: str
    to_agent: str
    action: str
    details: str


class WorkflowState(TypedDict):
    task_brief: str
    task_type: str              # copywriting | support | analytics
    decomposed_tasks: List[str]
    specialist_output: str
    confidence_score: int       # 0–100
    review_status: str          # auto_approve | sample_review | human_review | pending
    review_feedback: str        # manager's written feedback, passed to specialist on retry
    retry_count: int            # incremented by retry_prep; capped at 2 retries
    audit_log: Annotated[List[AuditEntry], add]
    product_metadata: Optional[dict]  # e.g. {"price": "$34.99", "audience": "...", "specs": [...]}
    brand_name: str             # key matching a file in config/brand_configs/
    error: Optional[str]
