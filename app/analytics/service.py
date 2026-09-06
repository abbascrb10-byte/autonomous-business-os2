from typing import Dict, Any, List
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from app.database.models import DemandSignal, PurchaseIntent, Offer, OutreachMessage, Click, Conversion, Commission

class AnalyticsService:
    """
    Computes real-time funnel metrics and business insights across the GPIE workflow.
    """

    async def get_funnel_metrics(self, session: AsyncSession) -> Dict[str, Any]:
        demand_count = (await session.execute(select(func.count(DemandSignal.id)))).scalar() or 0
        intent_count = (await session.execute(select(func.count(PurchaseIntent.id)))).scalar() or 0
        qualified_intent_count = (await session.execute(select(func.count(PurchaseIntent.id)).where(PurchaseIntent.is_qualified == True))).scalar() or 0
        offers_count = (await session.execute(select(func.count(Offer.id)))).scalar() or 0
        outreach_count = (await session.execute(select(func.count(OutreachMessage.id)))).scalar() or 0
        clicks_count = (await session.execute(select(func.count(Click.id)))).scalar() or 0
        conversions_count = (await session.execute(select(func.count(Conversion.id)))).scalar() or 0
        total_revenue = (await session.execute(select(func.sum(Conversion.amount)))).scalar() or 0.0
        total_commissions = (await session.execute(select(func.sum(Commission.amount)))).scalar() or 0.0

        conversion_rate = round((conversions_count / clicks_count * 100), 2) if clicks_count > 0 else 0.0
        qualification_rate = round((qualified_intent_count / intent_count * 100), 2) if intent_count > 0 else 0.0

        return {
            "demand_signals_total": demand_count,
            "intents_total": intent_count,
            "qualified_intents_total": qualified_intent_count,
            "qualification_rate_pct": qualification_rate,
            "offers_discovered_total": offers_count,
            "outreach_messages_total": outreach_count,
            "clicks_total": clicks_count,
            "conversions_total": conversions_count,
            "conversion_rate_pct": conversion_rate,
            "total_gross_revenue": round(total_revenue, 2),
            "total_commissions_earned": round(total_commissions, 2),
            "currency": "EUR"
        }

analytics_service = AnalyticsService()
