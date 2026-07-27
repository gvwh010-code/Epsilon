from __future__ import annotations

from typing import Any

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