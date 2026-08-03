from __future__ import annotations

from contextlib import contextmanager
from copy import deepcopy
from dataclasses import dataclass
from pathlib import Path
import sys
from types import SimpleNamespace
import unittest


INTERFACE_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(INTERFACE_DIR))

from knowledge import (
    KnowledgeCandidatePlan,
    KnowledgeManager,
    KnowledgeManagerError,
)
from knowledge_target import KnowledgeSlot


@dataclass(frozen=True)
class FakeDiff:
    manifest_digest: str = "a" * 64
    added: int = 0
    modified: int = 0
    deleted: int = 0
    dirs_created: int = 0
    dirs_removed: int = 0
    unmodified: int = 4
    errors: tuple[str, ...] = ()

    @property
    def failed(self) -> bool:
        return bool(self.errors)

    @property
    def has_changes(self) -> bool:
        return any(
            (
                self.added,
                self.modified,
                self.deleted,
                self.dirs_created,
                self.dirs_removed,
            )
        )


class FakeClient:
    """Cliente en memoria que simula la API de Open WebUI."""

    def __init__(
        self,
        model: dict,
        candidate_record: dict,
    ) -> None:
        self.current_model = deepcopy(model)
        self.candidate_record = deepcopy(candidate_record)
        self.updates: list[dict] = []
        self.export_calls = 0
        self.prewrite_override: dict | None = None
        self.mutate_first_update = False
        self.fail_update_numbers: set[int] = set()

    def export_model(self, model_id: str) -> dict:
        self.export_calls += 1

        if (
            self.export_calls == 2
            and self.prewrite_override is not None
        ):
            return deepcopy(self.prewrite_override)

        return deepcopy(self.current_model)

    def get(self, endpoint: str) -> dict:
        return deepcopy(self.candidate_record)

    def import_models(
        self,
        models: list[dict],
    ) -> None:
        if len(models) != 1:
            raise AssertionError(
                "El fake espera exactamente un modelo por import."
            )

        model = models[0]

        update_number = len(self.updates) + 1
        self.updates.append(deepcopy(model))

        if update_number in self.fail_update_numbers:
            raise RuntimeError(
                f"simulated update failure {update_number}"
            )

        updated_model = deepcopy(model)

        if "access_grants" not in updated_model:
            updated_model["access_grants"] = deepcopy(
                self.current_model["access_grants"]
            )

        self.current_model = updated_model
        self.current_model["updated_at"] = (
            self.current_model.get("updated_at", 0) + 1
        )

        if (
            update_number == 1
            and self.mutate_first_update
        ):
            self.current_model["params"]["system"] = (
                "unexpected mutation"
            )

class FakeKnowledgeManager(KnowledgeManager):
    """KnowledgeManager sin disco, bloqueo real ni red."""

    def __init__(
        self,
        client: FakeClient,
        plan: KnowledgeCandidatePlan,
        *,
        post_diff: FakeDiff | None = None,
    ) -> None:
        self.client = client
        self.current_plan = plan
        self.post_diff = post_diff or plan.diff
        self.target = SimpleNamespace(
            model_id="epsilon",
            slots=(
                plan.active_slot,
                plan.candidate_slot,
            ),
        )

    @contextmanager
    def deployment_lock(self):
        yield

    @contextmanager
    def staged_source(self):
        yield Path("/tmp/fake-epsilon-staging")

    def _candidate_plan_from_staging(
        self,
        staging_directory: Path,
    ) -> KnowledgeCandidatePlan:
        return self.current_plan

    def _require_matching_candidate_plan(
        self,
        approved_plan: KnowledgeCandidatePlan,
        current_plan: KnowledgeCandidatePlan,
    ) -> KnowledgeCandidatePlan:
        if approved_plan != current_plan:
            raise KnowledgeManagerError(
                "Plan candidato obsoleto."
            )

        return current_plan

    def _load_target(self):
        return self.target

    def _plan_for_slot_from_staging(
        self,
        slot: KnowledgeSlot,
        staging_directory: Path,
        *,
        slot_role: str,
    ) -> FakeDiff:
        return self.post_diff


