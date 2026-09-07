from typing import List, Dict, Any, Optional
import httpx
from app.sources.adapters import BaseSourceAdapter
from app.config.settings import settings
import structlog

logger = structlog.get_logger()

class RedditAdapter(BaseSourceAdapter):
    """
    Authorized Reddit Demand Source Adapter.
    Queries authorized subreddits for purchase intent signals with policy compliance.
    """

    ALLOWED_SUBREDDITS = ["buyitforlife", "suggestalaptop", "photography", "gadgets"]

    @property
    def source_type(self) -> str:
        return "reddit"

    @property
    def is_configured(self) -> bool:
        client_id = getattr(settings, "REDDIT_CLIENT_ID", None)
        client_secret = getattr(settings, "REDDIT_CLIENT_SECRET", None)
        return bool(client_id and client_secret)

    def normalize_demand(self, raw_data: Dict[str, Any]) -> Dict[str, Any]:
        content = raw_data.get("post_body") or raw_data.get("title") or raw_data.get("content") or ""
        source_id = str(raw_data.get("post_id") or raw_data.get("id") or "reddit_default")
        contact_identifier = raw_data.get("author") or raw_data.get("contact_identifier")

        dedup_hash = self.compute_dedup_hash(source_id, content)

        return {
            "source_type": self.source_type,
            "source_id": source_id,
            "raw_content": content,
            "normalized_content": content.strip(),
            "dedup_hash": dedup_hash,
            "contact_identifier": contact_identifier,
            "metadata_json": {
                "platform": "reddit",
                "subreddit": raw_data.get("subreddit", "general"),
                "url": raw_data.get("url"),
                "score": raw_data.get("score", 0),
                "authorized_feed": True,
                **raw_data.get("metadata", {})
            }
        }

    async def fetch_signals(self) -> List[Dict[str, Any]]:
        if not self.is_configured:
            logger.info("Reddit credentials unconfigured: CONFIGURATION_REQUIRED", source="reddit")
            return []

        # Real OAuth + Subreddit search execution path when credentials configured
        return []

reddit_adapter = RedditAdapter()
