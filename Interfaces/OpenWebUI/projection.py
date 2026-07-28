from __future__ import annotations

from pathlib import Path
from typing import Any

from results import Change, Plan
from sync_module import SyncModule


class ProjectionManager(SyncModule):
    """Compara la proyección local con el modelo personalizado remoto."""

    name = "Projection"

    def __init__(
        self,
        project_root: Path,
        client: Any,
        model_id: str = "epsilon",
        base_model_id: str = "gemma4:12b",
    ):
        self.project_root = project_root
        self.client = client
        self.model_id = model_id
        self.base_model_id = base_model_id
        self.projection_path = (
            project_root
            / "Interfaces"
            / "OpenWebUI"
            / "EPSILON_PROJECTION.md"
        )

    def read_local(self) -> str:
        """Lee exactamente el system prompt declarado en Git."""

        return self.projection_path.read_text(encoding="utf-8")

    def read_remote_models(self) -> list[dict[str, Any]]:
        """Obtiene las definiciones exportables de Open WebUI."""

        return self.client.export_models()

    def find_remote_model(
        self,
        models: list[dict[str, Any]],
    ) -> dict[str, Any] | None:
        """Busca el modelo administrado por su identificador exacto."""

        return next(
            (
                model
                for model in models
                if model.get("id") == self.model_id
            ),
            None,
        )

    def plan(self) -> Plan:
        """Construye un plan de solo lectura para la proyección."""

        local_prompt = self.read_local()
        remote_models = self.read_remote_models()
        remote_model = self.find_remote_model(remote_models)

        if remote_model is None:
            return Plan(
                changes=(
                    Change(
                        component="projection",
                        action="create",
                        resource_id=self.model_id,
                        summary=(
                            f"Crear el modelo personalizado "
                            f"'{self.model_id}'"
                        ),
                        reasons=(
                            "El modelo no existe en el export de Open WebUI.",
                            (
                                "El modelo base deseado es "
                                f"'{self.base_model_id}'."
                            ),
                            (
                                "El system prompt provendrá de "
                                "EPSILON_PROJECTION.md."
                            ),
                        ),
                    ),
                )
            )

        reasons: list[str] = []

        remote_base_model = remote_model.get("base_model_id")

        if remote_base_model != self.base_model_id:
            reasons.append(
                "El modelo base es diferente: "
                f"remoto={remote_base_model!r}, "
                f"deseado={self.base_model_id!r}."
            )

        params = remote_model.get("params")

        if not isinstance(params, dict):
            reasons.append(
                "La configuración remota 'params' no es válida."
            )
        else:
            remote_prompt = params.get("system")

            if not isinstance(remote_prompt, str):
                reasons.append(
                    "El campo remoto 'params.system' no es texto válido."
                )
            elif remote_prompt != local_prompt:
                reasons.append(
                    "El system prompt remoto es diferente "
                    "de EPSILON_PROJECTION.md."
                )

        if not reasons:
            return Plan()

        return Plan(
            changes=(
                Change(
                    component="projection",
                    action="update",
                    resource_id=self.model_id,
                    summary=(
                        f"Actualizar el modelo personalizado "
                        f"'{self.model_id}'"
                    ),
                    reasons=tuple(reasons),
                ),
            )
        )

    def sync(self, dry_run: bool = True) -> bool:
        """Adaptador temporal para el contrato SyncModule antiguo."""

        plan = self.plan()

        if not plan.has_changes:
            print("✓ Projection sincronizada")
            return True

        for change in plan.changes:
            print(f"✗ {change.summary}")

            for reason in change.reasons:
                print(f"  - {reason}")

        if dry_run:
            print("  Dry-run: no se aplicaron cambios")
        else:
            print("  La aplicación todavía no está implementada")

        return False