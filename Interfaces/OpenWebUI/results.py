from __future__ import annotations

from dataclasses import dataclass
from typing import Literal


DiagnosticStatus = Literal["ok", "warning", "error"]
ChangeAction = Literal["create", "update"]


@dataclass(frozen=True)
class DiagnosticResult:
    component: str
    status: DiagnosticStatus
    summary: str
    details: tuple[str, ...] = ()

    @property
    def failed(self) -> bool:
        return self.status == "error"


@dataclass(frozen=True)
class Change:
    """Diferencia entre el estado deseado y el estado observado."""

    component: str
    action: ChangeAction
    resource_id: str
    summary: str
    reasons: tuple[str, ...] = ()


@dataclass(frozen=True)
class Plan:
    """Cambios propuestos que todavía no han sido aplicados."""

    changes: tuple[Change, ...] = ()

    @property
    def has_changes(self) -> bool:
        return bool(self.changes)

    @property
    def create_count(self) -> int:
        return sum(
            change.action == "create"
            for change in self.changes
        )

    @property
    def update_count(self) -> int:
        return sum(
            change.action == "update"
            for change in self.changes
        )