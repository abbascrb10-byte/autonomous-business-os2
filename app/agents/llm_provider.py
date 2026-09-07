import re
import json
import httpx
from typing import Dict, Any, Optional, Tuple
from app.config.settings import settings
import structlog

logger = structlog.get_logger()

class LLMProvider:
    """
    LLM abstraction supporting Ollama (default local open-weight model), Gemini,
    OpenAI, Anthropic, with a transparent, deterministic fallback path when API credentials/servers are unavailable.
    """

    def __init__(self):
        self.provider = settings.AI_PROVIDER.lower() if settings.AI_PROVIDER else "ollama"
        self._is_configured = False
        self._llm = None

        self._check_and_init_provider()

    def _check_and_init_provider(self):
        if self.provider == "ollama":
            self._is_configured = True
        elif self.provider == "openai" and settings.OPENAI_API_KEY:
            try:
                from langchain_openai import ChatOpenAI
                self._llm = ChatOpenAI(openai_api_key=settings.OPENAI_API_KEY, model="gpt-4o-mini", temperature=0.0)
                self._is_configured = True
            except Exception:
                self._is_configured = False
        elif self.provider == "anthropic" and settings.ANTHROPIC_API_KEY:
            try:
                from langchain_anthropic import ChatAnthropic
                self._llm = ChatAnthropic(anthropic_api_key=settings.ANTHROPIC_API_KEY, model="claude-3-haiku-20240307", temperature=0.0)
                self._is_configured = True
            except Exception:
                self._is_configured = False
        elif self.provider == "gemini" and settings.GEMINI_API_KEY:
            self._is_configured = True
        else:
            self._is_configured = False

    @property
    def is_configured(self) -> bool:
        return self._is_configured

    async def _query_ollama(self, prompt: str) -> Optional[str]:
        try:
            url = f"{settings.OLLAMA_BASE_URL.rstrip('/')}/api/generate"
            payload = {
                "model": settings.OLLAMA_MODEL,
                "prompt": prompt,
                "stream": False,
                "options": {"temperature": 0.0}
            }
            async with httpx.AsyncClient(timeout=10.0) as client:
                res = await client.post(url, json=payload)
                if res.status_code == 200:
                    return res.json().get("response")
        except Exception as e:
            logger.warning("Ollama server unreachable or call failed, falling back to deterministic mode", error=str(e))
        return None

    async def classify_intent(self, text: str) -> Dict[str, Any]:
        """
        Classifies purchase intent using Ollama, Cloud LLM, or deterministic fallback.
        """
        if self.provider == "ollama":
            prompt = (
                "You are a purchase intent classifier. Analyze the text and output valid JSON with keys:\n"
                "- has_intent (bool)\n"
                "- confidence_score (float 0.0 to 1.0)\n"
                "- intent_stage (string: 'ready_to_buy', 'high_intent', 'research', 'unqualified')\n"
                "- rationale (string explaining score based on explicit purchase language, urgency, budget, specs)\n\n"
                f"Text: \"{text}\""
            )
            raw_response = await self._query_ollama(prompt)
            if raw_response:
                json_match = re.search(r"\{.*\}", raw_response, re.DOTALL)
                if json_match:
                    try:
                        data = json.loads(json_match.group(0))
                        data["llm_used"] = True
                        data["provider"] = "ollama"
                        return data
                    except Exception:
                        pass

        elif self.is_configured and self._llm:
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
                    data["provider"] = self.provider
                    return data
            except Exception as e:
                logger.warning("LLM classification failed", provider=self.provider, error=str(e))

        return self._deterministic_classify_intent(text)

    async def extract_product_requirements(self, text: str) -> Dict[str, Any]:
        """
        Extracts structured product requirements using Ollama, Cloud LLM, or deterministic fallback.
        """
        if self.provider == "ollama":
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
            raw_response = await self._query_ollama(prompt)
            if raw_response:
                json_match = re.search(r"\{.*\}", raw_response, re.DOTALL)
                if json_match:
                    try:
                        data = json.loads(json_match.group(0))
                        data["llm_used"] = True
                        data["provider"] = "ollama"
                        return data
                    except Exception:
                        pass

        elif self.is_configured and self._llm:
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
                    data["provider"] = self.provider
                    return data
            except Exception as e:
                logger.warning("LLM extraction failed", provider=self.provider, error=str(e))

        return self._deterministic_extract_requirements(text)

    async def reason_offer_suitability(self, offer_title: str, offer_price: float, requirement: Dict[str, Any]) -> Dict[str, Any]:
        """
        Reasons about offer suitability when deterministic scoring is insufficient.
        """
        return {
            "match_score": self._deterministic_match_score(offer_title, requirement),
            "reasoning": "Deterministic pattern matching evaluation.",
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

        c_matches = re.findall(r"(€|\$|EUR|USD)\s*(\d+(?:[.,]\d+)?)", text, re.IGNORECASE)
        if not c_matches:
            c_matches = re.findall(r"(\d+(?:[.,]\d+)?)\s*(€|\$|EUR|USD|euros|dollars)", text, re.IGNORECASE)
            if c_matches:
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

        condition = "any"
        if re.search(r"\bnew\b", text, re.IGNORECASE):
            condition = "new"
        elif re.search(r"\b(used|second hand)\b", text, re.IGNORECASE):
            condition = "used"
        elif re.search(r"\brefurbished\b", text, re.IGNORECASE):
            condition = "refurbished"

        destination_country = None
        country_match = re.search(r"(?:shipped to|shipping to|in)\s+([A-Z][a-z]+)", text, re.IGNORECASE)
        if country_match:
            destination_country = country_match.group(1).strip()

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
