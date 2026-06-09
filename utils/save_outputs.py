"""Shared output-saving utilities — used by run.py and portal/app.py."""
from __future__ import annotations
import json
import os
from datetime import datetime
from schemas.state import WorkflowState

# Resolved relative to this file so both run.py (project root) and
# portal/app.py (one level down) get the same outputs/ directory.
OUTPUTS_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "outputs")


def save_outputs(final: WorkflowState) -> tuple[str, str]:
    """Persist a completed workflow state to outputs/.

    Writes three files:
      {stem}.md           — human-readable summary
      {stem}_audit.json   — audit log array
      {stem}_result.json  — full state snapshot (used by the portal history view)

    Returns (md_path, audit_path).
    """
    os.makedirs(OUTPUTS_DIR, exist_ok=True)
    ts = datetime.now().strftime("%Y-%m-%d_%H%M%S")
    brand = (final.get("brand_name") or "unknown").replace(" ", "_")
    task_type = (final.get("task_type") or "unknown").replace(" ", "_")
    stem = f"{ts}_{brand}_{task_type}"

    # ── markdown summary ─────────────────────────────────────────────────────
    md_path = os.path.join(OUTPUTS_DIR, f"{stem}.md")
    with open(md_path, "w", encoding="utf-8") as f:
        f.write(f"# {task_type} — {ts}\n\n")
        f.write(f"**Brand:** {brand}  \n")
        f.write(f"**Brief:** {final['task_brief']}\n\n")
        f.write(f"**Confidence score:** {final['confidence_score']}  \n")
        f.write(f"**Review status:** {final['review_status']}\n\n")
        f.write("---\n\n")
        f.write(final["specialist_output"])

    # ── audit log ────────────────────────────────────────────────────────────
    audit_path = os.path.join(OUTPUTS_DIR, f"{stem}_audit.json")
    with open(audit_path, "w", encoding="utf-8") as f:
        json.dump(final["audit_log"], f, indent=2, ensure_ascii=False)

    # ── full state snapshot (portal history) ─────────────────────────────────
    result_path = os.path.join(OUTPUTS_DIR, f"{stem}_result.json")
    with open(result_path, "w", encoding="utf-8") as f:
        json.dump(dict(final), f, indent=2, ensure_ascii=False, default=str)

    return md_path, audit_path
