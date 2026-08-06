from __future__ import annotations

import os

from .controller import ResearchController
from .fetch import WebFetcher
from .llm import LlamaCppClient
from .search import SearXNGClient


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

    return ResearchController(
        llm=LlamaCppClient(
            llm_url,
            llm_model,
        ),
        searcher=SearXNGClient(
            searxng_url,
        ),
        fetcher=WebFetcher(),
        max_searches=3,
        max_fetches=3,
        max_fetch_attempts=5,
    )
