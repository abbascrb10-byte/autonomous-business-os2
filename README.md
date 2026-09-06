# Global Purchase Intent Engine (GPIE) Professional v1

GPIE (Global Purchase Intent Engine) is a real, balanced, professional software system designed to detect genuine purchase intent, extract structured product requirements, discover and rank commercial offers from authorized merchant platforms, evaluate compliance policies and user permissions, generate affiliate recommendations, track conversion funnels, and learn from feedback outcomes.

---

## 1. Architecture & Business Flow

GPIE implements a complete state-preserving 12-stage workflow:

```
Demand Ingestion
  ↓
Normalize
  ↓
Deduplicate (SHA256 Hashing)
  ↓
Purchase Intent Detection & Qualification
  ↓
Product / Requirement Extraction
  ↓
Offer Discovery (Amazon & eBay Adapters)
  ↓
Offer Verification (Price, Availability, URL, Freshness)
  ↓
Offer Ranking (Weighted Buyer Suitability vs. Commission)
  ↓
Policy Engine Check (Source, Anti-Spam, Affiliate Compliance)
  ↓
Permission Check & Outreach Abstraction
  ↓
Affiliate Recommendation & Click Tracking
  ↓
Conversion & Idempotent Commission Tracking
  ↓
Funnel Analytics & Outcome Learning Loop
```

---

## 2. Repository Structure

```
.
├── app/
│   ├── main.py                  # FastAPI application entrypoint
│   ├── config/
│   │   └── settings.py          # Pydantic Settings configuration
│   ├── database/
│   │   ├── session.py           # Async SQLAlchemy session management
│   │   └── models.py            # PostgreSQL ORM models & relationships
│   ├── agents/
│   │   └── llm_provider.py      # LLM provider abstraction (OpenAI, Anthropic, Gemini, fallback)
│   ├── services/
│   │   ├── intent_service.py    # Intent scoring & requirement extraction
│   │   ├── ranking_service.py   # Verification & weighted offer ranking
│   │   ├── outreach_service.py  # Permission request & recommendation outreach
│   │   └── tracking_service.py  # Click token & conversion/commission calculation
│   ├── sources/
│   │   └── adapters.py          # Owned API, Authorized Public, Commercial Search source adapters
│   ├── merchants/
│   │   └── adapters.py          # Amazon & eBay adapters (real API vs. isolated test adapter)
│   ├── policy/
│   │   └── engine.py            # Compliance policy engine
│   ├── graph/
│   │   └── workflow.py          # Stateful LangGraph workflow orchestrator
│   ├── workers/
│   │   └── manager.py           # Redis job manager & idempotency locks
│   ├── analytics/
│   │   └── service.py           # Funnel analytics aggregation service
│   ├── learning/
│   │   └── service.py           # Outcome-based learning loop service
│   └── api/
│       └── routes.py            # FastAPI REST API endpoints
├── alembic/                     # Database migrations
├── tests/                       # Automated test suite (16 test cases)
├── Dockerfile                   # Application container definition
├── docker-compose.yml           # Multi-container orchestration (App + PostgreSQL + Redis)
├── requirements.txt             # Dependency definitions
└── .env.example                 # Environment variables template
```

---

## 3. Environment Setup & Execution

### Local Development Setup

1. **Install Dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

2. **Environment Configuration**:
   Copy `.env.example` to `.env`:
   ```bash
   cp .env.example .env
   ```

3. **Database Migration**:
   ```bash
   alembic upgrade head
   ```

4. **Running the FastAPI Application**:
   ```bash
   uvicorn app.main:app --reload --port 8000
   ```

5. **Running Tests**:
   ```bash
   PYTHONPATH=. pytest tests/
   ```

---

## 4. Docker Compose Startup

Start the complete stack (PostgreSQL 16, Redis 7, and FastAPI application) with health checks:

```bash
docker compose up --build
```

Access API Documentation:
- Swagger UI: `http://localhost:8000/docs`
- ReDoc: `http://localhost:8000/redoc`

---

## 5. API Endpoints

- `GET /health`: Health status.
- `GET /readiness`: Component readiness check (DB, Redis, LLM, Merchants).
- `POST /api/v1/demand`: Submit raw demand signal and run LangGraph workflow.
- `GET /api/v1/intents/{id}`: Inspect purchase intent state.
- `GET /api/v1/offers`: Inspect discovered & ranked offers.
- `POST /api/v1/permission/grant`: Grant or deny user contact permission.
- `GET /api/v1/outreach/messages`: Inspect outreach messages.
- `GET /api/v1/tracking/click/{token}`: Track click and redirect.
- `POST /api/v1/tracking/conversion`: Idempotently record conversion and commission.
- `GET /api/v1/analytics/funnel`: View funnel conversion metrics.
- `GET /api/v1/learning/metrics`: View learning feedback outcome metrics.

---

## 6. External Credentials & Unconfigured Behavior

- **AI Engine (OpenAI / Anthropic / Gemini)**: When API keys are missing, system falls back gracefully to explainable deterministic rule-based intent scoring and requirement parsing.
- **Merchants (Amazon / eBay)**: When merchant API credentials are missing, system routes offer discovery through isolated test adapters (`is_test_offer=True`), ensuring test data is never conflated with real production offers.
- **Outreach Providers**: When no external messaging API key is configured, messages are held at a local approval boundary (`status="awaiting_approval"`).

---

## 7. Known Bounded Scope & Future Expansion

- **Bounded Integrations**: Bounded strictly to Amazon and eBay merchants, and 3 clean demand source adapters.
- **Future Expansion**: Clean interface abstractions (`BaseSourceAdapter`, `BaseMerchantAdapter`, `LLMProvider`) allow adding new merchants or AI providers with zero core logic refactoring.
