from __future__ import annotations

import argparse
import json
import os
import hashlib
from pathlib import Path
from typing import Any
from oikb.client import OikbClient
from oikb.connectors.filesystem import FilesystemConnector
from oikb.sync import run_sync


def require_environment(name: str) -> str:
    """Lee una variable obligatoria sin imprimir su contenido."""

    value = os.getenv(name, "").strip()

    if not value:
        raise RuntimeError(
            f"Falta la variable de entorno obligatoria: {name}"
        )

    return value


def canonical_digest(value: Any) -> str:
    """Calcula una huella SHA-256 sobre JSON canónico."""

    serialized = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")

    return hashlib.sha256(
        serialized
    ).hexdigest()


def build_source_manifest(
    source_path: Path,
) -> tuple[list[dict[str, Any]], str]:
    """Construye el manifiesto ordenado de la fuente temporal."""

    connector = FilesystemConnector(
        source_path
    )

    try:
        entries = connector.build_manifest()
    finally:
        connector.close()

    if not entries:
        raise RuntimeError(
            "La fuente Knowledge no contiene archivos "
            "sincronizables; se rechaza la comparación "
            "para evitar un falso estado limpio."
        )

    manifest = [
        entry.to_dict()
        for entry in entries
    ]

    return (
        manifest,
        canonical_digest(manifest),
    )


def require_entry_text(
    entry: dict[str, Any],
    field_name: str,
    *,
    context: str,
    allow_empty: bool = False,
) -> str:
    """Valida un texto recibido desde sync/diff."""

    value = entry.get(field_name)

    if not isinstance(value, str):
        raise RuntimeError(
            f"{context} contiene un {field_name} inválido."
        )

    if not allow_empty and not value.strip():
        raise RuntimeError(
            f"{context} contiene un {field_name} vacío."
        )

    return value


def normalize_entries(
    diff: dict[str, Any],
    field_name: str,
    expected_fields: tuple[str, ...],
) -> list[dict[str, str]]:
    """Valida y normaliza una lista de cambios de archivos."""

    value = diff.get(field_name)

    if not isinstance(value, list):
        raise RuntimeError(
            f"sync/diff devolvió un campo {field_name} inválido."
        )

    normalized: list[dict[str, str]] = []

    for index, entry in enumerate(value):
        context = (
            f"{field_name}[{index}]"
        )

        if not isinstance(entry, dict):
            raise RuntimeError(
                f"{context} no es un objeto."
            )

        if set(entry) != set(expected_fields):
            raise RuntimeError(
                f"{context} no contiene exactamente "
                f"los campos esperados: "
                + ", ".join(expected_fields)
            )

        normalized_entry: dict[str, str] = {}

        for expected_field in expected_fields:
            normalized_entry[expected_field] = (
                require_entry_text(
                    entry,
                    expected_field,
                    context=context,
                    allow_empty=(
                        expected_field == "path"
                    ),
                )
            )

        normalized.append(
            normalized_entry
        )

    return normalized


def normalize_string_list(
    diff: dict[str, Any],
    field_name: str,
) -> list[str]:
    """Valida una lista de rutas o identificadores."""

    value = diff.get(field_name)

    if (
        not isinstance(value, list)
        or not all(
            isinstance(item, str)
            and bool(item.strip())
            for item in value
        )
    ):
        raise RuntimeError(
            f"sync/diff devolvió un campo {field_name} inválido."
        )

    return list(value)