class KnowledgeSwitchOperationTests(unittest.TestCase):
    """Pruebas de la operación completa de intercambio."""

    def setUp(self) -> None:
        self.blue = KnowledgeSlot(
            name="blue",
            kb_id="blue-id",
        )
        self.green = KnowledgeSlot(
            name="green",
            kb_id="green-id",
        )
        self.clean = FakeDiff()
        self.plan = KnowledgeCandidatePlan(
            active_slot=self.blue,
            candidate_slot=self.green,
            diff=self.clean,
        )

    def entry(
        self,
        knowledge_id: str,
    ) -> dict:
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

    def model(
        self,
        active_id: str = "blue-id",
    ) -> dict:
        return {
            "id": "epsilon",
            "base_model_id": "gemma4:12b",
            "name": "Epsilon",
            "meta": {
                "knowledge": [
                    self.entry("unrelated-before"),
                    self.entry(active_id),
                    self.entry("unrelated-after"),
                ],
                "skillIds": ["skill-id"],
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

    def candidate_record(self) -> dict:
        return {
            "id": "green-id",
            "user_id": "owner-id",
            "name": "Epsilon System Green",
            "description": "",
            "meta": None,
            "access_grants": [],
            "created_at": 3,
            "updated_at": 4,
            "files": None,
            "write_access": True,
        }

    def build_manager(
        self,
        *,
        model: dict | None = None,
        plan: KnowledgeCandidatePlan | None = None,
        post_diff: FakeDiff | None = None,
    ) -> tuple[FakeKnowledgeManager, FakeClient]:
        client = FakeClient(
            model or self.model(),
            self.candidate_record(),
        )
        manager = FakeKnowledgeManager(
            client,
            plan or self.plan,
            post_diff=post_diff,
        )
        return manager, client

    def test_switches_candidate_successfully(
        self,
    ) -> None:
        manager, client = self.build_manager()

        result = manager.switch_candidate(
            self.plan
        )

        self.assertEqual(
            result.previous_slot,
            self.blue,
        )
        self.assertEqual(
            result.active_slot,
            self.green,
        )
        self.assertEqual(len(client.updates), 1)
        self.assertNotIn(
            "access_grants",
            client.updates[0],
        )

        ids = [
            entry["id"]
            for entry in (
                client.current_model["meta"]["knowledge"]
            )
        ]

        self.assertEqual(
            ids,
            [
                "unrelated-before",
                "green-id",
                "unrelated-after",
            ],
        )

    def test_preserves_fields_outside_knowledge(
        self,
    ) -> None:
        original = self.model()
        manager, client = self.build_manager(
            model=original
        )

        manager.switch_candidate(self.plan)

        KnowledgeManager._require_same_model_outside_knowledge(
            original,
            client.current_model,
        )

    def test_rejects_dirty_candidate_without_write(
        self,
    ) -> None:
        dirty = FakeDiff(
            added=1,
            unmodified=3,
        )
        dirty_plan = KnowledgeCandidatePlan(
            active_slot=self.blue,
            candidate_slot=self.green,
            diff=dirty,
        )

        manager, client = self.build_manager(
            plan=dirty_plan
        )

        with self.assertRaisesRegex(
            KnowledgeManagerError,
            "todavía contiene diferencias",
        ):
            manager.switch_candidate(dirty_plan)

        self.assertEqual(client.updates, [])

    def test_rejects_changed_active_slot_without_write(
        self,
    ) -> None:
        manager, client = self.build_manager(
            model=self.model("green-id")
        )

        with self.assertRaisesRegex(
            KnowledgeManagerError,
            "slot activo cambió",
        ):
            manager.switch_candidate(self.plan)

        self.assertEqual(client.updates, [])

    def test_rejects_stale_model_before_write(
        self,
    ) -> None:
        manager, client = self.build_manager()

        stale = self.model()
        stale["params"]["system"] = "external change"
        client.prewrite_override = stale

        with self.assertRaises(
            KnowledgeManagerError
        ):
            manager.switch_candidate(self.plan)

        self.assertEqual(client.updates, [])

    def test_rolls_back_nonknowledge_mutation(
        self,
    ) -> None:
        manager, client = self.build_manager()
        client.mutate_first_update = True

        with self.assertRaisesRegex(
            KnowledgeManagerError,
            "restaurado correctamente",
        ):
            manager.switch_candidate(self.plan)

        self.assertEqual(len(client.updates), 2)

        active = (
            KnowledgeManager._active_slot_from_model(
                manager.target,
                client.current_model,
            )
        )
        self.assertEqual(active, self.blue)

    def test_rolls_back_failed_content_verification(
        self,
    ) -> None:
        dirty_after = FakeDiff(
            added=1,
            unmodified=3,
        )

        manager, client = self.build_manager(
            post_diff=dirty_after
        )

        with self.assertRaisesRegex(
            KnowledgeManagerError,
            "restaurado correctamente",
        ):
            manager.switch_candidate(self.plan)

        self.assertEqual(len(client.updates), 2)

        active = (
            KnowledgeManager._active_slot_from_model(
                manager.target,
                client.current_model,
            )
        )
        self.assertEqual(active, self.blue)

    def test_reports_unverified_rollback_failure(
        self,
    ) -> None:
        dirty_after = FakeDiff(
            added=1,
            unmodified=3,
        )

        manager, client = self.build_manager(
            post_diff=dirty_after
        )
        client.fail_update_numbers.add(2)

        with self.assertRaisesRegex(
            KnowledgeManagerError,
            "no pudo restaurarse",
        ):
            manager.switch_candidate(self.plan)

        self.assertEqual(len(client.updates), 2)


if __name__ == "__main__":
    unittest.main()
