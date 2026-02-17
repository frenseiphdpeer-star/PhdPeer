# Contributing to PhD Timeline Intelligence Platform

Thank you for your interest in contributing to the PhD Timeline Intelligence Platform.

This guide is for everyone contributing to the project — especially **tech interns**. It covers setup, workflow, standards, and best practices in one place.

---

## Table of Contents

1. [What Is This Project?](#1-what-is-this-project)
2. [Repository Layout](#2-repository-layout)
3. [Documentation Flow: What to Read & in What Order](#3-documentation-flow-what-to-read--in-what-order)
4. [Prerequisites](#4-prerequisites)
5. [Initial Setup (First-Time)](#5-initial-setup-first-time)
6. [Daily Development Workflow](#6-daily-development-workflow)
7. [Code Standards & Conventions](#7-code-standards--conventions)
8. [Testing](#8-testing)
9. [Git & Commit Messages](#9-git--commit-messages)
10. [Pull Request Process](#10-pull-request-process)
11. [Where to Find Things](#11-where-to-find-things)
12. [Common Tasks](#12-common-tasks)
13. [Troubleshooting](#13-troubleshooting)
14. [Who to Ask & Questions](#14-who-to-ask--questions)
15. [License](#15-license)

---

## 1. What Is This Project?

The **PhD Timeline Intelligence Platform** helps manage and optimize PhD research timelines with:

- **Backend (Python/FastAPI):** REST API, PostgreSQL, document processing, analytics.
- **Frontend (React/TypeScript):** Vite, React, shadcn/ui, Tailwind — timelines, well-being check-ins, writing evolution.
- **Knowledge Graph (Python):** LangChain, Neo4j — document analysis and graph features.

As an intern you might work on backend API, frontend UI, tests, or docs. This guide applies to all of these.

---

## 2. Repository Layout

```
Phdpeer-Backend/
├── backend/              # FastAPI Python backend
│   ├── app/              # Application code (models, routes, services)
│   ├── alembic/          # Database migrations
│   ├── tests/            # Backend tests
│   ├── requirements.txt
│   └── .env.example
├── frontend/             # React + Vite + TypeScript
│   ├── src/
│   │   ├── api/          # API client (see frontend/src/api/README.md)
│   │   ├── components/   # UI components
│   │   ├── lib/          # Shared utilities (utils, wellness, etc.)
│   │   ├── pages/        # Page components
│   │   ├── data/         # Static/mock data
│   │   └── ...
│   ├── package.json
│   └── .env (create from VITE_API_BASE_URL)
├── knowledge_graph/      # LangChain + Neo4j pipeline
│   ├── requirements.txt
│   └── .env.example
├── resources/            # PRDs, architecture, docs
│   └── docs/             # development-setup.md, etc.
├── infra/                # Docker, deployment, scripts
├── Makefile              # Common commands (install, test, lint)
└── CONTRIBUTION.md       # This file (contribution guide)
```

---

## 3. Documentation Flow: What to Read & in What Order

Use this order to get from “new to the repo” to “productive on a specific area.” Only the listed docs are needed; other `.md` files in the repo are historical or one-off and can be ignored unless a maintainer points you to one.

| Order | Document | Purpose |
|-------|----------|---------|
| **1** | [README.md](README.md) (repo root) | High-level overview, tech stack, quick start. |
| **2** | **CONTRIBUTION.md** (this file) | How to contribute: setup, workflow, standards, PR process. |
| **3** | [resources/docs/development-setup.md](resources/docs/development-setup.md) | Detailed dev environment: prerequisites, clone, env, DB, backend run. |
| **4** | [backend/README.md](backend/README.md) | Backend structure, patterns (models, schemas, services, routes), running API, migrations. |
| **5** | [frontend/README.md](frontend/README.md) | Frontend stack (Vite, React, Tailwind), how to run and edit. |
| **6** | [resources/docs/api-guidelines.md](resources/docs/api-guidelines.md) | REST conventions, response format, status codes, auth. |
| **7** | [resources/README.md](resources/README.md) | Where PRDs, architecture, and docs live. |
| **8** | [resources/prds/product-vision.md](resources/prds/product-vision.md) | Product vision and requirements (optional but useful). |
| **9** | [resources/architecture/system-overview.md](resources/architecture/system-overview.md) | System architecture (optional). |
| **10** | [frontend/src/api/README.md](frontend/src/api/README.md) | How to use the frontend API client for backend calls. |
| **11** | [infra/README.md](infra/README.md) | Docker, deployment, env (when you need infra). |
| **12** | [DEMO_QUICK_REF.md](DEMO_QUICK_REF.md) | Demo users and how to run demos (when needed). |

**When working on a specific area:**

- **Frontend routing/guards:** `frontend/src/guards/README.md` or `frontend/src/guards/ROUTE_GUARDS_GUIDE.md`
- **Frontend state:** `frontend/src/store/README.md`
- **Frontend data flow:** `frontend/docs/data-flow-architecture.md`
- **Diagrams:** `resources/diagrams/README.md`

All other `.md` files (implementation summaries, fix logs, migration notes, one-off guides) are **not** part of this flow; use them only if a maintainer or issue references them.

---

## 4. Prerequisites

Install before starting:

| Tool | Purpose | Check |
|------|----------|--------|
| **Git** | Version control | `git --version` |
| **Python 3.11+** | Backend & knowledge_graph | `python --version` |
| **Node.js 18+ & npm** | Frontend | `node --version` && `npm --version` |
| **PostgreSQL 15+** | Database (or use Docker) | `psql --version` or Docker |
| **Docker & Docker Compose** | Optional: run DB and services | `docker --version` |

Recommended: an IDE (e.g. VS Code) and a REST client (Postman/Insomnia) for the API.

---

## 5. Initial Setup (First-Time)

### 5.1 Clone and Branch

1. **Fork** the repository on GitHub (if you contribute via fork).
2. **Clone** the repo (or your fork):
   ```bash
   git clone <repository-url>   # or your fork: git clone <your-fork-url>
   cd Phdpeer-Backend
   ```
3. **Create a branch** (use a descriptive name):
   ```bash
   git checkout -b feature/your-feature-name
   # or:  git checkout -b fix/short-bug-description
   ```

### 5.2 Backend

```bash
cd backend

# Virtual environment (recommended)
python -m venv .venv
# Windows:
.\.venv\Scripts\Activate.ps1
# macOS/Linux:
# source .venv/bin/activate

# Dependencies
pip install -r requirements.txt
# For dev (lint, type-check, tests):
pip install -r requirements-dev.txt

# Environment
cp .env.example .env
# Edit .env: set DATABASE_URL, SECRET_KEY, ALLOWED_ORIGINS, etc.

# Database (if using local PostgreSQL)
# Create DB if needed, then:
alembic upgrade head

# Run backend
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

- API: **http://localhost:8000**
- Swagger: **http://localhost:8000/docs**
- ReDoc: **http://localhost:8000/redoc**

### 5.3 Frontend

```bash
cd frontend

# Dependencies
npm install

# Optional: set API base URL (create .env if missing)
# echo "VITE_API_BASE_URL=http://localhost:8000/api/v1" > .env

# Run dev server
npm run dev
```

- App: **http://localhost:8080** (or the port Vite prints).

### 5.4 Knowledge Graph (Optional)

```bash
cd knowledge_graph
python -m venv .venv
# Activate venv (same as backend)
pip install -r requirements.txt
cp .env.example .env
# Fill in Neo4j and API keys in .env
```

### 5.5 Using Make (from repo root)

```bash
make install      # Backend deps
make setup-dev    # Copy .env from example
make dev-backend  # Run backend with uvicorn
make test         # Run tests
make lint         # Lint backend
make format       # Format backend (black)
```

**Quick start (with Docker):**

```bash
make install
make setup-dev
docker-compose up -d
```

See [Development Setup Guide](resources/docs/development-setup.md) for more.

---

## 6. Daily Development Workflow

1. **Pull latest** from `main` (or default branch):  
   `git pull origin main`
2. **Create/use a feature branch:**  
   `git checkout -b feature/your-task`
3. **Run the parts you need:**
   - Backend: `cd backend && uvicorn app.main:app --reload`
   - Frontend: `cd frontend && npm run dev`
4. **Make changes**, run tests and lint (see below).
5. **Commit** with clear messages (see [Git & Commit Messages](#8-git--commit-messages)).
6. **Push** and open a **Pull Request** (see [Pull Request Process](#9-pull-request-process)).

---

## 7. Code Standards & Conventions

### 7.1 Backend (Python)

- **Style:** PEP 8. Use **Black** for formatting and **flake8** for linting.
- **Types:** Use type hints; **mypy** is used for type checking.
- **Docstrings:** Use for public functions and classes.
- **Structure:** Prefer the existing patterns: models in `app/models/`, schemas in `app/schemas/`, business logic in `app/services/`, routes in `app/routes/`.

```bash
# Format
make format-backend   # or: cd backend && black app/

# Lint
make lint-backend    # or: cd backend && flake8 app/ && black --check app/ && mypy app/
```

### 7.2 Frontend (TypeScript/React)

- **Lint:** Run `npm run lint` in `frontend/` (ESLint).
- **Components:** Prefer functional components and hooks; use existing UI from `src/components/ui/`.
- **API:** Use the client in `src/api/` (see `frontend/src/api/README.md`); set `VITE_API_BASE_URL` in `.env` for the backend base URL.
- **Paths:** Use the `@/` alias (e.g. `@/components/ui/button`, `@/lib/utils`).

### 7.3 General

- Keep functions and files focused; avoid large “god” files.
- Name branches and commits so others can understand the change at a glance.

---

## 8. Testing

- **Backend:** Pytest. Run from repo root or backend:

  ```bash
  make test
  # or: cd backend && pytest
  # With coverage: cd backend && pytest --cov=app tests/
  ```

- **Frontend:** Use existing test setup if present; add tests for new behavior where possible.
- Write tests for new features; aim to **maintain test coverage above 80%** where practical.
- **Before opening a PR:** Run the relevant test suite and fix any failures.

---

## 9. Git & Commit Messages

### 9.1 Branch Naming

- `feature/short-description` — new feature
- `fix/short-description` — bug fix
- `docs/short-description` — documentation only
- `refactor/short-description` — refactor

### 9.2 Conventional Commits

Use a type and short description:

- `feat:` New feature
- `fix:` Bug fix
- `docs:` Documentation
- `style:` Formatting (no logic change)
- `refactor:` Refactor
- `test:` Tests
- `chore:` Build/tooling/other

Examples:

- `feat: add timeline export endpoint`
- `fix: correct RCI calculation for edge case`
- `docs: update CONTRIBUTION.md for interns`

### 9.3 What to Commit

- Do commit: source code, config examples (e.g. `.env.example`), docs, tests.
- Do not commit: `.env` (secrets), `node_modules/`, `__pycache__/`, virtualenvs, IDE-only config if not shared.

---

## 10. Pull Request Process

1. **Update from main:**  
   `git fetch origin main && git rebase origin/main` (or merge, per team preference).
2. **Ensure:**  
   - Tests pass (`make test` / `pytest`).  
   - Lint/format is clean (`make lint`, `make format`, `npm run lint`).
3. **Docs:**  
   Update README or docs if you changed setup, API, or behavior.
4. **CHANGELOG:**  
   If the project keeps a `CHANGELOG.md`, add an entry for user-facing changes.
5. **Open the PR:**  
   Clear title and description; link any issue; request review.
6. **Reviews:**  
   Address feedback; keep discussions professional and constructive.
7. **Merge:**  
   Follow maintainer instructions (e.g. squash or merge commit).

### Code Review Guidelines (for reviewers)

When reviewing PRs, check for:

- Code quality and readability
- Test coverage for new behavior
- Documentation updates where needed
- Performance implications
- Security considerations

---

## 11. Where to Find Things

| Need | Location |
|------|----------|
| Backend API entry | `backend/app/main.py` |
| Backend routes | `backend/app/routes/` |
| Backend models | `backend/app/models/` |
| Backend services | `backend/app/services/` |
| DB migrations | `backend/alembic/` |
| Frontend pages | `frontend/src/pages/` |
| Frontend UI components | `frontend/src/components/ui/` |
| Frontend API client | `frontend/src/api/` (see README there) |
| Shared frontend utils | `frontend/src/lib/` |
| Env examples | `backend/.env.example`, `knowledge_graph/.env.example` |
| Dev setup details | `resources/docs/development-setup.md` |
| Architecture/docs | `resources/`, `backend/README.md`, `frontend/README.md` |
| **Documentation flow** (what to read in order) | This file, [§3 Documentation Flow](#3-documentation-flow-what-to-read--in-what-order) |
| **RBAC (roles & permissions)** | Backend: `backend/app/core/security.py`, `backend/app/core/data_visibility.py`. Frontend: `frontend/src/lib/rbac.ts`, `frontend/src/store/auth-store.ts`, `frontend/src/guards/RoleGuard.tsx`, `frontend/src/hooks/usePermissions.ts`. |

---

## 12. Common Tasks

### Role-based access (RBAC)

- **Roles:** PhD Researcher, Supervisor, Institution Admin.
- **Permissions:** Timeline editing (Researcher only), Student risk visibility (Supervisor & Admin), Cohort aggregation (Admin only).
- **Backend:** All v1 endpoints that need auth use `get_current_user` (headers `X-User-Id`, `X-User-Role`). Use `require_permission(Permission.TIMELINE_EDIT)` or `require_roles(Role.SUPERVISOR)` etc. Data visibility: supervisors see only assigned students; admins see aggregated/anonymized data.
- **Frontend:** Set user/role in `auth-store`; API client sends RBAC headers from persisted auth. Use `ResearcherOnly`, `SupervisorOnly`, `AdminOnly` for dashboard routes. Use `useCanEditTimeline()`, `useCanViewStudentRisk()`, `useCanViewCohortAggregation()` to hide/show UI.
- **Routes:** `/dashboard` (Researcher), `/supervisor/dashboard` (Supervisor), `/admin/dashboard` (Admin).

### Add a new API endpoint (backend)

1. Add or reuse a model in `app/models/`.
2. Add Pydantic schemas in `app/schemas/`.
3. Add or reuse a service in `app/services/`.
4. Add route in `app/routes/` and register in `app/routes/__init__.py`.
5. If DB changed: `alembic revision --autogenerate -m "description"` then `alembic upgrade head`.

### Add a new frontend page

1. Add a component under `frontend/src/pages/`.
2. Register the route in the app router (e.g. in `App.tsx` or your router file).
3. Use `@/api` for HTTP calls and `@/components/ui/*` for UI.

### Run only backend tests in a folder

```bash
cd backend && pytest tests/path/to/test_file.py -v
```

### Reset local DB (example)

```bash
# Depends on your setup; often:
cd backend && alembic downgrade base && alembic upgrade head
# Or use Docker: docker-compose down -v && docker-compose up -d
```

---

## 13. Troubleshooting

| Issue | What to try |
|-------|-------------|
| Backend won’t start | Check `.env`, `DATABASE_URL`, and that PostgreSQL is running. Run `alembic upgrade head`. |
| Frontend build fails on `@/lib/...` | Ensure `frontend/src/lib/` exists and is not ignored by Git (see repo `.gitignore`). |
| CORS errors in browser | Ensure backend `ALLOWED_ORIGINS` includes your frontend origin (e.g. `http://localhost:8080`). |
| Import errors in Python | Activate the correct venv; run `pip install -r requirements.txt` (and `requirements-dev.txt` if needed). |
| Port already in use | Change port (e.g. `uvicorn ... --port 8001`) or stop the process using the port. |

If something isn’t covered here, check `resources/docs/development-setup.md` and the READMEs in `backend/`, `frontend/`, and `infra/`.

---

## 14. Who to Ask & Questions

- **Process / access:** Your internship mentor or project lead.
- **Code/design:** Open an issue or ask in the PR; tag maintainers if the repo uses them.
- **Urgent block:** Use the channel or contact your mentor uses (Slack, email, etc.).

Questions? Feel free to open an issue for discussion or reach out to the maintainers.

---

## 15. License

By contributing, you agree that your contributions will be licensed under the same license as the project.

---

## Summary Checklist for Interns

- [ ] Prerequisites installed (Git, Python 3.11+, Node/npm, PostgreSQL or Docker).
- [ ] Repo cloned; branch created for your work.
- [ ] Backend: venv, `pip install -r requirements.txt`, `.env` from `.env.example`, `alembic upgrade head`, server runs.
- [ ] Frontend: `npm install`, `npm run dev` runs; optional `VITE_API_BASE_URL` in `.env`.
- [ ] Before each PR: tests pass, lint/format clean, commit messages follow convention.
- [ ] PR has a clear description and is linked to an issue if applicable.

Thank you for contributing. If you find something unclear or outdated in this guide, consider suggesting an update in a PR.
