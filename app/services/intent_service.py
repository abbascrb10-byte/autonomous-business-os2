from typing import Dict, Any, Tuple, Optional
from app.agents.llm_provider import llm_provider
import structlog

logger = structlog.get_logger()

class IntentService:
    """
    Service for analyzing purchase intent and extracting normalized product requirements.
    Uses transparent scoring and qualification rules.
    """

    def __init__(self, qualification_threshold: float = 0.50):
        self.qualification_threshold = qualification_threshold

    async def analyze_and_extract(self, text: str) -> Dict[str, Any]:
        """
        Analyzes demand text to detect purchase intent and extract product requirements.
        Returns a dictionary containing intent classification and product extraction.
        """
        # 1. Purchase Intent Classification
        intent_res = await llm_provider.classify_intent(text)

        confidence_score = float(intent_res.get("confidence_score", 0.0))
        has_intent = bool(intent_res.get("has_intent", False))
        intent_stage = intent_res.get("intent_stage", "unqualified")
        rationale = intent_res.get("rationale", "No rationale provided")
        is_qualified = has_intent and confidence_score >= self.qualification_threshold

        # 2. Product Requirement Extraction if intent qualified
        requirement_res = None
        if is_qualified or has_intent:
            requirement_res = await llm_provider.extract_product_requirements(text)

        return {
            "has_intent": has_intent,
            "confidence_score": confidence_score,
            "intent_stage": intent_stage,
            "scoring_rationale": rationale,
            "is_qualified": is_qualified,
            "product_requirement": requirement_res,
            "llm_used": intent_res.get("llm_used", False) or (requirement_res.get("llm_used", False) if requirement_res else False)
        }

intent_service = IntentService()
