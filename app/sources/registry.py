from typing import Dict, Any, Optional
from app.sources.adapters import (
    BaseSourceAdapter, owned_adapter, public_adapter, search_adapter, tavily_adapter
)
from app.sources.reddit_adapter import reddit_adapter
from app.sources.twitter_adapter import twitter_adapter
import structlog

logger = structlog.get_logger()

class SourceAdapterRegistry:
    """
    Authoritative single registry for demand source adapters.
    Resolves source_type consistently across API, LangGraph, workers, and tests.
    """

    def __init__(self):
        self._adapters: Dict[str, BaseSourceAdapter] = {
            "owned_api": owned_adapter,
            "authorized_public": public_adapter,
            "commercial_search": search_adapter,
            "tavily_search": tavily_adapter,
            "reddit": reddit_adapter,
            "twitter": twitter_adapter,
        }

    def get_adapter(self, source_type: str) -> BaseSourceAdapter:
        adapter = self._adapters.get((source_type or "owned_api").lower())
        if not adapter:
            logger.warning("Unregistered source_type requested, defaulting to owned_api", requested=source_type)
            return owned_adapter
        return adapter

    def register_adapter(self, source_type: str, adapter: BaseSourceAdapter):
        self._adapters[source_type.lower()] = adapter

source_registry = SourceAdapterRegistry()
