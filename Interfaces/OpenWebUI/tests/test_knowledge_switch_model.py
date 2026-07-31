from __future__ import annotations

from copy import deepcopy
from pathlib import Path
import sys
import unittest


INTERFACE_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(INTERFACE_DIR))

from knowledge import (
    KnowledgeManager,
    KnowledgeManagerError,
)
from knowledge_target import KnowledgeSlot


class KnowledgeSwitchModelTests(unittest.TestCase):
    """Pruebas de reemplazo Blue–Green en el modelo."""

    def setUp(self) -> None:
        self.blue = KnowledgeSlot(
            name="blue",
            kb_id="blue-id",
        )
        self.green = KnowledgeSlot(
            name="green",
            kb_id="green-id",
        )

    def entry(
        self,
        knowledge_id: str,
    ) -> dict[str, object]:
        return {
            "id": knowledge_id,
            "user_id": "owner-id",
            "name": knowledge_id,
            "description": "",
            "meta": None,
            "access_grants": [],
            "created_at": 1,
            "updated_at": 2,
            "user": {
                "id": "owner-id",
            },
            "write_access": True,
            "type": "collection",
        }

    def build_model(
        self,
    ) -> dict[str, object]:
        return {
            "id": "epsilon",
            "base_model_id": "gemma4:12b",
            "name": "Epsilon",
            "meta": {
                "knowledge": [
                    self.entry("unrelated-before"),
                    self.entry("blue-id"),
                    self.entry("unrelated-after"),
                ],
                "skillIds": ["skill-id"],
                "defaultFeatureIds": ["feature-id"],
            },
            "params": {
                "system": "controlled prompt",
            },
            "access_grants": [],
            "is_active": True,
            "created_at": 10,
            "updated_at": 20,
            "user_id": "owner-id",
        }

    def switch(
        self,
        model: dict[str, object],
    ) -> dict[str, object]:
        return KnowledgeManager._build_switched_model(
            model,
            model_id="epsilon",
            active_slot=self.blue,
            candidate_slot=self.green,
            candidate_entry=self.entry("green-id"),
        )

    def test_replaces_active_slot_in_place(
        self,
    ) -> None:
        result = self.switch(self.build_model())

        knowledge_ids = [
            entry["id"]
            for entry in result["meta"]["knowledge"]
        ]

        self.assertEqual(
            knowledge_ids,
            [
                "unrelated-before",
                "green-id",
                "unrelated-after",
            ],
        )

    def test_preserves_everything_outside_knowledge(
        self,
    ) -> None:
        original = self.build_model()
        result = self.switch(original)

        KnowledgeManager._require_same_model_outside_knowledge(
            original,
            result,
        )

        self.assertEqual(
            result["params"],
            original["params"],
        )
        self.assertEqual(
            result["meta"]["skillIds"],
            original["meta"]["skillIds"],
        )

    def test_does_not_mutate_original_model(
        self,
    ) -> None:
        original = self.build_model()
        snapshot = deepcopy(original)

        result = self.switch(original)
        result["meta"]["knowledge"][1]["name"] = "Changed"

        self.assertEqual(original, snapshot)

    def test_rejects_missing_active_slot(
        self,
    ) -> None:
        model = self.build_model()
        model["meta"]["knowledge"] = [
            self.entry("unrelated")
        ]

        with self.assertRaisesRegex(
            KnowledgeManagerError,
            "exactamente una",
        ):
            self.switch(model)

    def test_rejects_duplicate_active_slot(
        self,
    ) -> None:
        model = self.build_model()
        model["meta"]["knowledge"].append(
            self.entry("blue-id")
        )

        with self.assertRaisesRegex(
            KnowledgeManagerError,
            "exactamente una",
        ):
            self.switch(model)

    def test_rejects_candidate_already_attached(
        self,
    ) -> None:
        model = self.build_model()
        model["meta"]["knowledge"].append(
            self.entry("green-id")
        )

        with self.assertRaisesRegex(
            KnowledgeManagerError,
            "ya se encuentra conectado",
        ):
            self.switch(model)

    def test_semantic_comparison_ignores_server_fields(
        self,
    ) -> None:
        original = self.build_model()
        exported = deepcopy(original)

        exported["created_at"] = 100
        exported["updated_at"] = 200
        exported["user_id"] = "server-owner"
        exported["meta"]["knowledge"] = [
            self.entry("green-id")
        ]

        KnowledgeManager._require_same_model_outside_knowledge(
            original,
            exported,
        )

    def test_semantic_comparison_ignores_grant_metadata(
        self,
    ) -> None:
        original = self.build_model()
        exported = deepcopy(original)

        original["access_grants"] = [
            {
                "id": "old-id",
                "resource_type": "model",
                "resource_id": "epsilon",
                "principal_type": "group",
                "principal_id": "group-1",
                "permission": "read",
                "created_at": 10,
            },
        ]

        exported["access_grants"] = [
            {
                "id": "new-id",
                "resource_type": "model",
                "resource_id": "epsilon",
                "principal_type": "group",
                "principal_id": "group-1",
                "permission": "read",
                "created_at": 999,
            },
        ]

        KnowledgeManager._require_same_model_outside_knowledge(
            original,
            exported,
        )

    def test_semantic_comparison_rejects_grant_change(
        self,
    ) -> None:
        original = self.build_model()
        changed = deepcopy(original)

        original["access_grants"] = [
            {
                "id": "old-id",
                "resource_type": "model",
                "resource_id": "epsilon",
                "principal_type": "group",
                "principal_id": "group-1",
                "permission": "read",
                "created_at": 10,
            },
        ]

        changed["access_grants"] = [
            {
                "id": "new-id",
                "resource_type": "model",
                "resource_id": "epsilon",
                "principal_type": "group",
                "principal_id": "group-1",
                "permission": "write",
                "created_at": 999,
            },
        ]

        with self.assertRaisesRegex(
            KnowledgeManagerError,
            "ajenos a meta.knowledge",
        ):
            KnowledgeManager._require_same_model_outside_knowledge(
                original,
                changed,
            )

    def test_semantic_comparison_rejects_params_change(
        self,
    ) -> None:
        original = self.build_model()
        changed = deepcopy(original)
        changed["params"]["system"] = "different"

        with self.assertRaisesRegex(
            KnowledgeManagerError,
            "ajenos a meta.knowledge",
        ):
            (
                KnowledgeManager
                ._require_same_model_outside_knowledge(
                    original,
                    changed,
                )
            )

    def test_semantic_comparison_rejects_meta_change(
        self,
    ) -> None:
        original = self.build_model()
        changed = deepcopy(original)
        changed["meta"]["skillIds"] = ["other-skill"]

        with self.assertRaisesRegex(
            KnowledgeManagerError,
            "ajenos a meta.knowledge",
        ):
            (
                KnowledgeManager
                ._require_same_model_outside_knowledge(
                    original,
                    changed,
                )
            )


if __name__ == "__main__":
    unittest.main()
