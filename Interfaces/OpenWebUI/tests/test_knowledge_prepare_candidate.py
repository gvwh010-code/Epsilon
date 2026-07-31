from __future__ import annotations

from contextlib import contextmanager
from pathlib import Path
import sys
import unittest
from typing import Iterator


INTERFACE_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(INTERFACE_DIR))

from knowledge import (
    KnowledgeCandidatePlan,
    KnowledgeManager,
    KnowledgeManagerError,
)
from knowledge_target import KnowledgeSlot
from results import (
    KnowledgeAddedFile,
    KnowledgeDiffResult,
)


MANIFEST_DIGEST = "a" * 64
PLAN_DIFF_DIGEST = "b" * 64
CLEAN_DIFF_DIGEST = "c" * 64


class PrepareCandidateKnowledgeManager(KnowledgeManager):
    """Manager simulado sin red ni escritura remota."""

    def __init__(
        self,
        *,
        current_plan: KnowledgeCandidatePlan,
        verified_diff: KnowledgeDiffResult,
        sync_payload: dict[str, object],
        fail_active_check: int | None = None,
    ) -> None:
        self.source_name = "epsilon-system"
        self.current_plan = current_plan
        self.verified_diff = verified_diff
        self.sync_payload = sync_payload
        self.fail_active_check = fail_active_check

        self.staging_path = Path(
            "/tmp/epsilon-prepare-candidate-test"
        )
        self.active_check_count = 0
        self.calls: list[tuple[object, ...]] = []

    @contextmanager
    def staged_source(self) -> Iterator[Path]:
        self.calls.append(
            ("staging_enter", self.staging_path)
        )

        try:
            yield self.staging_path
        finally:
            self.calls.append(
                ("staging_exit", self.staging_path)
            )

    def _candidate_plan_from_staging(
        self,
        staging_directory: Path,
    ) -> KnowledgeCandidatePlan:
        self.calls.append(
            ("candidate_plan", staging_directory)
        )
        return self.current_plan

    def _run_bridge(
        self,
        source_path: Path,
        *,
        kb_id: str,
        operation: str = "diff",
    ) -> dict[str, object]:
        self.calls.append(
            (
                "bridge",
                source_path,
                kb_id,
                operation,
            )
        )
        return dict(self.sync_payload)

    def _plan_for_slot_from_staging(
        self,
        slot: KnowledgeSlot,
        staging_directory: Path,
        *,
        slot_role: str,
    ) -> KnowledgeDiffResult:
        self.calls.append(
            (
                "verification",
                staging_directory,
                slot,
                slot_role,
            )
        )
        return self.verified_diff

    def _require_active_slot(
        self,
        expected_slot: KnowledgeSlot,
    ) -> KnowledgeSlot:
        self.active_check_count += 1
        self.calls.append(
            (
                "active_check",
                self.active_check_count,
                expected_slot,
            )
        )

        if (
            self.fail_active_check
            == self.active_check_count
        ):
            raise KnowledgeManagerError(
                "El slot activo cambió durante la "
                "preparación del candidato."
            )

        return expected_slot


