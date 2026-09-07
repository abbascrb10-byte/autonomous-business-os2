import pytest
from app.agents.llm_provider import LLMProvider, llm_provider
from app.services.intent_service import IntentService, intent_service

class MalformedLLMClient:
    async def classify_intent(self, text):
        return {"has_intent": "yes", "confidence_score": 4.0, "intent_stage": "unknown", "rationale": 7}

    async def extract_product_requirements(self, text):
        return {"product_name": "camera", "currency": "EUR"}

@pytest.mark.asyncio
async def test_llm_provider_fallback_classification():
    # Test deterministic classification when no LLM API key is present
    text = "I need a Sony A7 IV body under €1800, preferably new, shipped to France."
    res = await llm_provider.classify_intent(text)

    assert "has_intent" in res
    assert res["has_intent"] is True
    assert res["confidence_score"] >= 0.5
    assert "ready_to_buy" in res["intent_stage"] or "high_intent" in res["intent_stage"]
    assert "Deterministic" in res["rationale"] or "LLM" in res["rationale"]

@pytest.mark.asyncio
async def test_llm_provider_fallback_requirement_extraction():
    text = "I need a Sony A7 IV body under €1800, preferably new, shipped to France."
    res = await llm_provider.extract_product_requirements(text)

    assert res["budget_max"] == 1800.0
    assert res["currency"] == "EUR"
    assert res["condition"] == "new"
    assert res["destination_country"] == "France"
    assert "Sony" in (res["brand"] or res["product_name"])

@pytest.mark.asyncio
async def test_intent_service_qualification():
    service = IntentService(qualification_threshold=0.5)

    # Qualified intent example
    text_qualified = "Looking to buy a Dell XPS 15 laptop for under $1500 immediately"
    res_q = await service.analyze_and_extract(text_qualified)

    assert res_q["has_intent"] is True
    assert res_q["is_qualified"] is True
    assert res_q["confidence_score"] >= 0.5
    assert res_q["product_requirement"] is not None
    assert res_q["product_requirement"]["budget_max"] == 1500.0

    # Unqualified text example
    text_unqualified = "Good morning everyone, how are you today?"
    res_unq = await service.analyze_and_extract(text_unqualified)

    assert res_unq["has_intent"] is False
    assert res_unq["is_qualified"] is False
    assert res_unq["confidence_score"] < 0.5

@pytest.mark.asyncio
async def test_invalid_llm_output_uses_explicit_fallback_status():
    provider = LLMProvider()
    provider._client = MalformedLLMClient()

    intent = await provider.classify_intent("I need a camera under 1000 EUR")
    requirements = await provider.extract_product_requirements("I need a camera under 1000 EUR")

    assert intent["llm_status"] == "FALLBACK_USED"
    assert intent["llm_error"] == "INVALID_LLM_OUTPUT"
    assert requirements["llm_status"] == "FALLBACK_USED"
    assert requirements["llm_error"] == "INVALID_LLM_OUTPUT"
