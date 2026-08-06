from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from tools_manager import ToolsManager


class FakeClient:
    def __init__(
        self,
        tools: list[dict] | None = None,
    ):
        self.tools = {
            tool["id"]: deepcopy(tool)
            for tool in (tools or [])
        }
        self.post_calls: list[
            tuple[str, dict]
        ] = []

    def get(
        self,
        endpoint: str,
    ):
        if endpoint != "/api/v1/tools/export":
            raise AssertionError(
                f"GET inesperado: {endpoint}"
            )

        return [
            deepcopy(tool)
            for tool in self.tools.values()
        ]

    def post(
        self,
        endpoint: str,
        payload: dict,
    ):
        self.post_calls.append(
            (
                endpoint,
                deepcopy(payload),
            )
        )

        if endpoint == "/api/v1/tools/create":
            created = {
                **deepcopy(payload),
                "specs": [],
                "access_grants": [],
            }

            self.tools[payload["id"]] = (
                deepcopy(created)
            )

            return created

        prefix = "/api/v1/tools/id/"
        suffix = "/update"

        if (
            endpoint.startswith(prefix)
            and endpoint.endswith(suffix)
        ):
            tool_id = endpoint[
                len(prefix) : -len(suffix)
            ]

            updated = {
                **deepcopy(
                    self.tools.get(
                        tool_id,
                        {},
                    )
                ),
                **deepcopy(payload),
            }

            self.tools[tool_id] = (
                deepcopy(updated)
            )

            return updated

        raise AssertionError(
            f"POST inesperado: {endpoint}"
        )


class ToolsManagerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = TemporaryDirectory()
        self.root = Path(
            self.temp_dir.name
        )

        tools_dir = (
            self.root
            / "Interfaces"
            / "OpenWebUI"
            / "tools"
        )

        tools_dir.mkdir(parents=True)

        self.content = (
            "class Tools:\n"
            "    def research(self, question: str) -> str:\n"
            "        return question\n"
        )

        (
            tools_dir
            / "epsilon_research.py"
        ).write_text(
            self.content,
            encoding="utf-8",
        )

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def make_manager(
        self,
        client: FakeClient,
    ) -> ToolsManager:
        return ToolsManager(
            project_root=self.root,
            client=client,
        )

    def test_missing_tool_is_detected(self) -> None:
        client = FakeClient()
        manager = self.make_manager(client)

        self.assertFalse(
            manager.sync(
                dry_run=True,
            )
        )

        self.assertEqual(
            client.post_calls,
            [],
        )

    def test_update_preserves_meta_and_access_grants(
        self,
    ) -> None:
        remote_tool = {
            "id": "epsilon_research",
            "name": "Epsilon Research",
            "content": "contenido viejo",
            "meta": {
                "manifest": {
                    "version": "remote",
                },
            },
            "access_grants": [
                {
                    "id": "server-generated",
                    "permission": "read",
                }
            ],
            "specs": [],
        }

        client = FakeClient(
            [remote_tool]
        )
        manager = self.make_manager(client)

        self.assertTrue(
            manager.sync(
                dry_run=False,
            )
        )

        self.assertEqual(
            len(client.post_calls),
            1,
        )

        endpoint, payload = (
            client.post_calls[0]
        )

        self.assertEqual(
            endpoint,
            (
                "/api/v1/tools/id/"
                "epsilon_research/update"
            ),
        )

        self.assertEqual(
            payload["meta"],
            remote_tool["meta"],
        )

        self.assertEqual(
            payload["access_grants"],
            remote_tool[
                "access_grants"
            ],
        )

        self.assertEqual(
            payload["content"],
            self.content,
        )

    def test_matching_tool_is_in_sync(
        self,
    ) -> None:
        client = FakeClient(
            [
                {
                    "id": "epsilon_research",
                    "name": "Epsilon Research",
                    "content": self.content,
                    "meta": {},
                    "access_grants": [],
                    "specs": [],
                }
            ]
        )

        manager = self.make_manager(client)

        self.assertTrue(
            manager.sync(
                dry_run=True,
            )
        )

        self.assertEqual(
            client.post_calls,
            [],
        )


if __name__ == "__main__":
    unittest.main()
