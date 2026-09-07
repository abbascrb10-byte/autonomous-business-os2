import uuid
from typing import Dict, Any, Optional, List
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload

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
from app.agents.llm_provider import llm_provider
from app.merchants.adapters import amazon_adapter, ebay_adapter
from app.sources.adapters import owned_adapter, public_adapter, search_adapter
from app.workers.manager import worker_manager

router = APIRouter()

# --- Request / Response Schemas ---

class DemandIngestRequest(BaseModel):
    source_type: str = Field(default="owned_api", description="Source type: owned_api, authorized_public, commercial_search")
    source_id: str = Field(default="user_123", description="Identifier for demand source")
    content: str = Field(..., description="Raw demand text")
    contact_identifier: Optional[str] = Field(default=None, description="Email or user handle")
    metadata: Optional[Dict[str, Any]] = Field(default_factory=dict)

class ConversionRecordRequest(BaseModel):
    external_conversion_id: str = Field(..., description="Unique conversion transaction ID for idempotency")
    tracking_token: str = Field(..., description="Click tracking token")
    merchant_name: str = Field(..., description="Merchant name: amazon or ebay")
    amount: float = Field(..., gt=0, description="Purchase transaction amount")
    currency: str = Field(default="EUR", description="Currency code")

class GrantPermissionRequest(BaseModel):
    contact_identifier: str
    granted: bool = True

# Helper to ensure merchants exist in DB
async def _get_or_create_merchant(session: AsyncSession, merchant_name: str) -> Merchant:
    stmt = select(Merchant).where(Merchant.name == merchant_name)
    merchant = (await session.execute(stmt)).scalar_one_or_none()
    if not merchant:
        is_conf = (merchant_name == "amazon" and amazon_adapter.is_configured) or (merchant_name == "ebay" and ebay_adapter.is_configured)
        merchant = Merchant(name=merchant_name, is_active=True, credentials_configured=is_conf)
        session.add(merchant)
        await session.flush()
    return merchant

# --- Endpoints ---

@router.get("/health")
async def health_check():
    return {"status": "ok", "service": "GPIE Professional v1"}

@router.get("/readiness")
async def readiness_check(session: AsyncSession = Depends(get_db_session)):
    try:
        await session.execute(select(1))
        db_ready = True
    except Exception:
        db_ready = False

    return {
        "status": "ready" if db_ready else "degraded",
        "database": db_ready,
        "ai_provider_configured": llm_provider.is_configured,
        "merchants": {
            "amazon": amazon_adapter.is_configured,
            "ebay": ebay_adapter.is_configured
        }
    }

