import uuid
from datetime import datetime, timezone
from typing import Optional, Dict, Any
from sqlalchemy import (
    String, Text, Boolean, Float, Integer, DateTime, ForeignKey, JSON, Index, UniqueConstraint
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID
from app.database.session import Base

def generate_uuid() -> str:
    return str(uuid.uuid4())

def utc_now() -> datetime:
    return datetime.now(timezone.utc)

class DemandSignal(Base):
    __tablename__ = "demand_signals"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    source_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    source_id: Mapped[str] = mapped_column(String(100), nullable=False)
    raw_content: Mapped[str] = mapped_column(Text, nullable=False)
    normalized_content: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    dedup_hash: Mapped[str] = mapped_column(String(64), nullable=False, index=True, unique=True)
    metadata_json: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, nullable=True)
    contact_identifier: Mapped[Optional[str]] = mapped_column(String(255), nullable=True, index=True)
    status: Mapped[str] = mapped_column(String(50), default="ingested", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)

    intents: Mapped[list["PurchaseIntent"]] = relationship("PurchaseIntent", back_populates="demand_signal", cascade="all, delete-orphan")

class PurchaseIntent(Base):
    __tablename__ = "purchase_intents"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    demand_signal_id: Mapped[str] = mapped_column(String(36), ForeignKey("demand_signals.id", ondelete="CASCADE"), nullable=False)
    has_intent: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    confidence_score: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    intent_stage: Mapped[str] = mapped_column(String(50), nullable=False, default="unqualified")
    scoring_rationale: Mapped[str] = mapped_column(Text, nullable=False)
    is_qualified: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    # Enhanced requirement tracking attributes
    urgency_score: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    budget_min: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    budget_max: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    currency: Mapped[Optional[str]] = mapped_column(String(10), nullable=True, default="EUR")
    shipping_destination: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    timeframe: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)

    demand_signal: Mapped["DemandSignal"] = relationship("DemandSignal", back_populates="intents")
    product_requirement: Mapped[Optional["ProductRequirement"]] = relationship("ProductRequirement", back_populates="purchase_intent", uselist=False, cascade="all, delete-orphan")
    offers: Mapped[list["Offer"]] = relationship("Offer", back_populates="purchase_intent", cascade="all, delete-orphan")

class ProductRequirement(Base):
    __tablename__ = "product_requirements"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    purchase_intent_id: Mapped[str] = mapped_column(String(36), ForeignKey("purchase_intents.id", ondelete="CASCADE"), nullable=False, unique=True)
    product_name: Mapped[str] = mapped_column(String(255), nullable=False)
    brand: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    model: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    category: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    budget_max: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    currency: Mapped[str] = mapped_column(String(10), default="EUR", nullable=False)
    condition: Mapped[str] = mapped_column(String(50), default="any", nullable=False)
    destination_country: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    shipping_preferences: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    specifications: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, nullable=True)
    urgency: Mapped[str] = mapped_column(String(50), default="normal", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)

    purchase_intent: Mapped["PurchaseIntent"] = relationship("PurchaseIntent", back_populates="product_requirement")

class Merchant(Base):
    __tablename__ = "merchants"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    name: Mapped[str] = mapped_column(String(100), nullable=False, unique=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    credentials_configured: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    commission_rate_estimate: Mapped[float] = mapped_column(Float, default=0.04, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)

    offers: Mapped[list["Offer"]] = relationship("Offer", back_populates="merchant")

class Offer(Base):
    __tablename__ = "offers"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    purchase_intent_id: Mapped[str] = mapped_column(String(36), ForeignKey("purchase_intents.id", ondelete="CASCADE"), nullable=False)
    merchant_id: Mapped[str] = mapped_column(String(36), ForeignKey("merchants.id"), nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    external_product_id: Mapped[str] = mapped_column(String(100), nullable=False)
    price: Mapped[float] = mapped_column(Float, nullable=False)
    currency: Mapped[str] = mapped_column(String(10), default="EUR", nullable=False)
    url: Mapped[str] = mapped_column(Text, nullable=False)
    affiliate_url: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    availability: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    seller_name: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    shipping_cost: Mapped[Optional[float]] = mapped_column(Float, default=0.0, nullable=True)
    return_policy: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    is_verified: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_test_offer: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    product_match_score: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    rank_score: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    win_rationale: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    freshness_timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)

    purchase_intent: Mapped["PurchaseIntent"] = relationship("PurchaseIntent", back_populates="offers")
    merchant: Mapped["Merchant"] = relationship("Merchant", back_populates="offers")
    clicks: Mapped[list["Click"]] = relationship("Click", back_populates="offer")

class Contact(Base):
    __tablename__ = "contacts"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    identifier: Mapped[str] = mapped_column(String(255), nullable=False, unique=True, index=True)
    channel: Mapped[str] = mapped_column(String(50), default="email", nullable=False)
    permission_status: Mapped[str] = mapped_column(String(50), default="pending", nullable=False)
    permission_requested_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    permission_granted_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)

    outreach_messages: Mapped[list["OutreachMessage"]] = relationship("OutreachMessage", back_populates="contact")

