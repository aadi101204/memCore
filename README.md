# memCore — Memory-as-a-Service (MaaS)

A production-grade backend platform that provides persistent, semantically-searchable, scoped memory for AI agents.

## Architecture

```
Agents / Services
     │  (JWT Bearer / X-API-Key)
     ▼
FastAPI (app.main)
     ├── AuthMiddleware       ← populates request.state.auth_context
     ├── RateLimitMiddleware  ← 100 req/min per IP
     └── RequestLoggingMiddleware + Prometheus metrics
           │
           ├── /auth/*          ← Registration, login, JWT, API keys
           ├── /memory/*        ← CRUD + hybrid semantic search (Auth required)
           ├── /working/*       ← Session memory (Redis)
           ├── /conflicts/*     ← Conflict detection & resolution (Auth required)
           └── /health/         ← Service health checks
                 │
       ┌─────────┼──────────┐
       ▼         ▼          ▼
  PostgreSQL   Qdrant     Redis
  (metadata)  (vectors)  (working mem)
```

## Tech Stack

| Component | Technology |
|-----------|-----------|
| API | FastAPI 0.109, Uvicorn |
| Auth | JWT (python-jose) + API Keys (SHA-256) |
| DB | PostgreSQL + SQLAlchemy 2 (async) |
| Vectors | Qdrant (AsyncQdrantClient) |
| Embeddings | sentence-transformers `all-MiniLM-L6-v2` |
| Working Memory | Redis (asyncio) |
| Background Jobs | Celery + Redis broker |
| Migrations | Alembic |
| Metrics | Prometheus |

## Quick Start (Local)

### 1. Start infrastructure

```bash
# Start Postgres (port 5433), Redis (6379), Qdrant (6333)
docker-compose up -d postgres redis qdrant
```

### 2. Install dependencies

```bash
python -m venv venv
# Windows:
venv\Scripts\activate
# Linux/Mac:
source venv/bin/activate

pip install -r requirements.txt
```

### 3. Configure environment

A ready-to-use `.env` file is included. Edit if needed:

```bash
# Key settings already configured:
# DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5433/maas_db
# REDIS_URL=redis://localhost:6379/0
# QDRANT_HOST=localhost
# SECRET_KEY=dev-secret-key-change-in-production-32chars!!
```

### 4. Run migrations

```bash
alembic upgrade head
```

### 5. Start the API

```bash
uvicorn app.main:app --reload
```

API available at: http://localhost:8000  
Swagger docs: http://localhost:8000/docs

### 6. Run end-to-end tests

```bash
python scripts/test_api.py
```

---

## API Reference

### Authentication

All `/memory/*` and `/conflicts/*` endpoints require:
- `Authorization: Bearer <jwt_token>` — from `/auth/login`
- `X-API-Key: maas_<key>` — from `/auth/api-keys`

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/auth/register` | POST | Register a new user |
| `/auth/login` | POST | Login → JWT tokens |
| `/auth/refresh` | POST | Refresh access token |
| `/auth/logout` | POST | Logout (revoke token) |
| `/auth/me` | GET | Current user profile |
| `/auth/api-keys` | POST | Create API key |
| `/auth/api-keys` | GET | List org API keys |
| `/auth/api-keys/{id}` | DELETE | Revoke API key |

### Memory Operations

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/memory/` | POST | Create memory + embed to Qdrant |
| `/memory/{id}` | GET | Get memory (increments usage) |
| `/memory/{id}` | PUT | Update memory (re-embeds if content changed) |
| `/memory/{id}` | DELETE | Soft-delete + remove vector |
| `/memory/search` | POST | Hybrid semantic search |

**Search scoring formula:**
```
score = 0.6 × semantic + 0.2 × recency + 0.1 × confidence + 0.1 × usage
```

### Working Memory (Redis)

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/working/{session_id}` | PUT | Set session data (with TTL) |
| `/working/{session_id}` | GET | Get session data |
| `/working/{session_id}` | DELETE | Clear session |

### Conflict Resolution

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/conflicts/resolve` | POST | Resolve conflicts with strategy |
| `/conflicts/` | GET | List conflicting memories |
| `/conflicts/flag` | POST | Flag memories as conflicting |

**Resolution strategies:**
- `latest_wins` — keep most recent
- `confidence_weighted` — keep highest confidence
- `source_trust` — keep most-used source
- `merge_flag` — flag all for human merge
- `manual_review` — flag, no deletions

### Health & Metrics

| Endpoint | Description |
|----------|-------------|
| `/health/` | Service health (Postgres, Redis, Qdrant) |
| `/metrics` | Prometheus metrics |

---

## Memory Scopes

```
global  ← accessible to all agents
  └── org  ← accessible within an organisation
       └── team  ← accessible to a team
            └── agent  ← private to one agent
```

## Project Structure

```
memCore/
├── app/
│   ├── configs/         # Settings, DB, Redis, Qdrant
│   ├── controllers/     # Route handlers (auth, memory, working, conflicts, health)
│   ├── services/        # Business logic (auth, memory, embedding, conflict)
│   ├── repositories/    # DB/Redis access layer
│   ├── models/          # SQLAlchemy models + Pydantic schemas
│   ├── middlewares/     # Auth, rate limit, logging
│   ├── dependencies/    # FastAPI auth dependencies
│   ├── workers/         # Celery app + tasks
│   ├── interfaces/      # Abstract base classes
│   ├── decorators/      # Prometheus metrics decorator
│   └── utils/           # Encryption, transaction management
├── alembic/             # Database migrations
│   └── versions/        # 001 (memory), 002 (auth), 003 (audit)
├── docker/              # Dockerfile
├── scripts/
│   └── test_api.py      # End-to-end test runner
├── .env                 # Local dev configuration
├── docker-compose.yml   # Infrastructure services
└── requirements.txt
```

## Celery Worker (Optional)

For async background embedding (decouples embedding from request thread):

```bash
celery -A app.workers.celery_app worker --loglevel=info
celery -A app.workers.celery_app beat --loglevel=info  # periodic tasks
```

Scheduled tasks:
- Every 6h: cleanup expired memories
- Every 12h: cleanup expired token blacklist

## License

MIT