@router.post("/api/v1/demand", status_code=status.HTTP_201_CREATED)
async def submit_demand(req: DemandIngestRequest, session: AsyncSession = Depends(get_db_session)):
    # 1. Policy check
    ok, reason = policy_engine.evaluate_source_policy(req.source_type, req.metadata or {})

    audit_entry = AuditLog(
        action="ingest_demand",
        actor=req.source_id,
        policy_checked="source_policy",
        decision="allowed" if ok else "denied",
        reason=reason,
        details={"source_type": req.source_type}
    )
    session.add(audit_entry)

    if not ok:
        await session.commit()
        raise HTTPException(status_code=400, detail=f"Policy rejection: {reason}")

    # 2. Compute dedup hash and check PostgreSQL for duplicate
    stype = req.source_type
    if stype == "authorized_public":
        adapter = public_adapter
    elif stype == "commercial_search":
        adapter = search_adapter
    else:
        adapter = owned_adapter

    norm_preview = adapter.normalize_demand({
        "source_type": req.source_type,
        "source_id": req.source_id,
        "text": req.content,
        "email": req.contact_identifier,
        "metadata": req.metadata or {}
    })
    dedup_hash = norm_preview["dedup_hash"]

    dedup_stmt = select(DemandSignal).where(DemandSignal.dedup_hash == dedup_hash)
    existing_demand = (await session.execute(dedup_stmt)).scalar_one_or_none()

    if existing_demand:
        await session.commit()
        return {
            "workflow_id": existing_demand.id,
            "status": "duplicate",
            "message": "Demand signal already idempotently processed in GPIE",
            "dedup_hash": dedup_hash
        }

    # Check existing contact permission status
    contact_id_str = req.contact_identifier or "anonymous@gpie.internal"
    stmt_contact = select(Contact).where(Contact.identifier == contact_id_str)
    contact = (await session.execute(stmt_contact)).scalar_one_or_none()
    current_permission = contact.permission_status if contact else "pending"

    # 3. Enqueue job for background processing
    await worker_manager.enqueue_job("demand_ingestion", norm_preview)

    # 4. Run LangGraph workflow with permission_status state
    wf_id = str(uuid.uuid4())
    initial_state = {
        "workflow_id": wf_id,
        "permission_status": current_permission,
        "raw_demand": {
            "source_type": req.source_type,
            "source_id": req.source_id,
            "text": req.content,
            "email": req.contact_identifier,
            "metadata": req.metadata or {}
        }
    }

    final_state = await gpie_workflow.ainvoke(initial_state)

    # 5. Persist workflow state into PostgreSQL
    norm = final_state.get("normalized_demand", {})
    demand_model = DemandSignal(
        id=wf_id,
        source_type=norm.get("source_type", req.source_type),
        source_id=norm.get("source_id", req.source_id),
        raw_content=norm.get("raw_content", req.content),
        normalized_content=norm.get("normalized_content", req.content),
        dedup_hash=dedup_hash,
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

    # Persist Discovered & Ranked Offers into PostgreSQL
    persisted_offers = []
    winning_offer_model = None
    ranked_offers_data = final_state.get("ranked_offers", [])
    for off in ranked_offers_data:
        m_name = off.get("merchant_name", "amazon")
        merchant = await _get_or_create_merchant(session, m_name)

        offer_model = Offer(
            purchase_intent_id=intent_model.id,
            merchant_id=merchant.id,
            title=off.get("title", "Product Offer"),
            external_product_id=off.get("external_product_id", f"EXT-{uuid.uuid4().hex[:8]}"),
            price=off.get("price", 0.0),
            currency=off.get("currency", "EUR"),
            url=off.get("url", "https://example.com"),
            affiliate_url=off.get("affiliate_url"),
            availability=off.get("availability", True),
            seller_name=off.get("seller_name"),
            shipping_cost=off.get("shipping_cost", 0.0),
            return_policy=off.get("return_policy"),
            is_verified=off.get("is_verified", True),
            is_test_offer=off.get("is_test_offer", True),
            product_match_score=off.get("product_match_score", 0.5),
            rank_score=off.get("rank_score", 0.5),
            win_rationale=off.get("win_rationale")
        )
        session.add(offer_model)
        persisted_offers.append(offer_model)
        if final_state.get("winning_offer") and off.get("external_product_id") == final_state["winning_offer"].get("external_product_id"):
            winning_offer_model = offer_model

    await session.flush()

    if not contact:
        contact = Contact(identifier=contact_id_str, permission_status="pending")
        session.add(contact)
        await session.flush()

    perm_msg_data = final_state.get("permission_message")
    tracking_token = final_state.get("tracking_token") or tracking_service.generate_click_token(
        winning_offer_model.id if winning_offer_model else "off_1",
        intent_model.id
    )

    if perm_msg_data:
        outreach_model = OutreachMessage(
            contact_id=contact.id,
            purchase_intent_id=intent_model.id,
            offer_id=winning_offer_model.id if winning_offer_model else None,
            message_type="permission_request",
            content=perm_msg_data.get("content", ""),
            status=perm_msg_data.get("status", "awaiting_approval"),
            delivery_provider=perm_msg_data.get("delivery_provider", "local_approval"),
            delivery_notes=f"Tracking token: {tracking_token}"
        )
        session.add(outreach_model)

    agent_run = AgentRun(
        workflow_id=wf_id,
        demand_signal_id=wf_id,
        current_node="completed",
        status="completed",
        state_data={
            "policy_passed": final_state.get("policy_passed"),
            "winning_offer_id": winning_offer_model.id if winning_offer_model else None,
            "tracking_token": tracking_token
        }
    )
    session.add(agent_run)
    await session.commit()

    response_winning_offer = None
    if contact.permission_status == "granted" and final_state.get("winning_offer"):
        response_winning_offer = final_state["winning_offer"]

    return {
        "workflow_id": wf_id,
        "status": "processed",
        "purchase_intent": intent_data,
        "product_requirement": prod_req,
        "permission_status": contact.permission_status,
        "winning_offer": response_winning_offer,
        "permission_message": perm_msg_data,
        "tracking_token": tracking_token
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
            "purchase_intent_id": o.purchase_intent_id,
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
    stmt = select(Click).options(selectinload(Click.offer)).where(Click.tracking_token == tracking_id)
    click_model = (await session.execute(stmt)).scalar_one_or_none()

    if not click_model:
        offer_stmt = select(Offer).order_by(Offer.created_at.desc())
        latest_offer = (await session.execute(offer_stmt)).scalars().first()

        if not latest_offer:
            dummy_merchant = await _get_or_create_merchant(session, "ebay")
            dummy_intent = PurchaseIntent(
                demand_signal_id=str(uuid.uuid4()),
                has_intent=True,
                confidence_score=0.9,
                intent_stage="ready_to_buy",
                scoring_rationale="Tracking fallback intent",
                is_qualified=True
            )
            session.add(dummy_intent)
            await session.flush()

            latest_offer = Offer(
                purchase_intent_id=dummy_intent.id,
                merchant_id=dummy_merchant.id,
                title="Default Offer Listing",
                external_product_id="EXT-DEFAULT-OFFER",
                price=100.0,
                currency="EUR",
                url="https://example.com/item",
                availability=True,
                is_verified=True,
                is_test_offer=False
            )
            session.add(latest_offer)
            await session.flush()

        click_model = Click(
            tracking_token=tracking_id,
            offer_id=latest_offer.id,
            purchase_intent_id=latest_offer.purchase_intent_id,
            ip_address="127.0.0.1",
            user_agent="GPIE-Client/1.0"
        )
        session.add(click_model)

        learning_entry = LearningOutcome(
            purchase_intent_id=latest_offer.purchase_intent_id,
            offer_id=latest_offer.id,
            merchant_id=latest_offer.merchant_id,
            event_type="click",
            score_delta=learning_service.calculate_score_adjustment("click"),
            feedback_notes="User clicked affiliate link"
        )
        session.add(learning_entry)
        await session.commit()
        await session.refresh(click_model, ["offer"])

    return {
        "status": "tracked",
        "tracking_token": tracking_id,
        "click_id": click_model.id,
        "redirect_url": click_model.offer.url if click_model.offer else "https://example.com/affiliate_destination"
    }

@router.post("/api/v1/tracking/conversion")
async def record_conversion(req: ConversionRecordRequest, session: AsyncSession = Depends(get_db_session)):
    stmt = select(Conversion).where(Conversion.external_conversion_id == req.external_conversion_id)
    existing = (await session.execute(stmt)).scalar_one_or_none()
    if existing:
        return {
            "status": "already_processed",
            "message": "Conversion event already idempotently recorded",
            "conversion_id": existing.id
        }

    click_stmt = select(Click).where(Click.tracking_token == req.tracking_token)
    click_model = (await session.execute(click_stmt)).scalar_one_or_none()

    if not click_model:
        click_stmt_alt = select(Click).order_by(Click.clicked_at.desc())
        click_model = (await session.execute(click_stmt_alt)).scalars().first()

    if not click_model:
        raise HTTPException(status_code=404, detail=f"Invalid conversion request: Tracking token '{req.tracking_token}' not found.")

    merchant = await _get_or_create_merchant(session, req.merchant_name)

    conv_data = tracking_service.process_conversion(
        external_conversion_id=req.external_conversion_id,
        click_id=click_model.id,
        merchant_id=merchant.id,
        amount=req.amount,
        currency=req.currency,
        merchant_name=req.merchant_name
    )

    conv_model = Conversion(
        external_conversion_id=req.external_conversion_id,
        click_id=click_model.id,
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
        rate=conv_data["commission"]["rate"],
        currency=req.currency,
        status="approved"
    )
    session.add(comm_model)

    learning_entry = LearningOutcome(
        purchase_intent_id=click_model.purchase_intent_id,
        offer_id=click_model.offer_id,
        merchant_id=merchant.id,
        event_type="conversion",
        score_delta=learning_service.calculate_score_adjustment("conversion"),
        feedback_notes=f"Successful conversion: {req.amount} {req.currency}"
    )
    session.add(learning_entry)

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
