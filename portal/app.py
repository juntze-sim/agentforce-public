"""AgentForce client portal — Streamlit app.

Run from the project root:
    streamlit run portal/app.py
"""
from __future__ import annotations
import json
import os
import sys
from pathlib import Path

# ── project root on sys.path ─────────────────────────────────────────────────
# Needed so imports from agents/, schemas/, config/, utils/ all resolve when
# Streamlit starts from the portal/ directory or from the project root.
_PROJECT_ROOT = Path(__file__).parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

import streamlit as st
from config.loader import load_brand_config
from graph import build_graph
from schemas.state import WorkflowState
from utils.save_outputs import save_outputs, OUTPUTS_DIR as _OUTPUTS_DIR_STR

# ── constants ────────────────────────────────────────────────────────────────
BRAND_CONFIGS_DIR = _PROJECT_ROOT / "config" / "brand_configs"
OUTPUTS_DIR = Path(_OUTPUTS_DIR_STR)


# ── helpers ──────────────────────────────────────────────────────────────────

def scan_brands() -> list[str]:
    """Return brand keys (JSON stems) sorted alphabetically."""
    return sorted(p.stem for p in BRAND_CONFIGS_DIR.glob("*.json"))


def brand_display_name(brand_key: str) -> str:
    cfg = load_brand_config(brand_key)
    return cfg.get("brand", {}).get("name", brand_key.replace("_", " ").title())


def make_initial_state(
    brief: str,
    metadata: dict | None,
    brand_name: str,
) -> WorkflowState:
    return WorkflowState(
        task_brief=brief,
        task_type="",
        decomposed_tasks=[],
        specialist_output="",
        confidence_score=0,
        review_status="pending",
        review_feedback="",
        retry_count=0,
        audit_log=[],
        product_metadata=metadata,
        brand_name=brand_name,
        error=None,
    )


def list_history() -> list[Path]:
    """Return .md output files (run summaries) sorted newest-first."""
    if not OUTPUTS_DIR.exists():
        return []
    return sorted(
        [p for p in OUTPUTS_DIR.glob("*.md")],
        key=lambda p: p.stem,
        reverse=True,
    )


def parse_stem(stem: str) -> tuple[str, str, str, str]:
    """Parse YYYY-MM-DD_HHMMSS_brand_tasktype → (date, time, brand_key, task_type)."""
    parts = stem.split("_")
    if len(parts) < 4:
        return stem, "", "", ""
    date = parts[0]
    time_raw = parts[1]           # e.g. "010923"
    task_type = parts[-1]         # always a single word
    brand_key = "_".join(parts[2:-1])
    time_str = f"{time_raw[:2]}:{time_raw[2:4]}" if len(time_raw) >= 4 else time_raw
    return date, time_str, brand_key, task_type


def load_history_result(stem: str) -> dict:
    """Load a saved run, preferring _result.json, falling back to parsing .md."""
    result_path = OUTPUTS_DIR / f"{stem}_result.json"
    if result_path.exists():
        return json.loads(result_path.read_text(encoding="utf-8"))

    # Legacy fallback: parse .md + _audit.json
    result: dict = {
        "task_brief": "", "task_type": "", "specialist_output": "",
        "confidence_score": 0, "review_status": "", "review_feedback": "",
        "retry_count": 0, "audit_log": [], "brand_name": "", "product_metadata": None,
    }
    md_path = OUTPUTS_DIR / f"{stem}.md"
    if md_path.exists():
        content = md_path.read_text(encoding="utf-8")
        for line in content.splitlines():
            if line.startswith("# "):
                result["task_type"] = line[2:].split(" — ")[0].strip()
            elif line.startswith("**Brand:**"):
                result["brand_name"] = line.replace("**Brand:**", "").strip().rstrip()
            elif line.startswith("**Brief:**"):
                result["task_brief"] = line.replace("**Brief:**", "").strip()
            elif line.startswith("**Confidence score:**"):
                try:
                    result["confidence_score"] = int(
                        line.replace("**Confidence score:**", "").strip().rstrip()
                    )
                except ValueError:
                    pass
            elif line.startswith("**Review status:**"):
                result["review_status"] = line.replace("**Review status:**", "").strip()
        if "---\n\n" in content:
            result["specialist_output"] = content.split("---\n\n", 1)[1]

    audit_path = OUTPUTS_DIR / f"{stem}_audit.json"
    if audit_path.exists():
        result["audit_log"] = json.loads(audit_path.read_text(encoding="utf-8"))

    return result


