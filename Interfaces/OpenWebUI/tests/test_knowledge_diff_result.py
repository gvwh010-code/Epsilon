from __future__ import annotations

from pathlib import Path
import sys
import unittest


INTERFACE_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(INTERFACE_DIR))

from results import (
    KnowledgeAddedFile,
    KnowledgeDeletedFile,
    KnowledgeDiffResult,
    KnowledgeModifiedFile,
    KnowledgeSyncResult,
)

DIGEST_A = "a" * 64
DIGEST_B = "b" * 64


class KnowledgeFileChangeTests(unittest.TestCase):
    """Pruebas de los cambios exactos de archivos."""

    def test_added_file_builds_relative_path(self) -> None:
        nested = KnowledgeAddedFile(
            path="Knowledge/Game",
            filename="CURRENT_STATE.md",
        )
        root = KnowledgeAddedFile(
            path="",
            filename="README.md",
        )

        self.assertEqual(
            nested.relative_path,
            "Knowledge/Game/CURRENT_STATE.md",
        )
        self.assertEqual(
            root.relative_path,
            "README.md",
        )

    def test_modified_file_builds_relative_path(self) -> None:
        change = KnowledgeModifiedFile(
            path="Core",
            filename="EPSILON_CORE.md",
            stale_file_id="remote-file-id",
        )

        self.assertEqual(
            change.relative_path,
            "Core/EPSILON_CORE.md",
        )

    def test_rejects_invalid_file_details(self) -> None:
        with self.assertRaises(ValueError):
            KnowledgeAddedFile(
                path="Core",
                filename="",
            )

        with self.assertRaises(ValueError):
            KnowledgeModifiedFile(
                path="Core",
                filename="EPSILON_CORE.md",
                stale_file_id="",
            )

        with self.assertRaises(ValueError):
            KnowledgeDeletedFile(
                filename="OLD.md",
                file_id="",
            )


