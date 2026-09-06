import uuid
from typing import TypedDict, List, Dict, Any, Optional
from langgraph.graph import StateGraph, END
from app.sources.adapters import owned_adapter, public_adapter, search_adapter
from app.services.intent_service import intent_service
from app.merchants.adapters import amazon_adapter, ebay_adapter
from app.services.ranking_service import ranking_service
from app.policy.engine import policy_engine
from app.services.outreach_service import outreach_service
from app.services.tracking_service import tracking_service
import structlog

logger = structlog.get_logger()

class WorkflowState(TypedDict, total=False):
    workflow_id: str
    raw_demand: Dict[str, Any]
    normalized_demand: Dict[str, Any]
    is_duplicate: bool
    dedup_hash: str
    purchase_intent: Dict[str, Any]
    product_requirement: Dict[str, Any]
    discovered_offers: List[Dict[str, Any]]
    verified_offers: List[Dict[str, Any]]
    ranked_offers: List[Dict[str, Any]]
    winning_offer: Optional[Dict[str, Any]]
    policy_passed: bool
    policy_reason: str
    contact_identifier: Optional[str] = None
    permission_status: str
    permission_message: Optional[Dict[str, Any]] = None
    recommendation_message: Optional[Dict[str, Any]] = None
    tracking_token: Optional[str] = None
    tracking_url: Optional[str] = None
    errors: List[str]

async def node_ingest(state: WorkflowState) -> WorkflowState:
    raw = state.get("raw_demand", {})
    stype = raw.get("source_type", "owned_api")
    if stype == "authorized_public":
        adapter = public_adapter
    elif stype == "commercial_search":
        adapter = search_adapter
    else:
        adapter = owned_adapter

    norm = adapter.normalize_demand(raw)
    state["normalized_demand"] = norm
    state["contact_identifier"] = norm.get("contact_identifier")
    state["dedup_hash"] = norm.get("dedup_hash", "")
    return state

async def node_normalize(state: WorkflowState) -> WorkflowState:
    norm = state.get("normalized_demand", {})
    norm["normalized_content"] = norm.get("raw_content", "").strip()
    state["normalized_demand"] = norm
    return state

async def node_deduplicate(state: WorkflowState) -> WorkflowState:
    state["is_duplicate"] = False
    return state

async def node_intent(state: WorkflowState) -> WorkflowState:
    content = state.get("normalized_demand", {}).get("raw_content", "")
    analysis = await intent_service.analyze_and_extract(content)

    state["purchase_intent"] = {
        "has_intent": analysis["has_intent"],
        "confidence_score": analysis["confidence_score"],
        "intent_stage": analysis["intent_stage"],
        "scoring_rationale": analysis["scoring_rationale"],
        "is_qualified": analysis["is_qualified"]
    }
    state["product_requirement"] = analysis.get("product_requirement") or {}
    return state

async def node_product(state: WorkflowState) -> WorkflowState:
    req = state.get("product_requirement", {})
    if not req.get("product_name"):
        req["product_name"] = state.get("normalized_demand", {}).get("raw_content", "General Product")
    state["product_requirement"] = req
    return state

async def node_offer_discovery(state: WorkflowState) -> WorkflowState:
    req = state.get("product_requirement", {})
    amz_offers = await amazon_adapter.discover_offers(req)
    ebay_offers = await ebay_adapter.discover_offers(req)

    all_offers = amz_offers + ebay_offers
    state["discovered_offers"] = all_offers
    return state

async def node_verification(state: WorkflowState) -> WorkflowState:
    req = state.get("product_requirement", {})
    discovered = state.get("discovered_offers", [])

    verified = []
    for offer in discovered:
        is_ok, msg = ranking_service.verify_offer(offer, req)
        if is_ok:
            verified.append(offer)

    state["verified_offers"] = verified
    return state

