from __future__ import annotations

import re
import unicodedata


def _normalize_for_match(
    text: str,
) -> str:
    """
    Normaliza texto para coincidencia léxica.

    Mantiene el texto original intacto para la
    evidencia; solo elimina diferencias de
    mayúsculas y diacríticos durante el scoring.
    """

    normalized = unicodedata.normalize(
        "NFKD",
        text.casefold(),
    )

    return "".join(
        char
        for char in normalized
        if not unicodedata.combining(char)
    )


STOPWORDS = {
    "the", "and", "for", "with", "from",
    "that", "this", "what", "how", "was",
    "were", "are", "their", "about",
    "una", "uno", "unos", "unas", "con",
    "del", "las", "los", "por", "para",
    "que", "qué", "como", "cómo", "cual",
    "cuál", "fue", "son", "sus", "entre",
    "relacion", "relación",
}


def _terms(question: str) -> set[str]:
    normalized = _normalize_for_match(
        question
    )

    normalized_stopwords = {
        _normalize_for_match(word)
        for word in STOPWORDS
    }

    words = re.findall(
        r"[a-z0-9]+",
        normalized,
    )

    return {
        word
        for word in words
        if len(word) >= 3
        and word not in normalized_stopwords
    }


def select_relevant_passages(
    question: str,
    text: str,
    *,
    chunk_chars: int = 900,
    overlap_chars: int = 200,
    max_passages: int = 2,
) -> str:
    text = text.strip()

    if not text:
        return ""

    if len(text) <= chunk_chars:
        return text

    terms = _terms(question)

    chunks: list[
        tuple[int, str]
    ] = []

    step = max(
        1,
        chunk_chars - overlap_chars,
    )

    for start in range(
        0,
        len(text),
        step,
    ):
        chunk = text[
            start:start + chunk_chars
        ].strip()

        if not chunk:
            continue

        normalized_chunk = (
            _normalize_for_match(
                chunk
            )
        )

        score = sum(
            min(
                normalized_chunk.count(term),
                4,
            )
            for term in terms
        )

        chunks.append(
            (
                score,
                chunk,
            )
        )

        if start + chunk_chars >= len(text):
            break

    ranked = sorted(
        enumerate(chunks),
        key=lambda item: (
            item[1][0],
            -item[0],
        ),
        reverse=True,
    )

    chosen_indexes = sorted(
        index
        for index, _ in ranked[
            :max_passages
        ]
    )

    return "\n\n".join(
        chunks[index][1]
        for index in chosen_indexes
    )
