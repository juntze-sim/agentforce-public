from __future__ import annotations
import json
import re
from functools import lru_cache
from pathlib import Path

_DATA_PATH = Path(__file__).parent.parent / "data" / "mock_orders.json"


@lru_cache(maxsize=1)
def _load_orders() -> dict[str, dict]:
    with _DATA_PATH.open() as f:
        orders = json.load(f)
    return {o["order_id"]: o for o in orders}


def lookup_order(order_id: str) -> dict | None:
    """Return order data for the given order ID, or None if not found.

    Accepts bare digits ('4821'), hash-prefixed ('#4821'), or padded strings.
    """
    normalised = re.sub(r"[#\s]", "", order_id).lstrip("0") or order_id.strip()
    orders = _load_orders()
    # try exact match first, then leading-zero-stripped key
    return orders.get(normalised) or orders.get(order_id.strip())


def extract_order_ids(text: str) -> list[str]:
    """Return all order IDs found in *text* (matches #NNNNN or 'order NNNNN')."""
    pattern = r"(?:order\s*#?\s*|#)(\d{4,6})\b"
    return re.findall(pattern, text, flags=re.IGNORECASE)


def format_order_context(orders: list[dict]) -> str:
    """Render a list of looked-up orders as a structured prompt block."""
    if not orders:
        return ""
    sep = "─" * 56
    lines = [
        sep,
        "ORDER DATA (authoritative — use these exact values, do not invent or estimate):",
    ]
    for o in orders:
        items_str = ", ".join(
            f"{item} × {qty}"
            for item, qty in zip(o["items"], o["quantities"])
        )
        lines += [
            sep,
            f"  Order #     : {o['order_id']}",
            f"  Customer    : {o['customer_name']} <{o['customer_email']}>",
            f"  Items       : {items_str}",
            f"  Total       : ${o['total']:.2f}",
            f"  Status      : {o['status']}",
            f"  Carrier     : {o['shipping_carrier'] or 'N/A'}",
            f"  Tracking    : {o['tracking_number'] or 'N/A'}",
            f"  Order date  : {o['order_date']}",
            f"  Delivered   : {o['delivery_date'] or 'Not yet delivered'}",
        ]
    lines.append(sep)
    return "\n".join(lines)
