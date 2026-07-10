import json
from pathlib import Path
from typing import Any


class Identity:
    """Carga y expone la identidad estable de Epsilon."""

    def __init__(self, identity_path: Path | None = None) -> None:
        self.identity_path = identity_path or Path(__file__).with_name(
            "identity.json"
        )
        self._data = self._load_identity()

    def _load_identity(self) -> dict[str, Any]:
        if not self.identity_path.exists():
            raise FileNotFoundError(
                f"No se encontró el archivo de identidad: {self.identity_path}"
            )

        try:
            with self.identity_path.open("r", encoding="utf-8") as file:
                data = json.load(file)
        except json.JSONDecodeError as error:
            raise ValueError(
                f"identity.json contiene JSON inválido: {error}"
            ) from error

        required_fields = ("name", "role", "purpose", "behavior")
        missing_fields = [
            field for field in required_fields if field not in data
        ]

        if missing_fields:
            raise ValueError(
                "Faltan campos obligatorios en identity.json: "
                + ", ".join(missing_fields)
            )

        return data

    @property
    def name(self) -> str:
        return str(self._data["name"])

    @property
    def role(self) -> str:
        return str(self._data["role"])

    @property
    def purpose(self) -> str:
        return str(self._data["purpose"])

    def build_system_prompt(self) -> str:
        behavior = "\n".join(
            f"- {rule}" for rule in self._data["behavior"]
        )

        model_relationship = self._data.get("model_relationship", "")

        return (
            f"Tu nombre es {self.name}.\n"
            f"Eres: {self.role}.\n\n"
            f"Propósito:\n{self.purpose}\n\n"
            f"Reglas de comportamiento:\n{behavior}\n\n"
            f"{model_relationship}\n"
            "Cuando te pregunten quién eres, responde como Epsilon, "
            "no con el nombre del modelo subyacente."
        )