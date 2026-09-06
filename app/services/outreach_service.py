import secrets
from typing import Dict, Any, Tuple, Optional
from app.config.settings import settings
import structlog

logger = structlog.get_logger()

class OutreachService:
    """
    Handles permission-based outreach.
    First contact: asks permission ("I found an option... Would you like me to send you the link?").
    Only after permission is granted: generates recommendation outreach message.
    If no authorized sending provider is configured, holds messages safely at an approval boundary (awaiting_approval).
    """

    def generate_permission_request(self, contact_identifier: str, product_name: str) -> Dict[str, Any]:
        content = (
            f"Hello, I found an option for '{product_name}' that matches your requirements. "
            f"Would you like me to send you the link?"
        )
        provider = settings.OUTREACH_PROVIDER.lower() if settings.OUTREACH_PROVIDER else "local_approval"

        return {
            "contact_identifier": contact_identifier,
            "message_type": "permission_request",
            "content": content,
            "status": "awaiting_approval" if provider == "local_approval" or not settings.OUTREACH_API_KEY else "sent",
            "delivery_provider": provider,
            "delivery_notes": "Held at local approval boundary for review." if provider == "local_approval" or not settings.OUTREACH_API_KEY else "Dispatched to provider API."
        }

    def generate_recommendation_message(self, contact_identifier: str, offer: Dict[str, Any], tracking_url: str) -> Dict[str, Any]:
        title = offer.get("title", "Product Offer")
        price = offer.get("price", 0.0)
        currency = offer.get("currency", "EUR")

        content = (
            f"Here is your recommended option:\n"
            f"Product: {title}\n"
            f"Price: {price} {currency}\n"
            f"Link: {tracking_url}\n\n"
            f"Note: This is an affiliate link."
        )
        provider = settings.OUTREACH_PROVIDER.lower() if settings.OUTREACH_PROVIDER else "local_approval"

        return {
            "contact_identifier": contact_identifier,
            "message_type": "recommendation",
            "content": content,
            "status": "awaiting_approval" if provider == "local_approval" or not settings.OUTREACH_API_KEY else "sent",
            "delivery_provider": provider,
            "delivery_notes": "Held at local approval boundary." if provider == "local_approval" or not settings.OUTREACH_API_KEY else "Dispatched to provider API."
        }

outreach_service = OutreachService()
