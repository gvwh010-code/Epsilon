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


@dataclass(frozen=True)
class KnowledgeDiffResult:
    """Comparación estructurada de una fuente Knowledge."""

    source_name: str
    kb_id: str

    added: int = 0
    modified: int = 0
    deleted: int = 0
    unmodified: int = 0

    dirs_created: int = 0
    dirs_removed: int = 0

    warnings: tuple[str, ...] = ()
    errors: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        counters = (
            self.added,
            self.modified,
            self.deleted,
            self.unmodified,
            self.dirs_created,
            self.dirs_removed,
        )

        if any(
            not isinstance(value, int) or value < 0
            for value in counters
        ):
            raise ValueError(
                "Los contadores de Knowledge deben ser "
                "números enteros no negativos."
            )

    @property
    def failed(self) -> bool:
        return bool(self.errors)

    @property
    def file_changes(self) -> int:
        return (
            self.added
            + self.modified
            + self.deleted
        )

    @property
    def directory_changes(self) -> int:
        return (
            self.dirs_created
            + self.dirs_removed
        )

    @property
    def total_changes(self) -> int:
        return (
            self.file_changes
            + self.directory_changes
        )

    @property
    def has_changes(self) -> bool:
        return self.total_changes > 0

    @property
    def has_destructive_changes(self) -> bool:
        return (
            self.deleted > 0
            or self.dirs_removed > 0
        )