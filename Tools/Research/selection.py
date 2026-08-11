from __future__ import annotations

from urllib.parse import urlsplit

from .models import SearchResult


def _domain(url: str) -> str:
    domain = urlsplit(url).netloc.lower()

    if domain.startswith("www."):
        domain = domain[4:]

    return domain


def select_candidates(
    results: list[SearchResult],
    queries: list[str],
    *,
    max_candidates: int,
    question: str = "",
) -> list[SearchResult]:
    """
    `results` ya viene ordenado por relevancia y
    calidad.

    Primera pasada:
    una sola página por dominio.

    Segunda pasada:
    permite repetir dominios únicamente si todavía
    faltan candidatos.
    """

    if max_candidates <= 0:
        return []

    selected: list[SearchResult] = []
    used_urls: set[str] = set()
    used_domains: set[str] = set()

    # Calidad del ranking manda, pero evitamos que
    # un único sitio monopolice toda la evidencia.
    for result in results:
        if len(selected) >= max_candidates:
            return selected

        if result.url in used_urls:
            continue

        domain = _domain(
            result.url
        )

        if domain in used_domains:
            continue

        selected.append(result)
        used_urls.add(result.url)
        used_domains.add(domain)

    # Si no existen suficientes dominios distintos,
    # completar respetando el ranking original.
    for result in results:
        if len(selected) >= max_candidates:
            break

        if result.url in used_urls:
            continue

        selected.append(result)
        used_urls.add(result.url)

    return selected
