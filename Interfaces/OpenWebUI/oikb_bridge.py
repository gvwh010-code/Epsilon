from __future__ import annotations

import argparse
from contextlib import redirect_stderr, redirect_stdout
import io
import json
import os
from pathlib import Path
from typing import Any

import yaml

from oikb.client import OikbClient
from oikb.connectors.filesystem import FilesystemConnector
from oikb.sync import SyncResult, run_sync


def require_environment(name: str) -> str:
    """Lee una variable obligatoria sin imprimir su contenido."""

    value = os.getenv(name, "").strip()

    if not value:
        raise RuntimeError(
            f"Falta la variable de entorno obligatoria: {name}"
        )

    return value


def load_source_entry(
    config_path: Path,
    source_name: str,
) -> tuple[Path, str]:
    """Obtiene una fuente local y su KB desde .oikb.yaml."""

    if not config_path.is_file():
        raise RuntimeError(
            f"No se encontró la configuración: {config_path}"
        )

    try:
        document = yaml.safe_load(
            config_path.read_text(encoding="utf-8")
        )
    except (OSError, yaml.YAMLError) as error:
        raise RuntimeError(
            f"No fue posible leer {config_path}: {error}"
        ) from error

    if not isinstance(document, dict):
        raise RuntimeError(
            "La configuración de oikb no es un objeto válido."
        )

    sources = document.get("sources")

    if not isinstance(sources, list):
        raise RuntimeError(
            "La configuración de oikb no contiene una lista 'sources'."
        )

    matches = [
        entry
        for entry in sources
        if isinstance(entry, dict)
        and entry.get("name") == source_name
    ]

    if not matches:
        raise RuntimeError(
            f"No existe la fuente '{source_name}' en {config_path}."
        )

    if len(matches) > 1:
        raise RuntimeError(
            f"La fuente '{source_name}' está declarada más de una vez."
        )

    entry = matches[0]
    source_value = entry.get("source")
    kb_id = entry.get("kb-id")

    if not isinstance(source_value, str) or not source_value.strip():
        raise RuntimeError(
            f"La fuente '{source_name}' no tiene una ruta válida."
        )

    if not isinstance(kb_id, str) or not kb_id.strip():
        raise RuntimeError(
            f"La fuente '{source_name}' no tiene un kb-id válido."
        )

    source_path = Path(source_value).expanduser()

    if not source_path.is_absolute():
        source_path = config_path.parent / source_path

    source_path = source_path.resolve()

    return source_path, kb_id.strip()

def ensure_non_empty_source(source_path: Path) -> None:
    """Rechaza una fuente sin archivos sincronizables."""

    connector = FilesystemConnector(source_path)

    try:
        manifest = connector.build_manifest()
    finally:
        connector.close()

    if not manifest:
        raise RuntimeError(
            "La fuente Knowledge no contiene archivos "
            "sincronizables; se rechaza la comparación "
            "para evitar un falso estado limpio."
        )

def result_to_dict(result: SyncResult) -> dict[str, Any]:
    """Convierte SyncResult en datos JSON estables."""

    directory_changes = (
        result.dirs_created
        + result.dirs_removed
    )

    return {
        "ok": not bool(result.errors),
        "added": result.added,
        "modified": result.modified,
        "deleted": result.deleted,
        "unmodified": result.unmodified,
        "dirs_created": result.dirs_created,
        "dirs_removed": result.dirs_removed,
        "file_changes": result.total_changes,
        "total_changes": (
            result.total_changes
            + directory_changes
        ),
        "warnings": list(result.warnings or []),
        "errors": list(result.errors or []),
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Adaptador JSON de solo lectura para oikb."
    )

    parser.add_argument(
        "command",
        choices=("diff",),
        help="Operación permitida.",
    )

    parser.add_argument(
        "--config",
        default=".oikb.yaml",
        help="Ruta al archivo de configuración de oikb.",
    )

    parser.add_argument(
        "--name",
        required=True,
        help="Nombre exacto de la fuente declarada en el YAML.",
    )

    parser.add_argument(
        "--source",
        help=(
            "Ruta opcional que reemplaza temporalmente "
            "la fuente declarada en el YAML."
        ),
    )

    parser.add_argument(
        "--timeout",
        type=float,
        default=120.0,
        help="Timeout HTTP en segundos.",
    )

    return parser


def main() -> int:
    parser = build_parser()
    arguments = parser.parse_args()

    try:
        config_path = Path(
            arguments.config
        ).expanduser().resolve()

        source_path, kb_id = load_source_entry(
            config_path=config_path,
            source_name=arguments.name,
        )

        if arguments.source:
            source_path = Path(
                arguments.source
            ).expanduser().resolve()

        if not source_path.is_dir():
            raise RuntimeError(
                "La fuente seleccionada no existe o no es "
                f"un directorio: {source_path}"
            )

        ensure_non_empty_source(source_path)

        base_url = require_environment(
            "OPEN_WEBUI_URL"
        ).rstrip("/")

        api_key = require_environment(
            "OPEN_WEBUI_API_KEY"
        )

        client = OikbClient(
            base_url=base_url,
            token=api_key,
            timeout=arguments.timeout,
        )

        connector = FilesystemConnector(source_path)

        hidden_stdout = io.StringIO()
        hidden_stderr = io.StringIO()

        try:
            with (
                redirect_stdout(hidden_stdout),
                redirect_stderr(hidden_stderr),
            ):
                result = run_sync(
                    client=client,
                    connector=connector,
                    kb_id=kb_id,
                    dry_run=True,
                    verbose=False,
                    quiet=True,
                )
        finally:
            client.close()

    except Exception as error:
        print(
            json.dumps(
                {
                    "ok": False,
                    "error": str(error),
                },
                ensure_ascii=False,
            )
        )
        return 1

    payload = {
        "source_name": arguments.name,
        "kb_id": kb_id,
        **result_to_dict(result),
    }

    print(
        json.dumps(
            payload,
            ensure_ascii=False,
            sort_keys=True,
        )
    )

    return 0 if payload["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())