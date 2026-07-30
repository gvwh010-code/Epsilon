from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
from typing import Any


class KnowledgeTargetError(RuntimeError):
    """Error controlado al leer la configuración Blue–Green."""


@dataclass(frozen=True)
class KnowledgeSlot:
    """Identifica uno de los dos slots remotos de Knowledge."""

    name: str
    kb_id: str


@dataclass(frozen=True)
class KnowledgeTarget:
    """Configuración validada del despliegue Blue–Green."""

    source_name: str
    model_id: str
    slots: tuple[KnowledgeSlot, ...]

    def slot(self, name: str) -> KnowledgeSlot:
        """Obtiene un slot configurado por su nombre."""

        for slot in self.slots:
            if slot.name == name:
                return slot

        raise KnowledgeTargetError(
            f"El slot {name!r} no está configurado."
        )

    def other_slot(self, name: str) -> KnowledgeSlot:
        """Obtiene el slot opuesto al indicado."""

        candidates = tuple(
            slot
            for slot in self.slots
            if slot.name != name
        )

        if len(candidates) != 1:
            raise KnowledgeTargetError(
                "No fue posible determinar el slot candidato."
            )

        return candidates[0]


def _required_text(
    document: dict[str, Any],
    field_name: str,
    *,
    context: str,
) -> str:
    """Lee un texto obligatorio y no vacío."""

    value = document.get(field_name)

    if not isinstance(value, str) or not value.strip():
        raise KnowledgeTargetError(
            f"{context} no contiene un {field_name} válido."
        )

    return value.strip()


def load_knowledge_target(
    target_path: Path,
) -> KnowledgeTarget:
    """Lee y valida knowledge_target.json."""

    try:
        document = json.loads(
            target_path.read_text(encoding="utf-8")
        )
    except OSError as error:
        raise KnowledgeTargetError(
            f"No fue posible leer {target_path}: {error}"
        ) from error
    except json.JSONDecodeError as error:
        raise KnowledgeTargetError(
            "La configuración de Knowledge "
            "no contiene JSON válido."
        ) from error

    if not isinstance(document, dict):
        raise KnowledgeTargetError(
            "La configuración de Knowledge "
            "debe ser un objeto JSON."
        )

    source_name = _required_text(
        document,
        "source_name",
        context="La configuración de Knowledge",
    )

    model_id = _required_text(
        document,
        "model_id",
        context="La configuración de Knowledge",
    )

    slots_document = document.get("slots")

    if not isinstance(slots_document, dict):
        raise KnowledgeTargetError(
            "La configuración no contiene un objeto slots."
        )

    expected_slot_names = {"blue", "green"}

    if set(slots_document) != expected_slot_names:
        raise KnowledgeTargetError(
            "La configuración debe contener exactamente "
            "los slots blue y green."
        )

    slots: list[KnowledgeSlot] = []

    for slot_name in ("blue", "green"):
        slot_document = slots_document.get(slot_name)

        if not isinstance(slot_document, dict):
            raise KnowledgeTargetError(
                f"El slot {slot_name!r} no es un objeto."
            )

        kb_id = _required_text(
            slot_document,
            "kb_id",
            context=f"El slot {slot_name!r}",
        )

        slots.append(
            KnowledgeSlot(
                name=slot_name,
                kb_id=kb_id,
            )
        )

    if len({slot.kb_id for slot in slots}) != len(slots):
        raise KnowledgeTargetError(
            "Los slots blue y green no pueden usar el mismo kb_id."
        )

    return KnowledgeTarget(
        source_name=source_name,
        model_id=model_id,
        slots=tuple(slots),
    )