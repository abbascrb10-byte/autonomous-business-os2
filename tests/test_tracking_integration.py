import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from app.main import app
from app.database.session import Base, get_db_session
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from app.merchants.adapters import ebay_adapter
from app.config.settings import settings

ADMIN_HEADERS = {"X-API-Key": settings.ADMIN_API_KEY or ""}

TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"

engine = create_async_engine(TEST_DATABASE_URL, echo=False)
TestingSessionLocal = async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)

async def override_get_db():
    async with TestingSessionLocal() as session:
        yield session

@pytest_asyncio.fixture(autouse=True)
async def prepare_database():
    app.dependency_overrides[get_db_session] = override_get_db
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)

@pytest.mark.asyncio
async def test_full_tracking_and_conversion_idempotency_api(monkeypatch):
    async def discover_test_offers(requirement):
        return [{
            "merchant_name": "ebay",
            "title": "Sony A7 IV Body",
            "external_product_id": "TEST-SONY-A7-IV",
            "price": 1750.0,
            "currency": "EUR",
            "url": "https://example.com/sony-a7-iv",
            "availability": True,
            "seller_name": "Test Seller",
            "is_verified": True,
            "is_test_offer": True
        }]

    monkeypatch.setattr(ebay_adapter, "discover_offers", discover_test_offers)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # Grant permission first to unmask winning offer and ensure offer creation
        await client.post("/api/v1/permission/grant", json={"contact_identifier": "buyer_conv@example.com", "granted": True}, headers=ADMIN_HEADERS)

        demand_res = await client.post("/api/v1/demand", json={
            "source_type": "owned_api",
            "source_id": "u_conv_1",
            "content": "Looking to buy Sony A7 IV camera body for €1800",
            "contact_identifier": "buyer_conv@example.com"
        })
        assert demand_res.status_code == 201
        token = demand_res.json()["tracking_token"]
        assert token is not None

        click_res = await client.get(f"/api/v1/tracking/click/{token}")
        assert click_res.status_code == 200
        assert click_res.json()["status"] == "tracked"
        assert click_res.json()["redirect_url"] == "https://example.com/sony-a7-iv"
        click_id = click_res.json()["click_id"]
        assert click_id is not None

        conv_payload = {
            "external_conversion_id": "EXT-CONV-9999",
            "tracking_token": token,
            "merchant_name": "ebay",
            "amount": 1800.0,
            "currency": "EUR"
        }
        conv_res = await client.post("/api/v1/tracking/conversion", json=conv_payload, headers=ADMIN_HEADERS)
        assert conv_res.status_code == 200
        assert conv_res.json()["status"] == "recorded"

        dup_res = await client.post("/api/v1/tracking/conversion", json=conv_payload, headers=ADMIN_HEADERS)
        assert dup_res.status_code == 200
        assert dup_res.json()["status"] == "already_processed"

        funnel_res = await client.get("/api/v1/analytics/funnel", headers=ADMIN_HEADERS)
        assert funnel_res.status_code == 200
        assert funnel_res.json()["conversions_total"] == 1

        learning_res = await client.get("/api/v1/learning/metrics", headers=ADMIN_HEADERS)
        assert learning_res.status_code == 200
        assert learning_res.json()["total_learning_events"] >= 1

@pytest.mark.asyncio
async def test_unknown_tracking_token_is_rejected():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        click_res = await client.get("/api/v1/tracking/click/unknown-token")
        assert click_res.status_code == 404

        conversion_res = await client.post("/api/v1/tracking/conversion", json={
            "external_conversion_id": "EXT-UNKNOWN-TOKEN",
            "tracking_token": "unknown-token",
            "merchant_name": "ebay",
            "amount": 10.0,
            "currency": "EUR"
        }, headers=ADMIN_HEADERS)
        assert conversion_res.status_code == 404
