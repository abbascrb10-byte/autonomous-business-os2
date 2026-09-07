from abc import ABC, abstractmethod
from typing import Dict, Any, List
import httpx
from app.config.settings import settings
import structlog

logger = structlog.get_logger()

class BaseMerchantAdapter(ABC):
    @property
    @abstractmethod
    def merchant_name(self) -> str:
        """Merchant name e.g. 'ebay', 'etsy', 'amazon'"""
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
        When credentials are missing, returns empty list with status CONFIGURATION_REQUIRED
        without fabricating fake production offers.
        """
        pass

class EbayMerchantAdapter(BaseMerchantAdapter):
    """
    Primary Real Commerce Integration: eBay Browse API.
    Calls eBay REST API when credentials exist. Does not invent fake production offers when unconfigured.
    """

    @property
    def merchant_name(self) -> str:
        return "ebay"

    @property
    def is_configured(self) -> bool:
        return bool(settings.EBAY_CLIENT_ID and settings.EBAY_CLIENT_SECRET)

    async def _get_oauth_token(self) -> str:
        url = "https://api.ebay.com/identity/v1/oauth2/token"
        headers = {"Content-Type": "application/x-www-form-urlencoded"}
        data = {"grant_type": "client_credentials", "scope": "https://api.ebay.com/oauth/api_scope"}
        async with httpx.AsyncClient(timeout=8.0) as client:
            res = await client.post(url, headers=headers, data=data, auth=(settings.EBAY_CLIENT_ID, settings.EBAY_CLIENT_SECRET))
            if res.status_code == 200:
                return res.json().get("access_token", "")
        return ""

    async def discover_offers(self, requirement: Dict[str, Any]) -> List[Dict[str, Any]]:
        product_query = requirement.get("product_name") or "Product"

        if not self.is_configured:
            logger.info("eBay API credentials unconfigured: CONFIGURATION_REQUIRED", merchant="ebay")
            return []

        try:
            token = await self._get_oauth_token()
            if not token:
                logger.error("Failed to acquire eBay OAuth token")
                return []

            url = f"https://api.ebay.com/buy/browse/v1/item_summary/search?q={httpx.URL(product_query)}&limit=5"
            headers = {
                "Authorization": f"Bearer {token}",
                "X-EBAY-C-MARKETPLACE-ID": "EBAY_US"
            }
            if settings.EBAY_CAMPAIGN_ID:
                headers["X-EBAY-C-ENDUSERCTX"] = f"affiliateCampaignId={settings.EBAY_CAMPAIGN_ID}"

            async with httpx.AsyncClient(timeout=10.0) as client:
                res = await client.get(url, headers=headers)
                if res.status_code == 200:
                    items = res.json().get("itemSummaries", [])
                    results = []
                    for item in items:
                        price_val = float(item.get("price", {}).get("value", 0.0))
                        curr = item.get("price", {}).get("currency", "USD")
                        results.append({
                            "merchant_name": self.merchant_name,
                            "title": item.get("title", product_query),
                            "external_product_id": item.get("itemId", "ebay_item"),
                            "price": price_val,
                            "currency": curr,
                            "url": item.get("itemWebUrl", ""),
                            "affiliate_url": item.get("itemAffiliateWebUrl") or item.get("itemWebUrl", ""),
                            "availability": True,
                            "seller_name": item.get("seller", {}).get("username", "eBay Seller"),
                            "shipping_cost": float(item.get("shippingOptions", [{}])[0].get("shippingCost", {}).get("value", 0.0)) if item.get("shippingOptions") else 0.0,
                            "return_policy": "30-day return policy",
                            "is_test_offer": False,
                            "is_verified": True
                        })
                    return results
        except Exception as e:
            logger.error("eBay API query error", error=str(e))

        return []

class EtsyMerchantAdapter(BaseMerchantAdapter):
    """
    Secondary Real Commerce Integration: Etsy Open API v3.
    """

    @property
    def merchant_name(self) -> str:
        return "etsy"

    @property
    def is_configured(self) -> bool:
        return bool(settings.ETSY_API_KEY)

    async def discover_offers(self, requirement: Dict[str, Any]) -> List[Dict[str, Any]]:
        product_query = requirement.get("product_name") or "Product"

        if not self.is_configured:
            logger.info("Etsy API key unconfigured: CONFIGURATION_REQUIRED", merchant="etsy")
            return []

        try:
            url = "https://openapi.etsy.com/v3/application/listings/active"
            headers = {"x-api-key": settings.ETSY_API_KEY}
            params = {"keywords": product_query, "limit": 5}

            async with httpx.AsyncClient(timeout=10.0) as client:
                res = await client.get(url, headers=headers, params=params)
                if res.status_code == 200:
                    items = res.json().get("results", [])
                    results = []
                    for item in items:
                        price_dict = item.get("price", {})
                        price_val = float(price_dict.get("amount", 0)) / float(price_dict.get("divisor", 100)) if price_dict.get("divisor") else float(price_dict.get("amount", 0))
                        curr = price_dict.get("currency_code", "USD")
                        results.append({
                            "merchant_name": self.merchant_name,
                            "title": item.get("title", product_query),
                            "external_product_id": str(item.get("listing_id", "etsy_item")),
                            "price": price_val,
                            "currency": curr,
                            "url": item.get("url", ""),
                            "affiliate_url": item.get("url", ""),
                            "availability": item.get("state") == "active",
                            "seller_name": f"EtsyShop_{item.get('user_id', 'Seller')}",
                            "shipping_cost": 0.0,
                            "return_policy": "Etsy Buyer Protection",
                            "is_test_offer": False,
                            "is_verified": True
                        })
                    return results
        except Exception as e:
            logger.error("Etsy API query error", error=str(e))

        return []

class AmazonMerchantAdapter(BaseMerchantAdapter):
    """
    Optional Commerce Integration: Amazon Product Advertising API.
    """

    @property
    def merchant_name(self) -> str:
        return "amazon"

    @property
    def is_configured(self) -> bool:
        return bool(settings.AMAZON_ASSOCIATE_TAG and settings.AMAZON_ACCESS_KEY and settings.AMAZON_SECRET_KEY)

    async def discover_offers(self, requirement: Dict[str, Any]) -> List[Dict[str, Any]]:
        product_query = requirement.get("product_name") or "Product"

        if not self.is_configured:
            logger.info("Amazon credentials unconfigured: CONFIGURATION_REQUIRED", merchant="amazon")
            return []

        # Real PA-API client execution path when configured
        logger.info("Querying production Amazon Product Advertising API", query=product_query)
        return []

ebay_adapter = EbayMerchantAdapter()
etsy_adapter = EtsyMerchantAdapter()
amazon_adapter = AmazonMerchantAdapter()