class KnowledgeDiffResultTests(unittest.TestCase):
    """Pruebas de consistencia del plan exacto."""

    def build_exact_result(
        self,
        **overrides,
    ) -> KnowledgeDiffResult:
        values = {
            "source_name": "epsilon-system",
            "kb_id": "green-id",
            "manifest_digest": DIGEST_A,
            "diff_digest": DIGEST_B,
            "added": 1,
            "modified": 1,
            "deleted": 1,
            "unmodified": 2,
            "dirs_created": 1,
            "dirs_removed": 1,
            "added_files": (
                KnowledgeAddedFile(
                    path="Core",
                    filename="NEW.md",
                ),
            ),
            "modified_files": (
                KnowledgeModifiedFile(
                    path="Knowledge/Game",
                    filename="CURRENT_STATE.md",
                    stale_file_id="stale-id",
                ),
            ),
            "deleted_files": (
                KnowledgeDeletedFile(
                    filename="OLD.md",
                    file_id="old-id",
                ),
            ),
            "directories_to_create": (
                "Knowledge/Game",
            ),
            "directory_ids_to_remove": (
                "old-directory-id",
            ),
            "directory_map": (
                (
                    "Core",
                    "core-directory-id",
                ),
            ),
        }
        values.update(overrides)

        return KnowledgeDiffResult(**values)

    def test_accepts_consistent_exact_result(self) -> None:
        result = self.build_exact_result()

        self.assertTrue(
            result.has_exact_details
        )
        self.assertTrue(
            result.has_changes
        )
        self.assertTrue(
            result.has_destructive_changes
        )
        self.assertEqual(
            result.file_changes,
            3,
        )
        self.assertEqual(
            result.directory_changes,
            2,
        )
        self.assertEqual(
            result.total_changes,
            5,
        )

    def test_accepts_exact_clean_result(self) -> None:
        result = KnowledgeDiffResult(
            source_name="epsilon-system",
            kb_id="blue-id",
            manifest_digest=DIGEST_A,
            diff_digest=DIGEST_B,
            unmodified=4,
        )

        self.assertTrue(
            result.has_exact_details
        )
        self.assertFalse(
            result.has_changes
        )
        self.assertEqual(
            result.total_changes,
            0,
        )

    def test_rejects_invalid_digests(self) -> None:
        with self.assertRaisesRegex(
            ValueError,
            "manifest_digest",
        ):
            self.build_exact_result(
                manifest_digest="not-a-digest",
            )

        with self.assertRaisesRegex(
            ValueError,
            "diff_digest",
        ):
            self.build_exact_result(
                diff_digest="z" * 64,
            )

    def test_rejects_inconsistent_file_counter(self) -> None:
        with self.assertRaisesRegex(
            ValueError,
            "contador added",
        ):
            self.build_exact_result(
                added=2,
            )

        with self.assertRaisesRegex(
            ValueError,
            "contador modified",
        ):
            self.build_exact_result(
                modified=0,
            )

        with self.assertRaisesRegex(
            ValueError,
            "contador deleted",
        ):
            self.build_exact_result(
                deleted=0,
            )

    def test_rejects_inconsistent_directory_counter(
        self,
    ) -> None:
        with self.assertRaisesRegex(
            ValueError,
            "contador dirs_created",
        ):
            self.build_exact_result(
                dirs_created=2,
            )

        with self.assertRaisesRegex(
            ValueError,
            "contador dirs_removed",
        ):
            self.build_exact_result(
                dirs_removed=0,
            )

    def test_rejects_invalid_directory_details(self) -> None:
        with self.assertRaisesRegex(
            ValueError,
            "carpetas por crear",
        ):
            self.build_exact_result(
                directories_to_create=("",),
            )

        with self.assertRaisesRegex(
            ValueError,
            "carpetas por retirar",
        ):
            self.build_exact_result(
                directory_ids_to_remove=("",),
            )

        with self.assertRaisesRegex(
            ValueError,
            "mapa de carpetas",
        ):
            self.build_exact_result(
                directory_map=(
                    ("Core", ""),
                ),
            )

    def test_frozen_results_compare_exactly(self) -> None:
        approved = self.build_exact_result()
        identical = self.build_exact_result()
        changed_remote_state = self.build_exact_result(
            diff_digest="c" * 64,
        )

        self.assertEqual(
            approved,
            identical,
        )
        self.assertNotEqual(
            approved,
            changed_remote_state,
        )

class KnowledgeSyncResultTests(unittest.TestCase):
    """Pruebas del resultado de escritura controlada."""

    def test_accepts_successful_sync_result(self) -> None:
        result = KnowledgeSyncResult(
            source_name="epsilon-system",
            kb_id="green-id",
            manifest_digest=DIGEST_A,
            added=4,
            dirs_created=3,
        )

        self.assertFalse(result.failed)
        self.assertEqual(result.file_changes, 4)
        self.assertEqual(result.directory_changes, 3)
        self.assertEqual(result.total_changes, 7)

    def test_preserves_sync_warnings_and_errors(self) -> None:
        result = KnowledgeSyncResult(
            source_name="epsilon-system",
            kb_id="green-id",
            manifest_digest=DIGEST_A,
            warnings=("warning",),
            errors=("upload failed",),
        )

        self.assertTrue(result.failed)
        self.assertEqual(result.warnings, ("warning",))
        self.assertEqual(result.errors, ("upload failed",))

    def test_rejects_invalid_sync_digest(self) -> None:
        with self.assertRaisesRegex(
            ValueError,
            "manifest_digest",
        ):
            KnowledgeSyncResult(
                source_name="epsilon-system",
                kb_id="green-id",
                manifest_digest="invalid",
            )

    def test_rejects_invalid_sync_counters(self) -> None:
        with self.assertRaisesRegex(
            ValueError,
            "contadores",
        ):
            KnowledgeSyncResult(
                source_name="epsilon-system",
                kb_id="green-id",
                manifest_digest=DIGEST_A,
                added=-1,
            )

        with self.assertRaisesRegex(
            ValueError,
            "contadores",
        ):
            KnowledgeSyncResult(
                source_name="epsilon-system",
                kb_id="green-id",
                manifest_digest=DIGEST_A,
                added=True,
            )

if __name__ == "__main__":
    unittest.main()