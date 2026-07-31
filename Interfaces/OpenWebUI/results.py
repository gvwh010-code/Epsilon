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
class KnowledgeAddedFile:
    """Archivo nuevo detectado en el destino Knowledge."""

    path: str
    filename: str

    def __post_init__(self) -> None:
        if not isinstance(self.path, str):
            raise ValueError(
                "La ruta de un archivo agregado debe ser texto."
            )

        if (
            not isinstance(self.filename, str)
            or not self.filename.strip()
        ):
            raise ValueError(
                "El nombre de un archivo agregado no es válido."
            )

    @property
    def relative_path(self) -> str:
        if self.path:
            return f"{self.path}/{self.filename}"

        return self.filename


@dataclass(frozen=True)
class KnowledgeModifiedFile:
    """Archivo remoto que debe ser reemplazado."""

    path: str
    filename: str
    stale_file_id: str

    def __post_init__(self) -> None:
        if not isinstance(self.path, str):
            raise ValueError(
                "La ruta de un archivo modificado debe ser texto."
            )

        if (
            not isinstance(self.filename, str)
            or not self.filename.strip()
        ):
            raise ValueError(
                "El nombre de un archivo modificado no es válido."
            )

        if (
            not isinstance(self.stale_file_id, str)
            or not self.stale_file_id.strip()
        ):
            raise ValueError(
                "El identificador remoto obsoleto no es válido."
            )

    @property
    def relative_path(self) -> str:
        if self.path:
            return f"{self.path}/{self.filename}"

        return self.filename


@dataclass(frozen=True)
class KnowledgeDeletedFile:
    """Archivo remoto ausente en el manifiesto local."""

    filename: str
    file_id: str

    def __post_init__(self) -> None:
        if (
            not isinstance(self.filename, str)
            or not self.filename.strip()
        ):
            raise ValueError(
                "El nombre de un archivo eliminado no es válido."
            )

        if (
            not isinstance(self.file_id, str)
            or not self.file_id.strip()
        ):
            raise ValueError(
                "El identificador del archivo eliminado no es válido."
            )


