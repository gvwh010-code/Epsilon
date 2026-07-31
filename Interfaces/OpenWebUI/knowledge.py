from __future__ import annotations

from contextlib import contextmanager
from copy import deepcopy
from dataclasses import dataclass
import fcntl
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import time
from typing import Any, Iterator

from config import Config

from results import (
    KnowledgeAddedFile,
    KnowledgeDeletedFile,
    KnowledgeDiffResult,
    KnowledgeModifiedFile,
    KnowledgeSyncResult,
)

from sync_module import SyncModule

from knowledge_target import (
    KnowledgeSlot,
    KnowledgeTarget,
    load_knowledge_target,
)

class KnowledgeManagerError(RuntimeError):
    """Error controlado al comparar Knowledge mediante oikb."""

@dataclass(frozen=True)
class KnowledgeCandidatePlan:
    """Plan de despliegue hacia el slot inactivo."""

    active_slot: KnowledgeSlot
    candidate_slot: KnowledgeSlot
    diff: KnowledgeDiffResult

class KnowledgeManager(SyncModule):
    """Compara Knowledge local con Open WebUI sin modificarlo."""

    name = "Knowledge"

    verification_retry_delays = (
        0.0,
        0.5,
        1.0,
        2.0,
        4.0,
    )

    def __init__(
        self,
        project_root: Path,
        config: Config,
        client: Any,
        source_name: str = "epsilon-system",
        timeout_seconds: float = 120.0,
    ):
        self.project_root = project_root.resolve()
        self.config = config
        self.client = client
        self.source_name = source_name
        self.timeout_seconds = timeout_seconds

        interface_dir = (
            self.project_root
            / "Interfaces"
            / "OpenWebUI"
        )

        self.manifest_path = (
            interface_dir
            / "knowledge_manifest.txt"
        )

        self.target_path = (
            interface_dir
            / "knowledge_target.json"
        )

        self.bridge_path = (
            interface_dir
            / "oikb_bridge.py"
        )

        venv_dir = interface_dir / ".venv"

        candidates = (
            venv_dir / "bin" / "python3",
            venv_dir / "Scripts" / "python.exe",
        )

        self.python_executable = next(
            (
                candidate
                for candidate in candidates
                if candidate.is_file()
            ),
            None,
        )

        if self.python_executable is None:
            raise FileNotFoundError(
                "No se encontró el Python ejecutable "
                "del entorno virtual de oikb."
            )

        if not self.bridge_path.is_file():
            raise FileNotFoundError(
                f"No se encontró el adaptador: {self.bridge_path}"
            )

        if not self.target_path.is_file():
            raise FileNotFoundError(
                "No se encontró la configuración de destino: "
                f"{self.target_path}"
            )

        if not self.manifest_path.is_file():
            raise FileNotFoundError(
                f"No se encontró el manifiesto: {self.manifest_path}"
            )

    def _load_target(self) -> KnowledgeTarget:
        """Carga y valida la configuración Blue–Green."""

        target = load_knowledge_target(
            self.target_path
        )

        if target.source_name != self.source_name:
            raise KnowledgeManagerError(
                "La configuración de Knowledge declara "
                "una fuente diferente de la esperada."
            )

        return target

    def _active_slot(
        self,
        target: KnowledgeTarget,
    ) -> KnowledgeSlot:
        """Identifica el slot conectado actualmente al modelo."""

        models = self.client.export_models()

        model = next(
            (
                item
                for item in models
                if item.get("id") == target.model_id
            ),
            None,
        )

        if model is None:
            raise KnowledgeManagerError(
                f"No existe el modelo {target.model_id!r} "
                "configurado para Knowledge."
            )

        meta = model.get("meta")

        if not isinstance(meta, dict):
            raise KnowledgeManagerError(
                "El modelo activo no contiene metadatos válidos."
            )

        attached_knowledge = meta.get("knowledge")

        if not isinstance(attached_knowledge, list):
            raise KnowledgeManagerError(
                "El modelo activo no contiene una lista "
                "válida de Knowledge."
            )

        attached_ids = {
            item.get("id")
            for item in attached_knowledge
            if (
                isinstance(item, dict)
                and isinstance(item.get("id"), str)
            )
        }

        active_slots = tuple(
            slot
            for slot in target.slots
            if slot.kb_id in attached_ids
        )

        if len(active_slots) != 1:
            raise KnowledgeManagerError(
                "El modelo debe tener conectado exactamente "
                "uno de los slots blue o green."
            )

        return active_slots[0]


    @staticmethod
    def _build_candidate_knowledge_entry(
        active_entry: dict[str, Any],
        candidate_record: dict[str, Any],
        candidate_slot: KnowledgeSlot,
    ) -> dict[str, Any]:
        """Construye la entrada conectable del slot candidato."""

        if not isinstance(active_entry, dict):
            raise KnowledgeManagerError(
                "La entrada Knowledge activa no es válida."
            )

        if not isinstance(candidate_record, dict):
            raise KnowledgeManagerError(
                "La respuesta del slot candidato no es válida."
            )

        candidate_id = candidate_record.get("id")

        if candidate_id != candidate_slot.kb_id:
            raise KnowledgeManagerError(
                "Open WebUI devolvió una Knowledge diferente "
                "del slot candidato configurado."
            )

        active_user_id = active_entry.get("user_id")
        candidate_user_id = candidate_record.get("user_id")

        if (
            not isinstance(active_user_id, str)
            or not active_user_id.strip()
            or not isinstance(candidate_user_id, str)
            or not candidate_user_id.strip()
        ):
            raise KnowledgeManagerError(
                "No fue posible validar el propietario de "
                "los slots Knowledge."
            )

        if active_user_id != candidate_user_id:
            raise KnowledgeManagerError(
                "Los slots activo y candidato pertenecen "
                "a propietarios diferentes."
            )

        if candidate_record.get("write_access") is not True:
            raise KnowledgeManagerError(
                "La API key no tiene acceso de escritura "
                "al slot candidato."
            )

        text_fields = (
            "id",
            "user_id",
            "name",
            "description",
        )

        for field_name in text_fields:
            value = candidate_record.get(field_name)

            if not isinstance(value, str):
                raise KnowledgeManagerError(
                    "El slot candidato contiene un campo "
                    f"{field_name!r} inválido."
                )

            if (
                field_name != "description"
                and not value.strip()
            ):
                raise KnowledgeManagerError(
                    "El slot candidato contiene un campo "
                    f"{field_name!r} vacío."
                )

        meta = candidate_record.get("meta")

        if meta is not None and not isinstance(meta, dict):
            raise KnowledgeManagerError(
                "El slot candidato contiene meta inválido."
            )

        access_grants = candidate_record.get(
            "access_grants"
        )

        if (
            not isinstance(access_grants, list)
            or not all(
                isinstance(item, dict)
                for item in access_grants
            )
        ):
            raise KnowledgeManagerError(
                "El slot candidato contiene "
                "access_grants inválidos."
            )

        for field_name in (
            "created_at",
            "updated_at",
        ):
            value = candidate_record.get(field_name)

            if (
                isinstance(value, bool)
                or not isinstance(value, int)
                or value < 0
            ):
                raise KnowledgeManagerError(
                    "El slot candidato contiene un campo "
                    f"{field_name!r} inválido."
                )

        connected_type = active_entry.get("type")

        if (
            not isinstance(connected_type, str)
            or not connected_type.strip()
        ):
            raise KnowledgeManagerError(
                "La entrada Knowledge activa no contiene "
                "un tipo conectable válido."
            )

        connected_user = active_entry.get("user")

        if not isinstance(connected_user, dict):
            raise KnowledgeManagerError(
                "La entrada Knowledge activa no contiene "
                "información válida del propietario."
            )

        candidate_entry = deepcopy(active_entry)

        for field_name in (
            "id",
            "user_id",
            "name",
            "description",
            "meta",
            "access_grants",
            "created_at",
            "updated_at",
        ):
            candidate_entry[field_name] = deepcopy(
                candidate_record[field_name]
            )

        candidate_entry["write_access"] = True

        candidate_entry.pop("files", None)
        candidate_entry.pop("file_count", None)

        return candidate_entry


    @staticmethod
    def _model_state_without_knowledge(
        model: dict[str, Any],
    ) -> dict[str, Any]:
        """Extrae el ModelForm ignorando solo meta.knowledge."""

        if not isinstance(model, dict):
            raise KnowledgeManagerError(
                "El modelo exportado no es válido."
            )

        model_id = model.get("id")
        name = model.get("name")
        meta = model.get("meta")
        params = model.get("params")
        access_grants = model.get("access_grants")
        is_active = model.get("is_active")

        if (
            not isinstance(model_id, str)
            or not model_id.strip()
        ):
            raise KnowledgeManagerError(
                "El modelo exportado no contiene un id válido."
            )

        if (
            not isinstance(name, str)
            or not name.strip()
        ):
            raise KnowledgeManagerError(
                "El modelo exportado no contiene "
                "un nombre válido."
            )

        if not isinstance(meta, dict):
            raise KnowledgeManagerError(
                "El modelo exportado no contiene "
                "metadatos válidos."
            )

        attached_knowledge = meta.get("knowledge")

        if not isinstance(attached_knowledge, list):
            raise KnowledgeManagerError(
                "El modelo exportado no contiene una lista "
                "válida de Knowledge."
            )

        if not isinstance(params, dict):
            raise KnowledgeManagerError(
                "El modelo exportado no contiene params válidos."
            )

        if (
            not isinstance(access_grants, list)
            or not all(
                item is None
                or isinstance(item, dict)
                for item in access_grants
            )
        ):
            raise KnowledgeManagerError(
                "El modelo exportado no contiene "
                "access_grants válidos."
            )

        if not isinstance(is_active, bool):
            raise KnowledgeManagerError(
                "El modelo exportado no contiene "
                "is_active válido."
            )

        if "base_model_id" not in model:
            raise KnowledgeManagerError(
                "El modelo exportado no contiene base_model_id."
            )

        base_model_id = model.get("base_model_id")

        if (
            base_model_id is not None
            and (
                not isinstance(base_model_id, str)
                or not base_model_id.strip()
            )
        ):
            raise KnowledgeManagerError(
                "El modelo exportado contiene "
                "un base_model_id inválido."
            )

        semantic_meta = deepcopy(meta)
        semantic_meta.pop("knowledge")

        return {
            "id": model_id,
            "base_model_id": base_model_id,
            "name": name,
            "meta": semantic_meta,
            "params": deepcopy(params),
            "access_grants": deepcopy(access_grants),
            "is_active": is_active,
        }

    @classmethod
    def _require_same_model_outside_knowledge(
        cls,
        reference_model: dict[str, Any],
        candidate_model: dict[str, Any],
    ) -> None:
        """Rechaza cualquier cambio ajeno a meta.knowledge."""

        reference_state = (
            cls._model_state_without_knowledge(
                reference_model
            )
        )
        candidate_state = (
            cls._model_state_without_knowledge(
                candidate_model
            )
        )

        if candidate_state != reference_state:
            raise KnowledgeManagerError(
                "El intercambio intentó modificar campos "
                "del modelo ajenos a meta.knowledge."
            )

    @classmethod
    def _build_switched_model(
        cls,
        model: dict[str, Any],
        *,
        model_id: str,
        active_slot: KnowledgeSlot,
        candidate_slot: KnowledgeSlot,
        candidate_entry: dict[str, Any],
    ) -> dict[str, Any]:
        """Reemplaza únicamente el slot activo en el modelo."""

        if (
            not isinstance(model_id, str)
            or not model_id.strip()
        ):
            raise KnowledgeManagerError(
                "El id del modelo configurado no es válido."
            )

        if model.get("id") != model_id:
            raise KnowledgeManagerError(
                "El modelo exportado no coincide con "
                "el modelo configurado."
            )

        if active_slot == candidate_slot:
            raise KnowledgeManagerError(
                "Los slots activo y candidato no pueden ser "
                "el mismo."
            )

        if (
            not isinstance(candidate_entry, dict)
            or candidate_entry.get("id")
            != candidate_slot.kb_id
        ):
            raise KnowledgeManagerError(
                "La entrada conectable no corresponde "
                "al slot candidato."
            )

        meta = model.get("meta")

        if not isinstance(meta, dict):
            raise KnowledgeManagerError(
                "El modelo exportado no contiene "
                "metadatos válidos."
            )

        attached_knowledge = meta.get("knowledge")

        if not isinstance(attached_knowledge, list):
            raise KnowledgeManagerError(
                "El modelo exportado no contiene una lista "
                "válida de Knowledge."
            )

        active_indexes: list[int] = []
        candidate_indexes: list[int] = []

        for index, entry in enumerate(attached_knowledge):
            if not isinstance(entry, dict):
                raise KnowledgeManagerError(
                    "El modelo contiene una entrada Knowledge "
                    "inválida."
                )

            entry_id = entry.get("id")

            if (
                not isinstance(entry_id, str)
                or not entry_id.strip()
            ):
                raise KnowledgeManagerError(
                    "El modelo contiene una entrada Knowledge "
                    "sin identificador válido."
                )

            if entry_id == active_slot.kb_id:
                active_indexes.append(index)

            if entry_id == candidate_slot.kb_id:
                candidate_indexes.append(index)

        if len(active_indexes) != 1:
            raise KnowledgeManagerError(
                "El modelo debe contener exactamente una "
                "entrada para el slot activo."
            )

        if candidate_indexes:
            raise KnowledgeManagerError(
                "El slot candidato ya se encuentra conectado "
                "al modelo."
            )

        switched_model = deepcopy(model)
        switched_knowledge = (
            switched_model["meta"]["knowledge"]
        )

        switched_knowledge[
            active_indexes[0]
        ] = deepcopy(candidate_entry)

        cls._require_same_model_outside_knowledge(
            model,
            switched_model,
        )

        return switched_model

    @staticmethod
    def _read_counter(
        payload: dict[str, Any],
        key: str,
    ) -> int:
        value = payload.get(key)

        if (
            isinstance(value, bool)
            or not isinstance(value, int)
            or value < 0
        ):
            raise KnowledgeManagerError(
                f"El contador '{key}' devuelto por oikb no es válido."
            )

        return value

    @staticmethod
    def _read_messages(
        payload: dict[str, Any],
        key: str,
    ) -> tuple[str, ...]:
        value = payload.get(key, [])

        if (
            not isinstance(value, list)
            or not all(
                isinstance(item, str)
                for item in value
            )
        ):
            raise KnowledgeManagerError(
                f"El campo '{key}' devuelto por oikb no es válido."
            )

        return tuple(value)

    @staticmethod
    def _read_digest(
        payload: dict[str, Any],
        key: str,
    ) -> str:
        """Lee una huella SHA-256 devuelta por el puente."""

        value = payload.get(key)
        hexadecimal = set(
            "0123456789abcdefABCDEF"
        )

        if (
            not isinstance(value, str)
            or len(value) != 64
            or any(
                character not in hexadecimal
                for character in value
            )
        ):
            raise KnowledgeManagerError(
                f"El campo '{key}' no contiene "
                "una huella SHA-256 válida."
            )

        return value

    @staticmethod
    def _read_exact_entries(
        payload: dict[str, Any],
        key: str,
        expected_fields: tuple[str, ...],
    ) -> tuple[dict[str, str], ...]:
        """Lee una lista exacta de objetos textuales."""

        value = payload.get(key)

        if not isinstance(value, list):
            raise KnowledgeManagerError(
                f"El campo '{key}' devuelto por oikb "
                "no es una lista válida."
            )

        entries: list[dict[str, str]] = []

        for index, item in enumerate(value):
            if (
                not isinstance(item, dict)
                or set(item) != set(expected_fields)
            ):
                raise KnowledgeManagerError(
                    f"El elemento {key}[{index}] no contiene "
                    "exactamente los campos esperados."
                )

            entry: dict[str, str] = {}

            for field_name in expected_fields:
                field_value = item.get(field_name)

                if not isinstance(field_value, str):
                    raise KnowledgeManagerError(
                        f"El campo {key}[{index}].{field_name} "
                        "no es texto."
                    )

                if (
                    field_name != "path"
                    and not field_value.strip()
                ):
                    raise KnowledgeManagerError(
                        f"El campo {key}[{index}].{field_name} "
                        "está vacío."
                    )

                entry[field_name] = field_value

            entries.append(entry)

        return tuple(entries)

    @staticmethod
    def _read_string_items(
        payload: dict[str, Any],
        key: str,
    ) -> tuple[str, ...]:
        """Lee una lista de textos no vacíos."""

        value = payload.get(key)

        if (
            not isinstance(value, list)
            or not all(
                isinstance(item, str)
                and bool(item.strip())
                for item in value
            )
        ):
            raise KnowledgeManagerError(
                f"El campo '{key}' devuelto por oikb "
                "no es una lista de textos válida."
            )

        return tuple(value)

    @staticmethod
    def _read_directory_map(
        payload: dict[str, Any],
    ) -> tuple[tuple[str, str], ...]:
        """Lee el mapa estable de rutas e IDs remotos."""

        value = payload.get("directory_map")

        if (
            not isinstance(value, dict)
            or not all(
                isinstance(path, str)
                and isinstance(directory_id, str)
                and bool(directory_id.strip())
                for path, directory_id in value.items()
            )
        ):
            raise KnowledgeManagerError(
                "El campo 'directory_map' devuelto por oikb "
                "no es válido."
            )

        return tuple(
            sorted(
                value.items()
            )
        )

    def _read_sync_result(
        self,
        payload: dict[str, Any],
        *,
        expected_kb_id: str,
    ) -> KnowledgeSyncResult:
        """Convierte y valida el resultado de una sincronización."""

        if (
            not isinstance(expected_kb_id, str)
            or not expected_kb_id.strip()
        ):
            raise KnowledgeManagerError(
                "El kb-id esperado para la sincronización "
                "no es válido."
            )

        source_name = payload.get("source_name")
        kb_id = payload.get("kb_id")

        if source_name != self.source_name:
            raise KnowledgeManagerError(
                "oikb devolvió una fuente diferente "
                "durante la sincronización."
            )

        if (
            not isinstance(kb_id, str)
            or not kb_id.strip()
        ):
            raise KnowledgeManagerError(
                "oikb no devolvió un kb-id válido "
                "durante la sincronización."
            )

        if kb_id != expected_kb_id:
            raise KnowledgeManagerError(
                "oikb sincronizó un slot diferente "
                "del candidato autorizado."
            )

        try:
            result = KnowledgeSyncResult(
                source_name=source_name,
                kb_id=kb_id,
                manifest_digest=self._read_digest(
                    payload,
                    "manifest_digest",
                ),
                added=self._read_counter(
                    payload,
                    "added",
                ),
                modified=self._read_counter(
                    payload,
                    "modified",
                ),
                deleted=self._read_counter(
                    payload,
                    "deleted",
                ),
                unmodified=self._read_counter(
                    payload,
                    "unmodified",
                ),
                dirs_created=self._read_counter(
                    payload,
                    "dirs_created",
                ),
                dirs_removed=self._read_counter(
                    payload,
                    "dirs_removed",
                ),
                warnings=self._read_messages(
                    payload,
                    "warnings",
                ),
                errors=self._read_messages(
                    payload,
                    "errors",
                ),
            )
        except ValueError as error:
            raise KnowledgeManagerError(
                "El resultado de sincronización Knowledge "
                "no es válido."
            ) from error

        if result.failed:
            raise KnowledgeManagerError(
                "La sincronización del slot candidato informó "
                "errores: "
                + "; ".join(result.errors)
            )

        return result

    @staticmethod
    def _sha256(path: Path) -> str:
        """Calcula el SHA-256 de un archivo sin cargarlo entero."""

        digest = hashlib.sha256()

        with path.open("rb") as file:
            for chunk in iter(
                lambda: file.read(1024 * 1024),
                b"",
            ):
                digest.update(chunk)

        return digest.hexdigest()

    def _ensure_tracked_by_git(
        self,
        relative_paths: tuple[str, ...],
    ) -> None:
        """Impide publicar archivos no registrados por Git."""

        pathspecs = [
            f":(literal){relative_path}"
            for relative_path in relative_paths
        ]

        try:
            result = subprocess.run(
                [
                    "git",
                    "ls-files",
                    "-z",
                    "--cached",
                    "--",
                    *pathspecs,
                ],
                cwd=self.project_root,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=30,
                check=False,
            )
        except (
            OSError,
            subprocess.TimeoutExpired,
        ) as error:
            raise KnowledgeManagerError(
                "No fue posible comprobar el manifiesto con Git."
            ) from error

        if result.returncode != 0:
            detail = result.stderr.strip()

            raise KnowledgeManagerError(
                "Git no pudo comprobar los archivos autorizados: "
                f"{detail or result.returncode}"
            )

        tracked_paths = {
            path
            for path in result.stdout.split("\0")
            if path
        }

        untracked_paths = tuple(
            sorted(
                set(relative_paths)
                - tracked_paths
            )
        )

        if untracked_paths:
            raise KnowledgeManagerError(
                "El manifiesto contiene archivos no registrados "
                "por Git: "
                + ", ".join(untracked_paths)
            )

    def _validate_manifest_source(
        self,
        relative_path: Path,
        normalized: str,
    ) -> None:
        """Valida que la entrada sea un archivo regular interno."""

        source_path = (
            self.project_root
            / relative_path
        )

        current_path = self.project_root

        for part in relative_path.parts:
            current_path = current_path / part

            if current_path.is_symlink():
                raise KnowledgeManagerError(
                    "El manifiesto no puede publicar enlaces "
                    f"simbólicos: {normalized}"
                )

        try:
            resolved_path = source_path.resolve(
                strict=True
            )
        except FileNotFoundError as error:
            raise KnowledgeManagerError(
                "El archivo declarado en el manifiesto "
                f"no existe: {normalized}"
            ) from error
        except OSError as error:
            raise KnowledgeManagerError(
                "No fue posible resolver la ruta declarada "
                f"en el manifiesto: {normalized}"
            ) from error

        if not resolved_path.is_relative_to(
            self.project_root
        ):
            raise KnowledgeManagerError(
                "La ruta declarada escapa del repositorio: "
                f"{normalized}"
            )

        if not resolved_path.is_file():
            raise KnowledgeManagerError(
                "La entrada del manifiesto no es un archivo "
                f"regular: {normalized}"
            )

    def _manifest_paths(self) -> tuple[str, ...]:
        """Lee y valida los archivos autorizados para Knowledge."""

        try:
            lines = self.manifest_path.read_text(
                encoding="utf-8"
            ).splitlines()
        except OSError as error:
            raise KnowledgeManagerError(
                "No fue posible leer el manifiesto de Knowledge."
            ) from error

        relative_paths: list[str] = []

        for line_number, raw_line in enumerate(lines, start=1):
            value = raw_line.strip()

            if not value or value.startswith("#"):
                continue

            path = Path(value)

            if path.is_absolute() or ".." in path.parts:
                raise KnowledgeManagerError(
                    "Ruta inválida en el manifiesto, "
                    f"línea {line_number}: {value}"
                )

            normalized = path.as_posix()

            if not (
                normalized.startswith("Core/")
                or normalized.startswith("Knowledge/")
            ):
                raise KnowledgeManagerError(
                    "El manifiesto solo puede publicar archivos "
                    "de Core/ o Knowledge/: "
                    f"{normalized}"
                )

            self._validate_manifest_source(
                path,
                normalized,
            )

            relative_paths.append(normalized)

        if not relative_paths:
            raise KnowledgeManagerError(
                "El manifiesto de Knowledge está vacío."
            )

        duplicates = sorted(
            {
                path
                for path in relative_paths
                if relative_paths.count(path) > 1
            }
        )

        if duplicates:
            raise KnowledgeManagerError(
                "El manifiesto contiene rutas duplicadas: "
                + ", ".join(duplicates)
            )

        manifest_paths = tuple(relative_paths)

        self._ensure_tracked_by_git(
            manifest_paths
        )

        return manifest_paths

    @contextmanager
    def staged_source(self) -> Iterator[Path]:
        """Construye una copia temporal validada de Knowledge."""

        relative_paths = self._manifest_paths()

        with tempfile.TemporaryDirectory(
            prefix="epsilon-knowledge-"
        ) as temporary_directory:
            staging_directory = Path(temporary_directory)

            for relative_path in relative_paths:
                source_path = (
                    self.project_root
                    / relative_path
                )

                staged_path = (
                    staging_directory
                    / relative_path
                )

                staged_path.parent.mkdir(
                    parents=True,
                    exist_ok=True,
                )

                shutil.copyfile(
                    source_path,
                    staged_path,
                )

                if self._sha256(source_path) != self._sha256(
                    staged_path
                ):
                    raise KnowledgeManagerError(
                        "La copia temporal no coincide con "
                        f"su fuente: {relative_path}"
                    )

            staged_paths = tuple(
                sorted(
                    path.relative_to(
                        staging_directory
                    ).as_posix()
                    for path in staging_directory.rglob("*")
                    if path.is_file()
                )
            )

            if staged_paths != tuple(sorted(relative_paths)):
                raise KnowledgeManagerError(
                    "El staging temporal no coincide "
                    "con el manifiesto de Knowledge."
                )

            yield staging_directory

    def _run_bridge(
        self,
        source_path: Path,
        *,
        kb_id: str,
        operation: str = "diff",
    ) -> dict[str, Any]:
        """Ejecuta una operación controlada mediante el adaptador."""

        if operation not in {"diff", "sync"}:
            raise KnowledgeManagerError(
                "La operación solicitada al adaptador "
                "de Knowledge no es válida."
            )

        environment = os.environ.copy()
        environment["PYTHONIOENCODING"] = "utf-8"
        environment["PYTHONUTF8"] = "1"
        environment["OPEN_WEBUI_URL"] = self.config.base_url
        environment["OPEN_WEBUI_API_KEY"] = (
            self.config.require_api_key()
        )

        process_command = [
            str(self.python_executable),
            str(self.bridge_path),
            operation,
            "--source-name",
            self.source_name,
            "--kb-id",
            kb_id,
            "--source",
            str(source_path.resolve()),
            "--timeout",
            str(self.timeout_seconds),
        ]

        try:
            result = subprocess.run(
                process_command,
                cwd=self.project_root,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                env=environment,
                timeout=self.timeout_seconds + 30,
                check=False,
            )

        except subprocess.TimeoutExpired as error:
            raise KnowledgeManagerError(
                "La operación de Knowledge superó "
                "el tiempo máximo permitido."
            ) from error

        output = result.stdout.strip()

        if not output:
            detail = result.stderr.strip()

            if detail:
                detail = detail[-500:]
            else:
                detail = "el adaptador no produjo una respuesta"

            raise KnowledgeManagerError(
                f"No fue posible leer el resultado de oikb: {detail}"
            )

        try:
            payload = json.loads(output)
        except json.JSONDecodeError as error:
            raise KnowledgeManagerError(
                "El adaptador de oikb devolvió JSON inválido."
            ) from error

        if not isinstance(payload, dict):
            raise KnowledgeManagerError(
                "El adaptador de oikb no devolvió un objeto JSON."
            )

        if payload.get("command") != operation:
            raise KnowledgeManagerError(
                "El adaptador de oikb respondió por una "
                "operación diferente de la solicitada."
            )

        if result.returncode != 0 or payload.get("ok") is not True:
            message = payload.get("error")

            if not isinstance(message, str) or not message:
                errors = payload.get("errors", [])

                if isinstance(errors, list):
                    message = "; ".join(
                        item
                        for item in errors
                        if isinstance(item, str)
                    )

            raise KnowledgeManagerError(
                message
                or f"La operación Knowledge '{operation}' falló."
            )

        return payload

    def _plan_for_slot_from_staging(
        self,
        slot: KnowledgeSlot,
        staging_directory: Path,
        *,
        slot_role: str,
    ) -> KnowledgeDiffResult:
        """Compara un slot usando un staging ya inmovilizado."""

        payload = self._run_bridge(
            staging_directory,
            kb_id=slot.kb_id,
            operation="diff",
        )

        source_name = payload.get("source_name")
        kb_id = payload.get("kb_id")

        if source_name != self.source_name:
            raise KnowledgeManagerError(
                "oikb devolvió una fuente diferente "
                "de la solicitada."
            )

        if not isinstance(kb_id, str) or not kb_id:
            raise KnowledgeManagerError(
                "oikb no devolvió un kb-id válido."
            )

        if kb_id != slot.kb_id:
            raise KnowledgeManagerError(
                "oikb respondió por un slot diferente "
                f"del slot {slot_role}."
            )

        added_entries = self._read_exact_entries(
            payload,
            "added_files",
            (
                "filename",
                "path",
            ),
        )

        modified_entries = self._read_exact_entries(
            payload,
            "modified_files",
            (
                "filename",
                "path",
                "stale_file_id",
            ),
        )

        deleted_entries = self._read_exact_entries(
            payload,
            "deleted_files",
            (
                "file_id",
                "filename",
            ),
        )

        return KnowledgeDiffResult(
            source_name=source_name,
            kb_id=kb_id,
            manifest_digest=self._read_digest(
                payload,
                "manifest_digest",
            ),
            diff_digest=self._read_digest(
                payload,
                "diff_digest",
            ),
            added=self._read_counter(
                payload,
                "added",
            ),
            modified=self._read_counter(
                payload,
                "modified",
            ),
            deleted=self._read_counter(
                payload,
                "deleted",
            ),
            unmodified=self._read_counter(
                payload,
                "unmodified",
            ),
            dirs_created=self._read_counter(
                payload,
                "dirs_created",
            ),
            dirs_removed=self._read_counter(
                payload,
                "dirs_removed",
            ),
            added_files=tuple(
                KnowledgeAddedFile(
                    path=entry["path"],
                    filename=entry["filename"],
                )
                for entry in added_entries
            ),
            modified_files=tuple(
                KnowledgeModifiedFile(
                    path=entry["path"],
                    filename=entry["filename"],
                    stale_file_id=entry[
                        "stale_file_id"
                    ],
                )
                for entry in modified_entries
            ),
            deleted_files=tuple(
                KnowledgeDeletedFile(
                    filename=entry["filename"],
                    file_id=entry["file_id"],
                )
                for entry in deleted_entries
            ),
            directories_to_create=(
                self._read_string_items(
                    payload,
                    "directories_to_create",
                )
            ),
            directory_ids_to_remove=(
                self._read_string_items(
                    payload,
                    "directory_ids_to_remove",
                )
            ),
            directory_map=(
                self._read_directory_map(
                    payload
                )
            ),
            warnings=self._read_messages(
                payload,
                "warnings",
            ),
            errors=self._read_messages(
                payload,
                "errors",
            ),
        )

    def _plan_for_slot(
        self,
        slot: KnowledgeSlot,
        *,
        slot_role: str,
    ) -> KnowledgeDiffResult:
        """Compara un slot creando un staging temporal exacto."""

        with self.staged_source() as staging_directory:
            return self._plan_for_slot_from_staging(
                slot,
                staging_directory,
                slot_role=slot_role,
            )

    def plan(self) -> KnowledgeDiffResult:
        """Compara la fuente local con el slot activo."""

        target = self._load_target()
        active_slot = self._active_slot(target)

        return self._plan_for_slot(
            active_slot,
            slot_role="activo",
        )

    def _candidate_plan_from_staging(
        self,
        staging_directory: Path,
    ) -> KnowledgeCandidatePlan:
        """Calcula el plan candidato desde un staging inmovilizado."""

        target = self._load_target()
        active_slot = self._active_slot(target)
        candidate_slot = target.other_slot(
            active_slot.name
        )

        diff = self._plan_for_slot_from_staging(
            candidate_slot,
            staging_directory,
            slot_role="candidato",
        )

        return KnowledgeCandidatePlan(
            active_slot=active_slot,
            candidate_slot=candidate_slot,
            diff=diff,
        )

    def plan_candidate(self) -> KnowledgeCandidatePlan:
        """Compara la fuente local con el slot inactivo."""

        with self.staged_source() as staging_directory:
            return self._candidate_plan_from_staging(
                staging_directory
            )


    def _require_matching_candidate_plan(
        self,
        approved_plan: KnowledgeCandidatePlan,
        current_plan: KnowledgeCandidatePlan,
    ) -> KnowledgeCandidatePlan:
        """Rechaza un plan candidato distinto del aprobado."""

        if not isinstance(
            approved_plan,
            KnowledgeCandidatePlan,
        ):
            raise KnowledgeManagerError(
                "El plan candidato aprobado no es válido."
            )

        if not isinstance(
            current_plan,
            KnowledgeCandidatePlan,
        ):
            raise KnowledgeManagerError(
                "El plan candidato recalculado no es válido."
            )

        if not approved_plan.diff.has_exact_details:
            raise KnowledgeManagerError(
                "El plan candidato aprobado no contiene "
                "detalles exactos verificables."
            )

        if not current_plan.diff.has_exact_details:
            raise KnowledgeManagerError(
                "El plan candidato recalculado no contiene "
                "detalles exactos verificables."
            )

        if current_plan == approved_plan:
            return current_plan

        reasons: list[str] = []

        if (
            current_plan.active_slot
            != approved_plan.active_slot
        ):
            reasons.append(
                "cambió el slot activo"
            )

        if (
            current_plan.candidate_slot
            != approved_plan.candidate_slot
        ):
            reasons.append(
                "cambió el slot candidato"
            )

        if (
            current_plan.diff.manifest_digest
            != approved_plan.diff.manifest_digest
        ):
            reasons.append(
                "cambió el manifiesto local"
            )

        if (
            current_plan.diff.diff_digest
            != approved_plan.diff.diff_digest
        ):
            reasons.append(
                "cambió el estado remoto del candidato"
            )

        if (
            current_plan.diff
            != approved_plan.diff
            and not reasons
        ):
            reasons.append(
                "cambiaron los detalles exactos del plan"
            )

        detail = ", ".join(reasons)

        raise KnowledgeManagerError(
            "El plan candidato quedó obsoleto"
            + (
                f": {detail}."
                if detail
                else "."
            )
            + " Debe generarse y aprobarse nuevamente."
        )

    def require_current_candidate_plan(
        self,
        approved_plan: KnowledgeCandidatePlan,
    ) -> KnowledgeCandidatePlan:
        """Recalcula y rechaza un plan candidato obsoleto."""

        current_plan = self.plan_candidate()

        return self._require_matching_candidate_plan(
            approved_plan,
            current_plan,
        )



    def _deployment_lock_path(self) -> Path:
        """Construye un bloqueo estable para este repositorio."""

        project_key = hashlib.sha256(
            str(
                self.project_root.resolve(
                    strict=False
                )
            ).encode("utf-8")
        ).hexdigest()[:16]

        return (
            Path(tempfile.gettempdir())
            / (
                "epsilon-knowledge-"
                f"{os.getuid()}-{project_key}.lock"
            )
        )

    @contextmanager
    def deployment_lock(self) -> Iterator[None]:
        """Impide despliegues Knowledge simultáneos."""

        lock_path = self._deployment_lock_path()

        try:
            lock_file = lock_path.open(
                "a+",
                encoding="utf-8",
            )
        except OSError as error:
            raise KnowledgeManagerError(
                "No se pudo abrir el bloqueo exclusivo "
                f"de Knowledge: {error}"
            ) from error

        acquired = False

        try:
            try:
                fcntl.flock(
                    lock_file.fileno(),
                    fcntl.LOCK_EX | fcntl.LOCK_NB,
                )
                acquired = True

            except BlockingIOError as error:
                lock_file.seek(0)
                owner = lock_file.read().strip()

                detail = (
                    f" Propietario registrado: {owner}."
                    if owner
                    else ""
                )

                raise KnowledgeManagerError(
                    "Ya existe otra operación de despliegue "
                    "Knowledge en curso."
                    + detail
                ) from error

            except OSError as error:
                raise KnowledgeManagerError(
                    "No se pudo adquirir el bloqueo exclusivo "
                    f"de Knowledge: {error}"
                ) from error

            lock_file.seek(0)
            lock_file.truncate()
            lock_file.write(
                f"pid={os.getpid()}\n"
            )
            lock_file.flush()

            yield

        finally:
            if acquired:
                fcntl.flock(
                    lock_file.fileno(),
                    fcntl.LOCK_UN,
                )

            lock_file.close()


    def _require_active_slot(
        self,
        expected_slot: KnowledgeSlot,
    ) -> KnowledgeSlot:
        """Confirma que el modelo conserva el slot activo esperado."""

        target = self._load_target()
        current_slot = self._active_slot(target)

        if current_slot != expected_slot:
            raise KnowledgeManagerError(
                "El slot activo cambió durante la preparación "
                "del candidato. La operación fue cancelada."
            )

        return current_slot


    def _wait_for_candidate_convergence(
        self,
        plan: KnowledgeCandidatePlan,
        staging_directory: Path,
    ) -> KnowledgeDiffResult:
        """Espera que Open WebUI refleje la sincronización."""

        expected_file_count = (
            plan.diff.added
            + plan.diff.modified
            + plan.diff.unmodified
        )
        last_reason = "estado remoto todavía no disponible"

        for delay in self.verification_retry_delays:
            if delay > 0:
                time.sleep(delay)

            verified_diff = (
                self._plan_for_slot_from_staging(
                    plan.candidate_slot,
                    staging_directory,
                    slot_role="candidato preparado",
                )
            )

            if (
                verified_diff.manifest_digest
                != plan.diff.manifest_digest
            ):
                raise KnowledgeManagerError(
                    "La verificación posterior utilizó un "
                    "manifiesto diferente del plan aprobado."
                )

            if verified_diff.failed:
                last_reason = (
                    "la verificación informó errores: "
                    + "; ".join(verified_diff.errors)
                )
                continue

            if verified_diff.has_changes:
                last_reason = (
                    "el slot candidato conserva diferencias: "
                    f"{verified_diff.total_changes} pendientes"
                )
                continue

            if (
                verified_diff.unmodified
                != expected_file_count
            ):
                last_reason = (
                    "la cantidad de archivos verificados "
                    "no coincide con el manifiesto"
                )
                continue

            return verified_diff

        raise KnowledgeManagerError(
            "El slot candidato no alcanzó un estado "
            "convergente después de "
            f"{len(self.verification_retry_delays)} intentos: "
            f"{last_reason}."
        )


    def prepare_candidate(
        self,
        approved_plan: KnowledgeCandidatePlan,
    ) -> KnowledgeSyncResult:
        """Prepara el candidato bajo un bloqueo exclusivo."""

        with self.deployment_lock():
            return self._prepare_candidate_locked(
                approved_plan
            )

    def _prepare_candidate_locked(
        self,
        approved_plan: KnowledgeCandidatePlan,
    ) -> KnowledgeSyncResult:
        """Sincroniza y verifica únicamente el slot inactivo."""

        with self.staged_source() as staging_directory:
            current_plan = self._candidate_plan_from_staging(
                staging_directory
            )

            validated_plan = (
                self._require_matching_candidate_plan(
                    approved_plan,
                    current_plan,
                )
            )

            self._require_active_slot(
                validated_plan.active_slot
            )

            sync_payload = self._run_bridge(
                staging_directory,
                kb_id=validated_plan.candidate_slot.kb_id,
                operation="sync",
            )

            sync_result = self._read_sync_result(
                sync_payload,
                expected_kb_id=(
                    validated_plan.candidate_slot.kb_id
                ),
            )

            if (
                sync_result.manifest_digest
                != validated_plan.diff.manifest_digest
            ):
                raise KnowledgeManagerError(
                    "La sincronización utilizó un manifiesto "
                    "diferente del plan aprobado."
                )

            self._wait_for_candidate_convergence(
                validated_plan,
                staging_directory,
            )

            self._require_active_slot(
                validated_plan.active_slot
            )

            return sync_result


    def sync(self, dry_run: bool = True) -> bool:
        """Compatibilidad temporal con SyncModule."""

        result = self.plan()

        if not result.has_changes:
            print(
                "✓ Knowledge sincronizada "
                f"({result.unmodified} archivos)"
            )
            return True

        print("✗ Knowledge tiene cambios pendientes")
        print(f"  Agregar:           {result.added}")
        print(f"  Modificar:         {result.modified}")
        print(f"  Eliminar:          {result.deleted}")
        print(f"  Carpetas a crear:  {result.dirs_created}")
        print(f"  Carpetas a retirar:{result.dirs_removed}")

        if result.has_destructive_changes:
            print(
                "  Advertencia: existen cambios "
                "potencialmente destructivos."
            )

        if dry_run:
            print("  Dry-run: no se aplicaron cambios")
        else:
            print(
                "  La aplicación de Knowledge "
                "todavía no está implementada"
            )

        return False