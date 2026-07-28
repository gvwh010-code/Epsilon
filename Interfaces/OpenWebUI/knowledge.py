from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
from typing import Any

from config import Config
from results import KnowledgeDiffResult
from sync_module import SyncModule


class KnowledgeManagerError(RuntimeError):
    """Error controlado al comparar Knowledge mediante oikb."""


class KnowledgeManager(SyncModule):
    """Compara Knowledge local con Open WebUI sin modificarlo."""

    name = "Knowledge"

    def __init__(
        self,
        project_root: Path,
        config: Config,
        source_name: str = "epsilon-system",
        timeout_seconds: float = 120.0,
    ):
        self.project_root = project_root.resolve()
        self.config = config
        self.source_name = source_name
        self.timeout_seconds = timeout_seconds

        interface_dir = (
            self.project_root
            / "Interfaces"
            / "OpenWebUI"
        )

        self.oikb_config_path = (
            self.project_root
            / ".oikb.yaml"
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

        if not self.oikb_config_path.is_file():
            raise FileNotFoundError(
                f"No se encontró: {self.oikb_config_path}"
            )

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

    def _run_bridge(self) -> dict[str, Any]:
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
            "--config",
            str(self.oikb_config_path),
            "--name",
            self.source_name,
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

    def plan(self) -> KnowledgeDiffResult:
        """Compara la proyección existente sin modificar archivos."""

        payload = self._run_bridge()

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

        return KnowledgeDiffResult(
            source_name=source_name,
            kb_id=kb_id,
            added=self._read_counter(payload, "added"),
            modified=self._read_counter(payload, "modified"),
            deleted=self._read_counter(payload, "deleted"),
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