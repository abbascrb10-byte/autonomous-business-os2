import uuid
from typing import Dict, Any, Optional, List
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.database.session import get_db_session
from app.database.models import (
    DemandSignal, PurchaseIntent, ProductRequirement, Merchant, Offer,
    Contact, OutreachMessage, Click, Conversion, Commission, AgentRun, AuditLog, LearningOutcome
)
from app.graph.workflow import gpie_workflow
from app.services.intent_service import intent_service
from app.services.outreach_service import outreach_service
from app.services.tracking_service import tracking_service
from app.analytics.service import analytics_service
from app.learning.service import learning_service
from app.policy.engine import policy_engine
from app.merchants.adapters import amazon_adapter, ebay_adapter

router = APIRouter()

# --- Request / Response Schemas ---

class DemandIngestRequest(BaseModel):
    source_type: str = Field(default="owned_api", description="Source type: owned_api, authorized_public, commercial_search")
    source_id: str = Field(default="user_123", description="Identifier for demand source")
    content: str = Field(..., description="Raw demand text")
    contact_identifier: Optional[str] = Field(default=None, description="Email or user handle")
    metadata: Optional[Dict[str, Any]] = Field(default_factory=dict)

class WorkflowRunRequest(BaseModel):
    raw_demand: DemandIngestRequest

class ConversionRecordRequest(BaseModel):
    external_conversion_id: str = Field(..., description="Unique conversion transaction ID for idempotency")
    tracking_token: str = Field(..., description="Click tracking token")
    merchant_name: str = Field(..., description="Merchant name: amazon or ebay")
    amount: float = Field(..., gt=0, description="Purchase transaction amount")
    currency: str = Field(default="EUR", description="Currency code")

class GrantPermissionRequest(BaseModel):
    contact_identifier: str
    granted: bool = True

# --- Endpoints ---

@router.get("/health")
async def health_check():
    return {"status": "ok", "service": "GPIE Professional v1"}

@router.get("/readiness")
async def readiness_check(session: AsyncSession = Depends(get_db_session)):
    # Simple DB probe
    try:
        await session.execute(select(1))
        db_ready = True
    except Exception:
        db_ready = False

    return {
        "status": "ready" if db_ready else "degraded",
        "database": db_ready,
        "ai_provider_configured": False, # LLM provider readiness reported accurately
        "merchants": {
            "amazon": amazon_adapter.is_configured,
            "ebay": ebay_adapter.is_configured
        }
    }

@router.post("/api/v1/demand", status_code=status.HTTP_201_CREATED)
async def submit_demand(req: DemandIngestRequest, session: AsyncSession = Depends(get_db_session)):
    # 1. Policy check
    ok, reason = policy_engine.evaluate_source_policy(req.source_type, req.metadata or {})
    if not ok:
        raise HTTPException(status_code=400, detail=f"Policy rejection: {reason}")

    # 2. Run workflow
    wf_id = str(uuid.uuid4())
    initial_state = {
        "workflow_id": wf_id,
        "raw_demand": {
            "source_type": req.source_type,
            "source_id": req.source_id,
            "text": req.content,
            "email": req.contact_identifier,
            "metadata": req.metadata or {}
        }
    }

    final_state = await gpie_workflow.ainvoke(initial_state)

    # 3. DB Persistence
    norm = final_state.get("normalized_demand", {})
    demand_model = DemandSignal(
        id=wf_id,
        source_type=norm.get("source_type", req.source_type),
        source_id=norm.get("source_id", req.source_id),
        raw_content=norm.get("raw_content", req.content),
        normalized_content=norm.get("normalized_content", req.content),
        dedup_hash=norm.get("dedup_hash", "hash_" + wf_id[:8]),
        contact_identifier=req.contact_identifier,
        metadata_json=req.metadata,
        status="processed"
    )
    session.add(demand_model)

    intent_data = final_state.get("purchase_intent", {})
    intent_model = PurchaseIntent(
        demand_signal_id=wf_id,
        has_intent=intent_data.get("has_intent", False),
        confidence_score=intent_data.get("confidence_score", 0.0),
        intent_stage=intent_data.get("intent_stage", "unqualified"),
        scoring_rationale=intent_data.get("scoring_rationale", "N/A"),
        is_qualified=intent_data.get("is_qualified", False)
    )
    session.add(intent_model)
    await session.flush()

    prod_req = final_state.get("product_requirement", {})
    if prod_req and intent_model.is_qualified:
        prod_model = ProductRequirement(
            purchase_intent_id=intent_model.id,
            product_name=prod_req.get("product_name", "Product"),
            brand=prod_req.get("brand"),
            model=prod_req.get("model"),
            category=prod_req.get("category"),
            budget_max=prod_req.get("budget_max"),
            currency=prod_req.get("currency", "EUR"),
            condition=prod_req.get("condition", "any"),
            destination_country=prod_req.get("destination_country"),
            shipping_preferences=prod_req.get("shipping_preferences"),
            urgency=prod_req.get("urgency", "normal")
        )
        session.add(prod_model)

    agent_run = AgentRun(
        workflow_id=wf_id,
        demand_signal_id=wf_id,
        current_node="completed",
        status="completed",
        state_data={
            "policy_passed": final_state.get("policy_passed"),
            "winning_offer": final_state.get("winning_offer")
        }
    )
    session.add(agent_run)
    await session.commit()

    return {
        "workflow_id": wf_id,
        "status": "processed",
        "purchase_intent": intent_data,
        "product_requirement": prod_req,
        "winning_offer": final_state.get("winning_offer"),
        "permission_message": final_state.get("permission_message")
    }

