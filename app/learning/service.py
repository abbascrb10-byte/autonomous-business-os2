from typing import Dict, Any, List
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from app.database.models import LearningOutcome

class LearningService:
    """
    Feedback loop recording recommendation outcomes (clicks, conversions, rejections)
    and calculating metrics to optimize future offer ranking or merchant preferences.
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

    async def get_learning_summary(self, session: AsyncSession) -> Dict[str, Any]:
        total_outcomes = (await session.execute(select(func.count(LearningOutcome.id)))).scalar() or 0
        total_delta = (await session.execute(select(func.sum(LearningOutcome.score_delta)))).scalar() or 0.0

        return {
            "total_learning_events": total_outcomes,
            "cumulative_score_delta": round(total_delta, 2),
            "status": "active_feedback_loop"
        }

learning_service = LearningService()
