# Global Purchase Intent Engine (GPIE Professional v1)

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
Purchase Intent Detection & Qualification (Ollama local default / Cloud LLMs)
  ↓
Product / Requirement Extraction
  ↓
Real Offer Discovery (eBay Browse API & Etsy API v3 Primary; Amazon Optional)
  ↓
Offer Verification (Price, Availability, URL, Freshness)
  ↓
Offer Ranking (Weighted Buyer Suitability vs. Commission)
  ↓
Policy Engine Check (Source, Anti-Spam, Affiliate Compliance)
  ↓
Permission Check & Outreach Abstraction (Local Approval Boundary)
  ↓
Affiliate Recommendation & Click Tracking
  ↓
Conversion & Idempotent Commission Tracking
  ↓
Funnel Analytics & Outcome Learning Loop
```

---

## 2. Configuration & Credentials Setup

Copy `.env.example` to `.env`:
```bash
cp .env.example .env
```

### Required Default Services
- **PostgreSQL Database**: Persistent source of truth for workflow signals, intents, offers, and conversions.
- **Redis Queue**: Background worker job queue and idempotency locks.
- **Ollama**: Default local open-weight LLM provider (`AI_PROVIDER=ollama`, model: `llama3.2`).
- **eBay Browse API**: Primary real commerce source (`EBAY_CLIENT_ID`, `EBAY_CLIENT_SECRET`).
- **Etsy Open API v3**: Secondary real commerce source (`ETSY_API_KEY`).
- **Tavily Web Search**: Primary commercial search source (`Tavily_API_KEY`).

### Optional Services
- **Google Gemini**: Set `AI_PROVIDER=gemini` and provide `GEMINI_API_KEY`.
- **OpenAI**: Set `AI_PROVIDER=openai` and provide `OPENAI_API_KEY`.
- **Anthropic**: Set `AI_PROVIDER=anthropic` and provide `ANTHROPIC_API_KEY`.
- **Amazon Product Advertising API**: Optional merchant adapter (`AMAZON_ASSOCIATE_TAG`, `AMAZON_ACCESS_KEY`, `AMAZON_SECRET_KEY`).
- **Outreach Providers**: Set `OUTREACH_PROVIDER=sendgrid` or `twilio` (Default is `local_approval` safe boundary).

*Note: Unconfigured merchant or AI providers report `CONFIGURATION_REQUIRED` cleanly without generating fake/mock production offers.*

---

## 3. Local Execution & Testing

1. **Install Dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

2. **Database Migration**:
   ```bash
   alembic upgrade head
   ```

3. **Run API Server**:
   ```bash
   uvicorn app.main:app --reload --port 8000
   ```

4. **Run Background Worker**:
   ```bash
   python -m app.workers.runner
   ```

5. **Run Automated Test Suite**:
   ```bash
   PYTHONPATH=. pytest tests/
   ```

---

## 4. Docker Compose Startup

Start the complete stack (PostgreSQL, Redis, FastAPI App, and Background Worker) with health checks:

```bash
docker compose up --build
```

Access API Documentation:
- Swagger UI: `http://localhost:8000/docs`
- ReDoc: `http://localhost:8000/redoc`

---

## 5. API Endpoints Overview

- `GET /health`: Health status.
- `GET /readiness`: Readiness check for DB, Redis, AI Provider, and Merchant configurations.
- `POST /api/v1/demand`: Submit raw demand signal and run 12-stage LangGraph workflow.
- `GET /api/v1/intents/{id}`: Inspect purchase intent state.
- `GET /api/v1/offers`: Inspect discovered & ranked offers.
- `POST /api/v1/permission/grant`: Grant or deny user contact permission.
- `GET /api/v1/outreach/messages`: Inspect outreach messages.
- `GET /api/v1/tracking/click/{token}`: Track click and redirect.
- `POST /api/v1/tracking/conversion`: Idempotently record conversion and commission.
- `GET /api/v1/analytics/funnel`: View funnel conversion metrics.
- `GET /api/v1/learning/metrics`: View learning feedback outcome metrics.
