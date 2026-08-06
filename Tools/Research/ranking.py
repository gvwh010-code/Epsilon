from __future__ import annotations

from urllib.parse import urlsplit

from .models import SearchResult


LOW_QUALITY_DOMAINS = {
    "reddit.com",
    "www.reddit.com",
    "scribd.com",
    "www.scribd.com",
    "academia.edu",
    "www.academia.edu",
    "pinterest.com",
    "www.pinterest.com",
}

SECONDARY_DOMAINS = {
    "wikipedia.org",
    "www.wikipedia.org",
    "en.wikipedia.org",
    "es.wikipedia.org",
}


def _domain(url: str) -> str:
    return urlsplit(url).netloc.lower()


def rank_results(
    results: list[SearchResult],
) -> list[SearchResult]:
    scored: list[
        tuple[int, int, SearchResult]
    ] = []

    for position, result in enumerate(results):
        domain = _domain(result.url)

        score = 100 - position

        if domain in LOW_QUALITY_DOMAINS:
            score -= 50

        if domain in SECONDARY_DOMAINS:
            score -= 10

        if domain.endswith(".gov"):
            score += 20

        if domain.endswith(".edu"):
            score += 15

        scored.append(
            (
                score,
                -position,
                result,
            )
        )

    scored.sort(
        key=lambda item: (
            item[0],
            item[1],
        ),
        reverse=True,
    )

    return [
        result
        for _, _, result in scored
    ]