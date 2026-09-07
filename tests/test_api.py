import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from app.main import app
from app.database.session import Base, get_db_session
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
async def test_health_check_endpoint():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        res = await client.get("/health")
        assert res.status_code == 200
        assert res.json()["service"] == "GPIE Professional v1"

@pytest.mark.asyncio
async def test_ui_dashboard_renders_operational_sections():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        res = await client.get("/ui")
        assert res.status_code == 200
        assert "لوحة تشغيل GPIE" in res.text
        assert "حالة مفاتيح التكامل" in res.text
        assert "مسارات API المتاحة" in res.text
        assert "آخر 10 إشارات واردة" in res.text
        assert "/api/v1/demand" in res.text

@pytest.mark.asyncio
async def test_readiness_check_endpoint():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        res = await client.get("/readiness")
        assert res.status_code == 200
        assert "database" in res.json()

@pytest.mark.asyncio
async def test_sensitive_routes_require_admin_key_in_production(monkeypatch):
    monkeypatch.setattr(settings, "APP_ENV", "production")
    monkeypatch.setattr(settings, "ADMIN_API_KEY", "test-admin-key")

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        missing = await client.get("/api/v1/offers")
        assert missing.status_code == 401

        invalid = await client.get("/api/v1/offers", headers={"X-API-Key": "wrong-key"})
        assert invalid.status_code == 403

        valid = await client.get("/api/v1/offers", headers={"X-API-Key": "test-admin-key"})
        assert valid.status_code == 200

@pytest.mark.asyncio
async def test_submit_demand_workflow():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        payload = {
            "source_type": "owned_api",
            "source_id": "user_456",
            "content": "I need a Sony A7 IV camera body under €1800 shipped to France",
            "contact_identifier": "buyer_test@example.com"
        }
        res = await client.post("/api/v1/demand", json=payload)
        assert res.status_code == 201
        data = res.json()
        assert "workflow_id" in data
        assert data["purchase_intent"]["has_intent"] is True
        assert data["permission_status"] == "pending"
        assert data["winning_offer"] is None
        assert data["permission_message"] is not None

        offers_res = await client.get("/api/v1/offers", headers=ADMIN_HEADERS)
        assert offers_res.status_code == 200

        msg_res = await client.get("/api/v1/outreach/messages", headers=ADMIN_HEADERS)
        assert msg_res.status_code == 200
        assert len(msg_res.json()) >= 1

@pytest.mark.asyncio
async def test_permission_grant_and_unmasking():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        perm_res = await client.post("/api/v1/permission/grant", json={"contact_identifier": "buyer_granted@example.com", "granted": True}, headers=ADMIN_HEADERS)
        assert perm_res.status_code == 200
        assert perm_res.json()["permission_status"] == "granted"

        payload = {
            "source_type": "owned_api",
            "source_id": "user_789",
            "content": "I need a Sony A7 IV camera body under €1800 shipped to France",
            "contact_identifier": "buyer_granted@example.com"
        }
        res = await client.post("/api/v1/demand", json=payload)
        assert res.status_code == 201
        data = res.json()
        assert data["permission_status"] == "granted"
