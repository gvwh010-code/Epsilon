from typing import Any

from client import OpenWebUIClient


class KnowledgeManager:
    def __init__(self, client: OpenWebUIClient):
        self.client = client

    def list_collections(self) -> list[dict[str, Any]]:
        response = self.client.get("/api/v1/knowledge/list")

        if isinstance(response, list):
            return response

        if isinstance(response, dict):
            return response.get("data", [])

        return []