async def node_ranking(state: WorkflowState) -> WorkflowState:
    req = state.get("product_requirement", {})
    verified = state.get("verified_offers", [])

    if verified:
        ranked = await ranking_service.rank_offers(verified, req)
        state["ranked_offers"] = ranked
        state["winning_offer"] = ranked[0] if ranked else None
    else:
        state["ranked_offers"] = []
        state["winning_offer"] = None
    return state

async def node_policy(state: WorkflowState) -> WorkflowState:
    stype = state.get("normalized_demand", {}).get("source_type", "owned_api")
    meta = state.get("normalized_demand", {}).get("metadata_json", {})
    is_source_ok, reason = policy_engine.evaluate_source_policy(stype, meta)

    state["policy_passed"] = is_source_ok
    state["policy_reason"] = reason
    return state

async def node_permission(state: WorkflowState) -> WorkflowState:
    contact = state.get("contact_identifier", "anonymous@gpie.internal")
    prod = state.get("product_requirement", {}).get("product_name", "product")

    perm_msg = outreach_service.generate_permission_request(contact, prod)
    state["permission_message"] = perm_msg
    if "permission_status" not in state or not state["permission_status"]:
        state["permission_status"] = "pending"
    return state

async def node_recommendation(state: WorkflowState) -> WorkflowState:
    winning = state.get("winning_offer")
    contact = state.get("contact_identifier", "anonymous@gpie.internal")

    if winning and state.get("permission_status") == "granted":
        token = tracking_service.generate_click_token(
            winning.get("external_product_id", "off_1"),
            state.get("workflow_id", "wf_1")
        )
        url = tracking_service.generate_tracking_url(token)
        rec_msg = outreach_service.generate_recommendation_message(contact, winning, url)

        state["tracking_token"] = token
        state["tracking_url"] = url
        state["recommendation_message"] = rec_msg
    else:
        state["recommendation_message"] = None

    return state

async def node_tracking(state: WorkflowState) -> WorkflowState:
    logger.info("GPIE Workflow state tracking completed", workflow_id=state.get("workflow_id"))
    return state

def route_after_intent(state: WorkflowState) -> str:
    intent = state.get("purchase_intent", {})
    if intent.get("is_qualified", False):
        return "product"
    return "END"

def route_after_policy(state: WorkflowState) -> str:
    if state.get("policy_passed", True):
        return "permission"
    return "END"

def build_gpie_graph() -> StateGraph:
    workflow = StateGraph(WorkflowState)

    workflow.add_node("ingest", node_ingest)
    workflow.add_node("normalize", node_normalize)
    workflow.add_node("deduplicate", node_deduplicate)
    workflow.add_node("intent", node_intent)
    workflow.add_node("product", node_product)
    workflow.add_node("offer_discovery", node_offer_discovery)
    workflow.add_node("verification", node_verification)
    workflow.add_node("ranking", node_ranking)
    workflow.add_node("policy", node_policy)
    workflow.add_node("permission", node_permission)
    workflow.add_node("recommendation", node_recommendation)
    workflow.add_node("tracking", node_tracking)

    workflow.set_entry_point("ingest")

    workflow.add_edge("ingest", "normalize")
    workflow.add_edge("normalize", "deduplicate")
    workflow.add_edge("deduplicate", "intent")

    workflow.add_conditional_edges(
        "intent",
        route_after_intent,
        {
            "product": "product",
            "END": END
        }
    )

    workflow.add_edge("product", "offer_discovery")
    workflow.add_edge("offer_discovery", "verification")
    workflow.add_edge("verification", "ranking")
    workflow.add_edge("ranking", "policy")

    workflow.add_conditional_edges(
        "policy",
        route_after_policy,
        {
            "permission": "permission",
            "END": END
        }
    )

    workflow.add_edge("permission", "recommendation")
    workflow.add_edge("recommendation", "tracking")
    workflow.add_edge("tracking", END)

    return workflow.compile()

gpie_workflow = build_gpie_graph()
