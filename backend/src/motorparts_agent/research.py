"""Research route configuration skeleton without model initialization."""

from dataclasses import dataclass


@dataclass(frozen=True)
class ResearchConfiguration:
    enabled: bool = False
    provider: str | None = None


def build_research_configuration() -> ResearchConfiguration:
    """Return inert configuration; callers opt in to providers later."""
    return ResearchConfiguration()


def research_placeholder(question: str) -> dict[str, str]:
    return {
        "status": "not_configured",
        "message": "Research is not configured.",
        "question": question,
    }
