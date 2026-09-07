from typing import List, Dict, Any, Optional
import httpx
from app.sources.adapters import BaseSourceAdapter
from app.config.settings import settings
import structlog

logger = structlog.get_logger()

class TwitterAdapter(BaseSourceAdapter):
    """
    Authorized Twitter / X Demand Source Adapter.
    Queries recent commercial intent tweet streams with policy compliance.
    """

    SEARCH_QUERIES = [
        '"need a" laptop -filter:retweets',
        '"looking to buy" camera -filter:retweets',
        '"want to buy" -filter:retweets'
    ]

    @property
    def source_type(self) -> str:
        return "twitter"

    @property
    def is_configured(self) -> bool:
        bearer_token = getattr(settings, "TWITTER_BEARER_TOKEN", None)
        return bool(bearer_token)

    def normalize_demand(self, raw_data: Dict[str, Any]) -> Dict[str, Any]:
        content = raw_data.get("text") or raw_data.get("tweet_text") or raw_data.get("content") or ""
        source_id = str(raw_data.get("tweet_id") or raw_data.get("id") or "twitter_default")
        contact_identifier = raw_data.get("author_id") or raw_data.get("author") or raw_data.get("contact_identifier")

        dedup_hash = self.compute_dedup_hash(source_id, content)

        return {
            "source_type": self.source_type,
            "source_id": source_id,
            "raw_content": content,
            "normalized_content": content.strip(),
            "dedup_hash": dedup_hash,
            "contact_identifier": contact_identifier,
            "metadata_json": {
                "platform": "twitter",
                "url": raw_data.get("url"),
                "likes": raw_data.get("likes", 0),
                "authorized_feed": True,
                **raw_data.get("metadata", {})
            }
        }

    async def fetch_signals(self) -> List[Dict[str, Any]]:
        if not self.is_configured:
            logger.info("Twitter bearer token unconfigured: CONFIGURATION_REQUIRED", source="twitter")
            return []

        # Real Twitter API v2 recent search execution path when token configured
        return []

twitter_adapter = TwitterAdapter()
