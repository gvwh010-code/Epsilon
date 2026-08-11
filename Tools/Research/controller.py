from __future__ import annotations
from .planning import build_research_plan
from .ranking import rank_results
from .selection import select_candidates
from .passages import select_relevant_passages
from .provenance import (
    provenance_candidates,
    should_replace_source,
)

import time

from urllib.parse import (
    urlsplit,
    urlunsplit,
)

from .grounding import citation_diagnostics
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
        max_provenance_fetches: int = 0,
    ):
        if max_fetch_attempts < max_fetches:
            raise ValueError(
                "max_fetch_attempts no puede ser menor "
                "que max_fetches."
            )

        if max_provenance_fetches < 0:
            raise ValueError(
                "max_provenance_fetches "
                "no puede ser negativo."
            )

        self.llm = llm
        self.searcher = searcher
        self.fetcher = fetcher
        self.max_searches = max_searches
        self.max_fetches = max_fetches
        self.max_fetch_attempts = max_fetch_attempts
        self.max_provenance_fetches = (
            max_provenance_fetches
        )

    def run(
        self,
        question: str,
        context: list[dict[str, str]] | None = None,
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
            "provenance_attempts_used": 0,
            "provenance_urls": [],
            "provenance_replacements": [],
            "search_results": 0,
            "sources_fetched": 0,
            "planned_queries": [],
            "search_provider_events": [],
            "candidate_urls": [],
            "selected_urls": [],
            "source_selector_ids": [],
            "source_selector_used": False,
            "errors": [],
        }

        original_question = question
        context = context or []

        diagnostics[
            "context_message_count"
        ] = len(context)

        diagnostics["context_used"] = False
        diagnostics[
            "original_question"
        ] = original_question

        resolver = getattr(
            self.llm,
            "resolve_research_question",
            None,
        )

        if context and callable(resolver):
            try:
                resolved = resolver(
                    question,
                    context,
                )

                if (
                    isinstance(resolved, str)
                    and resolved.strip()
                ):
                    question = resolved.strip()
                    diagnostics[
                        "context_used"
                    ] = True

            except Exception as error:
                diagnostics["errors"].append(
                    f"context: {error}"
                )

        diagnostics[
            "resolved_question"
        ] = question

        plan = build_research_plan(
            question
        )

        queries = list(
            plan.queries[: self.max_searches]
        )

        if not queries:
            queries = [question]

        diagnostics["planned_queries"] = queries
        diagnostics["source_mode"] = plan.source_mode

        all_results: list[SearchResult] = []
        search_started = time.monotonic()

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
            finally:
                provider_event = getattr(
                    self.searcher,
                    "last_diagnostics",
                    None,
                )

                if isinstance(
                    provider_event,
                    dict,
                ):
                    diagnostics[
                        "search_provider_events"
                    ].append(
                        {
                            "query": query,
                            **provider_event,
                        }
                    )

        diagnostics["search_seconds"] = round(
            time.monotonic() - search_started,
            3,
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

        # Ranking determinista inicial. Sirve para
        # reducir ruido y como fallback si el selector
        # semántico no puede utilizarse.
        ranked_candidates = rank_results(
            deduplicated,
            queries[0],
            source_mode=plan.source_mode,
        )

        candidate_results: list[SearchResult] = []
        candidate_urls: set[str] = set()
        candidate_domains: set[str] = set()

        # Selección determinista después del ranking.
        # Qwen no participa en esta etapa.
        candidate_results = select_candidates(
            ranked_candidates,
            queries,
            max_candidates=self.max_fetch_attempts,
            question=queries[0],
        )

        diagnostics["source_selector_ids"] = []
        diagnostics["source_selector_used"] = False
        diagnostics["selection_mode"] = (
            "deterministic"
        )

        diagnostics["candidate_urls"] = [
            result.url
            for result in candidate_results
        ]

        sources: list[EvidenceSource] = []
        failed_domains: set[str] = set()
        fetch_started = time.monotonic()

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

            page = None
            fetch_page = getattr(
                self.fetcher,
                "fetch_page",
                None,
            )

            try:
                if callable(fetch_page):
                    page = fetch_page(
                        result.url
                    )
                    source_text = page.text
                else:
                    source_text = (
                        self.fetcher.fetch(
                            result.url
                        )
                    )
            except Exception as error:
                failed_domains.add(domain)

                diagnostics["errors"].append(
                    f"fetch {result.url}: {error}"
                )
                continue

            effective_result = result

            if (
                page is not None
                and callable(fetch_page)
                and int(
                    diagnostics[
                        "provenance_attempts_used"
                    ]
                )
                < self.max_provenance_fetches
            ):
                remaining = (
                    self.max_provenance_fetches
                    - int(
                        diagnostics[
                            "provenance_attempts_used"
                        ]
                    )
                )

                candidates = (
                    provenance_candidates(
                        result,
                        page.links,
                        question,
                        max_candidates=remaining,
                    )
                )

                for candidate in candidates:
                    if (
                        int(
                            diagnostics[
                                "provenance_attempts_used"
                            ]
                        )
                        >= self.max_provenance_fetches
                    ):
                        break

                    diagnostics[
                        "provenance_attempts_used"
                    ] = (
                        int(
                            diagnostics[
                                "provenance_attempts_used"
                            ]
                        )
                        + 1
                    )

                    diagnostics[
                        "provenance_urls"
                    ].append(
                        candidate.url
                    )

                    try:
                        candidate_page = (
                            fetch_page(
                                candidate.url
                            )
                        )
                    except Exception as error:
                        diagnostics[
                            "errors"
                        ].append(
                            "provenance "
                            f"{candidate.url}: "
                            f"{error}"
                        )
                        continue

                    if not should_replace_source(
                        result,
                        candidate,
                    ):
                        continue

                    effective_result = (
                        SearchResult(
                            title=(
                                candidate_page.title
                                or candidate.title
                            ),
                            url=candidate.url,
                            snippet=(
                                candidate.snippet
                            ),
                            query=result.query,
                        )
                    )

                    source_text = (
                        candidate_page.text
                    )

                    diagnostics[
                        "provenance_replacements"
                    ].append(
                        {
                            "from": result.url,
                            "to": candidate.url,
                        }
                    )

                    break

            relevant_text = (
                select_relevant_passages(
                    question,
                    source_text,
                )
            )

            if not relevant_text:
                continue

            sources.append(
                EvidenceSource(
                    source_id=(
                        f"S{len(sources) + 1}"
                    ),
                    title=result.title,
                    url=result.url,
                    text=relevant_text,
                )
            )

            diagnostics["selected_urls"].append(
                effective_result.url
            )

        diagnostics["fetch_seconds"] = round(
            time.monotonic() - fetch_started,
            3,
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

        diagnostics[
            "citation_diagnostics"
        ] = citation_diagnostics(
            answer,
            (
                source.source_id
                for source in sources
            ),
        )

        return ResearchResult(
            answer=answer,
            plan=plan,
            sources=tuple(sources),
            diagnostics=diagnostics,
        )
