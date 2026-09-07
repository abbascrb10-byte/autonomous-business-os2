from typing import Dict, Any, List
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from app.database.session import get_db_session
from app.database.models import DemandSignal, PurchaseIntent, Offer, OutreachMessage, Conversion, Commission, AgentRun, LearningOutcome, SourceWeight
from app.learning.service import learning_service

router = APIRouter()

@router.get("/api/v1/dashboard/stats")
async def get_dashboard_stats(session: AsyncSession = Depends(get_db_session)):
    """
    Exposes real system health, demand signals, purchase intents, offers, conversions,
    commissions, and learning metrics for the frontend dashboard.
    """
    total_signals = (await session.execute(select(func.count(DemandSignal.id)))).scalar() or 0
    total_intents = (await session.execute(select(func.count(PurchaseIntent.id)))).scalar() or 0
    qualified_intents = (await session.execute(select(func.count(PurchaseIntent.id)).where(PurchaseIntent.is_qualified == True))).scalar() or 0
    total_offers = (await session.execute(select(func.count(Offer.id)))).scalar() or 0
    total_conversions = (await session.execute(select(func.count(Conversion.id)))).scalar() or 0
    total_revenue = (await session.execute(select(func.sum(Conversion.amount)))).scalar() or 0.0
    total_commissions = (await session.execute(select(func.sum(Commission.amount)))).scalar() or 0.0

    learning_summary = await learning_service.get_learning_summary(session)

    weights_stmt = select(SourceWeight)
    weights = (await session.execute(weights_stmt)).scalars().all()
    source_weights_map = {w.source_name: {"weight": w.weight, "conversion_rate": w.conversion_rate} for w in weights}

    return {
        "overview": {
            "demand_signals": total_signals,
            "purchase_intents": total_intents,
            "qualified_intents": qualified_intents,
            "offers_discovered": total_offers,
            "conversions": total_conversions,
            "gross_revenue": round(total_revenue, 2),
            "commissions": round(total_commissions, 2)
        },
        "learning": learning_summary,
        "source_weights": source_weights_map
    }
