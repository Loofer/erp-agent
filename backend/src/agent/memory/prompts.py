"""Versioned prompt composition for the primary Deep Agents runtime."""

SYSTEM_IDENTITY = "You are a motor-parts procurement assistant."
OPERATING_CONSTRAINTS = (
    "Use only the provided tools for ERP data and explain when a capability is "
    "not configured. State-changing supplier requests require human approval "
    "before execution."
)


def build_system_prompt() -> str:
    """Return the stable instructions supplied to the primary Deep Agent."""
    return f"{SYSTEM_IDENTITY} {OPERATING_CONSTRAINTS}"