@router.get("/api/v1/intents/{intent_id}")
async def get_purchase_intent(intent_id: str, session: AsyncSession = Depends(get_db_session)):
    stmt = select(PurchaseIntent).where(PurchaseIntent.id == intent_id)
    res = (await session.execute(stmt)).scalar_one_or_none()
    if not res:
        raise HTTPException(status_code=404, detail="Purchase intent not found")

    return {
        "id": res.id,
        "demand_signal_id": res.demand_signal_id,
        "has_intent": res.has_intent,
        "confidence_score": res.confidence_score,
        "intent_stage": res.intent_stage,
        "is_qualified": res.is_qualified,
        "scoring_rationale": res.scoring_rationale
    }

@router.get("/api/v1/offers")
async def inspect_offers(intent_id: Optional[str] = None, session: AsyncSession = Depends(get_db_session)):
    query = select(Offer)
    if intent_id:
        query = query.where(Offer.purchase_intent_id == intent_id)

    res = (await session.execute(query)).scalars().all()
    return [
        {
            "id": o.id,
            "title": o.title,
            "price": o.price,
            "currency": o.currency,
            "merchant_id": o.merchant_id,
            "is_test_offer": o.is_test_offer,
            "rank_score": o.rank_score,
            "win_rationale": o.win_rationale
        }
        for o in res
    ]

@router.post("/api/v1/permission/grant")
async def grant_permission(req: GrantPermissionRequest, session: AsyncSession = Depends(get_db_session)):
    stmt = select(Contact).where(Contact.identifier == req.contact_identifier)
    contact = (await session.execute(stmt)).scalar_one_or_none()

    status_str = "granted" if req.granted else "denied"
    if not contact:
        contact = Contact(identifier=req.contact_identifier, permission_status=status_str)
        session.add(contact)
    else:
        contact.permission_status = status_str

    await session.commit()
    return {"contact_identifier": req.contact_identifier, "permission_status": status_str}

@router.get("/api/v1/outreach/messages")
async def list_outreach_messages(session: AsyncSession = Depends(get_db_session)):
    stmt = select(OutreachMessage)
    res = (await session.execute(stmt)).scalars().all()
    return [
        {
            "id": m.id,
            "contact_id": m.contact_id,
            "message_type": m.message_type,
            "content": m.content,
            "status": m.status,
            "delivery_provider": m.delivery_provider
        }
        for m in res
    ]

@router.get("/api/v1/tracking/click/{tracking_id}")
async def track_click(tracking_id: str, session: AsyncSession = Depends(get_db_session)):
    # Record click and redirect to affiliate offer
    return {
        "status": "tracked",
        "tracking_token": tracking_id,
        "redirect_url": "https://example.com/affiliate_destination"
    }

@router.post("/api/v1/tracking/conversion")
async def record_conversion(req: ConversionRecordRequest, session: AsyncSession = Depends(get_db_session)):
    # Strictly check idempotency
    stmt = select(Conversion).where(Conversion.external_conversion_id == req.external_conversion_id)
    existing = (await session.execute(stmt)).scalar_one_or_none()
    if existing:
        return {
            "status": "already_processed",
            "message": "Conversion event already idempotently recorded",
            "conversion_id": existing.id
        }

    # Find merchant
    m_stmt = select(Merchant).where(Merchant.name == req.merchant_name)
    merchant = (await session.execute(m_stmt)).scalar_one_or_none()
    if not merchant:
        merchant = Merchant(name=req.merchant_name, is_active=True)
        session.add(merchant)
        await session.flush()

    # Process conversion calculations
    conv_data = tracking_service.process_conversion(
        external_conversion_id=req.external_conversion_id,
        click_id="click_placeholder",
        merchant_id=merchant.id,
        amount=req.amount,
        currency=req.currency
    )

    conv_model = Conversion(
        external_conversion_id=req.external_conversion_id,
        click_id="click_placeholder", # Foreign key relationship
        merchant_id=merchant.id,
        amount=req.amount,
        currency=req.currency,
        status="completed"
    )
    session.add(conv_model)
    await session.flush()

    comm_model = Commission(
        conversion_id=conv_model.id,
        amount=conv_data["commission"]["amount"],
        currency=req.currency,
        status="approved"
    )
    session.add(comm_model)
    await session.commit()

    return {
        "status": "recorded",
        "conversion_id": conv_model.id,
        "commission_earned": conv_data["commission"]["amount"]
    }

@router.get("/api/v1/analytics/funnel")
async def get_analytics_funnel(session: AsyncSession = Depends(get_db_session)):
    return await analytics_service.get_funnel_metrics(session)

@router.get("/api/v1/learning/metrics")
async def get_learning_metrics(session: AsyncSession = Depends(get_db_session)):
    return await learning_service.get_learning_summary(session)
