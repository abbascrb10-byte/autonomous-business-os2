import pytest
from app.services.ranking_service import RankingService, ranking_service
from app.policy.engine import PolicyEngine, policy_engine

@pytest.mark.asyncio
async def test_ranking_service_verification_and_ranking():
    service = RankingService()

    requirement = {
        "product_name": "Sony A7 IV",
        "budget_max": 1800.0,
        "currency": "EUR"
    }

    offers = [
        {
            "merchant_name": "amazon",
            "title": "Sony Alpha 7 IV Full-frame Mirrorless Camera Body",
            "price": 1750.0,
            "currency": "EUR",
            "availability": True,
            "seller_name": "Amazon Retail Verified",
            "url": "https://amazon.com/dp/123"
        },
        {
            "merchant_name": "ebay",
            "title": "Sony A7 IV Body Only Brand New",
            "price": 1650.0,
            "currency": "EUR",
            "availability": True,
            "seller_name": "TopRatedSeller",
            "url": "https://ebay.com/itm/456"
        },
        {
            "merchant_name": "unknown",
            "title": "Sony Camera Overpriced",
            "price": 2500.0, # Exceeds budget max
            "currency": "EUR",
            "availability": True,
            "seller_name": "Unknown Seller",
            "url": "https://example.com/789"
        }
    ]

    # Verify eligibility
    v1, msg1 = service.verify_offer(offers[0], requirement)
    assert v1 is True

    v3, msg3 = service.verify_offer(offers[2], requirement)
    assert v3 is False
    assert "exceeds budget max" in msg3

    # Rank eligible offers
    eligible = [offers[0], offers[1]]
    ranked = await service.rank_offers(eligible, requirement)

    assert len(ranked) == 2
    assert ranked[0]["rank_score"] > 0.0
    assert "win_rationale" in ranked[0]
    # Check that highest ranked offer comes first
    assert ranked[0]["rank_score"] >= ranked[1]["rank_score"]

def test_policy_engine_rules():
    policy = PolicyEngine()

    # Source policy
    ok, msg = policy.evaluate_source_policy("owned_api", {})
    assert ok is True

    bad_source, msg2 = policy.evaluate_source_policy("unauthorized_scraper", {})
    assert bad_source is False

    # Anti-spam permission policy
    # Unsolicited recommendation without permission MUST be blocked
    rec_blocked, msg3 = policy.evaluate_outreach_policy("user@example.com", "pending", "recommendation")
    assert rec_blocked is False
    assert "requires explicit permission" in msg3

    # First-contact permission request MUST be allowed
    perm_ok, msg4 = policy.evaluate_outreach_policy("user@example.com", "pending", "permission_request")
    assert perm_ok is True

    # Recommendation with granted permission MUST be allowed
    rec_ok, msg5 = policy.evaluate_outreach_policy("user@example.com", "granted", "recommendation")
    assert rec_ok is True
