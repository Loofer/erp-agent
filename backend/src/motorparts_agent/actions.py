"""Explicit representation of a staged state-changing operation."""

from dataclasses import dataclass


@dataclass(frozen=True)
class PendingAction:
    operation_name: str
    method: str
    path: str
    query: dict[str, object]
    body: dict[str, object] | None
