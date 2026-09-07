import hashlib
from typing import Dict, Any, Tuple, Optional, List
from rapidfuzz import fuzz
from app.agents.llm_provider import llm_provider
import structlog

logger = structlog.get_logger()

class IntentService:
    """
    Service for analyzing purchase intent, extracting normalized product requirements,
    and evaluating exact and fuzzy deduplication.
    """

    def __init__(self, qualification_threshold: float = 0.50):
        self.qualification_threshold = qualification_threshold

    def is_duplicate(self, new_text: str, existing_texts: List[str], fuzzy_threshold: float = 85.0) -> bool:
        """
        Multi-layered deduplication check:
        1. Exact SHA256 match
        2. Fuzzy similarity match (RapidFuzz ratio > 85%)
        """
        new_text_clean = new_text.strip().lower()
        new_hash = hashlib.sha256(new_text_clean.encode('utf-8')).hexdigest()

        for existing in existing_texts:
            existing_clean = existing.strip().lower()
            existing_hash = hashlib.sha256(existing_clean.encode('utf-8')).hexdigest()

            # 1. SHA256 Exact Match
            if new_hash == existing_hash:
                return True

            # 2. RapidFuzz Fuzzy Match
            if fuzz.ratio(new_text_clean, existing_clean) >= fuzzy_threshold:
                return True

        return False

    async def analyze_and_extract(self, text: str) -> Dict[str, Any]:
        """
        Analyzes demand text to detect purchase intent and extract product requirements.
        """
        intent_res = await llm_provider.classify_intent(text)

        confidence_score = float(intent_res.get("confidence_score", 0.0))
        has_intent = bool(intent_res.get("has_intent", False))
        intent_stage = intent_res.get("intent_stage", "unqualified")
        rationale = intent_res.get("rationale", "No rationale provided")
        is_qualified = has_intent and confidence_score >= self.qualification_threshold

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
