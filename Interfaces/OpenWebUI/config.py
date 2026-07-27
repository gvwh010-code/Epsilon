from dataclasses import dataclass, field
import os


def read_timeout() -> float:
    raw_value = os.getenv("EPSILON_HTTP_TIMEOUT", "5")

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
    base_url: str = field(
        default_factory=lambda: os.getenv(
            "OPEN_WEBUI_URL",
            "http://localhost:8081",
        ).rstrip("/")
    )

    api_key: str = field(
        default_factory=lambda: os.getenv(
            "OPEN_WEBUI_API_KEY",
            "",
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