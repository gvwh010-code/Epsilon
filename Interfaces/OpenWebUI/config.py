from dataclasses import dataclass
import os


@dataclass
class Config:
    base_url: str = os.getenv(
        "OPEN_WEBUI_URL",
        "http://localhost:8081",
    )

    api_key: str = os.getenv(
        "OPEN_WEBUI_API_KEY",
        "",
    )

    def __post_init__(self):
        if not self.api_key:
            raise RuntimeError(
                "Falta OPEN_WEBUI_API_KEY. "
                "Configúrala antes de ejecutar epsilon-sync."
            )