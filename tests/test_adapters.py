import pytest
from app.sources.adapters import OwnedDemandAdapter, AuthorizedPublicSourceAdapter, SearchIntentAdapter, TavilySearchAdapter
from app.sources.reddit_adapter import RedditAdapter, reddit_adapter
from app.sources.twitter_adapter import TwitterAdapter, twitter_adapter
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
    assert norm["contact_identifier"] == "buyer@example.com"
    assert len(norm["dedup_hash"]) == 64

    norm2 = adapter.normalize_demand(raw)
    assert norm["dedup_hash"] == norm2["dedup_hash"]

def test_reddit_and_twitter_adapters():
    r_adapter = RedditAdapter()
    t_adapter = TwitterAdapter()

    assert r_adapter.source_type == "reddit"
    assert t_adapter.source_type == "twitter"

    # Test Reddit normalization
    raw_reddit = {
        "post_id": "reddit_post_100",
        "title": "Need a laptop under $1000",
        "author": "u/testbuyer",
        "subreddit": "suggestalaptop"
    }
    norm_r = r_adapter.normalize_demand(raw_reddit)
    assert norm_r["source_type"] == "reddit"
    assert norm_r["contact_identifier"] == "u/testbuyer"
    assert len(norm_r["dedup_hash"]) == 64

    # Test Twitter normalization
    raw_twitter = {
        "tweet_id": "tweet_200",
        "text": "Looking to buy a camera body asap",
        "author_id": "twitter_user_1"
    }
    norm_t = t_adapter.normalize_demand(raw_twitter)
    assert norm_t["source_type"] == "twitter"
    assert norm_t["contact_identifier"] == "twitter_user_1"
    assert len(norm_t["dedup_hash"]) == 64

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

    ebay_offers = await ebay.discover_offers(req)
    assert ebay_offers == []

    etsy_offers = await etsy.discover_offers(req)
    assert etsy_offers == []

    amz_offers = await amazon.discover_offers(req)
    assert amz_offers == []
