import re
import json
from typing import Dict, Any, Optional, Tuple
from app.config.settings import settings
import structlog

logger = structlog.get_logger()

class LLMProvider:
    """
    Clean abstraction for LLM-based intelligence supporting OpenAI, Anthropic, Gemini,
    with a transparent, deterministic fallback path when API credentials are missing.
    """

    def __init__(self):
        self.provider = settings.AI_PROVIDER.lower() if settings.AI_PROVIDER else "mock"
        self.api_key = self._get_api_key()
        self._is_configured = bool(self.api_key and self.provider != "mock")
        self._llm = None

        if self._is_configured:
            try:
                if self.provider == "openai":
                    from langchain_openai import ChatOpenAI
                    self._llm = ChatOpenAI(openai_api_key=self.api_key, model="gpt-4o-mini", temperature=0.0)
                elif self.provider == "anthropic":
                    from langchain_anthropic import ChatAnthropic
                    self._llm = ChatAnthropic(anthropic_api_key=self.api_key, model="claude-3-haiku-20240307", temperature=0.0)
                else:
                    logger.warning("Unsupported LLM provider or missing library, falling back to deterministic mode", provider=self.provider)
                    self._is_configured = False
            except Exception as e:
                logger.error("Failed to initialize LLM provider, falling back to deterministic mode", error=str(e))
                self._is_configured = False

    def _get_api_key(self) -> Optional[str]:
        if self.provider == "openai":
            return settings.OPENAI_API_KEY
        elif self.provider == "anthropic":
            return settings.ANTHROPIC_API_KEY
        elif self.provider == "gemini":
            return settings.GEMINI_API_KEY
        return None

    @property
    def is_configured(self) -> bool:
        return self._is_configured

    async def classify_intent(self, text: str) -> Dict[str, Any]:
        """
        Classifies purchase intent. Returns structured dict with has_intent, score, stage, rationale, llm_used.
        """
        if self.is_configured and self._llm:
            try:
                prompt = (
                    "You are a purchase intent classifier. Analyze the text and output valid JSON with keys:\n"
                    "- has_intent (bool)\n"
                    "- confidence_score (float 0.0 to 1.0)\n"
                    "- intent_stage (string: 'ready_to_buy', 'high_intent', 'research', 'unqualified')\n"
                    "- rationale (string explaining score based on explicit purchase language, urgency, budget, specs)\n\n"
                    f"Text: \"{text}\""
                )
                response = await self._llm.ainvoke(prompt)
                content = response.content if hasattr(response, "content") else str(response)
                json_match = re.search(r"\{.*\}", content, re.DOTALL)
                if json_match:
                    data = json.loads(json_match.group(0))
                    data["llm_used"] = True
                    return data
            except Exception as e:
                logger.warning("LLM classification failed, falling back to deterministic classifier", error=str(e))

        return self._deterministic_classify_intent(text)

    async def extract_product_requirements(self, text: str) -> Dict[str, Any]:
        """
        Extracts structured product requirements from text.
        """
        if self.is_configured and self._llm:
            try:
                prompt = (
                    "You are a product requirement extractor. Extract structured parameters from the input text and output valid JSON with keys:\n"
                    "- product_name (string)\n"
                    "- brand (string or null)\n"
                    "- model (string or null)\n"
                    "- category (string or null)\n"
                    "- budget_max (float or null)\n"
                    "- currency (string e.g. EUR, USD)\n"
                    "- condition (string e.g. new, used, refurbished, any)\n"
                    "- destination_country (string or null)\n"
                    "- shipping_preferences (string or null)\n"
                    "- specifications (object/dict or null)\n"
                    "- urgency (string e.g. immediate, high, normal, low)\n\n"
                    f"Input: \"{text}\""
                )
                response = await self._llm.ainvoke(prompt)
                content = response.content if hasattr(response, "content") else str(response)
                json_match = re.search(r"\{.*\}", content, re.DOTALL)
                if json_match:
                    data = json.loads(json_match.group(0))
                    data["llm_used"] = True
                    return data
            except Exception as e:
                logger.warning("LLM extraction failed, falling back to deterministic extractor", error=str(e))

        return self._deterministic_extract_requirements(text)

    async def reason_offer_suitability(self, offer_title: str, offer_price: float, requirement: Dict[str, Any]) -> Dict[str, Any]:
        """
        Reasons about offer suitability when deterministic scoring is insufficient.
        """
        if self.is_configured and self._llm:
            try:
                prompt = (
                    "Evaluate if this offer matches the buyer requirement. Output valid JSON with keys:\n"
                    "- match_score (float 0.0 to 1.0)\n"
                    "- reasoning (string)\n\n"
                    f"Requirement: {json.dumps(requirement)}\n"
                    f"Offer Title: {offer_title}, Price: {offer_price}\n"
                )
                response = await self._llm.ainvoke(prompt)
                content = response.content if hasattr(response, "content") else str(response)
                json_match = re.search(r"\{.*\}", content, re.DOTALL)
                if json_match:
                    data = json.loads(json_match.group(0))
                    data["llm_used"] = True
                    return data
            except Exception as e:
                logger.warning("LLM offer reasoning failed, using deterministic evaluation", error=str(e))

        return {
            "match_score": self._deterministic_match_score(offer_title, requirement),
            "reasoning": "Deterministic pattern matching evaluation (LLM not used/configured).",
            "llm_used": False
        }

    def _deterministic_classify_intent(self, text: str) -> Dict[str, Any]:
        text_lower = text.lower()
        purchase_keywords = ["buy", "need", "looking for", "want to purchase", "price", "under", "where to buy", "order", "shipped to", "budget"]
        urgency_keywords = ["immediately", "asap", "today", "now", "urgent"]

        match_count = sum(1 for kw in purchase_keywords if kw in text_lower)
        has_urgency = any(kw in text_lower for kw in urgency_keywords)

        if match_count >= 3 or (match_count >= 1 and re.search(r"(under|<|€|\$|EUR|USD|\d+\s*euro)", text_lower)):
            has_intent = True
            score = min(0.95, 0.60 + (match_count * 0.10) + (0.10 if has_urgency else 0.0))
            stage = "ready_to_buy" if score >= 0.8 else "high_intent"
            rationale = f"Deterministic rule: detected {match_count} purchase indicators (e.g., budget/explicit buy terms)."
        elif match_count >= 1:
            has_intent = True
            score = 0.55
            stage = "research"
            rationale = "Deterministic rule: detected mild commercial research intent."
        else:
            has_intent = False
            score = 0.15
            stage = "unqualified"
            rationale = "Deterministic rule: no purchase intent keywords detected."

        return {
            "has_intent": has_intent,
            "confidence_score": score,
            "intent_stage": stage,
            "rationale": rationale,
            "llm_used": False
        }

    def _deterministic_extract_requirements(self, text: str) -> Dict[str, Any]:
        budget_max = None
        currency = "EUR"

        # Explicit regex searching for currency symbol + amount or amount + currency code/name
        # e.g., "under €1800", "$1500", "1800 EUR", "1500 USD"
        c_matches = re.findall(r"(€|\$|EUR|USD)\s*(\d+(?:[.,]\d+)?)", text, re.IGNORECASE)
        if not c_matches:
            c_matches = re.findall(r"(\d+(?:[.,]\d+)?)\s*(€|\$|EUR|USD|euros|dollars)", text, re.IGNORECASE)
            if c_matches:
                # Group 1 is number, Group 2 is symbol/currency
                for num_str, sym in c_matches:
                    try:
                        val = float(num_str.replace(",", "."))
                        if val >= 10:
                            budget_max = val
                            sym_u = sym.upper()
                            if "$" in sym_u or "USD" in sym_u or "DOLLAR" in sym_u:
                                currency = "USD"
                            elif "€" in sym_u or "EUR" in sym_u or "EURO" in sym_u:
                                currency = "EUR"
                            break
                    except Exception:
                        pass
        else:
            # Group 1 is symbol, Group 2 is number
            for sym, num_str in c_matches:
                try:
                    val = float(num_str.replace(",", "."))
                    if val >= 10:
                        budget_max = val
                        sym_u = sym.upper()
                        if "$" in sym_u or "USD" in sym_u:
                            currency = "USD"
                        elif "€" in sym_u or "EUR" in sym_u:
                            currency = "EUR"
                        break
                except Exception:
                    pass

        # Extract condition
        condition = "any"
        if re.search(r"\bnew\b", text, re.IGNORECASE):
            condition = "new"
        elif re.search(r"\b(used|second hand)\b", text, re.IGNORECASE):
            condition = "used"
        elif re.search(r"\brefurbished\b", text, re.IGNORECASE):
            condition = "refurbished"

        # Extract country
        destination_country = None
        country_match = re.search(r"(?:shipped to|shipping to|in)\s+([A-Z][a-z]+)", text, re.IGNORECASE)
        if country_match:
            destination_country = country_match.group(1).strip()

        # Clean product query
        cleaned_product = text
        remove_patterns = [
            r"i (?:need|want|am looking for) (?:a|an)?",
            r"looking to buy (?:a|an)?",
            r"under\s*(?:€|\$|EUR|USD)?\s*\d+",
            r"for\s*(?:€|\$|EUR|USD)?\s*\d+",
            r"preferably\s+\w+",
            r"shipped to\s+[A-Za-z\s]+",
            r"shipping to\s+[A-Za-z\s]+",
            r"immediately|asap|today"
        ]
        for pat in remove_patterns:
            cleaned_product = re.sub(pat, "", cleaned_product, flags=re.IGNORECASE)

        cleaned_product = cleaned_product.strip(" .,!?")
        if not cleaned_product:
            cleaned_product = text.strip()

        # Extract brand heuristics
        brand = None
        known_brands = ["Sony", "Canon", "Nikon", "Apple", "Samsung", "Dell", "Lenovo", "Bose", "LG", "ASUS"]
        for b in known_brands:
            if re.search(r"\b" + b + r"\b", text, re.IGNORECASE):
                brand = b
                break

        category = "electronics"

        return {
            "product_name": cleaned_product,
            "brand": brand,
            "model": None,
            "category": category,
            "budget_max": budget_max,
            "currency": currency,
            "condition": condition,
            "destination_country": destination_country,
            "shipping_preferences": None,
            "specifications": {},
            "urgency": "normal",
            "llm_used": False
        }

    def _deterministic_match_score(self, offer_title: str, requirement: Dict[str, Any]) -> float:
        product_req = (requirement.get("product_name") or "").lower()
        title_lower = offer_title.lower()

        if not product_req:
            return 0.5

        tokens = [t for t in product_req.split() if len(t) > 2]
        if not tokens:
            return 0.5

        matches = sum(1 for t in tokens if t in title_lower)
        return min(1.0, round(matches / len(tokens), 2))

llm_provider = LLMProvider()
