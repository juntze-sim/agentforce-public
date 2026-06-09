from __future__ import annotations
import json
from functools import lru_cache
from pathlib import Path

_BRAND_CONFIGS_DIR = Path(__file__).parent / "brand_configs"
_DEFAULT_BRAND = "terra_and_clay"


@lru_cache(maxsize=8)
def load_brand_config(brand_name: str = _DEFAULT_BRAND) -> dict:
    path = _BRAND_CONFIGS_DIR / f"{brand_name}.json"
    if not path.exists():
        return {}
    with path.open() as f:
        return json.load(f)


def get_brand_context(task_type: str, brand_name: str = _DEFAULT_BRAND) -> str:
    """Return a formatted brand-context block for injection into agent system prompts."""
    cfg = load_brand_config(brand_name)
    if not cfg:
        return ""

    brand = cfg["brand"]
    voice = cfg["voice"]
    vocab = cfg["vocabulary"]
    tone_general = cfg["tone_rules"]["general"]
    tone_specific = cfg["tone_rules"].get(task_type, [])
    fmt = cfg["formatting"].get(task_type, {})

    lines = [
        "─" * 60,
        f"BRAND: {brand['name']} — {brand['tagline']}",
        f"Store: {brand['store_type']}",
        f"Mission: {brand['mission']}",
        "",
        f"VOICE & PERSONALITY",
        f"  Traits     : {', '.join(voice['primary_traits'])}",
        f"  Personality: {voice['personality']}",
        "",
        "TONE RULES (general):",
        *[f"  • {r}" for r in tone_general],
    ]

    if tone_specific:
        lines += [
            f"\nTONE RULES (for {task_type}):",
            *[f"  • {r}" for r in tone_specific],
        ]

    lines += [
        "",
        f"PREFERRED WORDS: {', '.join(vocab['preferred'])}",
        f"WORDS TO AVOID:  {', '.join(vocab['avoid'])}",
    ]

    if fmt:
        lines.append("\nFORMATTING RULES:")
        for key, value in fmt.items():
            lines.append(f"  {key}: {value}")

    lines.append("─" * 60)
    return "\n".join(lines)


def get_brand_review_criteria(brand_name: str = _DEFAULT_BRAND) -> str:
    """Return a brand-alignment rubric section for the manager review prompt."""
    cfg = load_brand_config(brand_name)
    if not cfg:
        return ""

    brand = cfg["brand"]
    voice = cfg["voice"]
    avoid = cfg["vocabulary"]["avoid"]
    preferred = cfg["vocabulary"]["preferred"]
    traits = ", ".join(voice["primary_traits"])

    return (
        f"\nBRAND ALIGNMENT (score this as one of your rubric dimensions):\n"
        f"  Brand: {brand['name']} — voice is {traits}\n"
        f"  Check: Does the output match the brand personality? "
        f"({voice['personality']})\n"
        f"  Check: Does it use preferred vocabulary? (e.g. {', '.join(preferred[:6])})\n"
        f"  Check: Does it avoid banned words? (e.g. {', '.join(avoid[:6])})\n"
        f"  Check: Is the tone consistent with the brand voice — {traits}?\n"
        f"  Penalise: vocabulary from the avoid list, off-brand tone, or generic e-commerce language.\n"
        f"  Reward: adherence to the brand's formatting rules and vocabulary preferences.\n"
    )
