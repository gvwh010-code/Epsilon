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
    KnowledgeSwitchResult,
)
from knowledge_target import KnowledgeSlot
from results import (
    KnowledgeAddedFile,
    KnowledgeDiffResult,
)


MANIFEST_DIGEST = "a" * 64
DIFF_DIGEST = "b" * 64


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
    """Manager simulado para probar únicamente la CLI."""

    def __init__(
        self,
        plan: KnowledgeCandidatePlan,
        *,
        result: KnowledgeSwitchResult | None = None,
        plan_error: Exception | None = None,
        switch_error: Exception | None = None,
    ) -> None:
        self.plan = plan
        self.result = result
        self.plan_error = plan_error
        self.switch_error = switch_error

        self.plan_calls = 0
        self.switch_calls = 0
        self.approved_plan: KnowledgeCandidatePlan | None = None

    def plan_candidate(self) -> KnowledgeCandidatePlan:
        self.plan_calls += 1

        if self.plan_error is not None:
            raise self.plan_error

        return self.plan

    def switch_candidate(
        self,
        approved_plan: KnowledgeCandidatePlan,
    ) -> KnowledgeSwitchResult:
        self.switch_calls += 1
        self.approved_plan = approved_plan

        if self.switch_error is not None:
            raise self.switch_error

        if self.result is None:
            raise AssertionError(
                "La prueba no configuró un resultado."
            )

        return self.result


class KnowledgeSwitchCliTests(unittest.TestCase):
    """Pruebas del comando knowledge switch."""

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
        clean: bool = True,
    ) -> KnowledgeCandidatePlan:
        diff = KnowledgeDiffResult(
            source_name="epsilon-system",
            kb_id="green-id",
            added=0 if clean else 1,
            unmodified=4 if clean else 3,
            manifest_digest=MANIFEST_DIGEST,
            diff_digest=DIFF_DIGEST,
            added_files=(
                ()
                if clean
                else (
                    KnowledgeAddedFile(
                        path="Core",
                        filename="pending.md",
                    ),
                )
            ),
        )

        return KnowledgeCandidatePlan(
            active_slot=self.blue,
            candidate_slot=self.green,
            diff=diff,
        )

    def build_result(self) -> KnowledgeSwitchResult:
        return KnowledgeSwitchResult(
            previous_slot=self.blue,
            active_slot=self.green,
            manifest_digest=MANIFEST_DIGEST,
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
            status = sync_cli.run_switch_knowledge(
                confirmed
            )

        return status, output.getvalue()

    def test_main_routes_switch_without_yes(
        self,
    ) -> None:
        with patch.object(
            sync_cli,
            "run_switch_knowledge",
            return_value=7,
        ) as run_switch:
            status = sync_cli.main(
                ["knowledge", "switch"]
            )

        self.assertEqual(status, 7)
        run_switch.assert_called_once_with(False)

    def test_main_routes_switch_with_yes(
        self,
    ) -> None:
        with patch.object(
            sync_cli,
            "run_switch_knowledge",
            return_value=7,
        ) as run_switch:
            status = sync_cli.main(
                [
                    "knowledge",
                    "switch",
                    "--yes",
                ]
            )

        self.assertEqual(status, 7)
        run_switch.assert_called_once_with(True)

    def test_without_yes_never_switches(
        self,
    ) -> None:
        plan = self.build_plan()
        manager = StubKnowledgeManager(
            plan,
            result=self.build_result(),
        )

        status, output = self.run_command(
            manager,
            confirmed=False,
        )

        self.assertEqual(status, 2)
        self.assertEqual(manager.plan_calls, 1)
        self.assertEqual(manager.switch_calls, 0)
        self.assertIn(
            "Intercambio no autorizado",
            output,
        )
        self.assertIn(
            "knowledge switch --yes",
            output,
        )
        self.assertIn(
            "No se aplicaron cambios",
            output,
        )

    def test_dirty_candidate_never_switches(
        self,
    ) -> None:
        plan = self.build_plan(clean=False)
        manager = StubKnowledgeManager(
            plan,
            result=self.build_result(),
        )

        status, output = self.run_command(
            manager,
            confirmed=True,
        )

        self.assertEqual(status, 2)
        self.assertEqual(manager.switch_calls, 0)
        self.assertIn(
            "todavía no está preparado",
            output,
        )
        self.assertIn(
            "knowledge prepare --yes",
            output,
        )

    def test_authorized_switch_reports_success(
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
        self.assertEqual(manager.switch_calls, 1)
        self.assertIs(
            manager.approved_plan,
            plan,
        )
        self.assertIn(
            "EPSILON KNOWLEDGE SWITCHED",
            output,
        )
        self.assertIn(
            "Intercambio Blue–Green completado",
            output,
        )
        self.assertIn("blue-id", output)
        self.assertIn("green-id", output)
        self.assertIn(
            "candidato de rollback",
            output,
        )

    def test_switch_failure_reports_verification_steps(
        self,
    ) -> None:
        manager = StubKnowledgeManager(
            self.build_plan(),
            switch_error=KnowledgeManagerError(
                "simulated switch failure"
            ),
        )

        status, output = self.run_command(
            manager,
            confirmed=True,
        )

        self.assertEqual(status, 1)
        self.assertEqual(manager.switch_calls, 1)
        self.assertIn(
            "simulated switch failure",
            output,
        )
        self.assertIn(
            "No se debe asumir",
            output,
        )
        self.assertIn("'verify'", output)
        self.assertIn(
            "'plan --candidate'",
            output,
        )
        self.assertNotIn(
            "EPSILON KNOWLEDGE SWITCHED",
            output,
        )

    def test_plan_failure_never_switches(
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
        self.assertEqual(manager.switch_calls, 0)
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
