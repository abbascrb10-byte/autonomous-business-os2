from typing import Dict, Any, Optional

class CurrencyService:
    """
    Currency normalization and total cost calculation layer.
    Converts amounts between currencies and calculates total cost (item price + shipping + fees).
    """

    FX_RATES_TO_EUR = {
        "EUR": 1.0,
        "USD": 0.92,
        "GBP": 1.17,
        "CAD": 0.68,
        "AUD": 0.60
    }

    def normalize_to_eur(self, amount: float, currency: str) -> float:
        curr_u = (currency or "EUR").upper()
        rate = self.FX_RATES_TO_EUR.get(curr_u, 1.0)
        return round(amount * rate, 2)

    def calculate_total_cost(self, price: float, shipping_cost: Optional[float] = 0.0, mandatory_fees: Optional[float] = 0.0) -> float:
        p = price or 0.0
        s = shipping_cost or 0.0
        f = mandatory_fees or 0.0
        return round(p + s + f, 2)

currency_service = CurrencyService()
