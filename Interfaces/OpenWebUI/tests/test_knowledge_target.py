from __future__ import annotations

import json
from pathlib import Path
import sys
import tempfile
from typing import Any
import unittest


INTERFACE_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(INTERFACE_DIR))

from knowledge import (
    KnowledgeManager,
    KnowledgeManagerError,
)
from knowledge_target import (
    KnowledgeSlot,
    KnowledgeTarget,
    KnowledgeTargetError,
    load_knowledge_target,
)


BLUE_ID = "11111111-1111-4111-8111-111111111111"
GREEN_ID = "22222222-2222-4222-8222-222222222222"


class FakeOpenWebUIClient:
    """Cliente local que devuelve modelos controlados."""

    def __init__(
        self,
        models: list[dict[str, Any]],
    ) -> None:
        self.models = models

    def export_models(self) -> list[dict[str, Any]]:
        return self.models


class KnowledgeTargetLoaderTests(unittest.TestCase):
    """Pruebas de knowledge_target.json."""

    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory(
            prefix="epsilon-target-tests-"
        )

        self.target_path = (
            Path(self.temporary_directory.name)
            / "knowledge_target.json"
        )

    def tearDown(self) -> None:
        self.temporary_directory.cleanup()

    def valid_document(self) -> dict[str, Any]:
        return {
            "source_name": "epsilon-system",
            "model_id": "epsilon",
            "slots": {
                "blue": {
                    "kb_id": BLUE_ID,
                },
                "green": {
                    "kb_id": GREEN_ID,
                },
            },
        }

    def write_document(
        self,
        document: Any,
    ) -> None:
        self.target_path.write_text(
            json.dumps(
                document,
                ensure_ascii=False,
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )

    def test_loads_valid_blue_green_target(self) -> None:
        self.write_document(
            self.valid_document()
        )

        target = load_knowledge_target(
            self.target_path
        )

        self.assertEqual(
            target.source_name,
            "epsilon-system",
        )
        self.assertEqual(
            target.model_id,
            "epsilon",
        )
        self.assertEqual(
            target.slots,
            (
                KnowledgeSlot(
                    name="blue",
                    kb_id=BLUE_ID,
                ),
                KnowledgeSlot(
                    name="green",
                    kb_id=GREEN_ID,
                ),
            ),
        )

    def test_strips_required_text_values(self) -> None:
        document = self.valid_document()
        document["source_name"] = "  epsilon-system  "
        document["model_id"] = "  epsilon  "
        document["slots"]["blue"]["kb_id"] = (
            f"  {BLUE_ID}  "
        )

        self.write_document(document)

        target = load_knowledge_target(
            self.target_path
        )

        self.assertEqual(
            target.source_name,
            "epsilon-system",
        )
        self.assertEqual(
            target.model_id,
            "epsilon",
        )
        self.assertEqual(
            target.slot("blue").kb_id,
            BLUE_ID,
        )

    def test_rejects_invalid_json(self) -> None:
        self.target_path.write_text(
            "{ invalid json",
            encoding="utf-8",
        )

        with self.assertRaisesRegex(
            KnowledgeTargetError,
            "no contiene JSON válido",
        ):
            load_knowledge_target(
                self.target_path
            )

    def test_rejects_non_object_document(self) -> None:
        self.write_document(
            ["blue", "green"]
        )

        with self.assertRaisesRegex(
            KnowledgeTargetError,
            "debe ser un objeto JSON",
        ):
            load_knowledge_target(
                self.target_path
            )

    def test_rejects_blank_source_name(self) -> None:
        document = self.valid_document()
        document["source_name"] = "   "

        self.write_document(document)

        with self.assertRaisesRegex(
            KnowledgeTargetError,
            "source_name válido",
        ):
            load_knowledge_target(
                self.target_path
            )

    def test_rejects_blank_model_id(self) -> None:
        document = self.valid_document()
        document["model_id"] = ""

        self.write_document(document)

        with self.assertRaisesRegex(
            KnowledgeTargetError,
            "model_id válido",
        ):
            load_knowledge_target(
                self.target_path
            )

    def test_rejects_missing_slots_object(self) -> None:
        document = self.valid_document()
        document.pop("slots")

        self.write_document(document)

        with self.assertRaisesRegex(
            KnowledgeTargetError,
            "objeto slots",
        ):
            load_knowledge_target(
                self.target_path
            )

    def test_rejects_missing_green_slot(self) -> None:
        document = self.valid_document()
        document["slots"].pop("green")

        self.write_document(document)

        with self.assertRaisesRegex(
            KnowledgeTargetError,
            "exactamente los slots blue y green",
        ):
            load_knowledge_target(
                self.target_path
            )

    def test_rejects_extra_slot(self) -> None:
        document = self.valid_document()
        document["slots"]["staging"] = {
            "kb_id": (
                "33333333-3333-4333-8333-333333333333"
            ),
        }

        self.write_document(document)

        with self.assertRaisesRegex(
            KnowledgeTargetError,
            "exactamente los slots blue y green",
        ):
            load_knowledge_target(
                self.target_path
            )

    def test_rejects_non_object_slot(self) -> None:
        document = self.valid_document()
        document["slots"]["blue"] = BLUE_ID

        self.write_document(document)

        with self.assertRaisesRegex(
            KnowledgeTargetError,
            "slot 'blue' no es un objeto",
        ):
            load_knowledge_target(
                self.target_path
            )

    def test_rejects_blank_kb_id(self) -> None:
        document = self.valid_document()
        document["slots"]["green"]["kb_id"] = " "

        self.write_document(document)

        with self.assertRaisesRegex(
            KnowledgeTargetError,
            "kb_id válido",
        ):
            load_knowledge_target(
                self.target_path
            )

    def test_rejects_duplicate_kb_ids(self) -> None:
        document = self.valid_document()
        document["slots"]["green"]["kb_id"] = BLUE_ID

        self.write_document(document)

        with self.assertRaisesRegex(
            KnowledgeTargetError,
            "no pueden usar el mismo kb_id",
        ):
            load_knowledge_target(
                self.target_path
            )

    def test_slot_helpers_return_expected_slot(self) -> None:
        self.write_document(
            self.valid_document()
        )

        target = load_knowledge_target(
            self.target_path
        )

        self.assertEqual(
            target.slot("blue").kb_id,
            BLUE_ID,
        )
        self.assertEqual(
            target.other_slot("blue").name,
            "green",
        )
        self.assertEqual(
            target.other_slot("green").name,
            "blue",
        )

    def test_slot_helpers_reject_unknown_name(self) -> None:
        self.write_document(
            self.valid_document()
        )

        target = load_knowledge_target(
            self.target_path
        )

        with self.assertRaisesRegex(
            KnowledgeTargetError,
            "no está configurado",
        ):
            target.slot("unknown")

        with self.assertRaisesRegex(
            KnowledgeTargetError,
            "determinar el slot candidato",
        ):
            target.other_slot("unknown")

    def test_manager_rejects_unexpected_source_name(
        self,
    ) -> None:
        document = self.valid_document()
        document["source_name"] = "other-system"

        self.write_document(document)

        manager = KnowledgeManager.__new__(
            KnowledgeManager
        )
        manager.target_path = self.target_path
        manager.source_name = "epsilon-system"

        with self.assertRaisesRegex(
            KnowledgeManagerError,
            "fuente diferente",
        ):
            manager._load_target()


class KnowledgeActiveSlotTests(unittest.TestCase):
    """Pruebas de selección del slot conectado al modelo."""

    def setUp(self) -> None:
        self.target = KnowledgeTarget(
            source_name="epsilon-system",
            model_id="epsilon",
            slots=(
                KnowledgeSlot(
                    name="blue",
                    kb_id=BLUE_ID,
                ),
                KnowledgeSlot(
                    name="green",
                    kb_id=GREEN_ID,
                ),
            ),
        )

    def manager_with_models(
        self,
        models: list[dict[str, Any]],
    ) -> KnowledgeManager:
        manager = KnowledgeManager.__new__(
            KnowledgeManager
        )
        manager.client = FakeOpenWebUIClient(
            models
        )

        return manager

    def model_with_knowledge(
        self,
        *knowledge_ids: str,
    ) -> dict[str, Any]:
        return {
            "id": "epsilon",
            "meta": {
                "knowledge": [
                    {
                        "id": knowledge_id,
                    }
                    for knowledge_id in knowledge_ids
                ],
            },
        }

    def test_identifies_blue_as_active(self) -> None:
        manager = self.manager_with_models(
            [
                self.model_with_knowledge(
                    BLUE_ID
                ),
            ]
        )

        active = manager._active_slot(
            self.target
        )

        self.assertEqual(
            active.name,
            "blue",
        )

    def test_identifies_green_as_active(self) -> None:
        manager = self.manager_with_models(
            [
                self.model_with_knowledge(
                    GREEN_ID
                ),
            ]
        )

        active = manager._active_slot(
            self.target
        )

        self.assertEqual(
            active.name,
            "green",
        )

    def test_ignores_unrelated_knowledge(self) -> None:
        unrelated_id = (
            "99999999-9999-4999-8999-999999999999"
        )

        manager = self.manager_with_models(
            [
                self.model_with_knowledge(
                    unrelated_id,
                    BLUE_ID,
                ),
            ]
        )

        active = manager._active_slot(
            self.target
        )

        self.assertEqual(
            active.name,
            "blue",
        )

    def test_rejects_missing_model(self) -> None:
        manager = self.manager_with_models(
            [
                {
                    "id": "another-model",
                    "meta": {
                        "knowledge": [],
                    },
                },
            ]
        )

        with self.assertRaisesRegex(
            KnowledgeManagerError,
            "No existe el modelo 'epsilon'",
        ):
            manager._active_slot(
                self.target
            )

    def test_rejects_invalid_model_metadata(self) -> None:
        manager = self.manager_with_models(
            [
                {
                    "id": "epsilon",
                    "meta": None,
                },
            ]
        )

        with self.assertRaisesRegex(
            KnowledgeManagerError,
            "metadatos válidos",
        ):
            manager._active_slot(
                self.target
            )

    def test_rejects_invalid_knowledge_list(self) -> None:
        manager = self.manager_with_models(
            [
                {
                    "id": "epsilon",
                    "meta": {
                        "knowledge": "not-a-list",
                    },
                },
            ]
        )

        with self.assertRaisesRegex(
            KnowledgeManagerError,
            "lista válida de Knowledge",
        ):
            manager._active_slot(
                self.target
            )

    def test_rejects_when_no_slot_is_attached(
        self,
    ) -> None:
        manager = self.manager_with_models(
            [
                self.model_with_knowledge(
                    "99999999-9999-4999-8999-999999999999"
                ),
            ]
        )

        with self.assertRaisesRegex(
            KnowledgeManagerError,
            "exactamente uno de los slots",
        ):
            manager._active_slot(
                self.target
            )

    def test_rejects_when_both_slots_are_attached(
        self,
    ) -> None:
        manager = self.manager_with_models(
            [
                self.model_with_knowledge(
                    BLUE_ID,
                    GREEN_ID,
                ),
            ]
        )

        with self.assertRaisesRegex(
            KnowledgeManagerError,
            "exactamente uno de los slots",
        ):
            manager._active_slot(
                self.target
            )


if __name__ == "__main__":
    unittest.main()