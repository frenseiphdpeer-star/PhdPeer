# PhD Timeline Intelligence Platform

A production-ready platform for managing and optimizing PhD research timelines with intelligent insights, document processing, and well-being tracking.

---

## Table of Contents

- [Overview](#overview)
- [Features](#features)
- [Tech Stack](#tech-stack)
- [Project Structure](#project-structure)
- [Prerequisites](#prerequisites)
- [Installation](#installation)
- [Configuration](#configuration)
- [Running the Application](#running-the-application)
- [API Documentation](#api-documentation)
- [Testing](#testing)
- [Documentation](#documentation)
- [Contributing](#contributing)
- [License](#license)

---

## Overview

The **PhD Timeline Intelligence Platform** helps PhD students, advisors, and institutions:

- **Manage research timelines** — Draft and commit timelines, track milestones and stages.
- **Process documents** — Upload proposals, theses, and papers; extract text from PDF/DOCX.
- **Track progress** — Record progress events, analytics snapshots, and journey assessments.
- **Support well-being** — Well-being check-ins, Research Climate Index (RCI), and recommendations.
- **Writing evolution** — Baseline and track academic writing development (frontend feature).

The system consists of a **FastAPI backend**, a **React frontend**, and an optional **knowledge-graph pipeline** (LangChain + Neo4j) for document analysis.

---

## Features

| Area | Description |
|------|-------------|
| **Timeline management** | Create draft timelines, commit them, manage stages and milestones. |
| **Document upload** | Upload PDF/DOCX; backend extracts text and stores artifacts. |
| **Progress tracking** | Log progress events; analytics and journey health engines. |
| **Well-being** | Quarterly check-ins, RCI score, signals, continuity reports, recommendations. |
| **Writing evolution** | Establish writing baseline, checkpoints, and certificates (frontend). |
| **API** | REST API with CORS and OpenAPI (Swagger/ReDoc). |
| **RBAC** | Roles: PhD Researcher, Supervisor, Institution Admin. Timeline editing (Researcher), student risk visibility (Supervisor/Admin), cohort aggregation (Admin). Separate dashboard routes and permission guards. |

---

## Tech Stack

| Layer | Technologies |
|-------|--------------|
| **Backend** | Python 3.11+, FastAPI, SQLAlchemy 2, PostgreSQL 15+, Alembic, Pydantic |
| **Frontend** | Node 18+, Vite, React 18, TypeScript, shadcn/ui, Tailwind CSS |
| **Knowledge graph** | Python, LangChain, Neo4j, PyMuPDF (optional) |
| **Infrastructure** | Docker & Docker Compose, PostgreSQL container |

---

## Project Structure

```
Phdpeer-Backend/
├── backend/                    # FastAPI Python backend
│   ├── app/
│   │   ├── main.py             # Application entry point
│   │   ├── config.py           # Settings
│   │   ├── database.py         # DB connection & session
│   │   ├── models/             # SQLAlchemy models
│   │   ├── routes/             # API routes
│   │   ├── schemas/            # Pydantic schemas
│   │   ├── services/           # Business logic
│   │   ├── orchestrators/      # Workflow coordination
│   │   └── utils/              # Helpers (e.g. text extraction)
│   ├── alembic/                # Database migrations
│   ├── tests/                  # Backend tests
│   ├── requirements.txt
│   ├── requirements-dev.txt
│   └── .env.example
├── frontend/                   # React + Vite + TypeScript
│   ├── src/
│   │   ├── api/                # API client
│   │   ├── components/         # UI components (incl. shadcn/ui)
│   │   ├── lib/                # Shared utilities
│   │   ├── pages/              # Page components
│   │   └── data/               # Static/mock data
│   ├── package.json
│   └── .env                    # VITE_API_BASE_URL (create locally)
├── knowledge_graph/            # LangChain + Neo4j (optional)
│   ├── requirements.txt
│   └── .env.example
├── resources/                  # Documentation
│   ├── docs/                   # Development setup, API guidelines
│   ├── prds/                   # Product requirements
│   ├── architecture/           # System overview
│   └── diagrams/
├── infra/                      # Docker, deployment, scripts
├── Makefile                    # install, test, lint, migrate, etc.
├── docker-compose.yml          # PostgreSQL + backend
├── CONTRIBUTION.md             # Contribution guide (setup, workflow, PRs)
├── DEMO_QUICK_REF.md           # Demo users and run instructions
└── README.md                   # This file
```

---

## Prerequisites

| Tool | Version | Purpose |
|------|---------|---------|
| **Git** | Latest | Version control |
| **Python** | 3.11+ | Backend and knowledge_graph |
| **Node.js** | 18+ | Frontend (npm comes with it) |
| **PostgreSQL** | 15+ | Database (or use Docker) |
| **Docker & Docker Compose** | Latest | Optional: run DB and backend in containers |

Check versions:

```bash
git --version
python --version
node --version
npm --version
# Optional:
docker --version
docker compose version
```

---

## Installation

### 1. Clone the repository

```bash
git clone https://github.com/Uttkarsh700/Phdpeer-Backend.git
cd Phdpeer-Backend
```

(Or use your fork or the upstream repo URL.)

### 2. Backend

```bash
cd backend

# Create and activate a virtual environment
python -m venv .venv

# Windows (PowerShell):
.\.venv\Scripts\Activate.ps1

# macOS / Linux:
# source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# For development (lint, type-check, tests):
pip install -r requirements-dev.txt

# Copy environment template and edit
cp .env.example .env
# Set DATABASE_URL, SECRET_KEY, ALLOWED_ORIGINS (see Configuration)

# Run database migrations
alembic upgrade head
```

### 3. Frontend

```bash
cd frontend

npm install

# Optional: point to backend API (create .env if missing)
# VITE_API_BASE_URL=http://localhost:8000/api/v1
```

### 4. Knowledge graph (optional)

Only if you need the LangChain/Neo4j pipeline:

```bash
cd knowledge_graph
python -m venv .venv
# Activate as above
pip install -r requirements.txt
cp .env.example .env
# Set Neo4j and API keys in .env
```

---

## Configuration

### Backend (`backend/.env`)

| Variable | Description | Example |
|----------|-------------|---------|
| `APP_NAME` | Application name | `PhD Timeline Intelligence Platform` |
| `DEBUG` | Debug mode | `True` (dev) / `False` (prod) |
| `ENVIRONMENT` | Environment | `development` / `staging` / `production` |
| `DATABASE_URL` | PostgreSQL connection URL | `postgresql://user:pass@localhost:5432/phd_timeline_db` |
| `DATABASE_ECHO` | Log SQL queries | `False` |
| `SECRET_KEY` | JWT signing key | Use `secrets.token_urlsafe(32)` |
| `ALGORITHM` | JWT algorithm | `HS256` |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | Token expiry | `30` |
| `ALLOWED_ORIGINS` | CORS origins (JSON array) | `["http://localhost:3000","http://localhost:8080"]` |
| `API_V1_PREFIX` | API path prefix | `/api/v1` |

### Frontend (`frontend/.env`)

| Variable | Description | Example |
|----------|-------------|---------|
| `VITE_API_BASE_URL` | Backend API base URL | `http://localhost:8000/api/v1` |

### Docker Compose

Default values in `docker-compose.yml`:

- **PostgreSQL:** user `postgres`, password `password`, DB `phd_timeline_db`, port `5432`.
- **Backend:** port `8000`, `DATABASE_URL` points at the `postgres` service.

---

## Running the Application

### Option A: Local development (backend + frontend)

**Terminal 1 — Backend:**

```bash
cd backend
# Activate venv if not already
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

**Terminal 2 — Frontend:**

```bash
cd frontend
npm run dev
```

- **Backend API:** http://localhost:8000  
- **Swagger UI:** http://localhost:8000/docs  
- **ReDoc:** http://localhost:8000/redoc  
- **Frontend:** http://localhost:8080 (or the port Vite prints)

### Option B: Docker Compose (PostgreSQL + backend)

From the repo root:

```bash
docker compose up -d
```

- Backend: http://localhost:8000  
- PostgreSQL: `localhost:5432` (use same credentials as in `docker-compose.yml` for local tools).

Run migrations against the containerized DB:

```bash
cd backend
# Ensure .env DATABASE_URL points at postgres (e.g. postgresql://postgres:password@localhost:5432/phd_timeline_db)
alembic upgrade head
```

### Make commands (from repo root)

| Command | Description |
|---------|-------------|
| `make help` | List all targets |
| `make install` | Install backend dev dependencies |
| `make setup-dev` | Copy `backend/.env.example` to `backend/.env` |
| `make up` | Start Docker Compose |
| `make down` | Stop Docker Compose |
| `make dev-backend` | Run backend with uvicorn (reload) |
| `make test` | Run backend tests |
| `make lint` | Lint backend (flake8, black, mypy) |
| `make format` | Format backend with black |
| `make migrate` | Run `alembic upgrade head` |

---

## Role-based access (RBAC)

- **Roles:** PhD Researcher, Supervisor, Institution Admin.
- **Backend:** Auth via headers `X-User-Id` and `X-User-Role` (or JWT when implemented). Permissions: `timeline_edit` (Researcher), `student_risk_visibility` (Supervisor & Admin), `cohort_aggregation` (Admin). Supervisors see only assigned students; admins see aggregated anonymized data. Endpoints: `/api/v1/supervisor/students`, `/api/v1/admin/cohort`.
- **Frontend:** Auth store holds user and role; route guards (`ResearcherOnly`, `SupervisorOnly`, `AdminOnly`) protect `/dashboard`, `/supervisor/dashboard`, `/admin/dashboard`. Hooks: `useCanEditTimeline()`, `useCanViewStudentRisk()`, `useCanViewCohortAggregation()`.

---

## API Documentation

Once the backend is running:

- **Swagger UI:** http://localhost:8000/docs  
- **ReDoc:** http://localhost:8000/redoc  

For REST conventions, response format, and auth, see [resources/docs/api-guidelines.md](resources/docs/api-guidelines.md).

---

## Testing

**Backend (pytest):**

```bash
cd backend
pytest
# With coverage:
pytest --cov=app tests/
```

Or from repo root:

```bash
make test
```

---

## Documentation

- **[CONTRIBUTION.md](CONTRIBUTION.md)** — Contribution guide: setup, workflow, code standards, Git, PR process, troubleshooting. Start here if you are contributing or onboarding.
- **Documentation flow** — CONTRIBUTION.md includes a [documentation flow](CONTRIBUTION.md#3-documentation-flow-what-to-read--in-what-order) that lists which docs to read and in what order (e.g. development-setup, backend README, frontend README, API guidelines).
- **[resources/](resources/)** — PRDs, architecture, and guides under `resources/docs/`, `resources/prds/`, `resources/architecture/`.
- **[backend/README.md](backend/README.md)** — Backend structure, patterns, migrations, and run instructions.
- **[frontend/README.md](frontend/README.md)** — Frontend stack and how to run/edit.
- **[DEMO_QUICK_REF.md](DEMO_QUICK_REF.md)** — Demo users and how to run demos.

---

## Contributing

1. Read [CONTRIBUTION.md](CONTRIBUTION.md) for setup, workflow, and PR process.
2. Fork the repo, create a branch (`feature/...` or `fix/...`), make changes, run tests and lint.
3. Open a Pull Request against the target repository.

By contributing, you agree that your contributions will be licensed under the same license as the project.

---

## License

[Add your license here]
