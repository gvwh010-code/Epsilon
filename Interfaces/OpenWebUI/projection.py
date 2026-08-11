from __future__ import annotations

from copy import deepcopy
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
        model_id: str,
        base_model_id: str,
        required_tool_ids: tuple[str, ...] = (),
        required_filter_ids: tuple[str, ...] = (),
        forbidden_tool_ids: tuple[str, ...] = (),
        forbidden_filter_ids: tuple[str, ...] = (),
        forbidden_default_feature_ids: tuple[str, ...] = (),
    ):
        self.project_root = project_root
        self.client = client
        self.model_id = model_id
        self.base_model_id = base_model_id
        self.required_tool_ids = tuple(required_tool_ids)
        self.required_filter_ids = tuple(
            required_filter_ids
        )
        self.forbidden_tool_ids = tuple(
            forbidden_tool_ids
        )
        self.forbidden_filter_ids = tuple(
            forbidden_filter_ids
        )
        self.forbidden_default_feature_ids = tuple(
            forbidden_default_feature_ids
        )
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

        if self.required_tool_ids:
            remote_meta = remote_model.get("meta")

            if not isinstance(remote_meta, dict):
                reasons.append(
                    "La configuración remota 'meta' no es válida."
                )
            else:
                remote_tool_ids = remote_meta.get(
                    "toolIds"
                )

                if remote_tool_ids is None:
                    remote_tool_ids = []

                elif not isinstance(
                    remote_tool_ids,
                    list,
                ):
                    reasons.append(
                        "El campo remoto 'meta.toolIds' "
                        "no es una lista válida."
                    )
                    remote_tool_ids = None

                if remote_tool_ids is not None:
                    missing_tool_ids = [
                        tool_id
                        for tool_id
                        in self.required_tool_ids
                        if tool_id
                        not in remote_tool_ids
                    ]

                    if missing_tool_ids:
                        reasons.append(
                            "Faltan Tools requeridos por "
                            "Epsilon: "
                            + ", ".join(
                                missing_tool_ids
                            )
                            + "."
                        )

        if self.required_filter_ids:
            remote_meta = remote_model.get("meta")

            if not isinstance(remote_meta, dict):
                reason = (
                    "La configuración remota 'meta' "
                    "no es válida."
                )

                if reason not in reasons:
                    reasons.append(reason)

            else:
                remote_filter_ids = remote_meta.get(
                    "filterIds"
                )

                if remote_filter_ids is None:
                    remote_filter_ids = []

                elif not isinstance(
                    remote_filter_ids,
                    list,
                ):
                    reasons.append(
                        "El campo remoto 'meta.filterIds' "
                        "no es una lista válida."
                    )
                    remote_filter_ids = None

                if remote_filter_ids is not None:
                    missing_filter_ids = [
                        filter_id
                        for filter_id
                        in self.required_filter_ids
                        if filter_id
                        not in remote_filter_ids
                    ]

                    if missing_filter_ids:
                        reasons.append(
                            "Faltan Filters requeridos por "
                            "Epsilon: "
                            + ", ".join(
                                missing_filter_ids
                            )
                            + "."
                        )

        if self.forbidden_tool_ids:
            remote_meta = remote_model.get("meta")

            if not isinstance(remote_meta, dict):
                reason = (
                    "La configuración remota 'meta' "
                    "no es válida."
                )

                if reason not in reasons:
                    reasons.append(reason)
            else:
                remote_tool_ids = remote_meta.get(
                    "toolIds"
                )

                if remote_tool_ids is None:
                    remote_tool_ids = []

                elif not isinstance(
                    remote_tool_ids,
                    list,
                ):
                    reasons.append(
                        "El campo remoto 'meta.toolIds' "
                        "no es una lista válida."
                    )
                    remote_tool_ids = None

                if remote_tool_ids is not None:
                    forbidden_present = [
                        tool_id
                        for tool_id
                        in self.forbidden_tool_ids
                        if tool_id in remote_tool_ids
                    ]

                    if forbidden_present:
                        reasons.append(
                            "Tools no permitidos en Epsilon: "
                            + ", ".join(
                                forbidden_present
                            )
                            + "."
                        )

        if self.forbidden_filter_ids:
            remote_meta = remote_model.get("meta")

            if not isinstance(remote_meta, dict):
                reason = (
                    "La configuración remota 'meta' "
                    "no es válida."
                )

                if reason not in reasons:
                    reasons.append(reason)
            else:
                remote_filter_ids = remote_meta.get(
                    "filterIds"
                )

                if remote_filter_ids is None:
                    remote_filter_ids = []

                elif not isinstance(
                    remote_filter_ids,
                    list,
                ):
                    reasons.append(
                        "El campo remoto 'meta.filterIds' "
                        "no es una lista válida."
                    )
                    remote_filter_ids = None

                if remote_filter_ids is not None:
                    forbidden_present = [
                        filter_id
                        for filter_id
                        in self.forbidden_filter_ids
                        if filter_id
                        in remote_filter_ids
                    ]

                    if forbidden_present:
                        reasons.append(
                            "Filters no permitidos en Epsilon: "
                            + ", ".join(
                                forbidden_present
                            )
                            + "."
                        )

        if self.forbidden_default_feature_ids:
            remote_meta = remote_model.get("meta")

            if not isinstance(remote_meta, dict):
                reason = (
                    "La configuración remota 'meta' "
                    "no es válida."
                )

                if reason not in reasons:
                    reasons.append(reason)

            else:
                remote_feature_ids = remote_meta.get(
                    "defaultFeatureIds"
                )

                if remote_feature_ids is None:
                    remote_feature_ids = []

                elif not isinstance(
                    remote_feature_ids,
                    list,
                ):
                    reasons.append(
                        "El campo remoto "
                        "'meta.defaultFeatureIds' "
                        "no es una lista válida."
                    )
                    remote_feature_ids = None

                if remote_feature_ids is not None:
                    forbidden_present = [
                        feature_id
                        for feature_id
                        in self.forbidden_default_feature_ids
                        if feature_id
                        in remote_feature_ids
                    ]

                    if forbidden_present:
                        reasons.append(
                            "Features por defecto no permitidas "
                            "en Epsilon: "
                            + ", ".join(
                                forbidden_present
                            )
                            + "."
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

    def build_import_model(
        self,
        remote_model: dict[str, Any] | None,
    ) -> dict[str, Any]:
        """Construye el modelo mínimo que se enviará a Open WebUI."""

        remote_name = (
            remote_model.get("name")
            if remote_model is not None
            else None
        )

        if isinstance(remote_name, str) and remote_name.strip():
            model_name = remote_name
        else:
            model_name = "Epsilon"

        remote_is_active = (
            remote_model.get("is_active")
            if remote_model is not None
            else None
        )

        is_active = (
            remote_is_active
            if isinstance(remote_is_active, bool)
            else True
        )

        remote_meta = (
            remote_model.get("meta")
            if remote_model is not None
            else None
        )

        meta = (
            deepcopy(remote_meta)
            if isinstance(remote_meta, dict)
            else {}
        )

        if self.required_tool_ids:
            remote_tool_ids = meta.get(
                "toolIds"
            )

            tool_ids = (
                list(remote_tool_ids)
                if isinstance(
                    remote_tool_ids,
                    list,
                )
                else []
            )

            for tool_id in self.required_tool_ids:
                if tool_id not in tool_ids:
                    tool_ids.append(tool_id)

            meta["toolIds"] = tool_ids

        if self.required_filter_ids:
            remote_filter_ids = meta.get(
                "filterIds"
            )

            filter_ids = (
                list(remote_filter_ids)
                if isinstance(
                    remote_filter_ids,
                    list,
                )
                else []
            )

            for filter_id in self.required_filter_ids:
                if filter_id not in filter_ids:
                    filter_ids.append(filter_id)

            meta["filterIds"] = filter_ids

        if self.forbidden_tool_ids:
            remote_tool_ids = meta.get(
                "toolIds"
            )

            tool_ids = (
                list(remote_tool_ids)
                if isinstance(
                    remote_tool_ids,
                    list,
                )
                else []
            )

            meta["toolIds"] = [
                tool_id
                for tool_id in tool_ids
                if tool_id
                not in self.forbidden_tool_ids
            ]

        if self.forbidden_filter_ids:
            remote_filter_ids = meta.get(
                "filterIds"
            )

            filter_ids = (
                list(remote_filter_ids)
                if isinstance(
                    remote_filter_ids,
                    list,
                )
                else []
            )

            meta["filterIds"] = [
                filter_id
                for filter_id in filter_ids
                if filter_id
                not in self.forbidden_filter_ids
            ]

        if self.forbidden_default_feature_ids:
            remote_feature_ids = meta.get(
                "defaultFeatureIds"
            )

            feature_ids = (
                list(remote_feature_ids)
                if isinstance(
                    remote_feature_ids,
                    list,
                )
                else []
            )

            meta["defaultFeatureIds"] = [
                feature_id
                for feature_id in feature_ids
                if feature_id
                not in self.forbidden_default_feature_ids
            ]

        remote_params = (
            remote_model.get("params")
            if remote_model is not None
            else None
        )

        if isinstance(remote_params, dict):
            params = {
                **remote_params,
                "system": self.read_local(),
            }
        else:
            params = {
                "system": self.read_local(),
            }

        return {
            "id": self.model_id,
            "name": model_name,
            "base_model_id": self.base_model_id,
            "meta": meta,
            "params": params,
            "is_active": is_active,
        }
        
    def apply(self, expected_plan: Plan) -> None:
        """Aplica un plan previamente revisado y verifica el resultado."""

        current_plan = self.plan()

        if current_plan != expected_plan:
            raise RuntimeError(
                "El estado cambió después de construir el plan. "
                "Genera un plan nuevo antes de aplicar."
            )

        if not current_plan.has_changes:
            return

        if len(current_plan.changes) != 1:
            raise RuntimeError(
                "Projection solo puede aplicar un cambio por ejecución."
            )

        change = current_plan.changes[0]

        if (
            change.component != "projection"
            or change.resource_id != self.model_id
            or change.action not in {"create", "update"}
        ):
            raise RuntimeError(
                "El plan contiene una operación no permitida "
                "para Projection."
            )

        remote_models = self.read_remote_models()
        remote_model = self.find_remote_model(remote_models)

        if change.action == "create" and remote_model is not None:
            raise RuntimeError(
                "El plan indicaba crear el modelo, "
                "pero el modelo ya existe."
            )

        if change.action == "update" and remote_model is None:
            raise RuntimeError(
                "El plan indicaba actualizar el modelo, "
                "pero el modelo ya no existe."
            )

        desired_model = self.build_import_model(remote_model)

        self.client.import_models([desired_model])

        verification_plan = self.plan()

        if verification_plan.has_changes:
            remaining_reasons = tuple(
                reason
                for pending_change in verification_plan.changes
                for reason in pending_change.reasons
            )

            details = (
                "; ".join(remaining_reasons)
                if remaining_reasons
                else "el estado remoto todavía es diferente"
            )

            raise RuntimeError(
                "Open WebUI respondió a la importación, "
                f"pero la verificación posterior falló: {details}."
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