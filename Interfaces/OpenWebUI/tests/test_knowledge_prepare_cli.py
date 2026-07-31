from __future__ import annotations

from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path
import sys
import unittest
from unittest.mock import patch


INTERFACE_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(INTERFACE_DIR))

import sync as sync_cli

from knowledge import (
    KnowledgeCandidatePlan,
    KnowledgeManagerError,
)
from knowledge_target import KnowledgeSlot
from results import (
    KnowledgeDiffResult,
    KnowledgeSyncResult,
)


MANIFEST_DIGEST = "a" * 64


class FakeClientContext:
    """Contexto local que reemplaza OpenWebUIClient."""

    def __enter__(self) -> object:
        return object()

    def __exit__(
        self,
        exc_type,
        exc_value,
        traceback,
    ) -> bool:
        return False


class StubKnowledgeManager:
    """Manager simulado para probar únicamente el CLI."""

    def __init__(
        self,
        plan: KnowledgeCandidatePlan,
        *,
        result: KnowledgeSyncResult | None = None,
        plan_error: Exception | None = None,
        prepare_error: Exception | None = None,
    ) -> None:
        self.plan = plan
        self.result = result
        self.plan_error = plan_error
        self.prepare_error = prepare_error

        self.plan_calls = 0
        self.prepare_calls = 0
        self.prepared_plan: KnowledgeCandidatePlan | None = None

    def plan_candidate(self) -> KnowledgeCandidatePlan:
        self.plan_calls += 1

        if self.plan_error is not None:
            raise self.plan_error

        return self.plan

    def prepare_candidate(
        self,
        approved_plan: KnowledgeCandidatePlan,
    ) -> KnowledgeSyncResult:
        self.prepare_calls += 1
        self.prepared_plan = approved_plan

        if self.prepare_error is not None:
            raise self.prepare_error

        if self.result is None:
            raise AssertionError(
                "La prueba no configuró un resultado."
            )

        return self.result


class KnowledgePrepareCliTests(unittest.TestCase):
    """Pruebas del comando knowledge prepare."""

    def setUp(self) -> None:
        self.blue = KnowledgeSlot(
            name="blue",
            kb_id="blue-id",
        )
        self.green = KnowledgeSlot(
            name="green",
            kb_id="green-id",
        )

    def build_plan(
        self,
        *,
        has_changes: bool = True,
    ) -> KnowledgeCandidatePlan:
        diff = KnowledgeDiffResult(
            source_name="epsilon-system",
            kb_id="green-id",
            added=1 if has_changes else 0,
            unmodified=0 if has_changes else 4,
        )

        return KnowledgeCandidatePlan(
            active_slot=self.blue,
            candidate_slot=self.green,
            diff=diff,
        )

    def build_result(self) -> KnowledgeSyncResult:
        return KnowledgeSyncResult(
            source_name="epsilon-system",
            kb_id="green-id",
            manifest_digest=MANIFEST_DIGEST,
            added=1,
        )

    def run_command(
        self,
        manager: StubKnowledgeManager,
        *,
        confirmed: bool,
    ) -> tuple[int, str]:
        output = StringIO()

        with (
            patch.object(
                sync_cli,
                "Config",
                return_value=object(),
            ),
            patch.object(
                sync_cli,
                "OpenWebUIClient",
                return_value=FakeClientContext(),
            ),
            patch.object(
                sync_cli,
                "build_knowledge_manager",
                return_value=manager,
            ),
            redirect_stdout(output),
        ):
            status = sync_cli.run_prepare_knowledge(
                confirmed
            )

        return status, output.getvalue()

    def test_main_routes_prepare_without_yes(self) -> None:
        with patch.object(
            sync_cli,
            "run_prepare_knowledge",
            return_value=7,
        ) as run_prepare:
            status = sync_cli.main(
                ["knowledge", "prepare"]
            )

        self.assertEqual(status, 7)
        run_prepare.assert_called_once_with(False)

    def test_main_routes_prepare_with_yes(self) -> None:
        with patch.object(
            sync_cli,
            "run_prepare_knowledge",
            return_value=7,
        ) as run_prepare:
            status = sync_cli.main(
                [
                    "knowledge",
                    "prepare",
                    "--yes",
                ]
            )

        self.assertEqual(status, 7)
        run_prepare.assert_called_once_with(True)

    def test_without_yes_never_prepares_candidate(
        self,
    ) -> None:
        manager = StubKnowledgeManager(
            self.build_plan(),
            result=self.build_result(),
        )

        status, output = self.run_command(
            manager,
            confirmed=False,
        )

        self.assertEqual(status, 2)
        self.assertEqual(manager.plan_calls, 1)
        self.assertEqual(manager.prepare_calls, 0)
        self.assertIn(
            "Preparación no autorizada",
            output,
        )
        self.assertIn(
            "No se aplicaron cambios",
            output,
        )

    def test_clean_candidate_requires_no_write(
        self,
    ) -> None:
        manager = StubKnowledgeManager(
            self.build_plan(
                has_changes=False
            ),
            result=self.build_result(),
        )

        status, output = self.run_command(
            manager,
            confirmed=True,
        )

        self.assertEqual(status, 0)
        self.assertEqual(manager.prepare_calls, 0)
        self.assertIn(
            "ya estaba preparado",
            output,
        )
        self.assertIn(
            "slot activo original",
            output,
        )

    def test_authorized_prepare_reports_success(
        self,
    ) -> None:
        plan = self.build_plan()
        manager = StubKnowledgeManager(
            plan,
            result=self.build_result(),
        )

        status, output = self.run_command(
            manager,
            confirmed=True,
        )

        self.assertEqual(status, 0)
        self.assertEqual(manager.prepare_calls, 1)
        self.assertIs(
            manager.prepared_plan,
            plan,
        )
        self.assertIn(
            "EPSILON KNOWLEDGE PREPARED",
            output,
        )
        self.assertIn(
            "Slot candidato sincronizado y verificado",
            output,
        )
        self.assertIn(
            "green-id",
            output,
        )
        self.assertIn(
            "No se realizó el intercambio Blue–Green",
            output,
        )

    def test_authorized_prepare_reports_failure(
        self,
    ) -> None:
        manager = StubKnowledgeManager(
            self.build_plan(),
            prepare_error=KnowledgeManagerError(
                "simulated sync failure"
            ),
        )

        status, output = self.run_command(
            manager,
            confirmed=True,
        )

        self.assertEqual(status, 1)
        self.assertEqual(manager.prepare_calls, 1)
        self.assertIn(
            "simulated sync failure",
            output,
        )
        self.assertIn(
            "parcialmente preparado",
            output,
        )
        self.assertIn(
            "plan --candidate",
            output,
        )
        self.assertNotIn(
            "EPSILON KNOWLEDGE PREPARED",
            output,
        )

    def test_plan_failure_never_attempts_prepare(
        self,
    ) -> None:
        manager = StubKnowledgeManager(
            self.build_plan(),
            plan_error=KnowledgeManagerError(
                "simulated plan failure"
            ),
        )

        status, output = self.run_command(
            manager,
            confirmed=True,
        )

        self.assertEqual(status, 1)
        self.assertEqual(manager.prepare_calls, 0)
        self.assertIn(
            "simulated plan failure",
            output,
        )
        self.assertIn(
            "No se aplicaron cambios",
            output,
        )


if __name__ == "__main__":
    unittest.main()
