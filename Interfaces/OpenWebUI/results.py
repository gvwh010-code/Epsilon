from dataclasses import dataclass
from typing import Literal


DiagnosticStatus = Literal["ok", "warning", "error"]


@dataclass(frozen=True)
class DiagnosticResult:
    """Resultado estructurado de una comprobación de Epsilon."""

    component: str
    status: DiagnosticStatus
    summary: str
    details: tuple[str, ...] = ()

    @property
    def failed(self) -> bool:
        return self.status == "error"