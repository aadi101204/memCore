# memCore - Memory-as-a-Service for AI Agents

A production-grade backend platform that provides persistent, queryable, and multi-scope memory for AI agents.

## Project Overview

MaaS (Memory-as-a-Service) enables AI agents to:
- Store and retrieve long-term semantic memory using embeddings
- Manage short-term working memory with fast access
- Share knowledge across multiple agents
- Resolve memory conflicts intelligently
- Handle memory lifecycle with TTL and decay mechanisms

## Architecture

```
Agents → API Gateway → Memory Services
                    ↓
        ┌──────────┼──────────┐
        ↓          ↓          ↓
    Postgres   Vector DB   Redis
   (metadata) (embeddings) (working memory)
```

## Tech Stack

- **Language**: Python 3.11+
- **Framework**: FastAPI
- **Metadata Store**: PostgreSQL
- **Vector Store**: Qdrant / pgvector
- **Working Memory**: Redis
- **Async Jobs**: Celery / RQ
- **Containerization**: Docker
- **Observability**: Prometheus + Grafana

## Project Structure

```
memCore/
├── app/
│   ├── configs/        # Application configuration
│   ├── models/         # Database schemas and Pydantic models
│   ├── repositories/   # Database interaction layer
│   ├── services/       # Business logic
│   ├── controllers/    # Route handlers
│   ├── middlewares/    # Custom middlewares
│   ├── validators/     # Request/response validators
│   ├── interfaces/     # Abstract interfaces and protocols
│   ├── decorators/     # Custom decorators
│   └── utils/          # Utility functions
├── tests/              # Test suite
├── scripts/            # Utility scripts
├── docker/             # Docker configuration
└── requirements.txt    # Python dependencies
```

## Getting Started

### Prerequisites

- Python 3.11+
- Docker and Docker Compose
- PostgreSQL (or via Docker)
- Redis (or via Docker)

### Installation

1. Clone the repository:
```bash
git clone <repository-url>
cd memCore
```

2. Create virtual environment:
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. Install dependencies:
```bash
pip install -r requirements.txt
```

4. Set up environment variables:
```bash
cp .env.example .env
# Edit .env with your configuration
```

5. Start services with Docker:
```bash
docker-compose up -d
```

6. Run the application:
```bash
uvicorn app.main:app --reload
```

## API Endpoints

### Memory Operations
- `POST /memory` - Write new memory
- `POST /memory/search` - Search memories
- `GET /memory/{id}` - Get specific memory
- `DELETE /memory/{id}` - Delete memory

### Working Memory
- `PUT /working/{session}` - Update working memory
- `GET /working/{session}` - Get working memory

### Conflict Resolution
- `POST /memory/resolve` - Resolve memory conflicts

## Features

- ✅ Semantic memory with vector embeddings
- ✅ Fast working memory via Redis
- ✅ Hybrid retrieval (semantic + metadata + recency)
- ✅ Multi-agent namespacing (agent/team/org/global)
- ✅ Conflict detection and resolution
- ✅ TTL and memory decay
- ✅ Async embedding pipeline
- ✅ Observability and metrics

## Development

Run tests:
```bash
pytest
```

Format code:
```bash
black app/
isort app/
```

Lint:
```bash
flake8 app/
mypy app/
```

## Deployment

See [deployment documentation](docs/deployment.md) for detailed instructions on deploying to Fly.io, Render, or Railway.

## License

MIT

## Resume Value

This project demonstrates:
- Distributed backend design
- Hybrid storage architecture
- Async processing patterns
- AI infrastructure patterns
- Multi-tenant API architecture
