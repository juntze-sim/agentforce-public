from __future__ import annotations
import os
import sys
from schemas.state import WorkflowState
from agents.manager import manager_decompose, manager_review
from agents.copywriter import copywriter_node
from agents.support import support_node
from agents.analytics import analytics_node
from graph import build_graph
from utils.save_outputs import save_outputs, OUTPUTS_DIR

SEP = "=" * 72
SEP_THIN = "-" * 72


def _banner(title: str) -> None:
    print(f"\n{SEP}\n  {title}\n{SEP}")


def _print_audit(log: list) -> None:
    if not log:
        return
    print(f"\n{SEP_THIN}\nAudit log:")
    for e in log:
        print(f"  [{e['timestamp']}]  {e['from_agent']} → {e['to_agent']}  |  {e['action']}")
        print(f"    {e['details']}")


def _empty_state(
    brief: str,
    metadata: dict | None = None,
    brand_name: str = "terra_and_clay",
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


# ---------------------------------------------------------------------------
# Individual agent test helpers
# ---------------------------------------------------------------------------

def _test_decompose(brief: str) -> WorkflowState:
    state = _empty_state(brief)
    result = manager_decompose(state)
    merged: WorkflowState = {**state, **result}  # type: ignore[misc]
    print(f"  Task type : {result['task_type']}")
    print(f"  Subtasks  :")
    for t in result["decomposed_tasks"]:
        print(f"    • {t}")
    _print_audit(result["audit_log"])
    return merged


def _test_specialist(label: str, fn, state: WorkflowState) -> WorkflowState:
    _banner(f"Agent test — {label}")
    result = fn(state)
    merged: WorkflowState = {**state, **result}  # type: ignore[misc]
    output = result["specialist_output"]
    preview = output[:600] + ("…" if len(output) > 600 else "")
    print(f"\nOutput preview:\n{preview}")
    _print_audit(result["audit_log"])
    return merged


def _test_review(state: WorkflowState) -> WorkflowState:
    _banner("Agent test — Manager review")
    result = manager_review(state)
    merged: WorkflowState = {**state, **result}  # type: ignore[misc]
    print(f"  Confidence score : {result['confidence_score']}")
    print(f"  Review status    : {result['review_status']}")
    _print_audit(result["audit_log"])
    return merged


# ---------------------------------------------------------------------------
# Individual agent test suite
# ---------------------------------------------------------------------------

def run_individual_tests() -> None:
    _banner("INDIVIDUAL AGENT TESTS")

    # --- Copywriter pipeline ---
    copy_brief = (
        "Write product listings for our new wireless earbuds: SportPro X1 ($89, "
        "IPX7 waterproof, 36h battery), ComfortPlus ($129, ANC, memory foam tips), "
        "and BudgetBeat ($39, stereo sound, USB-C). Emphasise value for each tier."
    )
    _banner("Agent test — Manager decompose (copywriting)")
    state_c = _test_decompose(copy_brief)
    state_c = _test_specialist("Copywriter", copywriter_node, state_c)
    _test_review(state_c)

    # --- Support pipeline ---
    support_brief = (
        "Create customer-facing FAQ answers for: "
        "(1) How do I return a damaged item? "
        "(2) What is your shipping policy for international orders? "
        "(3) How long do refunds take to process?"
    )
    _banner("Agent test — Manager decompose (support)")
    state_s = _test_decompose(support_brief)
    state_s = _test_specialist("Support", support_node, state_s)
    _test_review(state_s)

    # --- Analytics pipeline ---
    analytics_brief = (
        "Our Q2 metrics: conversion rate fell from 3.2% to 2.1%, average order "
        "value rose from $45 to $67, cart abandonment is 78%, and mobile sessions "
        "are up 40% while mobile conversion is only 0.8% vs desktop 4.2%. "
        "Identify root causes and recommend priority actions."
    )
    _banner("Agent test — Manager decompose (analytics)")
    state_a = _test_decompose(analytics_brief)
    state_a = _test_specialist("Analytics", analytics_node, state_a)
    _test_review(state_a)


# ---------------------------------------------------------------------------
# Full graph run
# ---------------------------------------------------------------------------

def run_full_graph(
    brief: str,
    label: str = "",
    metadata: dict | None = None,
    brand_name: str = "terra_and_clay",
) -> None:
    title = f"FULL GRAPH RUN{' — ' + label if label else ''}"
    _banner(title)
    print(f"Brief: {brief}")
    print(f"Brand: {brand_name}")
    if metadata:
        print(f"Metadata: {metadata}")
    print()

    graph = build_graph()
    final = graph.invoke(_empty_state(brief, metadata, brand_name))

    print(f"  Task type routed to : {final['task_type']}")
    print(f"  Confidence score    : {final['confidence_score']}")
    print(f"  Review status       : {final['review_status']}")
    output = final["specialist_output"]
    preview = output[:700] + ("…" if len(output) > 700 else "")
    print(f"\nSpecialist output preview:\n{preview}")
    _print_audit(final["audit_log"])

    md_path, audit_path = save_outputs(final)
    print(f"\n  Saved → {md_path}")
    print(f"  Saved → {audit_path}")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> None:
    args = sys.argv[1:]

    if args and args[0] == "--agents-only":
        run_individual_tests()
        return

    if args and args[0] == "--graph-only":
        brief = " ".join(args[1:]) or (
            "Write a compelling product description for our new wireless noise-cancelling headphones."
        )
        run_full_graph(brief)
        return

    # Default: individual tests, then three graph demos
    run_individual_tests()

    _banner("FULL GRAPH DEMOS")

    demos = [
        (
            "Valentine's Day product copy for our chocolate box collection: "
            "'Luxury Dark' ($55, 72% cacao, Belgian origin), "
            "'Mixed Delight' ($35, milk & white assortment), "
            "'Vegan Paradise' ($40, oat-milk base). Include hero headline + short description each.",
            "copywriting",
            None,
            "terra_and_clay",
        ),
        (
            "Draft support responses: customer order #99821 arrived with a broken item, "
            "a customer asking about our GDPR data deletion policy, "
            "and someone wanting to know if we ship to Mexico.",
            "support",
            None,
            "terra_and_clay",
        ),
        (
            "Homepage bounce rate jumped from 35% to 58% over the past 7 days. "
            "Page load time increased from 1.8s to 4.3s on mobile. "
            "New homepage hero image is 4 MB uncompressed. "
            "Analyse impact and recommend immediate and long-term fixes.",
            "analytics",
            None,
            "terra_and_clay",
        ),
    ]

    for brief, label, metadata, brand in demos:
        run_full_graph(brief, label, metadata, brand)

    # Order tool integration test: #4821 missing mug complaint
    run_full_graph(
        "Customer order #4821 arrived but the Terracotta Ceramic Mug is missing from the package. "
        "The outer box looks intact so it may not have been packed. "
        "Please draft a response to the customer.",
        "support — order #4821 missing mug",
        None,
        "terra_and_clay",
    )

    # Two-brand comparison: same bamboo tumbler brief through Terra & Clay and VOLT
    _banner("TWO-BRAND COMPARISON — Bamboo Tumbler")
    bamboo_brief = "Write a product description for a bamboo tumbler."
    bamboo_meta = {
        "price": "$34.99",
        "audience": "young professionals who commute daily",
        "specs": [
            "sustainably sourced bamboo outer shell",
            "double-wall vacuum insulation",
            "keeps drinks hot up to 12 hours, cold up to 18 hours",
            "leak-proof twist lid",
            "fits standard car cup holders",
            "BPA-free, food-safe lining",
        ],
    }
    run_full_graph(bamboo_brief, "bamboo tumbler — Terra & Clay", bamboo_meta, "terra_and_clay")
    run_full_graph(bamboo_brief, "bamboo tumbler — VOLT", bamboo_meta, "volt")


if __name__ == "__main__":
    main()
