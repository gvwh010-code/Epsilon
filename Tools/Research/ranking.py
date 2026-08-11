from __future__ import annotations

import re
from urllib.parse import urlsplit

from .models import SearchResult


LOW_QUALITY_DOMAINS = {
    "scribd.com",
    "academia.edu",
    "pinterest.com",
}

COMMUNITY_DOMAINS = {
    "reddit.com",
    "quora.com",
}

SOCIAL_PLATFORM_DOMAINS = {
    "facebook.com",
    "instagram.com",
    "tiktok.com",
}

MUSIC_CATALOG_DOMAINS = {
    "spotify.com",
    "music.apple.com",
    "discogs.com",
    "deezer.com",
    "musicbrainz.org",
    "allmusic.com",
    "bandcamp.com",
}

MUSIC_CATALOG_ITEM_PATH_HINTS = (
    "/track/",
    "/album/",
    "/song/",
    "/release/",
    "/master/",
    "/recording/",
)

MUSIC_CATALOG_QUERY_HINTS = (
    " songs",
    " song",
    "discography",
    "track listing",
    "track list",
    "official releases",
    "official spanish versions",
    "official english versions",
    "official french versions",
    "official german versions",
    "official italian versions",
    "official portuguese versions",
)


SECONDARY_DOMAINS = {
    "wikipedia.org",
    "wikibooks.org",
    "handwiki.org",
}

COMMERCE_HINTS = (
    "merch",
    "shop",
    "store",
    "shopping",
    "product",
    "products",
    "all-items",
)

DIRECT_SOURCE_HINTS = (
    "interview",
    "entrevista",
    "transcript",
    "transcripción",
    "transcripcion",
    "statement",
    "declaración",
    "declaracion",
    "press release",
    "comunicado",
    "official statement",
    "official report",
    "official documentation",
    "testimony",
    "testimonio",
    "diary",
    "diario",
    "memoir",
    "memorias",
    "full interview",
    "complete interview",
    "oral history",
    "interviews",
    "transcripts",
    "q&a",
    "conversation",
)

AGGREGATION_HINTS = (
    "according to",
    "según",
    "recuerda que",
    "revela que",
    "explica que",
    "reported that",
    "reports that",
    "news",
    "noticias",
)


QUESTION_STOPWORDS = {
    "the", "and", "for", "with",
    "from", "that", "this", "what",
    "how", "about", "tell", "me",
    "research", "investigate",

    "los", "las", "una", "uno",
    "unos", "unas", "con", "del",
    "por", "para", "que", "qué",
    "como", "cómo", "cual", "cuál",
    "entre", "relacion", "relación",
    "hablame", "háblame",
    "investiga", "investigar",
    "investigación", "investigacion",
    "bien", "cuenta", "cuentas",
    "cuentame", "cuéntame",
}


def _domain(url: str) -> str:
    domain = urlsplit(url).netloc.lower()

    if domain.startswith("www."):
        domain = domain[4:]

    return domain


def _path(url: str) -> str:
    return urlsplit(url).path.lower()


def _matches_domain(
    domain: str,
    roots: set[str],
) -> bool:
    return any(
        domain == root
        or domain.endswith(
            "." + root
        )
        for root in roots
    )


def _contains_phrase(
    text: str,
    phrase: str,
) -> bool:
    if " " not in phrase:
        return bool(
            re.search(
                rf"\b{re.escape(phrase)}\b",
                text,
            )
        )

    return phrase in text


def _question_terms(
    question: str,
) -> set[str]:
    return {
        word
        for word in re.findall(
            r"[a-záéíóúüñ0-9]+",
            question.lower(),
        )
        if len(word) >= 3
        and word not in QUESTION_STOPWORDS
    }


def direct_source_hits(
    result: SearchResult,
) -> int:
    searchable = " ".join(
        (
            result.title,
            result.snippet,
            _path(result.url).replace(
                "-", " "
            ).replace(
                "_", " "
            ),
        )
    ).lower()

    return sum(
        _contains_phrase(
            searchable,
            hint,
        )
        for hint in DIRECT_SOURCE_HINTS
    )


