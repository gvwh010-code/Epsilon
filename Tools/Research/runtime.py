from __future__ import annotations

import os

from .controller import ResearchController
from .fetch import WebFetcher
from .llm import LlamaCppClient
from .search import ExaClient, FallbackSearchClient, SearXNGClient


def build_controller_from_env() -> ResearchController:
    searxng_url = os.environ.get(
        "RESEARCH_SEARXNG_URL",
        "http://localhost:8080",
    )

    llm_url = os.environ.get(
        "RESEARCH_LLM_URL",
        "http://127.0.0.1:10001",
    )

    llm_model = os.environ.get(
        "RESEARCH_LLM_MODEL",
        "qwen3.6-35b-a3b-test",
    )

    searxng = SearXNGClient(
        searxng_url,
        results_per_query=20,
    )

    exa_api_key = os.environ.get("EXA_API_KEY", "").strip()

    searcher = searxng

    if exa_api_key:
        searcher = FallbackSearchClient(
            ExaClient(
                exa_api_key,
                results_per_query=10,
            ),
            searxng,
        )

    return ResearchController(
        llm=LlamaCppClient(
            llm_url,
            llm_model,
        ),
        searcher=searcher,
        fetcher=WebFetcher(),
        max_searches=3,
        max_fetches=4,
        max_fetch_attempts=6,
        max_provenance_fetches=0,
    )
