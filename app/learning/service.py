from typing import Dict, Any, List
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from app.database.models import LearningOutcome, DemandSignal, PurchaseIntent, Click, Conversion, SourceWeight

class LearningService:
    """
    Feedback loop recording recommendation outcomes (clicks, conversions, rejections)
    and dynamically optimizing source weights and merchant preferences based on conversion rates.
    """

    def calculate_score_adjustment(self, event_type: str) -> float:
        adjustments = {
            "permission_granted": 0.10,
            "permission_denied": -0.20,
            "click": 0.15,
            "conversion": 0.50,
            "rejection": -0.30
        }
        return adjustments.get(event_type.lower(), 0.0)

    async def optimize_source_weights(self, session: AsyncSession) -> Dict[str, float]:
        """
        Dynamically adjusts source weights based on actual conversion rates.
        High conversion sources gain higher weights.
        """
        stmt = (
            select(
                DemandSignal.source_type,
                func.count(DemandSignal.id).label("total_signals"),
                func.count(Conversion.id).label("total_conversions")
            )
            .join(PurchaseIntent, DemandSignal.id == PurchaseIntent.demand_signal_id)
            .join(Click, PurchaseIntent.id == Click.purchase_intent_id, isouter=True)
            .join(Conversion, Click.id == Conversion.click_id, isouter=True)
            .group_by(DemandSignal.source_type)
        )
        results = await session.execute(stmt)

        new_weights = {}
        for row in results:
            source = row.source_type
            total = row.total_signals or 1
            conversions = row.total_conversions or 0
            conversion_rate = conversions / total

            target_rate = 0.05
            if conversion_rate > target_rate:
                weight = min(2.0, round(1.0 + (conversion_rate - target_rate) * 10, 2))
            else:
                weight = max(0.1, round(1.0 - (target_rate - conversion_rate) * 5, 2))

            new_weights[source] = weight

            sw_stmt = select(SourceWeight).where(SourceWeight.source_name == source)
            sw_model = (await session.execute(sw_stmt)).scalar_one_or_none()
            if not sw_model:
                sw_model = SourceWeight(
                    source_name=source,
                    weight=weight,
                    conversion_rate=round(conversion_rate, 4),
                    signals_count=total,
                    conversions_count=conversions
                )
                session.add(sw_model)
            else:
                sw_model.weight = weight
                sw_model.conversion_rate = round(conversion_rate, 4)
                sw_model.signals_count = total
                sw_model.conversions_count = conversions

        await session.commit()
        return new_weights

    async def get_learning_summary(self, session: AsyncSession) -> Dict[str, Any]:
        total_outcomes = (await session.execute(select(func.count(LearningOutcome.id)))).scalar() or 0
        total_delta = (await session.execute(select(func.sum(LearningOutcome.score_delta)))).scalar() or 0.0

        return {
            "total_learning_events": total_outcomes,
            "cumulative_score_delta": round(total_delta, 2),
            "status": "active_feedback_loop"
        }

learning_service = LearningService()
