from dataclasses import dataclass
import os


@dataclass
class Config:
    base_url: str = "http://localhost:8081"
    api_key: str = os.getenv("OPENWEBUI_API_KEY", "")