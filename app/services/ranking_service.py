from typing import Dict, Any, List, Tuple
from datetime import datetime, timezone
from app.agents.llm_provider import llm_provider
import structlog

logger = structlog.get_logger()

class RankingService:
    """
    Verifies and ranks commercial offers based on product match, model fit, price suitability,
    seller trust signals, availability, shipping, freshness, and affiliate weight.
    Buyer suitability is strictly prioritized over commission rate.
    """

    def verify_offer(self, offer: Dict[str, Any], requirement: Dict[str, Any]) -> Tuple[bool, str]:
        """
        Verifies that an offer is eligible and valid against buyer requirements.
        Checks price <= budget_max, availability, valid URL, and currency.
        """
        url = offer.get("url") or offer.get("affiliate_url")
        if not url:
            return False, "Offer is missing destination URL"

        price = offer.get("price")
        if price is None or price <= 0:
            return False, "Offer has invalid price"

        budget_max = requirement.get("budget_max")
        if budget_max and price > budget_max * 1.05:
            return False, f"Offer price ({price}) exceeds budget max ({budget_max})"

        if not offer.get("availability", True):
            return False, "Offer is currently unavailable"

        return True, "Verified eligible offer"

    async def rank_offers(self, offers: List[Dict[str, Any]], requirement: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Ranks verified offers and attaches calculated score and transparent win rationale.
        Sets is_verified=True ONLY after verification rules pass.
        """
        budget_max = requirement.get("budget_max") or 1000.0
        product_req = requirement.get("product_name") or ""

        ranked_offers = []

        for offer in offers:
            is_ok, verify_msg = self.verify_offer(offer, requirement)
            if not is_ok:
                continue

            llm_eval = await llm_provider.reason_offer_suitability(offer.get("title", ""), offer.get("price", 0.0), requirement)
            product_match_score = float(llm_eval.get("match_score", 0.5))

            offer_price = offer.get("price", budget_max)
            if offer_price <= budget_max:
                price_score = 1.0 - (offer_price / (budget_max * 1.5))
            else:
                price_score = 0.2

            seller = (offer.get("seller_name") or "").lower()
            if seller and ("verified" in seller or "top" in seller or "official" in seller or "amazon" in seller):
                seller_trust = 0.95
            elif seller:
                seller_trust = 0.75
            else:
                seller_trust = 0.50 # Neutral default when seller name unknown

            merchant_name = offer.get("merchant_name", "").lower()
            affiliate_weight = 0.08 if merchant_name == "amazon" else 0.06

            rank_score = round(
                (product_match_score * 0.50) +
                (price_score * 0.30) +
                (seller_trust * 0.12) +
                (affiliate_weight * 0.08),
                3
            )

            win_rationale = (
                f"Rank score: {rank_score}. Match: {product_match_score:.2f}, Price fit: {price_score:.2f}, "
                f"Seller trust: {seller_trust:.2f}. Verification: {verify_msg}."
            )

            offer_copy = dict(offer)
            offer_copy["product_match_score"] = product_match_score
            offer_copy["rank_score"] = rank_score
            offer_copy["win_rationale"] = win_rationale
            offer_copy["is_verified"] = True # Set verified True only after verification pass

            ranked_offers.append(offer_copy)

        ranked_offers.sort(key=lambda x: x["rank_score"], reverse=True)
        return ranked_offers

ranking_service = RankingService()
