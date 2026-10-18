"""Multi-agent runtime of the radar: the Media Master and the specialists it delegates to.

Code computes every decision and every number; the LLM (Qwen3-30B via Nebius, `contracts/agents.yaml`)
chooses tools and explains in Spanish. The Auditor is deterministic: a number in an answer that no tool
returned is flagged, never shown as fact.
"""
