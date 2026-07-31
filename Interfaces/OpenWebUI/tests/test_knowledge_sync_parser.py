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


DIGEST = "a" * 64


class SyncParserKnowledgeManager(KnowledgeManager):
    """Manager mínimo para probar el lector sin red."""

    def __init__(self) -> None:
        self.source_name = "epsilon-system"


class KnowledgeSyncParserTests(unittest.TestCase):
    """Validación estricta del resultado de escritura."""

    def setUp(self) -> None:
        self.manager = SyncParserKnowledgeManager()

    def build_payload(
        self,
        **overrides,
    ) -> dict[str, object]:
        payload: dict[str, object] = {
            "source_name": "epsilon-system",
            "kb_id": "green-id",
            "manifest_digest": DIGEST,
            "added": 4,
            "modified": 0,
            "deleted": 0,
            "unmodified": 0,
            "dirs_created": 3,
            "dirs_removed": 0,
            "warnings": ["candidate prepared"],
            "errors": [],
        }
        payload.update(overrides)
        return payload

    def test_accepts_valid_sync_result(self) -> None:
        result = self.manager._read_sync_result(
            self.build_payload(),
            expected_kb_id="green-id",
        )

        self.assertEqual(result.kb_id, "green-id")
        self.assertEqual(result.manifest_digest, DIGEST)
        self.assertEqual(result.total_changes, 7)
        self.assertEqual(
            result.warnings,
            ("candidate prepared",),
        )
        self.assertFalse(result.failed)

    def test_rejects_unexpected_source_name(self) -> None:
        with self.assertRaisesRegex(
            KnowledgeManagerError,
            "fuente diferente",
        ):
            self.manager._read_sync_result(
                self.build_payload(
                    source_name="other-source",
                ),
                expected_kb_id="green-id",
            )

    def test_rejects_invalid_kb_id(self) -> None:
        with self.assertRaisesRegex(
            KnowledgeManagerError,
            "kb-id válido",
        ):
            self.manager._read_sync_result(
                self.build_payload(
                    kb_id="",
                ),
                expected_kb_id="green-id",
            )

    def test_rejects_different_kb_id(self) -> None:
        with self.assertRaisesRegex(
            KnowledgeManagerError,
            "slot diferente",
        ):
            self.manager._read_sync_result(
                self.build_payload(
                    kb_id="blue-id",
                ),
                expected_kb_id="green-id",
            )

    def test_rejects_invalid_digest(self) -> None:
        with self.assertRaisesRegex(
            KnowledgeManagerError,
            "SHA-256",
        ):
            self.manager._read_sync_result(
                self.build_payload(
                    manifest_digest="invalid",
                ),
                expected_kb_id="green-id",
            )

    def test_rejects_invalid_counters(self) -> None:
        invalid_values = (
            {},
            {"added": -1},
            {"added": True},
        )

        for overrides in invalid_values:
            with self.subTest(overrides=overrides):
                payload = self.build_payload(
                    **overrides
                )

                if not overrides:
                    payload.pop("added")

                with self.assertRaisesRegex(
                    KnowledgeManagerError,
                    "contador",
                ):
                    self.manager._read_sync_result(
                        payload,
                        expected_kb_id="green-id",
                    )

    def test_rejects_invalid_messages(self) -> None:
        invalid_values = (
            {"warnings": "warning"},
            {"errors": [42]},
            {"warnings": [""]},
        )

        for overrides in invalid_values:
            with self.subTest(overrides=overrides):
                with self.assertRaises(
                    KnowledgeManagerError
                ):
                    self.manager._read_sync_result(
                        self.build_payload(
                            **overrides
                        ),
                        expected_kb_id="green-id",
                    )

    def test_rejects_reported_sync_errors(self) -> None:
        with self.assertRaisesRegex(
            KnowledgeManagerError,
            "upload failed",
        ):
            self.manager._read_sync_result(
                self.build_payload(
                    errors=["upload failed"],
                ),
                expected_kb_id="green-id",
            )


if __name__ == "__main__":
    unittest.main()
