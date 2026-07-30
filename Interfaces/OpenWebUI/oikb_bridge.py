from __future__ import annotations

import argparse
from contextlib import redirect_stderr, redirect_stdout
import io
import json
import os
from pathlib import Path
from typing import Any
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
        "--source-name",
        required=True,
        help="Nombre lógico de la fuente Knowledge.",
    )

    parser.add_argument(
        "--kb-id",
        required=True,
        help="Identificador de la Knowledge remota.",
    )

    parser.add_argument(
        "--source",
        required=True,
        help="Ruta al staging temporal de Knowledge.",
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
        source_name = arguments.source_name.strip()
        kb_id = arguments.kb_id.strip()

        if not source_name:
            raise RuntimeError(
                "No se proporcionó un source_name válido."
            )

        if not kb_id:
            raise RuntimeError(
                "No se proporcionó un kb_id válido."
            )

        source_path = Path(
            arguments.source
        ).expanduser().resolve()

        if not source_path.is_dir():
            raise RuntimeError(
                "La fuente temporal no existe o no es "
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
        "source_name": source_name,
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