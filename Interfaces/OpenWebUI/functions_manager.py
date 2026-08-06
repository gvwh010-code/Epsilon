from __future__ import annotations

from pathlib import Path
from typing import Any

from sync_module import SyncModule


class FunctionsManager(SyncModule):
    name = "Functions"

    def __init__(
        self,
        project_root: Path,
        client,
    ):
        self.project_root = project_root
        self.client = client
        self.functions_directory = (
            project_root
            / "Interfaces"
            / "OpenWebUI"
            / "functions"
        )

    @staticmethod
    def normalize_text(text: str) -> str:
        return (
            text
            .replace("\r\n", "\n")
            .strip()
        )

    @staticmethod
    def display_name(path: Path) -> str:
        return (
            path.stem
            .replace("_", " ")
            .title()
        )

    def read_local_functions(
        self,
    ) -> list[dict[str, Any]]:
        functions: list[dict[str, Any]] = []

        if not self.functions_directory.is_dir():
            return functions

        for path in sorted(
            self.functions_directory.glob("*.py")
        ):
            if path.name == "__init__.py":
                continue

            content = path.read_text(
                encoding="utf-8"
            )

            if not content.strip():
                continue

            function_id = path.stem.lower()

            functions.append(
                {
                    "id": function_id,
                    "name": self.display_name(path),
                    "content": content,
                    "path": path,
                    "is_active": True,
                }
            )

        return functions

    def read_remote_functions(
        self,
    ) -> list[dict[str, Any]]:
        response = self.client.get(
            "/api/v1/functions/export"
        )

        if not isinstance(response, list):
            return []

        return [
            function
            for function in response
            if isinstance(function, dict)
        ]

    def sync(
        self,
        dry_run: bool = True,
    ) -> bool:
        local_functions = (
            self.read_local_functions()
        )

        remote_functions = (
            self.read_remote_functions()
        )

        remote_by_id = {
            function.get("id"): function
            for function in remote_functions
            if function.get("id")
        }

        if not local_functions:
            print(
                "No se encontraron Functions locales."
            )
            return True

        success = True

        for local_function in local_functions:
            function_id = local_function["id"]
            function_name = local_function["name"]

            remote_function = remote_by_id.get(
                function_id
            )

            if remote_function is None:
                print(
                    f"+ Falta crear: "
                    f"{function_name} "
                    f"({function_id})"
                )

                if dry_run:
                    print(
                        "  Dry-run: no se aplicaron cambios"
                    )
                    success = False
                    continue

                created = self.client.post(
                    "/api/v1/functions/create",
                    {
                        "id": function_id,
                        "name": function_name,
                        "content": (
                            local_function["content"]
                        ),
                        "meta": {},
                    },
                )

                if not isinstance(created, dict):
                    raise RuntimeError(
                        "Open WebUI devolvió una "
                        "Function creada inválida."
                    )

                if not created.get(
                    "is_active",
                    False,
                ):
                    self.client.post(
                        (
                            "/api/v1/functions/id/"
                            f"{function_id}/toggle"
                        ),
                        {},
                    )

                print(
                    f"✓ {function_name} creada y activa"
                )
                continue

            local_content = self.normalize_text(
                local_function["content"]
            )

            remote_content = self.normalize_text(
                remote_function.get(
                    "content",
                    "",
                )
            )

            local_name = function_name
            remote_name = remote_function.get(
                "name",
                "",
            )

            content_matches = (
                local_content == remote_content
            )

            name_matches = (
                local_name == remote_name
            )

            active_matches = (
                remote_function.get("is_active")
                is True
            )

            function_matches = (
                content_matches
                and name_matches
                and active_matches
            )

            if function_matches:
                print(
                    f"✓ {function_name} sincronizada"
                )
                continue

            reasons: list[str] = []

            if not content_matches:
                reasons.append(
                    "contenido diferente"
                )

            if not name_matches:
                reasons.append(
                    "nombre diferente"
                )

            if not active_matches:
                reasons.append(
                    "Function inactiva"
                )

            print(
                f"~ Diferente: "
                f"{function_name} "
                f"({function_id})"
            )

            for reason in reasons:
                print(
                    f"  - {reason}"
                )

            if dry_run:
                print(
                    "  Dry-run: no se aplicaron cambios"
                )
                success = False
                continue

            if (
                not content_matches
                or not name_matches
            ):
                remote_meta = (
                    remote_function.get("meta")
                )

                if not isinstance(
                    remote_meta,
                    dict,
                ):
                    remote_meta = {}

                self.client.post(
                    (
                        "/api/v1/functions/id/"
                        f"{function_id}/update"
                    ),
                    {
                        "id": function_id,
                        "name": function_name,
                        "content": (
                            local_function["content"]
                        ),
                        "meta": remote_meta,
                    },
                )

            if not active_matches:
                self.client.post(
                    (
                        "/api/v1/functions/id/"
                        f"{function_id}/toggle"
                    ),
                    {},
                )

            print(
                f"✓ {function_name} actualizada"
            )

        if dry_run and not success:
            print(
                "Dry-run: no se aplicaron cambios"
            )

        return success
