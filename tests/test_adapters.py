import pytest
from app.sources.adapters import OwnedDemandAdapter, AuthorizedPublicSourceAdapter, SearchIntentAdapter
from app.merchants.adapters import AmazonMerchantAdapter, EbayMerchantAdapter

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
    assert norm["contact_identifier"] == "buyer@example.com"
    assert len(norm["dedup_hash"]) == 64

    # Duplicate payload produces identical hash
    norm2 = adapter.normalize_demand(raw)
    assert norm["dedup_hash"] == norm2["dedup_hash"]

@pytest.mark.asyncio
async def test_merchant_adapters_unconfigured_test_flag():
    amazon = AmazonMerchantAdapter()
    ebay = EbayMerchantAdapter()

    assert amazon.merchant_name == "amazon"
    assert ebay.merchant_name == "ebay"

    req = {
        "product_name": "Sony A7 IV",
        "budget_max": 1800.0,
        "currency": "EUR"
    }

    amz_offers = await amazon.discover_offers(req)
    assert len(amz_offers) == 1
    assert amz_offers[0]["is_test_offer"] is True
    assert "AMZ-TEST" in amz_offers[0]["external_product_id"]

    ebay_offers = await ebay.discover_offers(req)
    assert len(ebay_offers) == 1
    assert ebay_offers[0]["is_test_offer"] is True
    assert "EBAY-TEST" in ebay_offers[0]["external_product_id"]
