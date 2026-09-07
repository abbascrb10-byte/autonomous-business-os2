import hashlib
from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional
import httpx
from app.config.settings import settings
import structlog

logger = structlog.get_logger()

class BaseSourceAdapter(ABC):
    @property
    @abstractmethod
    def source_type(self) -> str:
        """Returns source identifier e.g. 'owned_api', 'authorized_public', 'commercial_search', 'tavily_search'"""
        pass

    @abstractmethod
    def normalize_demand(self, raw_data: Dict[str, Any]) -> Dict[str, Any]:
        """Normalizes raw input into standard demand representation."""
        pass

    def compute_dedup_hash(self, source_id: str, content: str) -> str:
        """Generates SHA256 hash for deduplication."""
        normalized_str = f"{self.source_type}:{source_id}:{content.strip().lower()}"
        return hashlib.sha256(normalized_str.encode('utf-8')).hexdigest()

class OwnedDemandAdapter(BaseSourceAdapter):
    @property
    def source_type(self) -> str:
        return "owned_api"

    def normalize_demand(self, raw_data: Dict[str, Any]) -> Dict[str, Any]:
        content = raw_data.get("text") or raw_data.get("content") or ""
        source_id = str(raw_data.get("user_id") or raw_data.get("source_id") or "owned_default")
        contact_identifier = raw_data.get("email") or raw_data.get("contact_identifier")

        dedup_hash = self.compute_dedup_hash(source_id, content)

        return {
            "source_type": self.source_type,
            "source_id": source_id,
            "raw_content": content,
            "normalized_content": content.strip(),
            "dedup_hash": dedup_hash,
            "contact_identifier": contact_identifier,
            "metadata_json": raw_data.get("metadata", {})
        }

class AuthorizedPublicSourceAdapter(BaseSourceAdapter):
    @property
    def source_type(self) -> str:
        return "authorized_public"

    def normalize_demand(self, raw_data: Dict[str, Any]) -> Dict[str, Any]:
        content = raw_data.get("post_body") or raw_data.get("message") or ""
        source_id = str(raw_data.get("post_id") or raw_data.get("author_id") or "public_default")
        contact_identifier = raw_data.get("author_email") or raw_data.get("author_handle")

        dedup_hash = self.compute_dedup_hash(source_id, content)

        return {
            "source_type": self.source_type,
            "source_id": source_id,
            "raw_content": content,
            "normalized_content": content.strip(),
            "dedup_hash": dedup_hash,
            "contact_identifier": contact_identifier,
            "metadata_json": {
                "platform": raw_data.get("platform", "public_forum"),
                "authorized_feed": True,
                **raw_data.get("metadata", {})
            }
        }

class SearchIntentAdapter(BaseSourceAdapter):
    @property
    def source_type(self) -> str:
        return "commercial_search"

    def normalize_demand(self, raw_data: Dict[str, Any]) -> Dict[str, Any]:
        content = raw_data.get("query") or raw_data.get("search_term") or ""
        source_id = str(raw_data.get("session_id") or "search_default")
        contact_identifier = raw_data.get("user_identifier")

        dedup_hash = self.compute_dedup_hash(source_id, content)

        return {
            "source_type": self.source_type,
            "source_id": source_id,
            "raw_content": content,
            "normalized_content": content.strip(),
            "dedup_hash": dedup_hash,
            "contact_identifier": contact_identifier,
            "metadata_json": {
                "search_engine": raw_data.get("engine", "internal_search"),
                **raw_data.get("metadata", {})
            }
        }

class TavilySearchAdapter(BaseSourceAdapter):
    """
    Search adapter using Tavily Web Search API (Free Tier).
    Fails gracefully without fabricating results if credentials are missing or quota is exhausted.
    """

    @property
    def source_type(self) -> str:
        return "tavily_search"

    @property
    def is_configured(self) -> bool:
        return bool(settings.TAVILY_API_KEY)

    def normalize_demand(self, raw_data: Dict[str, Any]) -> Dict[str, Any]:
        content = raw_data.get("query") or raw_data.get("search_term") or ""
        source_id = str(raw_data.get("source_id") or "tavily_default")
        contact_identifier = raw_data.get("contact_identifier")

        dedup_hash = self.compute_dedup_hash(source_id, content)

        return {
            "source_type": self.source_type,
            "source_id": source_id,
            "raw_content": content,
            "normalized_content": content.strip(),
            "dedup_hash": dedup_hash,
            "contact_identifier": contact_identifier,
            "metadata_json": {
                "search_engine": "tavily",
                "is_configured": self.is_configured,
                **raw_data.get("metadata", {})
            }
        }

    async def execute_web_search(self, query: str) -> Optional[List[Dict[str, Any]]]:
        if not self.is_configured:
            logger.info("Tavily API key not configured: search provider unavailable")
            return None

        try:
            url = "https://api.tavily.com/search"
            payload = {
                "api_key": settings.TAVILY_API_KEY,
                "query": query,
                "search_depth": "basic",
                "include_domains": ["amazon.com", "ebay.com", "etsy.com"]
            }
            async with httpx.AsyncClient(timeout=8.0) as client:
                res = await client.post(url, json=payload)
                if res.status_code == 200:
                    return res.json().get("results", [])
                else:
                    logger.warning("Tavily API error", status_code=res.status_code)
        except Exception as e:
            logger.error("Tavily search execution failed", error=str(e))

        return None

owned_adapter = OwnedDemandAdapter()
public_adapter = AuthorizedPublicSourceAdapter()
search_adapter = SearchIntentAdapter()
tavily_adapter = TavilySearchAdapter()