def topical_relevance_score(
    result: SearchResult,
    question: str,
) -> int:
    terms = _question_terms(
        question
    )

    if not terms:
        return 0

    title = result.title.lower()
    snippet = result.snippet.lower()

    title_hits = {
        term
        for term in terms
        if term in title
    }

    snippet_hits = {
        term
        for term in terms
        if term in snippet
    }

    matched = (
        title_hits
        | snippet_hits
    )

    coverage = (
        len(matched)
        / len(terms)
    )

    score = (
        len(title_hits) * 10
        + len(
            snippet_hits - title_hits
        ) * 4
    )

    if len(terms) >= 2:
        if coverage >= 0.80:
            score += 30
        elif coverage >= 0.50:
            score += 8
        elif coverage < 0.34:
            score -= 30

    return score


def _is_music_catalog_query(
    result: SearchResult,
) -> bool:
    query = (
        result.query.lower().strip()
        if isinstance(result.query, str)
        else ""
    )

    return any(
        hint in query
        for hint in MUSIC_CATALOG_QUERY_HINTS
    )


def source_quality_score(
    result: SearchResult,
    *,
    position: int = 0,
    source_mode: str = "factual",
) -> int:
    domain = _domain(
        result.url
    )

    path = _path(
        result.url
    )

    searchable = " ".join(
        (
            domain,
            result.title,
            result.snippet,
            path.replace(
                "-", " "
            ).replace(
                "_", " "
            ),
        )
    ).lower()

    score = 30 - min(
        position,
        30,
    )

    if _matches_domain(
        domain,
        LOW_QUALITY_DOMAINS,
    ):
        score -= 100

    if source_mode not in {
        "factual",
        "community",
        "mixed",
    }:
        source_mode = "factual"

    community = _matches_domain(
        domain,
        COMMUNITY_DOMAINS,
    )

    social = _matches_domain(
        domain,
        SOCIAL_PLATFORM_DOMAINS,
    )

    if community:
        if source_mode == "factual":
            score -= 70
        elif source_mode == "mixed":
            score -= 10
        else:
            score += 25

    if social:
        if source_mode == "factual":
            score -= 45
        elif source_mode == "mixed":
            score -= 10
        else:
            score += 15

    secondary = _matches_domain(
        domain,
        SECONDARY_DOMAINS,
    )

    if secondary:
        score -= 25

    if any(
        hint in searchable
        for hint in COMMERCE_HINTS
    ):
        score -= 120

    if domain.endswith(".gov"):
        score += 70

    if domain.endswith(".edu"):
        score += 40

    direct_hits = direct_source_hits(
        result
    )

    if direct_hits:
        score += 30
        score += min(
            direct_hits - 1,
            3,
        ) * 8

    aggregation_hits = sum(
        _contains_phrase(
            searchable,
            hint,
        )
        for hint in AGGREGATION_HINTS
    )

    score -= min(
        aggregation_hits,
        3,
    ) * 6

    # Para preguntas de catálogo musical, una página
    # concreta de track/álbum/release constituye
    # evidencia mucho más directa que traducciones,
    # redes sociales o una portada genérica de artista.
    if (
        source_mode == "factual"
        and _is_music_catalog_query(result)
        and _matches_domain(
            domain,
            MUSIC_CATALOG_DOMAINS,
        )
    ):
        score += 45

        if any(
            hint in path
            for hint
            in MUSIC_CATALOG_ITEM_PATH_HINTS
        ):
            score += 30

    return score


def result_rank_score(
    result: SearchResult,
    question: str,
    *,
    position: int = 0,
    source_mode: str = "factual",
) -> int:
    return (
        topical_relevance_score(
            result,
            question,
        )
        + source_quality_score(
            result,
            position=position,
            source_mode=source_mode,
        )
    )


def rank_results(
    results: list[SearchResult],
    question: str = "",
    *,
    source_mode: str = "factual",
) -> list[SearchResult]:
    """
    Cada resultado se evalúa contra la consulta
    que realmente lo recuperó.

    La posición también se calcula dentro de cada
    consulta, no sobre la lista global combinada.
    """

    query_positions: dict[str, int] = {}
    scored = []

    for result in results:
        context = (
            result.query
            or question
        )

        position = query_positions.get(
            context,
            0,
        )

        query_positions[context] = (
            position + 1
        )

        scored.append(
            (
                result_rank_score(
                    result,
                    context,
                    position=position,
                    source_mode=source_mode,
                ),
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
