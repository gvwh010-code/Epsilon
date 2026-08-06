from __future__ import annotations

from pathlib import Path
from typing import Any

from sync_module import SyncModule


class ToolsManager(SyncModule):
    name = "Tools"

    def __init__(
        self,
        project_root: Path,
        client,
    ):
        self.project_root = project_root
        self.client = client
        self.tools_directory = (
            project_root
            / "Interfaces"
            / "OpenWebUI"
            / "tools"
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

    def read_local_tools(
        self,
    ) -> list[dict[str, Any]]:
        tools: list[dict[str, Any]] = []

        if not self.tools_directory.is_dir():
            return tools

        for path in sorted(
            self.tools_directory.glob("*.py")
        ):
            if path.name == "__init__.py":
                continue

            content = path.read_text(
                encoding="utf-8"
            )

            if not content.strip():
                continue

            tool_id = path.stem.lower()

            tools.append(
                {
                    "id": tool_id,
                    "name": self.display_name(path),
                    "content": content,
                    "path": path,
                }
            )

        return tools

    def read_remote_tools(
        self,
    ) -> list[dict[str, Any]]:
        response = self.client.get(
            "/api/v1/tools/export"
        )

        if not isinstance(response, list):
            return []

        return [
            tool
            for tool in response
            if isinstance(tool, dict)
        ]

    def sync(
        self,
        dry_run: bool = True,
    ) -> bool:
        local_tools = self.read_local_tools()
        remote_tools = self.read_remote_tools()

        remote_by_id = {
            tool.get("id"): tool
            for tool in remote_tools
            if tool.get("id")
        }

        if not local_tools:
            print(
                "No se encontraron Tools locales."
            )
            return True

        success = True

        for local_tool in local_tools:
            tool_id = local_tool["id"]
            tool_name = local_tool["name"]

            remote_tool = remote_by_id.get(
                tool_id
            )

            if remote_tool is None:
                print(
                    f"+ Falta crear: "
                    f"{tool_name} "
                    f"({tool_id})"
                )

                if dry_run:
                    print(
                        "  Dry-run: no se aplicaron cambios"
                    )
                    success = False
                    continue

                created = self.client.post(
                    "/api/v1/tools/create",
                    {
                        "id": tool_id,
                        "name": tool_name,
                        "content": local_tool["content"],
                        "meta": {},
                    },
                )

                if not isinstance(created, dict):
                    raise RuntimeError(
                        "Open WebUI devolvió un "
                        "Tool creado inválido."
                    )

                if created.get("id") != tool_id:
                    raise RuntimeError(
                        "Open WebUI creó un Tool "
                        "diferente del solicitado."
                    )

                print(
                    f"✓ {tool_name} creado"
                )
                continue

            local_content = self.normalize_text(
                local_tool["content"]
            )

            remote_content = self.normalize_text(
                remote_tool.get(
                    "content",
                    "",
                )
            )

            local_name = tool_name
            remote_name = remote_tool.get(
                "name",
                "",
            )

            content_matches = (
                local_content == remote_content
            )

            name_matches = (
                local_name == remote_name
            )

            tool_matches = (
                content_matches
                and name_matches
            )

            if tool_matches:
                print(
                    f"✓ {tool_name} sincronizado"
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

            print(
                f"~ Diferente: "
                f"{tool_name} "
                f"({tool_id})"
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

            remote_meta = remote_tool.get(
                "meta"
            )

            if not isinstance(
                remote_meta,
                dict,
            ):
                remote_meta = {}

            remote_access_grants = (
                remote_tool.get(
                    "access_grants"
                )
            )

            if not isinstance(
                remote_access_grants,
                list,
            ):
                remote_access_grants = []

            updated = self.client.post(
                (
                    "/api/v1/tools/id/"
                    f"{tool_id}/update"
                ),
                {
                    "id": tool_id,
                    "name": tool_name,
                    "content": local_tool["content"],
                    "meta": remote_meta,
                    "access_grants": (
                        remote_access_grants
                    ),
                },
            )

            if not isinstance(updated, dict):
                raise RuntimeError(
                    "Open WebUI devolvió un "
                    "Tool actualizado inválido."
                )

            if updated.get("id") != tool_id:
                raise RuntimeError(
                    "Open WebUI actualizó un Tool "
                    "diferente del solicitado."
                )

            print(
                f"✓ {tool_name} actualizado"
            )

        if dry_run and not success:
            print(
                "Dry-run: no se aplicaron cambios"
            )

        return success