@dataclass(frozen=True)
class KnowledgeDiffResult:
    """Comparación estructurada y exacta de una fuente Knowledge."""

    source_name: str
    kb_id: str

    manifest_digest: str = ""
    diff_digest: str = ""

    added: int = 0
    modified: int = 0
    deleted: int = 0
    unmodified: int = 0

    dirs_created: int = 0
    dirs_removed: int = 0

    added_files: tuple[KnowledgeAddedFile, ...] = ()
    modified_files: tuple[KnowledgeModifiedFile, ...] = ()
    deleted_files: tuple[KnowledgeDeletedFile, ...] = ()

    directories_to_create: tuple[str, ...] = ()
    directory_ids_to_remove: tuple[str, ...] = ()
    directory_map: tuple[tuple[str, str], ...] = ()

    warnings: tuple[str, ...] = ()
    errors: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if (
            not isinstance(self.source_name, str)
            or not self.source_name.strip()
        ):
            raise ValueError(
                "El nombre de la fuente Knowledge no es válido."
            )

        if (
            not isinstance(self.kb_id, str)
            or not self.kb_id.strip()
        ):
            raise ValueError(
                "El identificador de Knowledge no es válido."
            )

        counters = (
            self.added,
            self.modified,
            self.deleted,
            self.unmodified,
            self.dirs_created,
            self.dirs_removed,
        )

        if any(
            isinstance(value, bool)
            or not isinstance(value, int)
            or value < 0
            for value in counters
        ):
            raise ValueError(
                "Los contadores de Knowledge deben ser "
                "números enteros no negativos."
            )

        if not all(
            isinstance(item, KnowledgeAddedFile)
            for item in self.added_files
        ):
            raise ValueError(
                "La lista de archivos agregados no es válida."
            )

        if not all(
            isinstance(item, KnowledgeModifiedFile)
            for item in self.modified_files
        ):
            raise ValueError(
                "La lista de archivos modificados no es válida."
            )

        if not all(
            isinstance(item, KnowledgeDeletedFile)
            for item in self.deleted_files
        ):
            raise ValueError(
                "La lista de archivos eliminados no es válida."
            )

        if not all(
            isinstance(path, str)
            and bool(path.strip())
            for path in self.directories_to_create
        ):
            raise ValueError(
                "Las carpetas por crear no son válidas."
            )

        if not all(
            isinstance(directory_id, str)
            and bool(directory_id.strip())
            for directory_id in self.directory_ids_to_remove
        ):
            raise ValueError(
                "Los identificadores de carpetas por retirar "
                "no son válidos."
            )

        if not all(
            isinstance(item, tuple)
            and len(item) == 2
            and isinstance(item[0], str)
            and isinstance(item[1], str)
            and bool(item[1].strip())
            for item in self.directory_map
        ):
            raise ValueError(
                "El mapa de carpetas remotas no es válido."
            )

        if not all(
            isinstance(message, str)
            for message in (
                *self.warnings,
                *self.errors,
            )
        ):
            raise ValueError(
                "Los mensajes de Knowledge no son válidos."
            )

        exact_details_present = bool(
            self.manifest_digest
            or self.diff_digest
            or self.added_files
            or self.modified_files
            or self.deleted_files
            or self.directories_to_create
            or self.directory_ids_to_remove
            or self.directory_map
        )

        if exact_details_present:
            hexadecimal = set(
                "0123456789abcdefABCDEF"
            )

            for field_name, digest in (
                (
                    "manifest_digest",
                    self.manifest_digest,
                ),
                (
                    "diff_digest",
                    self.diff_digest,
                ),
            ):
                if (
                    not isinstance(digest, str)
                    or len(digest) != 64
                    or any(
                        character not in hexadecimal
                        for character in digest
                    )
                ):
                    raise ValueError(
                        f"{field_name} no contiene "
                        "una huella SHA-256 válida."
                    )

            expected_counts = (
                (
                    "added",
                    self.added,
                    len(self.added_files),
                ),
                (
                    "modified",
                    self.modified,
                    len(self.modified_files),
                ),
                (
                    "deleted",
                    self.deleted,
                    len(self.deleted_files),
                ),
                (
                    "dirs_created",
                    self.dirs_created,
                    len(self.directories_to_create),
                ),
                (
                    "dirs_removed",
                    self.dirs_removed,
                    len(self.directory_ids_to_remove),
                ),
            )

            for field_name, counter, exact_count in expected_counts:
                if counter != exact_count:
                    raise ValueError(
                        f"El contador {field_name} no coincide "
                        "con los detalles exactos del plan."
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

    @property
    def has_exact_details(self) -> bool:
        return bool(
            self.manifest_digest
            and self.diff_digest
        )


@dataclass(frozen=True)
class KnowledgeSyncResult:
    """Resultado estructurado de preparar un slot Knowledge."""

    source_name: str
    kb_id: str
    manifest_digest: str

    added: int = 0
    modified: int = 0
    deleted: int = 0
    unmodified: int = 0

    dirs_created: int = 0
    dirs_removed: int = 0

    warnings: tuple[str, ...] = ()
    errors: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if (
            not isinstance(self.source_name, str)
            or not self.source_name.strip()
        ):
            raise ValueError(
                "El nombre de la fuente Knowledge no es válido."
            )

        if (
            not isinstance(self.kb_id, str)
            or not self.kb_id.strip()
        ):
            raise ValueError(
                "El identificador de Knowledge no es válido."
            )

        if (
            not isinstance(self.manifest_digest, str)
            or len(self.manifest_digest) != 64
            or any(
                character not in "0123456789abcdefABCDEF"
                for character in self.manifest_digest
            )
        ):
            raise ValueError(
                "manifest_digest no contiene "
                "una huella SHA-256 válida."
            )

        counters = (
            self.added,
            self.modified,
            self.deleted,
            self.unmodified,
            self.dirs_created,
            self.dirs_removed,
        )

        if any(
            isinstance(value, bool)
            or not isinstance(value, int)
            or value < 0
            for value in counters
        ):
            raise ValueError(
                "Los contadores de sincronización Knowledge "
                "deben ser enteros no negativos."
            )

        if not all(
            isinstance(message, str)
            and bool(message.strip())
            for message in (
                *self.warnings,
                *self.errors,
            )
        ):
            raise ValueError(
                "Los mensajes de sincronización Knowledge "
                "no son válidos."
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
