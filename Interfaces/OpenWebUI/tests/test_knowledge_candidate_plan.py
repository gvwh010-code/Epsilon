from __future__ import annotations

from pathlib import Path
import sys
import unittest


INTERFACE_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(INTERFACE_DIR))

from knowledge import (
    KnowledgeCandidatePlan,
    KnowledgeManager,
    KnowledgeManagerError,
)
from knowledge_target import KnowledgeSlot
from results import KnowledgeDiffResult


DIGEST_A = "a" * 64
DIGEST_B = "b" * 64


class StubKnowledgeManager(KnowledgeManager):
    """Manager controlado que devuelve un plan prefijado."""

    def __init__(
        self,
        current_plan: KnowledgeCandidatePlan,
    ) -> None:
        self.current_plan = current_plan

    def plan_candidate(self) -> KnowledgeCandidatePlan:
        return self.current_plan


class KnowledgeCandidatePlanTests(unittest.TestCase):
    """Pruebas de detección de planes obsoletos."""

    def build_diff(
        self,
        **overrides,
    ) -> KnowledgeDiffResult:
        values = {
            "source_name": "epsilon-system",
            "kb_id": "green-id",
            "manifest_digest": DIGEST_A,
            "diff_digest": DIGEST_B,
            "unmodified": 4,
        }
        values.update(overrides)

        return KnowledgeDiffResult(**values)

    def build_plan(
        self,
        *,
        active_slot: KnowledgeSlot | None = None,
        candidate_slot: KnowledgeSlot | None = None,
        diff: KnowledgeDiffResult | None = None,
    ) -> KnowledgeCandidatePlan:
        return KnowledgeCandidatePlan(
            active_slot=(
                active_slot
                or KnowledgeSlot(
                    name="blue",
                    kb_id="blue-id",
                )
            ),
            candidate_slot=(
                candidate_slot
                or KnowledgeSlot(
                    name="green",
                    kb_id="green-id",
                )
            ),
            diff=diff or self.build_diff(),
        )

    def test_accepts_identical_current_plan(self) -> None:
        approved = self.build_plan()
        manager = StubKnowledgeManager(
            self.build_plan()
        )

        current = manager.require_current_candidate_plan(
            approved
        )

        self.assertEqual(
            current,
            approved,
        )

    def test_rejects_invalid_approved_plan(self) -> None:
        manager = StubKnowledgeManager(
            self.build_plan()
        )

        with self.assertRaisesRegex(
            KnowledgeManagerError,
            "no es válido",
        ):
            manager.require_current_candidate_plan(
                object()
            )

    def test_rejects_approved_plan_without_exact_details(
        self,
    ) -> None:
        approved = self.build_plan(
            diff=KnowledgeDiffResult(
                source_name="epsilon-system",
                kb_id="green-id",
                unmodified=4,
            )
        )
        manager = StubKnowledgeManager(
            self.build_plan()
        )

        with self.assertRaisesRegex(
            KnowledgeManagerError,
            "aprobado no contiene",
        ):
            manager.require_current_candidate_plan(
                approved
            )

    def test_rejects_current_plan_without_exact_details(
        self,
    ) -> None:
        approved = self.build_plan()
        current = self.build_plan(
            diff=KnowledgeDiffResult(
                source_name="epsilon-system",
                kb_id="green-id",
                unmodified=4,
            )
        )
        manager = StubKnowledgeManager(current)

        with self.assertRaisesRegex(
            KnowledgeManagerError,
            "recalculado no contiene",
        ):
            manager.require_current_candidate_plan(
                approved
            )

    def test_rejects_changed_active_slot(self) -> None:
        approved = self.build_plan()
        current = self.build_plan(
            active_slot=KnowledgeSlot(
                name="blue",
                kb_id="other-blue-id",
            )
        )
        manager = StubKnowledgeManager(current)

        with self.assertRaisesRegex(
            KnowledgeManagerError,
            "cambió el slot activo",
        ):
            manager.require_current_candidate_plan(
                approved
            )

    def test_rejects_changed_candidate_slot(self) -> None:
        approved = self.build_plan()
        current = self.build_plan(
            candidate_slot=KnowledgeSlot(
                name="green",
                kb_id="other-green-id",
            )
        )
        manager = StubKnowledgeManager(current)

        with self.assertRaisesRegex(
            KnowledgeManagerError,
            "cambió el slot candidato",
        ):
            manager.require_current_candidate_plan(
                approved
            )

    def test_rejects_changed_local_manifest(self) -> None:
        approved = self.build_plan()
        current = self.build_plan(
            diff=self.build_diff(
                manifest_digest="c" * 64,
            )
        )
        manager = StubKnowledgeManager(current)

        with self.assertRaisesRegex(
            KnowledgeManagerError,
            "cambió el manifiesto local",
        ):
            manager.require_current_candidate_plan(
                approved
            )

    def test_rejects_changed_remote_state(self) -> None:
        approved = self.build_plan()
        current = self.build_plan(
            diff=self.build_diff(
                diff_digest="d" * 64,
            )
        )
        manager = StubKnowledgeManager(current)

        with self.assertRaisesRegex(
            KnowledgeManagerError,
            "cambió el estado remoto",
        ):
            manager.require_current_candidate_plan(
                approved
            )

    def test_rejects_other_exact_detail_changes(self) -> None:
        approved = self.build_plan()
        current = self.build_plan(
            diff=self.build_diff(
                unmodified=3,
            )
        )
        manager = StubKnowledgeManager(current)

        with self.assertRaisesRegex(
            KnowledgeManagerError,
            "cambiaron los detalles exactos",
        ):
            manager.require_current_candidate_plan(
                approved
            )


if __name__ == "__main__":
    unittest.main()