def _accumulate(base: dict, update: dict) -> dict:
    """Merge a node state-update into the accumulated state.

    audit_log uses an 'add' reducer (append semantics); all other keys replace.
    """
    merged = dict(base)
    for key, value in update.items():
        if key == "audit_log" and isinstance(value, list):
            merged[key] = merged.get(key, []) + value
        else:
            merged[key] = value
    return merged


# ── result display ───────────────────────────────────────────────────────────

_TASK_ICON = {"copywriting": "🔵", "support": "🟣", "analytics": "🟠"}
_STATUS_BADGE = {
    "auto_approve": "🟢 auto_approve",
    "sample_review": "🟡 sample_review",
    "human_review": "🔴 human_review",
    "pending": "⏳ pending",
}


def display_result(result: dict) -> None:
    """Render a completed workflow result in the main area."""
    score: int = result.get("confidence_score", 0)
    review_status: str = result.get("review_status", "")
    task_type: str = result.get("task_type", "")
    retry_count: int = result.get("retry_count", 0)

    # ── top metrics row ───────────────────────────────────────────────────────
    col1, col2, col3 = st.columns(3)
    with col1:
        score_icon = "🟢" if score >= 85 else ("🟡" if score >= 50 else "🔴")
        score_color = "normal" if score >= 85 else ("off" if score >= 50 else "inverse")
        st.metric(
            label="Confidence Score",
            value=f"{score_icon}  {score} / 100",
            delta=review_status or None,
            delta_color=score_color,
        )
    with col2:
        badge = _STATUS_BADGE.get(review_status, review_status)
        st.metric("Review Status", badge)
    with col3:
        task_icon = _TASK_ICON.get(task_type, "⚪")
        st.metric("Routed To", f"{task_icon}  {task_type or '—'}")

    if retry_count:
        st.warning(f"⚠️  {retry_count} retry(ies) occurred before final output.")

    st.divider()

    # ── specialist output ────────────────────────────────────────────────────
    st.subheader("📄 Specialist Output")
    with st.container(border=True):
        specialist_out = result.get("specialist_output", "").strip()
        if specialist_out:
            st.markdown(specialist_out)
        else:
            st.caption("_No output._")

    # ── manager feedback ─────────────────────────────────────────────────────
    feedback = result.get("review_feedback", "").strip()
    if feedback:
        st.subheader("💬 Manager Review Feedback")
        st.info(feedback)

    # ── audit log timeline ───────────────────────────────────────────────────
    audit_log: list = result.get("audit_log", [])
    if audit_log:
        with st.expander(f"📋  Audit Log  ({len(audit_log)} events)", expanded=False):
            for i, entry in enumerate(audit_log):
                ts = entry.get("timestamp", "")[:19].replace("T", " ")
                from_a = entry.get("from_agent", "")
                to_a = entry.get("to_agent", "")
                action = entry.get("action", "")
                details = entry.get("details", "")
                cols = st.columns([1, 4])
                with cols[0]:
                    st.caption(ts)
                    st.caption(f"`{from_a}` → `{to_a}`")
                with cols[1]:
                    st.markdown(f"**{action}**")
                    st.caption(details)
                if i < len(audit_log) - 1:
                    st.divider()


# ── page config ──────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="AgentForce Portal",
    page_icon="🤖",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── session state ─────────────────────────────────────────────────────────────
if "history_result" not in st.session_state:
    st.session_state.history_result = None
if "history_stem" not in st.session_state:
    st.session_state.history_stem = None
if "live_result" not in st.session_state:
    st.session_state.live_result = None

# ── sidebar ───────────────────────────────────────────────────────────────────
with st.sidebar:
    st.title("🤖 AgentForce")

    brand_tab, history_tab = st.tabs(["🏷️ Brand", "🕐 History"])

    with brand_tab:
        brand_keys = scan_brands()
        selected_brand: str = st.selectbox(
            "Select Brand",
            brand_keys,
            format_func=brand_display_name,
            key="selected_brand",
        )
        cfg = load_brand_config(selected_brand)
        if cfg:
            b = cfg.get("brand", {})
            st.markdown(f"**{b.get('tagline', '')}**")
            st.caption(b.get("mission", ""))

    with history_tab:
        history_files = list_history()
        if not history_files:
            st.info("No previous runs yet.")
        else:
            for md_file in history_files:
                stem = md_file.stem
                date, time_str, brand_key, task_type = parse_stem(stem)
                brand_label = brand_display_name(brand_key) if brand_key else brand_key
                task_icon = _TASK_ICON.get(task_type, "⚪")
                label = f"{date} {time_str}\n{task_icon} {brand_label} · {task_type}"
                if st.button(
                    label,
                    key=f"hist_{stem}",
                    use_container_width=True,
                    type="secondary",
                ):
                    st.session_state.history_result = load_history_result(stem)
                    st.session_state.history_stem = stem
                    st.session_state.live_result = None
                    st.rerun()

