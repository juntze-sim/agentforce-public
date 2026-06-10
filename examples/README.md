# Example runs

Real, unedited output from AgentForce — so you can see what the system
produces without cloning or running it. Each run includes the generated
output (`.md`) and its full audit log (`_audit.json`) recording every
agent handoff.

## 1 & 2 — Same brief, different brand (multi-tenant)

Both runs were given the **identical** brief — *"write a product
description for a bamboo tumbler"* — with the same product metadata. The
only difference is the active brand config. The output is completely
different, on-brand for each client:

- **Terra & Clay** (warm, artisanal): leads with sensory, grounded prose
  — *"smooth, grounded… a quiet act of care, made by hand in our studio."*
- **VOLT** (bold, technical): all-caps, spec-led, conversion-driven —
  *"ENGINEERED FOR ZERO-LAG… ORDER NOW."*

This demonstrates the multi-tenant brand system: one pipeline, distinct
voices per client, driven entirely by configuration.

## 3 — Support reply with live order lookup (tool use)

A customer reports order **#4821** arrived with a mug missing. The support
agent detects the order number, calls the order-lookup tool, and writes a
reply containing the **real** customer name and item — *"Priya… the
Terracotta Ceramic Mug"* — instead of placeholders. The audit log shows
`orders_resolved=1`, confirming the tool fired.

---

Every run is scored by the manager (these landed at 82 → sample-review)
and the routing, retry, and escalation logic is described in the main
[README](../README.md).
