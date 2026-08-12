from __future__ import annotations

import json
from urllib.error import HTTPError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from .models import SearchResult


class SearchError(RuntimeError):
    def __init__(
        self,
        message: str,
        *,
        provider: str | None = None,
        reason: str | None = None,
    ):
        super().__init__(message)
        self.provider = provider
        self.reason = reason


class ExaClient:
    name = "exa"

    def __init__(
        self,
        api_key: str,
        *,
        timeout_seconds: float = 20.0,
        results_per_query: int = 10,
    ):
        self.api_key = api_key
        self.timeout_seconds = timeout_seconds
        self.results_per_query = results_per_query

    def search(self, query: str) -> list[SearchResult]:
        payload = json.dumps(
            {
                "query": query,
                "numResults": self.results_per_query,
                "contents": {
                    "highlights": True,
                },
            }
        ).encode("utf-8")

        request = Request(
            "https://api.exa.ai/search",
            data=payload,
            headers={
                "x-api-key": self.api_key,
                "Content-Type": "application/json",
                "Accept": "application/json",
                "User-Agent": "EpsilonResearch/0.1",
            },
            method="POST",
        )

        try:
            with urlopen(
                request,
                timeout=self.timeout_seconds,
            ) as response:
                payload = json.load(response)
        except HTTPError as error:
            reason = {
                401: "unauthorized",
                402: "credits_exhausted",
                429: "rate_limited",
            }.get(
                error.code,
                f"http_{error.code}",
            )

            raise SearchError(
                f"Exa falló para la consulta {query!r}: {error}",
                provider="exa",
                reason=reason,
            ) from error
        except Exception as error:
            raise SearchError(
                f"Exa falló para la consulta {query!r}: {error}",
                provider="exa",
                reason="unavailable",
            ) from error

        raw_results = payload.get("results", [])

        if not isinstance(raw_results, list):
            raise SearchError(
                "Exa devolvió un formato de resultados inválido."
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
                    snippet=(
                        " ".join(
                            str(value).strip()
                            for value
                            in (
                                item.get("highlights")
                                or []
                            )
                            if str(value).strip()
                        )
                        or str(
                            item.get("text")
                            or item.get("summary")
                            or ""
                        ).strip()
                    ),
                    query=query,
                    published_date=(
                        str(
                            item.get("publishedDate")
                            or ""
                        ).strip()
                        or None
                    ),
                )
            )

        return results


class FallbackSearchClient:
    def __init__(self, primary, fallback):
        self.primary = primary
        self.fallback = fallback
        self.last_provider = None
        self.last_fallback_used = False
        self.last_errors = []

    @property
    def last_diagnostics(self):
        return {
            "provider": self.last_provider,
            "fallback_used": self.last_fallback_used,
            "provider_errors": list(
                self.last_errors
            ),
        }

    def _record_error(
        self,
        provider,
        error,
    ):
        self.last_errors.append(
            {
                "provider": getattr(
                    error,
                    "provider",
                    getattr(
                        provider,
                        "name",
                        provider.__class__.__name__,
                    ),
                ),
                "reason": getattr(
                    error,
                    "reason",
                    None,
                )
                or "error",
                "message": str(error),
            }
        )

    def search(self, query: str) -> list[SearchResult]:
        self.last_provider = None
        self.last_fallback_used = False
        self.last_errors = []

        primary_error = None

        try:
            results = self.primary.search(query)

            if results:
                self.last_provider = getattr(
                    self.primary,
                    "name",
                    "primary",
                )
                return results
        except Exception as error:
            primary_error = error
            self._record_error(
                self.primary,
                error,
            )

        self.last_fallback_used = True

        try:
            fallback_results = (
                self.fallback.search(query)
            )
        except Exception as fallback_error:
            self._record_error(
                self.fallback,
                fallback_error,
            )

            if primary_error is not None:
                raise SearchError(
                    "Fallaron ambos proveedores: "
                    f"principal={primary_error}; "
                    f"fallback={fallback_error}"
                ) from fallback_error

            raise

        if fallback_results:
            self.last_provider = getattr(
                self.fallback,
                "name",
                "fallback",
            )
            return fallback_results

        if primary_error is not None:
            raise SearchError(
                "El proveedor principal falló y "
                "el fallback no devolvió resultados: "
                f"{primary_error}"
            )

        self.last_provider = getattr(
            self.fallback,
            "name",
            "fallback",
        )

        return []


class SearXNGClient:
    name = "searxng"

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

        unresponsive = payload.get(
            "unresponsive_engines",
            [],
        )

        if (
            not raw_results
            and isinstance(unresponsive, list)
            and unresponsive
        ):
            failures = []

            for item in unresponsive:
                if (
                    isinstance(item, (list, tuple))
                    and len(item) >= 2
                ):
                    failures.append(
                        f"{item[0]}: {item[1]}"
                    )

            detail = (
                "; ".join(failures)
                or "motores no disponibles"
            )

            raise SearchError(
                "SearXNG no pudo completar la búsqueda: "
                + detail
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
