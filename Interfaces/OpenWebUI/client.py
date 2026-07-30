from __future__ import annotations

from typing import Any
from types import TracebackType

import requests

from config import Config


class OpenWebUIClientError(RuntimeError):
    """Error controlado al comunicarse con Open WebUI."""


class OpenWebUIAuthenticationError(OpenWebUIClientError):
    """La solicitud necesita credenciales válidas."""


class OpenWebUIClient:
    def __init__(self, config: Config | None = None):
        self.config = config or Config()
        self.session = requests.Session()

    def close(self) -> None:
        """Cierra la sesión HTTP administrada por el cliente."""

        self.session.close()

    def __enter__(self) -> OpenWebUIClient:
        """Permite administrar el cliente mediante with."""

        return self

    def __exit__(
        self,
        exception_type: type[BaseException] | None,
        exception: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        """Garantiza el cierre de la sesión al salir del contexto."""

        self.close()

    def health(self) -> None:
        """Comprueba disponibilidad básica sin autenticación."""

        self._request(
            method="GET",
            endpoint="/health",
            authenticated=False,
            expect_json=False,
        )

    def get(self, endpoint: str) -> Any:
        return self._request(
            method="GET",
            endpoint=endpoint,
            authenticated=True,
            expect_json=True,
        )

    def list_models(self) -> list[dict[str, Any]]:
        """Lista los modelos visibles para la API key."""

        payload = self.get("/api/models")

        if isinstance(payload, list):
            models = payload

        elif isinstance(payload, dict):
            models = payload.get("data")

            if models is None:
                models = payload.get("models")

        else:
            models = None

        if not isinstance(models, list):
            raise OpenWebUIClientError(
                "Open WebUI devolvió una lista de modelos inválida."
            )

        return [
            model
            for model in models
            if isinstance(model, dict)
        ]

    def export_models(self) -> list[dict[str, Any]]:
        """Exporta las definiciones de los modelos personalizados."""

        payload = self.get("/api/v1/models/export")

        if not isinstance(payload, list):
            raise OpenWebUIClientError(
                "Open WebUI devolvió un export de modelos inválido: "
                "se esperaba una lista."
            )

        if not all(isinstance(model, dict) for model in payload):
            raise OpenWebUIClientError(
                "Open WebUI devolvió elementos inválidos "
                "en el export de modelos."
            )

        return payload

    def import_models(
        self,
        models: list[dict[str, Any]],
    ) -> None:
        """Crea o actualiza modelos mediante la importación aditiva."""

        if not models:
            raise ValueError(
                "La importación necesita al menos un modelo."
            )

        model_ids: list[str] = []

        for index, model in enumerate(models):
            if not isinstance(model, dict):
                raise ValueError(
                    f"El modelo en la posición {index} no es un objeto."
                )

            model_id = model.get("id")

            if not isinstance(model_id, str) or not model_id.strip():
                raise ValueError(
                    f"El modelo en la posición {index} no tiene un id válido."
                )

            model_ids.append(model_id)

        if len(model_ids) != len(set(model_ids)):
            raise ValueError(
                "La importación contiene identificadores duplicados."
            )

        result = self.post(
            "/api/v1/models/import",
            {
                "models": models,
            },
        )

        if result is not True:
            raise OpenWebUIClientError(
                "Open WebUI no confirmó la importación de modelos."
            )

    def find_model(
        self,
        model_id: str,
        models: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any] | None:
        """Busca un modelo por su identificador canónico."""

        available_models = (
            models
            if models is not None
            else self.list_models()
        )

        for model in available_models:
            identifiers = {
                model.get("id"),
                model.get("model"),
                model.get("name"),
            }

            if model_id in identifiers:
                return model

        return None

    def post(self, endpoint: str, payload: dict[str, Any]) -> Any:
        return self._request(
            method="POST",
            endpoint=endpoint,
            payload=payload,
            authenticated=True,
            expect_json=True,
        )

    def _request(
        self,
        *,
        method: str,
        endpoint: str,
        payload: dict[str, Any] | None = None,
        authenticated: bool,
        expect_json: bool,
    ) -> Any:
        url = f"{self.config.base_url}{endpoint}"

        headers: dict[str, str] = {
            "Accept": "application/json",
        }

        if payload is not None:
            headers["Content-Type"] = "application/json"

        if authenticated:
            try:
                api_key = self.config.require_api_key()
            except RuntimeError as error:
                raise OpenWebUIAuthenticationError(
                    "OPEN_WEBUI_API_KEY no está configurada."
                ) from error

            headers["Authorization"] = f"Bearer {api_key}"

        try:
            response = self.session.request(
                method=method,
                url=url,
                headers=headers,
                json=payload,
                timeout=self.config.timeout_seconds,
            )

        except requests.Timeout as error:
            raise OpenWebUIClientError(
                f"Timeout al conectar con {self.config.base_url}."
            ) from error

        except requests.ConnectionError as error:
            raise OpenWebUIClientError(
                f"No fue posible conectar con {self.config.base_url}."
            ) from error

        except requests.RequestException as error:
            raise OpenWebUIClientError(
                "Falló la solicitud a Open WebUI."
            ) from error

        if response.status_code == 401:
            raise OpenWebUIAuthenticationError(
                "Open WebUI rechazó la API key."
            )

        if response.status_code == 403:
            raise OpenWebUIAuthenticationError(
                "La API key no tiene permisos suficientes."
            )

        try:
            response.raise_for_status()
        except requests.HTTPError as error:
            raise OpenWebUIClientError(
                f"Open WebUI respondió HTTP {response.status_code}."
            ) from error

        if not expect_json:
            return None

        try:
            return response.json()
        except ValueError as error:
            raise OpenWebUIClientError(
                "Open WebUI devolvió una respuesta JSON inválida."
            ) from error