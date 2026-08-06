from __future__ import annotations

import json
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from .models import SearchResult


class SearchError(RuntimeError):
    pass


class SearXNGClient:
    def __init__(
        self,
        base_url: str,
        *,
        timeout_seconds: float = 15.0,
        results_per_query: int = 8,
    ):
        self.base_url = base_url.rstrip("/")
        self.timeout_seconds = timeout_seconds
        self.results_per_query = results_per_query

    def search(self, query: str) -> list[SearchResult]:
        params = urlencode(
            {
                "q": query,
                "format": "json",
            }
        )

        request = Request(
            f"{self.base_url}/search?{params}",
            headers={
                "Accept": "application/json",
                "User-Agent": "EpsilonResearch/0.1",
            },
        )

        try:
            with urlopen(
                request,
                timeout=self.timeout_seconds,
            ) as response:
                payload = json.load(response)
        except Exception as error:
            raise SearchError(
                f"SearXNG falló para la consulta {query!r}: {error}"
            ) from error

        raw_results = payload.get("results", [])

        if not isinstance(raw_results, list):
            raise SearchError(
                "SearXNG devolvió un formato de resultados inválido."
            )

        results: list[SearchResult] = []

        for item in raw_results:
            if not isinstance(item, dict):
                continue

            url = str(item.get("url") or "").strip()

            if not url:
                continue

            results.append(
                SearchResult(
                    title=str(item.get("title") or "").strip(),
                    url=url,
                    snippet=str(
                        item.get("content")
                        or item.get("snippet")
                        or ""
                    ).strip(),
                    query=query,
                )
            )

            if len(results) >= self.results_per_query:
                break

        return results
