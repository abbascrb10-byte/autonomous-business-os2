import pytest
from app.services.outreach_service import outreach_service
from app.services.tracking_service import tracking_service
from app.learning.service import learning_service

def test_outreach_permission_and_recommendation():
    # Permission request message
    perm_msg = outreach_service.generate_permission_request("user@example.com", "Sony A7 IV")
    assert perm_msg["message_type"] == "permission_request"
    assert perm_msg["status"] == "awaiting_approval"
    assert "Would you like me to send you the link?" in perm_msg["content"]

    # Recommendation message
    offer = {"title": "Sony A7 IV Body", "price": 1750.0, "currency": "EUR"}
    rec_msg = outreach_service.generate_recommendation_message("user@example.com", offer, "http://localhost/click/123")
    assert rec_msg["message_type"] == "recommendation"
    assert "http://localhost/click/123" in rec_msg["content"]

def test_tracking_and_conversion_calculation():
    token = tracking_service.generate_click_token("offer_1", "intent_1")
    assert len(token) > 10

    url = tracking_service.generate_tracking_url(token)
    assert url.endswith(token)

    conversion = tracking_service.process_conversion("CONV-100", "click_1", "merchant_amz", 1000.0, "EUR")
    assert conversion["external_conversion_id"] == "CONV-100"
    assert conversion["amount"] == 1000.0
    assert conversion["commission"]["amount"] == 40.0 # 4% of 1000

def test_learning_score_delta():
    assert learning_service.calculate_score_adjustment("conversion") == 0.50
    assert learning_service.calculate_score_adjustment("permission_denied") == -0.20
