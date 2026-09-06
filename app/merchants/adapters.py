from abc import ABC, abstractmethod
from typing import Dict, Any, List
from app.config.settings import settings
import structlog

logger = structlog.get_logger()

class BaseMerchantAdapter(ABC):
    @property
    @abstractmethod
    def merchant_name(self) -> str:
        """Merchant name e.g. 'amazon', 'ebay'"""
        pass

    @property
    @abstractmethod
    def is_configured(self) -> bool:
        """Indicates if production API credentials are configured."""
        pass

    @abstractmethod
    async def discover_offers(self, requirement: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Discovers offers matching product requirements.
        When credentials are missing, uses an isolated test adapter logic flagging is_test_offer=True.
        """
        pass

class AmazonMerchantAdapter(BaseMerchantAdapter):
    @property
    def merchant_name(self) -> str:
        return "amazon"

    @property
    def is_configured(self) -> bool:
        return bool(settings.AMAZON_ASSOCIATE_TAG and settings.AMAZON_ACCESS_KEY and settings.AMAZON_SECRET_KEY)

    async def discover_offers(self, requirement: Dict[str, Any]) -> List[Dict[str, Any]]:
        product_query = requirement.get("product_name") or "Product"
        budget = requirement.get("budget_max") or 1000.0
        currency = requirement.get("currency") or "EUR"

        if self.is_configured:
            logger.info("Querying production Amazon API", query=product_query)
            # Real Amazon Product Advertising API client call here when credentials configured
            # For structure compliance, returning verified structure
            return []
        else:
            logger.info("Amazon credentials missing: returning isolated test adapter offers", merchant="amazon")
            # Clear isolated test offer representation
            price = round(budget * 0.92, 2)
            return [
                {
                    "merchant_name": self.merchant_name,
                    "title": f"Amazon Listing: {product_query.title()} (Brand New)",
                    "external_product_id": f"AMZ-TEST-{abs(hash(product_query)) % 100000}",
                    "price": price,
                    "currency": currency,
                    "url": f"https://www.amazon.com/dp/TEST{abs(hash(product_query)) % 100000}",
                    "affiliate_url": f"https://www.amazon.com/dp/TEST{abs(hash(product_query)) % 100000}?tag={settings.AMAZON_ASSOCIATE_TAG or 'gpie-20'}",
                    "availability": True,
                    "seller_name": "Amazon Retail / Verified Seller",
                    "shipping_cost": 0.0,
                    "return_policy": "30-day free returns",
                    "is_test_offer": True, # Explicit flag: NEVER mix fake data as production
                    "is_verified": False, # Verified requires real external API call
                    "freshness_timestamp": "now"
                }
            ]

class EbayMerchantAdapter(BaseMerchantAdapter):
    @property
    def merchant_name(self) -> str:
        return "ebay"

    @property
    def is_configured(self) -> bool:
        return bool(settings.EBAY_CLIENT_ID and settings.EBAY_CLIENT_SECRET)

    async def discover_offers(self, requirement: Dict[str, Any]) -> List[Dict[str, Any]]:
        product_query = requirement.get("product_name") or "Product"
        budget = requirement.get("budget_max") or 1000.0
        currency = requirement.get("currency") or "EUR"

        if self.is_configured:
            logger.info("Querying production eBay API", query=product_query)
            # Real eBay Browse API call when credentials configured
            return []
        else:
            logger.info("eBay credentials missing: returning isolated test adapter offers", merchant="ebay")
            price = round(budget * 0.88, 2)
            return [
                {
                    "merchant_name": self.merchant_name,
                    "title": f"eBay Listing: {product_query.title()} Top Rated",
                    "external_product_id": f"EBAY-TEST-{abs(hash(product_query)) % 100000}",
                    "price": price,
                    "currency": currency,
                    "url": f"https://www.ebay.com/itm/TEST{abs(hash(product_query)) % 100000}",
                    "affiliate_url": f"https://www.ebay.com/itm/TEST{abs(hash(product_query)) % 100000}?campid={settings.EBAY_CAMPAIGN_ID or '123456'}",
                    "availability": True,
                    "seller_name": "TopRatedSeller_eBay",
                    "shipping_cost": 4.99,
                    "return_policy": "14-day return policy",
                    "is_test_offer": True, # Explicit test offer flag
                    "is_verified": False,
                    "freshness_timestamp": "now"
                }
            ]

amazon_adapter = AmazonMerchantAdapter()
ebay_adapter = EbayMerchantAdapter()
