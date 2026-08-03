from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from projection import ProjectionManager


class FakeClient:
    def __init__(self, model: dict | None):
        self.model = deepcopy(model)
        self.import_calls: list[list[dict]] = []
        self.update_calls: list[tuple[dict, bool]] = []

    def export_models(self) -> list[dict]:
        if self.model is None:
            return []

        return [deepcopy(self.model)]

    def import_models(self, models: list[dict]) -> None:
        self.import_calls.append(deepcopy(models))

        incoming = deepcopy(models[0])

        existing_access_grants = (
            deepcopy(self.model.get("access_grants", []))
            if self.model is not None
            else []
        )

        self.model = incoming

        if "access_grants" not in incoming:
            self.model["access_grants"] = existing_access_grants

    def update_model(
        self,
        model: dict,
        *,
        include_access_grants: bool = True,
    ) -> dict:
        self.update_calls.append(
            (deepcopy(model), include_access_grants)
        )

        access_grants = (
            deepcopy(self.model.get("access_grants", []))
            if self.model is not None
            else []
        )

        self.model = deepcopy(model)
        self.model["access_grants"] = access_grants

        return deepcopy(self.model)


class ProjectionManagerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = TemporaryDirectory()
        self.root = Path(self.temp_dir.name)

        projection_dir = (
            self.root
            / "Interfaces"
            / "OpenWebUI"
        )
        projection_dir.mkdir(parents=True)

        self.prompt = "# Epsilon\n\nPrompt actual.\n"

        (
            projection_dir
            / "EPSILON_PROJECTION.md"
        ).write_text(
            self.prompt,
            encoding="utf-8",
        )

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def make_model(self) -> dict:
        return {
            "id": "epsilon",
            "name": "Epsilon",
            "base_model_id": "gemma4-12b-llamacpp",
            "meta": {
                "capabilities": {
                    "vision": True,
                    "web_search": True,
                    "builtin_tools": True,
                },
                "skillIds": ["research"],
                "defaultFeatureIds": ["web_search"],
            },
            "params": {
                "system": self.prompt,
                "function_calling": "native",
            },
            "is_active": True,
            "access_grants": [],
        }

    def make_manager(
        self,
        client: FakeClient,
    ) -> ProjectionManager:
        return ProjectionManager(
            project_root=self.root,
            client=client,
            model_id="epsilon",
            base_model_id="gemma4-12b-llamacpp",
        )

    def test_plan_is_empty_when_projection_matches(self) -> None:
        client = FakeClient(self.make_model())
        manager = self.make_manager(client)

        self.assertFalse(manager.plan().has_changes)

    def test_plan_detects_different_base_model(self) -> None:
        model = self.make_model()
        model["base_model_id"] = "gemma4:12b"

        manager = self.make_manager(FakeClient(model))
        plan = manager.plan()

        self.assertTrue(plan.has_changes)
        self.assertIn(
            "modelo base",
            plan.changes[0].reasons[0],
        )

    def test_plan_detects_different_system_prompt(self) -> None:
        model = self.make_model()
        model["params"]["system"] = "prompt viejo"

        manager = self.make_manager(FakeClient(model))

        self.assertTrue(manager.plan().has_changes)

    def test_build_model_preserves_meta_and_params(self) -> None:
        model = self.make_model()

        manager = self.make_manager(FakeClient(model))
        result = manager.build_import_model(model)

        self.assertEqual(result["meta"], model["meta"])
        self.assertEqual(
            result["params"]["function_calling"],
            "native",
        )
        self.assertEqual(
            result["base_model_id"],
            "gemma4-12b-llamacpp",
        )

    def test_update_preserves_server_access_grants(self) -> None:
        model = self.make_model()
        model["params"]["system"] = "prompt viejo"
        model["access_grants"] = [
            {
                "id": "server-generated",
                "permission": "read",
            }
        ]

        client = FakeClient(model)
        manager = self.make_manager(client)
        plan = manager.plan()

        manager.apply(plan)

        self.assertEqual(len(client.import_calls), 1)
        self.assertEqual(len(client.update_calls), 0)

        imported_model = client.import_calls[0][0]

        self.assertNotIn(
            "access_grants",
            imported_model,
        )

        self.assertEqual(
            client.model["access_grants"],
            model["access_grants"],
        )

        self.assertFalse(manager.plan().has_changes)

if __name__ == "__main__":
    unittest.main()