class OutreachMessage(Base):
    __tablename__ = "outreach_messages"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    contact_id: Mapped[str] = mapped_column(String(36), ForeignKey("contacts.id", ondelete="CASCADE"), nullable=False)
    purchase_intent_id: Mapped[Optional[str]] = mapped_column(String(36), ForeignKey("purchase_intents.id", ondelete="SET NULL"), nullable=True)
    offer_id: Mapped[Optional[str]] = mapped_column(String(36), ForeignKey("offers.id", ondelete="SET NULL"), nullable=True)
    message_type: Mapped[str] = mapped_column(String(50), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(50), default="awaiting_approval", nullable=False)
    delivery_provider: Mapped[str] = mapped_column(String(50), default="local_approval", nullable=False)
    delivery_notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)

    contact: Mapped["Contact"] = relationship("Contact", back_populates="outreach_messages")

class Click(Base):
    __tablename__ = "clicks"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    tracking_token: Mapped[str] = mapped_column(String(64), nullable=False, unique=True, index=True)
    offer_id: Mapped[str] = mapped_column(String(36), ForeignKey("offers.id", ondelete="CASCADE"), nullable=False)
    purchase_intent_id: Mapped[str] = mapped_column(String(36), ForeignKey("purchase_intents.id", ondelete="CASCADE"), nullable=False)
    ip_address: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    user_agent: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    clicked_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)

    offer: Mapped["Offer"] = relationship("Offer", back_populates="clicks")
    conversions: Mapped[list["Conversion"]] = relationship("Conversion", back_populates="click")

class Conversion(Base):
    __tablename__ = "conversions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    external_conversion_id: Mapped[str] = mapped_column(String(100), nullable=False, unique=True, index=True)
    click_id: Mapped[str] = mapped_column(String(36), ForeignKey("clicks.id", ondelete="CASCADE"), nullable=False)
    merchant_id: Mapped[str] = mapped_column(String(36), ForeignKey("merchants.id"), nullable=False)
    amount: Mapped[float] = mapped_column(Float, nullable=False)
    currency: Mapped[str] = mapped_column(String(10), default="EUR", nullable=False)
    status: Mapped[str] = mapped_column(String(50), default="completed", nullable=False)
    converted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)

    click: Mapped["Click"] = relationship("Click", back_populates="conversions")
    commission: Mapped[Optional["Commission"]] = relationship("Commission", back_populates="conversion", uselist=False, cascade="all, delete-orphan")

class Commission(Base):
    __tablename__ = "commissions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    conversion_id: Mapped[str] = mapped_column(String(36), ForeignKey("conversions.id", ondelete="CASCADE"), nullable=False, unique=True)
    amount: Mapped[float] = mapped_column(Float, nullable=False)
    rate: Mapped[float] = mapped_column(Float, default=0.04, nullable=False)
    currency: Mapped[str] = mapped_column(String(10), default="EUR", nullable=False)
    status: Mapped[str] = mapped_column(String(50), default="approved", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)

    conversion: Mapped["Conversion"] = relationship("Conversion", back_populates="commission")

class Event(Base):
    __tablename__ = "events"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    entity_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    entity_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    event_type: Mapped[str] = mapped_column(String(100), nullable=False)
    payload: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)

class AgentRun(Base):
    __tablename__ = "agent_runs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    workflow_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    demand_signal_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True)
    current_node: Mapped[str] = mapped_column(String(50), nullable=False)
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="running")
    state_data: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, nullable=True)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False)

class AuditLog(Base):
    __tablename__ = "audit_logs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    action: Mapped[str] = mapped_column(String(100), nullable=False)
    actor: Mapped[str] = mapped_column(String(100), nullable=False, default="system")
    policy_checked: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    decision: Mapped[str] = mapped_column(String(50), nullable=False)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    details: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)

class LearningOutcome(Base):
    __tablename__ = "learning_outcomes"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    purchase_intent_id: Mapped[str] = mapped_column(String(36), ForeignKey("purchase_intents.id", ondelete="CASCADE"), nullable=False)
    offer_id: Mapped[Optional[str]] = mapped_column(String(36), ForeignKey("offers.id", ondelete="SET NULL"), nullable=True)
    merchant_id: Mapped[Optional[str]] = mapped_column(String(36), ForeignKey("merchants.id", ondelete="SET NULL"), nullable=True)
    event_type: Mapped[str] = mapped_column(String(50), nullable=False)
    score_delta: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    feedback_notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)

class SourceWeight(Base):
    __tablename__ = "source_weights"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    source_name: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    weight: Mapped[float] = mapped_column(Float, default=1.0, nullable=False)
    conversion_rate: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    signals_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    conversions_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False)
