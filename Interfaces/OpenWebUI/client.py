import requests

from config import Config


class OpenWebUIClient:

    def __init__(self):
        self.config = Config()

        self.headers = {
            "Authorization": f"Bearer {self.config.api_key}",
            "Content-Type": "application/json",
        }

    def get(self, endpoint: str):
        response = requests.get(
            f"{self.config.base_url}{endpoint}",
            headers=self.headers,
        )

        response.raise_for_status()

        return response.json()