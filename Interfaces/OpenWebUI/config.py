from __future__ import annotations

from dataclasses import dataclass, field
import os
from pathlib import Path


ALLOWED_LOCAL_CREDENTIALS = {
    "OPEN_WEBUI_API_KEY",
}


def credentials_file_path() -> Path:
    """Devuelve la ruta privada de credenciales fuera del repositorio."""

    configured_home = os.getenv("XDG_CONFIG_HOME")

    if configured_home:
        config_home = Path(configured_home).expanduser()
    else:
        config_home = Path.home() / ".config"

    return config_home / "epsilon" / "credentials.env"


def read_local_credentials(path: Path) -> dict[str, str]:
    """Lee las credenciales permitidas sin modificar os.environ."""

    if not path.is_file():
        return {}

    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError as error:
        raise RuntimeError(
            f"No fue posible leer el archivo de credenciales: {path}"
        ) from error

    credentials: dict[str, str] = {}

    for line_number, raw_line in enumerate(lines, start=1):
        line = raw_line.strip()

        if not line or line.startswith("#"):
            continue

        if "=" not in line:
            raise RuntimeError(
                "Formato inválido en el archivo de credenciales, "
                f"línea {line_number}."
            )

        name, value = line.split("=", 1)
        name = name.strip()
        value = value.strip()

        if name not in ALLOWED_LOCAL_CREDENTIALS:
            raise RuntimeError(
                f"Variable no permitida en credentials.env: {name}"
            )

        if (
            len(value) >= 2
            and value[0] == value[-1]
            and value[0] in {"'", '"'}
        ):
            value = value[1:-1]

        credentials[name] = value

    return credentials


CREDENTIALS_PATH = credentials_file_path()
LOCAL_CREDENTIALS = read_local_credentials(CREDENTIALS_PATH)


def read_setting(name: str, default: str = "") -> str:
    """Prioriza el entorno explícito sobre el archivo local."""

    return os.getenv(
        name,
        LOCAL_CREDENTIALS.get(name, default),
    )


def read_timeout() -> float:
    raw_value = read_setting("EPSILON_HTTP_TIMEOUT", "5")

    try:
        timeout = float(raw_value)
    except ValueError as error:
        raise RuntimeError(
            "EPSILON_HTTP_TIMEOUT debe ser un número."
        ) from error

    if timeout <= 0:
        raise RuntimeError(
            "EPSILON_HTTP_TIMEOUT debe ser mayor que cero."
        )

    return timeout


@dataclass(frozen=True)
class Config:
    credentials_path: Path = field(
        default_factory=credentials_file_path
    )

    base_url: str = field(
        default_factory=lambda: read_setting(
            "OPEN_WEBUI_URL",
            "http://localhost:8081",
        ).rstrip("/")
    )

    api_key: str = field(
        default_factory=lambda: read_setting(
            "OPEN_WEBUI_API_KEY",
            "",
        ).strip()
    )

    openwebui_model: str = field(
        default_factory=lambda: read_setting(
            "EPSILON_OPENWEBUI_MODEL",
            "epsilon",
        ).strip()
    )

    ollama_url: str = field(
        default_factory=lambda: read_setting(
            "EPSILON_OLLAMA_URL",
            "http://localhost:11434",
        ).rstrip("/")
    )

    ollama_model: str = field(
        default_factory=lambda: read_setting(
            "EPSILON_OLLAMA_MODEL",
            "gemma4:12b",
        ).strip()
    )

    timeout_seconds: float = field(
        default_factory=read_timeout
    )

    @property
    def has_api_key(self) -> bool:
        return bool(self.api_key)

    def require_api_key(self) -> str:
        if not self.api_key:
            raise RuntimeError(
                "Falta OPEN_WEBUI_API_KEY."
            )

        return self.api_key