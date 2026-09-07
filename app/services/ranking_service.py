from typing import Dict, Any, List, Tuple
from datetime import datetime, timezone
from app.agents.llm_provider import llm_provider
from app.services.currency_service import currency_service
import structlog

logger = structlog.get_logger()

class RankingService:
    """
    Verifies and ranks commercial offers based on product match, model fit, price suitability,
    total cost (price + shipping converted to normalized currency), seller trust signals, availability,
    freshness, and affiliate weight.
    Buyer suitability is strictly prioritized over commission rate.
    """

    def verify_offer(self, offer: Dict[str, Any], requirement: Dict[str, Any]) -> Tuple[bool, str]:
        """
        Verifies that an offer is eligible and valid against buyer requirements.
        Checks price <= budget_max, total cost in normalized currency, availability, valid URL.
        """
        url = offer.get("url") or offer.get("affiliate_url")
        if not url or not (url.startswith("http://") or url.startswith("https://")):
            return False, "Offer is missing valid HTTP/HTTPS destination URL"

        price = offer.get("price")
        if price is None or price <= 0:
            return False, "Offer has invalid or non-positive price"

        offer_currency = offer.get("currency")
        if not offer_currency:
            return False, "Offer is missing source currency"

        shipping_cost = offer.get("shipping_cost")
        if shipping_cost is not None and shipping_cost < 0:
            return False, "Offer has invalid negative shipping cost"
        shipping_cost = shipping_cost or 0.0
        total_cost_orig = currency_service.calculate_total_cost(price, shipping_cost)
        total_cost_eur = currency_service.normalize_to_eur(total_cost_orig, offer_currency)

        budget_max = requirement.get("budget_max")
        req_currency = requirement.get("currency", "EUR")
        if budget_max:
            budget_max_eur = currency_service.normalize_to_eur(budget_max, req_currency)
            if total_cost_eur > budget_max_eur * 1.05:
                return False, f"Total cost ({total_cost_eur} EUR) exceeds budget max ({budget_max_eur} EUR)"

        if not offer.get("availability", True):
            return False, "Offer is currently unavailable"

        freshness_value = offer.get("freshness_timestamp")
        if freshness_value:
            try:
                if isinstance(freshness_value, str):
                    freshness_value = datetime.fromisoformat(freshness_value.replace("Z", "+00:00"))
                if freshness_value.tzinfo is None:
                    freshness_value = freshness_value.replace(tzinfo=timezone.utc)
                age_hours = (datetime.now(timezone.utc) - freshness_value).total_seconds() / 3600
                if age_hours > 24:
                    return False, "Offer is stale"
            except (TypeError, ValueError):
                return False, "Offer has invalid freshness timestamp"

        return True, "Verified eligible offer"

    async def rank_offers(self, offers: List[Dict[str, Any]], requirement: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Ranks verified offers and attaches calculated score and transparent win rationale.
        Sets is_verified=True ONLY after verification rules pass.
        """
        budget_max = requirement.get("budget_max") or 1000.0
        req_currency = requirement.get("currency", "EUR")
        budget_max_eur = currency_service.normalize_to_eur(budget_max, req_currency)

        ranked_offers = []

        for offer in offers:
            is_ok, verify_msg = self.verify_offer(offer, requirement)
            if not is_ok:
                continue

            llm_eval = await llm_provider.reason_offer_suitability(offer.get("title", ""), offer.get("price", 0.0), requirement)
            product_match_score = float(llm_eval.get("match_score", 0.5))

            offer_price = offer.get("price", budget_max)
            shipping_cost = offer.get("shipping_cost") or 0.0
            offer_currency = offer["currency"]
            total_cost_eur = currency_service.normalize_to_eur(currency_service.calculate_total_cost(offer_price, shipping_cost), offer_currency)

            if total_cost_eur <= budget_max_eur:
                price_score = 1.0 - (total_cost_eur / (budget_max_eur * 1.5))
            else:
                price_score = 0.2

            seller = (offer.get("seller_name") or "").lower()
            if seller and ("verified" in seller or "top" in seller or "official" in seller or "amazon" in seller):
                seller_trust = 0.95
            elif seller:
                seller_trust = 0.75
            else:
                seller_trust = 0.50

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
                f"Seller trust: {seller_trust:.2f}, Total Cost: {total_cost_eur} EUR. Verification: {verify_msg}."
            )

            offer_copy = dict(offer)
            offer_copy["product_match_score"] = product_match_score
            offer_copy["rank_score"] = rank_score
            offer_copy["total_cost_eur"] = total_cost_eur
            offer_copy["win_rationale"] = win_rationale
            offer_copy["is_verified"] = True

            ranked_offers.append(offer_copy)

        ranked_offers.sort(key=lambda x: x["rank_score"], reverse=True)
        return ranked_offers

ranking_service = RankingService()
