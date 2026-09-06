import pytest
import uuid
from app.graph.workflow import gpie_workflow
from app.workers.manager import worker_manager

@pytest.mark.asyncio
async def test_langgraph_workflow_end_to_end():
    wf_id = str(uuid.uuid4())
    initial_state = {
        "workflow_id": wf_id,
        "raw_demand": {
            "source_type": "owned_api",
            "user_id": "user_999",
            "text": "I need a Sony A7 IV body under €1800, preferably new, shipped to France.",
            "email": "camera_buyer@example.com"
        }
    }

    final_state = await gpie_workflow.ainvoke(initial_state)

    assert final_state["workflow_id"] == wf_id
    assert final_state["normalized_demand"]["source_type"] == "owned_api"
    assert final_state["purchase_intent"]["has_intent"] is True
    assert final_state["purchase_intent"]["is_qualified"] is True
    assert final_state["product_requirement"]["budget_max"] == 1800.0
    assert len(final_state["discovered_offers"]) >= 1
    assert len(final_state["ranked_offers"]) >= 1
    assert final_state["winning_offer"] is not None
    assert final_state["policy_passed"] is True
    assert final_state["permission_message"] is not None
    assert final_state["permission_message"]["status"] == "awaiting_approval"

@pytest.mark.asyncio
async def test_worker_manager_enqueue():
    job_id = await worker_manager.enqueue_job("demand_ingestion", {"workflow_id": "wf_test_123", "data": "test"})
    assert job_id == "wf_test_123"
