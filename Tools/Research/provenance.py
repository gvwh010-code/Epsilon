from __future__ import annotations

import re
from urllib.parse import urlsplit

from .fetch import PageLink
from .models import SearchResult
from .ranking import (
    direct_source_hits,
    source_quality_score,
)


_BLOCKED_DOMAINS = {
    "facebook.com",
    "instagram.com",
    "x.com",
    "twitter.com",
    "tiktok.com",
    "youtube.com",
    "youtu.be",
}

_BLOCKED_EXTENSIONS = (
    ".jpg",
    ".jpeg",
    ".png",
    ".gif",
    ".webp",
    ".svg",
    ".mp3",
    ".mp4",
    ".zip",
    ".pdf",
)

_STOPWORDS = {
    "the", "and", "for", "with",
    "from", "this", "that", "what",
    "how", "about",
    "los", "las", "una", "uno",
    "con", "del", "por", "para",
    "que", "qué", "como", "cómo",
    "entre", "relacion", "relación",
}


def _domain(url: str) -> str:
    domain = urlsplit(url).netloc.lower()

    if domain.startswith("www."):
        domain = domain[4:]

    return domain


def _terms(text: str) -> set[str]:
    return {
        word
        for word in re.findall(
            r"[a-záéíóúüñ0-9]+",
            text.lower(),
        )
        if len(word) >= 3
        and word not in _STOPWORDS
    }


def provenance_candidates(
    parent: SearchResult,
    links: tuple[PageLink, ...],
    question: str,
    *,
    max_candidates: int = 2,
) -> list[SearchResult]:
    parent_domain = _domain(parent.url)
    question_terms = _terms(question)

    scored: list[
        tuple[int, int, SearchResult]
    ] = []

    for position, link in enumerate(links):
        domain = _domain(link.url)

        if not domain:
            continue

        # Evita menús internos y recirculación
        # editorial. Buscamos el origen externo.
        if domain == parent_domain:
            continue

        if domain in _BLOCKED_DOMAINS:
            continue

        path = urlsplit(
            link.url
        ).path.lower()

        if path.endswith(
            _BLOCKED_EXTENSIONS
        ):
            continue

        candidate = SearchResult(
            title=(
                link.text.strip()
                or link.url
            ),
            url=link.url,
            snippet="",
            query=parent.query,
        )

        direct_hits = direct_source_hits(
            candidate
        )

        # No seguimos enlaces arbitrarios.
        # Debe parecer entrevista, transcript,
        # archivo, comunicado, documentación, etc.
        if direct_hits <= 0:
            continue

        searchable = (
            f"{link.text} {link.url}"
        ).lower()

        overlap = sum(
            term in searchable
            for term in question_terms
        )

        score = source_quality_score(
            candidate,
            position=min(position, 30),
        )

        score += min(
            overlap,
            4,
        ) * 5

        scored.append(
            (
                score,
                -position,
                candidate,
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
        for _, _, result
        in scored[:max_candidates]
    ]


def should_replace_source(
    parent: SearchResult,
    candidate: SearchResult,
) -> bool:
    parent_direct = direct_source_hits(
        parent
    )
    candidate_direct = direct_source_hits(
        candidate
    )

    if candidate_direct <= parent_direct:
        return False

    parent_score = source_quality_score(
        parent,
        position=0,
    )

    candidate_score = source_quality_score(
        candidate,
        position=0,
    )

    return (
        candidate_score
        >= parent_score + 10
    )
