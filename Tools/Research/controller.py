from __future__ import annotations
from .ranking import rank_results

from urllib.parse import (
    urlsplit,
    urlunsplit,
)

from .models import (
    EvidenceSource,
    ResearchResult,
    SearchResult,
)


def _canonical_url(url: str) -> str:
    parts = urlsplit(url)

    path = parts.path.rstrip("/")

    return urlunsplit(
        (
            parts.scheme.lower(),
            parts.netloc.lower(),
            path,
            parts.query,
            "",
        )
    )


def _domain(url: str) -> str:
    return urlsplit(url).netloc.lower()


class ResearchController:
    def __init__(
        self,
        llm,
        searcher,
        fetcher,
        *,
        max_searches: int = 3,
        max_fetches: int = 3,
        max_fetch_attempts: int = 5,
    ):
        if max_fetch_attempts < max_fetches:
            raise ValueError(
                "max_fetch_attempts no puede ser menor "
                "que max_fetches."
            )

        self.llm = llm
        self.searcher = searcher
        self.fetcher = fetcher
        self.max_searches = max_searches
        self.max_fetches = max_fetches
        self.max_fetch_attempts = max_fetch_attempts

    def run(
        self,
        question: str,
    ) -> ResearchResult:
        question = question.strip()

        if not question:
            raise ValueError(
                "La pregunta de investigación está vacía."
            )

        diagnostics: dict[str, object] = {
            "searches_used": 0,
            "fetches_used": 0,
            "fetch_attempts_used": 0,
            "search_results": 0,
            "sources_fetched": 0,
            "planned_queries": [],
            "candidate_urls": [],
            "selected_urls": [],
            "errors": [],
        }

        plan = self.llm.plan(question)

        queries = list(
            plan.queries[: self.max_searches]
        )

        if not queries:
            queries = [question]

        diagnostics["planned_queries"] = queries

        all_results: list[SearchResult] = []

        for query in queries:
            diagnostics["searches_used"] = (
                int(
                    diagnostics[
                        "searches_used"
                    ]
                )
                + 1
            )

            try:
                all_results.extend(
                    self.searcher.search(query)
                )
            except Exception as error:
                diagnostics["errors"].append(
                    f"search: {error}"
                )

        deduplicated: list[SearchResult] = []
        seen_urls: set[str] = set()

        for result in all_results:
            canonical = _canonical_url(
                result.url
            )

            if (
                not canonical
                or canonical in seen_urls
            ):
                continue

            seen_urls.add(canonical)
            deduplicated.append(result)

        diagnostics["search_results"] = len(
            deduplicated
        )

        if not deduplicated:
            return ResearchResult(
                answer=(
                    "No pude obtener resultados web "
                    "suficientes para investigar esta "
                    "pregunta con evidencia."
                ),
                plan=plan,
                sources=(),
                diagnostics=diagnostics,
            )

        candidate_results: list[SearchResult] = []
        candidate_urls: set[str] = set()
        candidate_domains: set[str] = set()

        # Primero reservamos una fuente distinta
        # para cada consulta, si existe.
        for query in queries:
            if (
                len(candidate_results)
                >= self.max_fetch_attempts
            ):
                break

            query_results: list[SearchResult] = []

            for result in all_results:
                if result.query != query:
                    continue

                canonical = _canonical_url(
                    result.url
                )

                if (
                    not canonical
                    or canonical in candidate_urls
                ):
                    continue

                query_results.append(result)

            if not query_results:
                continue

            ranked_results = rank_results(
                query_results
            )

            selected = next(
                (
                    result
                    for result in ranked_results
                    if _domain(result.url)
                    not in candidate_domains
                ),
                ranked_results[0],
            )

            canonical = _canonical_url(
                selected.url
            )

            candidate_urls.add(canonical)
            candidate_domains.add(
                _domain(selected.url)
            )
            candidate_results.append(selected)

        # Completamos la cola con candidatos globales.
        # Primero priorizamos diversidad de dominios.
        if (
            len(candidate_results)
            < self.max_fetch_attempts
        ):
            remaining_results = [
                result
                for result in deduplicated
                if _canonical_url(result.url)
                not in candidate_urls
            ]

            ranked_remaining = rank_results(
                remaining_results
            )

            for selected in ranked_remaining:
                if (
                    len(candidate_results)
                    >= self.max_fetch_attempts
                ):
                    break

                domain = _domain(selected.url)

                if domain in candidate_domains:
                    continue

                canonical = _canonical_url(
                    selected.url
                )

                candidate_urls.add(canonical)
                candidate_domains.add(domain)
                candidate_results.append(selected)

            # Solo si todavía faltan candidatos
            # permitimos repetir dominios.
            if (
                len(candidate_results)
                < self.max_fetch_attempts
            ):
                for selected in ranked_remaining:
                    if (
                        len(candidate_results)
                        >= self.max_fetch_attempts
                    ):
                        break

                    canonical = _canonical_url(
                        selected.url
                    )

                    if canonical in candidate_urls:
                        continue

                    candidate_urls.add(canonical)
                    candidate_results.append(selected)

        diagnostics["candidate_urls"] = [
            result.url
            for result in candidate_results
        ]

        sources: list[EvidenceSource] = []
        failed_domains: set[str] = set()

        for result in candidate_results:
            domain = _domain(result.url)

            if domain in failed_domains:
                continue
            if len(sources) >= self.max_fetches:
                break

            if (
                int(
                    diagnostics[
                        "fetch_attempts_used"
                    ]
                )
                >= self.max_fetch_attempts
            ):
                break

            diagnostics["fetch_attempts_used"] = (
                int(
                    diagnostics[
                        "fetch_attempts_used"
                    ]
                )
                + 1
            )

            try:
                source_text = self.fetcher.fetch(
                    result.url
                )
            except Exception as error:
                failed_domains.add(domain)

                diagnostics["errors"].append(
                    f"fetch {result.url}: {error}"
                )
                continue

            sources.append(
                EvidenceSource(
                    source_id=(
                        f"S{len(sources) + 1}"
                    ),
                    title=result.title,
                    url=result.url,
                    text=source_text,
                )
            )

            diagnostics["selected_urls"].append(
                result.url
            )

        diagnostics["fetches_used"] = len(
            sources
        )

        diagnostics["sources_fetched"] = len(
            sources
        )

        if not sources:
            return ResearchResult(
                answer=(
                    "Encontré resultados de búsqueda, "
                    "pero no pude recuperar ninguna "
                    "fuente utilizable. No voy a "
                    "completar la respuesta con "
                    "información no verificada."
                ),
                plan=plan,
                sources=(),
                diagnostics=diagnostics,
            )

        answer = self.llm.synthesize(
            question,
            plan,
            sources,
        )

        return ResearchResult(
            answer=answer,
            plan=plan,
            sources=tuple(sources),
            diagnostics=diagnostics,
        )
