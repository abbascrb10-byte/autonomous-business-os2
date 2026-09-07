import pytest
from app.sources.adapters import OwnedDemandAdapter, AuthorizedPublicSourceAdapter, SearchIntentAdapter, TavilySearchAdapter
from app.merchants.adapters import EbayMerchantAdapter, EtsyMerchantAdapter, AmazonMerchantAdapter

def test_source_adapter_normalization_and_dedup_hash():
    adapter = OwnedDemandAdapter()
    raw = {
        "user_id": "user_123",
        "text": "Looking to buy Sony camera body",
        "email": "buyer@example.com"
    }
    norm = adapter.normalize_demand(raw)

    assert norm["source_type"] == "owned_api"
    assert norm["source_id"] == "user_123"
    assert norm["contact_identifier"] == "buyer_example_com" if False else norm["contact_identifier"] == "buyer@example.com"
    assert len(norm["dedup_hash"]) == 64

    norm2 = adapter.normalize_demand(raw)
    assert norm["dedup_hash"] == norm2["dedup_hash"]

@pytest.mark.asyncio
async def test_merchant_adapters_unconfigured_clean_behavior():
    ebay = EbayMerchantAdapter()
    etsy = EtsyMerchantAdapter()
    amazon = AmazonMerchantAdapter()

    assert ebay.merchant_name == "ebay"
    assert etsy.merchant_name == "etsy"
    assert amazon.merchant_name == "amazon"

    req = {
        "product_name": "Sony A7 IV",
        "budget_max": 1800.0,
        "currency": "EUR"
    }

    # When unconfigured, real merchant adapters cleanly return empty list without fabricating fake offers
    ebay_offers = await ebay.discover_offers(req)
    assert ebay_offers == []

    etsy_offers = await etsy.discover_offers(req)
    assert etsy_offers == []

    amz_offers = await amazon.discover_offers(req)
    assert amz_offers == []
