from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from projection import ProjectionManager


class FakeClient:
    def __init__(self, models):
        self.models = deepcopy(models)

    def export_models(self):
        return deepcopy(self.models)


class ProjectionDefaultFeatureTests(
    unittest.TestCase
):
    def make_model(self):
        return {
            "id": "epsilon",
            "name": "Epsilon",
            "base_model_id": "qwen-test",
            "meta": {
                "defaultFeatureIds": [
                    "web_search",
                    "code_interpreter",
                ],
                "toolIds": [
                    "unrelated_tool",
                ],
                "filterIds": [
                    "unrelated_filter",
                ],
            },
            "params": {
                "system": "controlled prompt",
            },
            "is_active": True,
        }

    def make_manager(self, root, model):
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
            base_model_id="qwen-test",
            required_tool_ids=(
                "epsilon_research",
            ),
            required_filter_ids=(
                "epsilon_research_grounding",
            ),
            forbidden_default_feature_ids=(
                "web_search",
            ),
        )

    def test_plan_detects_forbidden_default(
        self,
    ):
        model = self.make_model()

        with TemporaryDirectory() as root:
            manager = self.make_manager(
                root,
                model,
            )

            plan = manager.plan()

        self.assertTrue(plan.has_changes)

        reasons = " ".join(
            plan.changes[0].reasons
        )

        self.assertIn(
            "web_search",
            reasons,
        )

        self.assertIn(
            "epsilon_research_grounding",
            reasons,
        )

    def test_build_preserves_other_defaults(
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
            result["meta"][
                "defaultFeatureIds"
            ],
            [
                "code_interpreter",
            ],
        )

        self.assertEqual(
            result["meta"]["toolIds"],
            [
                "unrelated_tool",
                "epsilon_research",
            ],
        )

        self.assertEqual(
            result["meta"]["filterIds"],
            [
                "unrelated_filter",
                "epsilon_research_grounding",
            ],
        )


if __name__ == "__main__":
    unittest.main()
