from __future__ import annotations

import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

OPENWEBUI_DIR = (
    Path(__file__).resolve().parents[1]
)

if str(OPENWEBUI_DIR) not in sys.path:
    sys.path.insert(
        0,
        str(OPENWEBUI_DIR),
    )

from projection import ProjectionManager


class FakeClient:
    def __init__(self, models):
        self.models = models

    def export_models(self):
        return self.models


class ProjectionForbiddenFeaturesTests(
    unittest.TestCase
):
    def make_model(self):
        return {
            "id": "epsilon",
            "name": "Epsilon",
            "base_model_id": "epsilon_router",
            "meta": {
                "toolIds": [
                    "unrelated_tool",
                    "epsilon_research",
                ],
                "filterIds": [
                    "unrelated_filter",
                    "epsilon_research_grounding",
                ],
                "defaultFeatureIds": [],
            },
            "params": {
                "system": "controlled prompt",
            },
            "is_active": True,
        }

    def make_manager(
        self,
        root,
        model,
    ):
        projection_dir = (
            Path(root)
            / "Interfaces"
            / "OpenWebUI"
        )

        projection_dir.mkdir(
            parents=True,
            exist_ok=True,
        )

        (
            projection_dir
            / "EPSILON_PROJECTION.md"
        ).write_text(
            "controlled prompt",
            encoding="utf-8",
        )

        return ProjectionManager(
            project_root=Path(root),
            client=FakeClient([model]),
            model_id="epsilon",
            base_model_id="epsilon_router",
            forbidden_tool_ids=(
                "epsilon_research",
            ),
            forbidden_filter_ids=(
                "epsilon_research_grounding",
            ),
        )

    def test_plan_detects_forbidden_tool_and_filter(
        self,
    ):
        model = self.make_model()

        with TemporaryDirectory() as root:
            manager = self.make_manager(
                root,
                model,
            )

            plan = manager.plan()

        self.assertTrue(
            plan.has_changes
        )

        reasons = " ".join(
            plan.changes[0].reasons
        )

        self.assertIn(
            "epsilon_research",
            reasons,
        )

        self.assertIn(
            "epsilon_research_grounding",
            reasons,
        )

    def test_build_removes_only_forbidden_ids(
        self,
    ):
        model = self.make_model()

        with TemporaryDirectory() as root:
            manager = self.make_manager(
                root,
                model,
            )

            result = manager.build_import_model(
                model
            )

        self.assertEqual(
            result["meta"]["toolIds"],
            ["unrelated_tool"],
        )

        self.assertEqual(
            result["meta"]["filterIds"],
            ["unrelated_filter"],
        )


if __name__ == "__main__":
    unittest.main()