# ── main area ─────────────────────────────────────────────────────────────────

# ── viewing a historical run ──────────────────────────────────────────────────
if st.session_state.history_result is not None:
    hist = st.session_state.history_result
    stem = st.session_state.history_stem or ""
    _, time_str, brand_key, task_type = parse_stem(stem)

    col_title, col_back = st.columns([5, 1])
    with col_title:
        st.title(f"📂  History · {stem[:16]}")
        brief_text = hist.get("task_brief", "")
        if brief_text:
            with st.expander("Brief", expanded=False):
                st.write(brief_text)
    with col_back:
        st.write("")  # vertical spacing
        if st.button("← New Run", type="primary"):
            st.session_state.history_result = None
            st.session_state.history_stem = None
            st.rerun()

    st.divider()
    display_result(hist)

# ── new run form ──────────────────────────────────────────────────────────────
else:
    st.title("📋  Client Brief")

    brief = st.text_area(
        "Brief",
        height=160,
        placeholder=(
            "Describe the task in plain language.\n"
            "Example: Write a product description for a bamboo tumbler."
        ),
        label_visibility="collapsed",
    )

    with st.expander("📦  Product Metadata", expanded=False):
        price = st.text_input("Price", placeholder="$34.99")
        audience = st.text_input(
            "Target Audience",
            placeholder="young professionals who commute daily",
        )
        specs_raw = st.text_area(
            "Specs  (one per line)",
            placeholder=(
                "sustainably sourced bamboo outer shell\n"
                "double-wall vacuum insulation\n"
                "keeps drinks hot up to 12 hours, cold up to 18 hours"
            ),
            height=140,
        )

    run_clicked = st.button("🚀  Run Agent Cluster", type="primary", use_container_width=False)

    if run_clicked:
        if not brief.strip():
            st.error("Please enter a client brief before running.")
            st.stop()

        # Build metadata — None if all three fields empty
        price_v = price.strip()
        audience_v = audience.strip()
        specs_v = [s.strip() for s in specs_raw.splitlines() if s.strip()]
        metadata = (
            {"price": price_v, "audience": audience_v, "specs": specs_v}
            if (price_v or audience_v or specs_v)
            else None
        )

        initial_state = make_initial_state(brief.strip(), metadata, selected_brand)
        graph = build_graph()

        final_state = dict(initial_state)

        try:
            with st.status("Running agent cluster…", expanded=True) as run_status:
                run_status.write("🔍  Manager decomposing brief…")
                for chunk in graph.stream(initial_state):
                    node_name, node_update = next(iter(chunk.items()))
                    final_state = _accumulate(final_state, node_update)

                    if node_name == "manager_decompose":
                        task_t = node_update.get("task_type", "")
                        run_status.write(
                            f"✅  Decomposed → routed to **{task_t}** specialist"
                        )
                    elif node_name == "copywriter":
                        run_status.write("✍️  Copywriter specialist working…")
                    elif node_name == "support":
                        run_status.write("🎧  Support specialist working…")
                    elif node_name == "analytics":
                        run_status.write("📊  Analytics specialist working…")
                    elif node_name == "manager_review":
                        run_status.write("📋  Manager reviewing output…")
                    elif node_name == "retry_prep":
                        retry_n = final_state.get("retry_count", "?")
                        run_status.write(f"🔄  Quality threshold not met — retry {retry_n}…")

                run_status.update(label="✅  Complete!", state="complete")

        except Exception as exc:
            st.error(f"Pipeline error: {exc}")
            st.stop()

        # ── save and display ──────────────────────────────────────────────────
        md_path, _ = save_outputs(final_state)  # type: ignore[arg-type]
        st.session_state.live_result = final_state

        saved_name = Path(md_path).name
        st.success(f"Saved → `{saved_name}`")
        st.divider()

        brief_preview = brief.strip()[:120] + ("…" if len(brief.strip()) > 120 else "")
        st.caption(f"Brief: {brief_preview}")
        display_result(final_state)