def normalize_sync_diff(
    diff: Any,
    *,
    manifest_digest: str,
) -> dict[str, Any]:
    """Convierte sync/diff en un plan JSON exacto y estable."""

    if not isinstance(diff, dict):
        raise RuntimeError(
            "sync/diff no devolvió un objeto JSON."
        )

    added_files = normalize_entries(
        diff,
        "added",
        (
            "filename",
            "path",
        ),
    )

    modified_files = normalize_entries(
        diff,
        "modified",
        (
            "filename",
            "path",
            "stale_file_id",
        ),
    )

    deleted_files = normalize_entries(
        diff,
        "deleted",
        (
            "file_id",
            "filename",
        ),
    )

    directories_to_create = (
        normalize_string_list(
            diff,
            "mkdir",
        )
    )

    directory_ids_to_remove = (
        normalize_string_list(
            diff,
            "rmdir",
        )
    )

    unmodified = diff.get(
        "unmodified_count"
    )

    if (
        isinstance(unmodified, bool)
        or not isinstance(unmodified, int)
        or unmodified < 0
    ):
        raise RuntimeError(
            "sync/diff devolvió un "
            "unmodified_count inválido."
        )

    directory_map = diff.get(
        "directory_map"
    )

    if (
        not isinstance(directory_map, dict)
        or not all(
            isinstance(path, str)
            and isinstance(directory_id, str)
            and bool(directory_id.strip())
            for path, directory_id
            in directory_map.items()
        )
    ):
        raise RuntimeError(
            "sync/diff devolvió un directory_map inválido."
        )

    added_files.sort(
        key=lambda item: (
            item["path"],
            item["filename"],
        )
    )

    modified_files.sort(
        key=lambda item: (
            item["path"],
            item["filename"],
            item["stale_file_id"],
        )
    )

    deleted_files.sort(
        key=lambda item: (
            item["filename"],
            item["file_id"],
        )
    )

    directories_to_create.sort(
        key=lambda path: (
            path.count("/"),
            path,
        )
    )

    directory_ids_to_remove.sort()

    normalized_directory_map = dict(
        sorted(
            directory_map.items()
        )
    )

    exact_diff = {
        "added_files": added_files,
        "modified_files": modified_files,
        "deleted_files": deleted_files,
        "directories_to_create": (
            directories_to_create
        ),
        "directory_ids_to_remove": (
            directory_ids_to_remove
        ),
        "directory_map": (
            normalized_directory_map
        ),
        "unmodified": unmodified,
    }

    added = len(added_files)
    modified = len(modified_files)
    deleted = len(deleted_files)
    dirs_created = len(
        directories_to_create
    )
    dirs_removed = len(
        directory_ids_to_remove
    )

    return {
        "ok": True,
        "manifest_digest": manifest_digest,
        "diff_digest": canonical_digest(
            exact_diff
        ),
        **exact_diff,
        "added": added,
        "modified": modified,
        "deleted": deleted,
        "dirs_created": dirs_created,
        "dirs_removed": dirs_removed,
        "file_changes": (
            added
            + modified
            + deleted
        ),
        "total_changes": (
            added
            + modified
            + deleted
            + dirs_created
            + dirs_removed
        ),
        "warnings": [],
        "errors": [],
    }


def normalize_sync_result(
    result: Any,
    *,
    manifest_digest: str,
) -> dict[str, Any]:
    """Convierte SyncResult en un resultado JSON estable."""

    counters: dict[str, int] = {}

    for field_name in (
        "added",
        "modified",
        "deleted",
        "unmodified",
        "dirs_created",
        "dirs_removed",
    ):
        value = getattr(
            result,
            field_name,
            None,
        )

        if (
            isinstance(value, bool)
            or not isinstance(value, int)
            or value < 0
        ):
            raise RuntimeError(
                f"run_sync devolvió un contador "
                f"{field_name} inválido."
            )

        counters[field_name] = value

    def read_messages(
        field_name: str,
    ) -> list[str]:
        value = getattr(
            result,
            field_name,
            None,
        )

        if value is None:
            return []

        if (
            not isinstance(value, list)
            or not all(
                isinstance(message, str)
                and bool(message.strip())
                for message in value
            )
        ):
            raise RuntimeError(
                f"run_sync devolvió un campo "
                f"{field_name} inválido."
            )

        return list(value)

    warnings = read_messages(
        "warnings"
    )
    errors = read_messages(
        "errors"
    )

    file_changes = (
        counters["added"]
        + counters["modified"]
        + counters["deleted"]
    )

    directory_changes = (
        counters["dirs_created"]
        + counters["dirs_removed"]
    )

    return {
        "ok": not errors,
        "manifest_digest": manifest_digest,
        **counters,
        "file_changes": file_changes,
        "directory_changes": directory_changes,
        "total_changes": (
            file_changes
            + directory_changes
        ),
        "warnings": warnings,
        "errors": errors,
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Adaptador JSON controlado para oikb."
    )

    parser.add_argument(
        "command",
        choices=("diff", "sync"),
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

        manifest, manifest_digest = (
            build_source_manifest(
                source_path
            )
        )

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

        try:
            if arguments.command == "diff":
                diff = client.sync_diff(
                    kb_id,
                    manifest,
                )

                normalized_result = normalize_sync_diff(
                    diff,
                    manifest_digest=manifest_digest,
                )
            else:
                connector = FilesystemConnector(
                    source_path
                )

                sync_result = run_sync(
                    client=client,
                    connector=connector,
                    kb_id=kb_id,
                    dry_run=False,
                    verbose=False,
                    quiet=True,
                    concurrency=1,
                )

                normalized_result = normalize_sync_result(
                    sync_result,
                    manifest_digest=manifest_digest,
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
        "command": arguments.command,
        "source_name": source_name,
        "kb_id": kb_id,
        **normalized_result,
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