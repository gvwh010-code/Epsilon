from __future__ import annotations

from typing import Any

import requests


class OllamaClientError(RuntimeError):
    """Error controlado al comunicarse con Ollama."""


class OllamaClient:
    def __init__(
        self,
        *,
        base_url: str,
        timeout_seconds: float,
    ):
        self.base_url = base_url.rstrip("/")
        self.timeout_seconds = timeout_seconds
        self.session = requests.Session()

    def version(self) -> str:
        response = self._request(
            method="GET",
            endpoint="/api/version",
        )

        version = response.get("version")

        if not isinstance(version, str) or not version.strip():
            raise OllamaClientError(
                "Ollama no informó una versión válida."
            )

        return version.strip()

    def list_models(self) -> list[dict[str, Any]]:
        response = self._request(
            method="GET",
            endpoint="/api/tags",
        )

        models = response.get("models")

        if not isinstance(models, list):
            raise OllamaClientError(
                "Ollama devolvió una lista de modelos inválida."
            )

        return [
            model
            for model in models
            if isinstance(model, dict)
        ]

    def _request(
        self,
        *,
        method: str,
        endpoint: str,
    ) -> dict[str, Any]:
        url = f"{self.base_url}{endpoint}"

        try:
            response = self.session.request(
                method=method,
                url=url,
                headers={
                    "Accept": "application/json",
                },
                timeout=self.timeout_seconds,
            )

        except requests.Timeout as error:
            raise OllamaClientError(
                f"Timeout al conectar con {self.base_url}."
            ) from error

        except requests.ConnectionError as error:
            raise OllamaClientError(
                f"No fue posible conectar con {self.base_url}."
            ) from error

        except requests.RequestException as error:
            raise OllamaClientError(
                "Falló la solicitud a Ollama."
            ) from error

        try:
            response.raise_for_status()
        except requests.HTTPError as error:
            raise OllamaClientError(
                f"Ollama respondió HTTP {response.status_code}."
            ) from error

        try:
            payload = response.json()
        except ValueError as error:
            raise OllamaClientError(
                "Ollama devolvió una respuesta JSON inválida."
            ) from error

        if not isinstance(payload, dict):
            raise OllamaClientError(
                "Ollama devolvió una estructura inesperada."
            )

        return payload