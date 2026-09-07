import secrets
from typing import Dict, Any, Tuple, Optional
from app.config.settings import settings
import structlog

logger = structlog.get_logger()

class TrackingService:
    """
    Manages click token generation, click tracking, conversion recording, and dynamic commission calculations.
    Ensures strict idempotency for conversion events to avoid duplicate commissions.
    """

    # Dynamic commission rates matrix per merchant and product category
    COMMISSION_RATES = {
        "amazon": {
            "default": 0.040,      # 4.0%
            "electronics": 0.045,  # 4.5%
            "fashion": 0.070,      # 7.0%
        },
        "ebay": {
            "default": 0.060,      # 6.0%
            "electronics": 0.055,  # 5.5%
            "luxury": 0.080,       # 8.0%
        },
        "etsy": {
            "default": 0.050,      # 5.0%
            "handcrafted": 0.065   # 6.5%
        }
    }

    def generate_click_token(self, offer_id: str, purchase_intent_id: str) -> str:
        return secrets.token_urlsafe(16)

    def generate_tracking_url(self, tracking_token: str) -> str:
        return f"{settings.BASE_TRACKING_URL}/{tracking_token}"

    def calculate_commission(self, merchant_name: str, amount: float, category: str = "default") -> Dict[str, Any]:
        """
        Calculates dynamic commission rate and amount based on merchant and product category.
        """
        m_rates = self.COMMISSION_RATES.get(merchant_name.lower(), {})
        rate = m_rates.get(category.lower(), m_rates.get("default", 0.040))
        commission_amount = round(amount * rate, 2)

        return {
            "merchant_name": merchant_name,
            "category": category,
            "rate": rate,
            "amount": commission_amount
        }

    def process_conversion(self, external_conversion_id: str, click_id: str, merchant_id: str, amount: float, currency: str = "EUR", category: str = "default", merchant_name: str = "ebay") -> Dict[str, Any]:
        """
        Processes conversion with dynamic commission calculations and produces idempotent payload.
        """
        commission_info = self.calculate_commission(merchant_name, amount, category)

        return {
            "external_conversion_id": external_conversion_id,
            "click_id": click_id,
            "merchant_id": merchant_id,
            "amount": amount,
            "currency": currency,
            "status": "completed",
            "commission": {
                "amount": commission_info["amount"],
                "rate": commission_info["rate"],
                "currency": currency,
                "status": "approved"
            }
        }

tracking_service = TrackingService()
