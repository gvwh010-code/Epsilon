from __future__ import annotations

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


class KnowledgeSwitchEntryTests(unittest.TestCase):
    """Pruebas del objeto conectable del slot candidato."""

    def setUp(self) -> None:
        self.green = KnowledgeSlot(
            name="green",
            kb_id="green-id",
        )

    def build_active(self) -> dict[str, object]:
        return {
            "id": "blue-id",
            "user_id": "owner-id",
            "name": "Epsilon System",
            "description": "Blue",
            "meta": None,
            "access_grants": [],
            "created_at": 1,
            "updated_at": 2,
            "user": {
                "id": "owner-id",
                "name": "Owner",
            },
            "write_access": True,
            "type": "collection",
            "presentation_marker": "preserved",
        }

    def build_candidate(
        self,
        **overrides: object,
    ) -> dict[str, object]:
        candidate: dict[str, object] = {
            "id": "green-id",
            "user_id": "owner-id",
            "name": "Epsilon System Green",
            "description": "Green",
            "meta": None,
            "access_grants": [],
            "created_at": 3,
            "updated_at": 4,
            "files": None,
            "file_count": 4,
            "write_access": True,
            "user": {
                "id": "different-presentation",
            },
        }
        candidate.update(overrides)
        return candidate

    def test_builds_green_from_active_template(
        self,
    ) -> None:
        result = (
            KnowledgeManager
            ._build_candidate_knowledge_entry(
                self.build_active(),
                self.build_candidate(),
                self.green,
            )
        )

        self.assertEqual(result["id"], "green-id")
        self.assertEqual(
            result["name"],
            "Epsilon System Green",
        )
        self.assertEqual(result["type"], "collection")
        self.assertEqual(
            result["presentation_marker"],
            "preserved",
        )
        self.assertEqual(
            result["user"]["id"],
            "owner-id",
        )

    def test_omits_transient_candidate_fields(
        self,
    ) -> None:
        result = (
            KnowledgeManager
            ._build_candidate_knowledge_entry(
                self.build_active(),
                self.build_candidate(),
                self.green,
            )
        )

        self.assertNotIn("files", result)
        self.assertNotIn("file_count", result)

    def test_does_not_mutate_inputs(
        self,
    ) -> None:
        active = self.build_active()
        candidate = self.build_candidate()

        result = (
            KnowledgeManager
            ._build_candidate_knowledge_entry(
                active,
                candidate,
                self.green,
            )
        )

        result["user"]["name"] = "Changed"
        result["access_grants"].append(
            {"permission": "write"}
        )

        self.assertEqual(
            active["user"]["name"],
            "Owner",
        )
        self.assertEqual(
            candidate["access_grants"],
            [],
        )

    def test_rejects_wrong_candidate_id(
        self,
    ) -> None:
        with self.assertRaisesRegex(
            KnowledgeManagerError,
            "Knowledge diferente",
        ):
            (
                KnowledgeManager
                ._build_candidate_knowledge_entry(
                    self.build_active(),
                    self.build_candidate(
                        id="other-id"
                    ),
                    self.green,
                )
            )

    def test_rejects_different_owner(
        self,
    ) -> None:
        with self.assertRaisesRegex(
            KnowledgeManagerError,
            "propietarios diferentes",
        ):
            (
                KnowledgeManager
                ._build_candidate_knowledge_entry(
                    self.build_active(),
                    self.build_candidate(
                        user_id="other-owner"
                    ),
                    self.green,
                )
            )

    def test_rejects_missing_write_access(
        self,
    ) -> None:
        with self.assertRaisesRegex(
            KnowledgeManagerError,
            "acceso de escritura",
        ):
            (
                KnowledgeManager
                ._build_candidate_knowledge_entry(
                    self.build_active(),
                    self.build_candidate(
                        write_access=False
                    ),
                    self.green,
                )
            )

    def test_rejects_invalid_candidate_record(
        self,
    ) -> None:
        invalid_records = (
            self.build_candidate(name=""),
            self.build_candidate(meta=[]),
            self.build_candidate(
                access_grants="invalid"
            ),
            self.build_candidate(
                updated_at=True
            ),
        )

        for candidate in invalid_records:
            with self.subTest(candidate=candidate):
                with self.assertRaises(
                    KnowledgeManagerError
                ):
                    (
                        KnowledgeManager
                        ._build_candidate_knowledge_entry(
                            self.build_active(),
                            candidate,
                            self.green,
                        )
                    )


if __name__ == "__main__":
    unittest.main()
