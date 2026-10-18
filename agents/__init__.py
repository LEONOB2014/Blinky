"""Multi-agent runtime of the radar: the Media Master and the specialists it delegates to.

Code computes every decision and every number; the LLM (Qwen3-30B via Nebius, `contracts/agents.yaml`)
chooses tools and explains in Spanish. The Auditor is deterministic: a number in an answer that no tool
returned is flagged, never shown as fact.
"""

from dotenv import load_dotenv

from radar.paths import REPO_ROOT

# Load .env before anything is traced: the LangSmith SDK reads LANGSMITH_TRACING once and caches it.
load_dotenv(REPO_ROOT / ".env")
