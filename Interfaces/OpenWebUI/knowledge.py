from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
from typing import Any, Iterator

from config import Config

from results import (
    KnowledgeAddedFile,
    KnowledgeDeletedFile,
    KnowledgeDiffResult,
    KnowledgeModifiedFile,
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
    ) -> dict[str, Any]:
        """Ejecuta el adaptador con la credencial solo en el subproceso."""

        environment = os.environ.copy()
        environment["PYTHONIOENCODING"] = "utf-8"
        environment["PYTHONUTF8"] = "1"
        environment["OPEN_WEBUI_URL"] = self.config.base_url
        environment["OPEN_WEBUI_API_KEY"] = (
            self.config.require_api_key()
        )

        command = [
            str(self.python_executable),
            str(self.bridge_path),
            "diff",
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
                command,
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
                "La comparación de Knowledge superó "
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
                message or "La comparación de Knowledge falló."
            )

        return payload

    def _plan_for_slot(
        self,
        slot: KnowledgeSlot,
        *,
        slot_role: str,
    ) -> KnowledgeDiffResult:
        """Compara la fuente local con un slot concreto."""

        with self.staged_source() as staging_directory:
            payload = self._run_bridge(
                staging_directory,
                kb_id=slot.kb_id,
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

    def plan(self) -> KnowledgeDiffResult:
        """Compara la fuente local con el slot activo."""

        target = self._load_target()
        active_slot = self._active_slot(target)

        return self._plan_for_slot(
            active_slot,
            slot_role="activo",
        )

    def plan_candidate(self) -> KnowledgeCandidatePlan:
        """Compara la fuente local con el slot inactivo."""

        target = self._load_target()
        active_slot = self._active_slot(target)
        candidate_slot = target.other_slot(
            active_slot.name
        )

        diff = self._plan_for_slot(
            candidate_slot,
            slot_role="candidato",
        )

        return KnowledgeCandidatePlan(
            active_slot=active_slot,
            candidate_slot=candidate_slot,
            diff=diff,
        )
    def plan(self) -> KnowledgeDiffResult:
        """Compara la fuente local con el slot activo."""

        target = self._load_target()
        active_slot = self._active_slot(target)

        return self._plan_for_slot(
            active_slot,
            slot_role="activo",
        )

    def plan_candidate(self) -> KnowledgeCandidatePlan:
        """Compara la fuente local con el slot inactivo."""

        target = self._load_target()
        active_slot = self._active_slot(target)
        candidate_slot = target.other_slot(
            active_slot.name
        )

        diff = self._plan_for_slot(
            candidate_slot,
            slot_role="candidato",
        )

        return KnowledgeCandidatePlan(
            active_slot=active_slot,
            candidate_slot=candidate_slot,
            diff=diff,
        )

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