class KnowledgePrepareCandidateTests(unittest.TestCase):
    """Pruebas de preparación segura del slot inactivo."""

    def setUp(self) -> None:
        self.blue = KnowledgeSlot(
            name="blue",
            kb_id="blue-id",
        )
        self.green = KnowledgeSlot(
            name="green",
            kb_id="green-id",
        )

    def build_pending_diff(
        self,
        **overrides,
    ) -> KnowledgeDiffResult:
        values = {
            "source_name": "epsilon-system",
            "kb_id": "green-id",
            "manifest_digest": MANIFEST_DIGEST,
            "diff_digest": PLAN_DIFF_DIGEST,
            "added": 1,
            "unmodified": 3,
            "added_files": (
                KnowledgeAddedFile(
                    path="Core",
                    filename="NEW.md",
                ),
            ),
        }
        values.update(overrides)

        return KnowledgeDiffResult(**values)

    def build_clean_diff(
        self,
        **overrides,
    ) -> KnowledgeDiffResult:
        values = {
            "source_name": "epsilon-system",
            "kb_id": "green-id",
            "manifest_digest": MANIFEST_DIGEST,
            "diff_digest": CLEAN_DIFF_DIGEST,
            "unmodified": 4,
        }
        values.update(overrides)

        return KnowledgeDiffResult(**values)

    def build_plan(
        self,
        *,
        diff: KnowledgeDiffResult | None = None,
    ) -> KnowledgeCandidatePlan:
        return KnowledgeCandidatePlan(
            active_slot=self.blue,
            candidate_slot=self.green,
            diff=diff or self.build_pending_diff(),
        )

    def build_sync_payload(
        self,
        **overrides,
    ) -> dict[str, object]:
        payload: dict[str, object] = {
            "source_name": "epsilon-system",
            "kb_id": "green-id",
            "manifest_digest": MANIFEST_DIGEST,
            "added": 1,
            "modified": 0,
            "deleted": 0,
            "unmodified": 3,
            "dirs_created": 0,
            "dirs_removed": 0,
            "warnings": [],
            "errors": [],
        }
        payload.update(overrides)
        return payload

    def build_manager(
        self,
        *,
        current_plan: KnowledgeCandidatePlan | None = None,
        verified_diff: KnowledgeDiffResult | None = None,
        sync_payload: dict[str, object] | None = None,
        fail_active_check: int | None = None,
    ) -> PrepareCandidateKnowledgeManager:
        return PrepareCandidateKnowledgeManager(
            current_plan=(
                current_plan
                or self.build_plan()
            ),
            verified_diff=(
                verified_diff
                or self.build_clean_diff()
            ),
            sync_payload=(
                sync_payload
                or self.build_sync_payload()
            ),
            fail_active_check=fail_active_check,
        )

    def test_prepares_candidate_using_one_staging(
        self,
    ) -> None:
        approved = self.build_plan()
        manager = self.build_manager()

        result = manager.prepare_candidate(
            approved
        )

        self.assertEqual(result.kb_id, "green-id")
        self.assertEqual(result.added, 1)
        self.assertEqual(
            manager.active_check_count,
            2,
        )

        bridge_calls = [
            call
            for call in manager.calls
            if call[0] == "bridge"
        ]

        self.assertEqual(
            bridge_calls,
            [
                (
                    "bridge",
                    manager.staging_path,
                    "green-id",
                    "sync",
                )
            ],
        )

        staging_uses = [
            call[1]
            for call in manager.calls
            if call[0] in {
                "candidate_plan",
                "bridge",
                "verification",
            }
        ]

        self.assertEqual(
            staging_uses,
            [
                manager.staging_path,
                manager.staging_path,
                manager.staging_path,
            ],
        )

        self.assertEqual(
            manager.calls[0],
            (
                "staging_enter",
                manager.staging_path,
            ),
        )
        self.assertEqual(
            manager.calls[-1],
            (
                "staging_exit",
                manager.staging_path,
            ),
        )

    def test_rejects_stale_plan_before_sync(
        self,
    ) -> None:
        approved = self.build_plan()
        current = self.build_plan(
            diff=self.build_pending_diff(
                manifest_digest="d" * 64,
            )
        )
        manager = self.build_manager(
            current_plan=current
        )

        with self.assertRaisesRegex(
            KnowledgeManagerError,
            "obsoleto",
        ):
            manager.prepare_candidate(approved)

        self.assertFalse(
            any(
                call[0] == "bridge"
                for call in manager.calls
            )
        )

    def test_rejects_sync_manifest_mismatch(
        self,
    ) -> None:
        manager = self.build_manager(
            sync_payload=self.build_sync_payload(
                manifest_digest="d" * 64,
            )
        )

        with self.assertRaisesRegex(
            KnowledgeManagerError,
            "manifiesto diferente del plan aprobado",
        ):
            manager.prepare_candidate(
                self.build_plan()
            )

    def test_rejects_verification_manifest_mismatch(
        self,
    ) -> None:
        manager = self.build_manager(
            verified_diff=self.build_clean_diff(
                manifest_digest="d" * 64,
            )
        )

        with self.assertRaisesRegex(
            KnowledgeManagerError,
            "verificación posterior utilizó",
        ):
            manager.prepare_candidate(
                self.build_plan()
            )

    def test_rejects_verification_errors(
        self,
    ) -> None:
        manager = self.build_manager(
            verified_diff=self.build_clean_diff(
                errors=("indexing failed",),
            )
        )

        with self.assertRaisesRegex(
            KnowledgeManagerError,
            "indexing failed",
        ):
            manager.prepare_candidate(
                self.build_plan()
            )

    def test_rejects_remaining_differences(
        self,
    ) -> None:
        manager = self.build_manager(
            verified_diff=self.build_pending_diff()
        )

        with self.assertRaisesRegex(
            KnowledgeManagerError,
            "conserva diferencias",
        ):
            manager.prepare_candidate(
                self.build_plan()
            )

    def test_rejects_wrong_verified_file_count(
        self,
    ) -> None:
        manager = self.build_manager(
            verified_diff=self.build_clean_diff(
                unmodified=3,
            )
        )

        with self.assertRaisesRegex(
            KnowledgeManagerError,
            "cantidad de archivos verificados",
        ):
            manager.prepare_candidate(
                self.build_plan()
            )

    def test_rejects_active_slot_change_before_sync(
        self,
    ) -> None:
        manager = self.build_manager(
            fail_active_check=1
        )

        with self.assertRaisesRegex(
            KnowledgeManagerError,
            "slot activo cambió",
        ):
            manager.prepare_candidate(
                self.build_plan()
            )

        self.assertFalse(
            any(
                call[0] == "bridge"
                for call in manager.calls
            )
        )

    def test_rejects_active_slot_change_after_sync(
        self,
    ) -> None:
        manager = self.build_manager(
            fail_active_check=2
        )

        with self.assertRaisesRegex(
            KnowledgeManagerError,
            "slot activo cambió",
        ):
            manager.prepare_candidate(
                self.build_plan()
            )

        self.assertTrue(
            any(
                call[0] == "bridge"
                for call in manager.calls
            )
        )
        self.assertTrue(
            any(
                call[0] == "verification"
                for call in manager.calls
            )
        )


if __name__ == "__main__":
    unittest.main()
