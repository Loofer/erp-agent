"""Agent state and explicit representations of staged operations."""

from copy import deepcopy
from dataclasses import dataclass


@dataclass(frozen=True)
class PendingAction:
    operation_name: str
    method: str
    path: str
    query: dict[str, object]
    body: dict[str, object] | None

    def __post_init__(self) -> None:
        """Detach a staged action from the mutable input supplied by callers."""
        object.__setattr__(self, "query", deepcopy(self.query))
        object.__setattr__(self, "body", deepcopy(self.body))
