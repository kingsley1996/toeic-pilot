# TOEIC AI

## 1. Vision

TOEIC AI is an AI-powered English learning platform designed to help learners improve their English skills and achieve their target TOEIC score through personalized AI coaching.

Unlike traditional TOEIC applications that only provide practice questions, TOEIC AI continuously analyzes learning progress, remembers user weaknesses, and adapts study plans based on individual performance.

The platform combines daily English learning with structured TOEIC preparation in a single learning experience.

---

## 2. Product Goals

The MVP aims to validate four core capabilities:

- Daily English learning
- TOEIC practice
- AI-powered study planning
- AI learning assistant

The platform should demonstrate production-level AI Engineering techniques rather than simply integrating an LLM chatbot.

---

## 3. MVP Scope

The MVP contains four product modules.

### 1. Learning Hub

Daily learning features.

- Dictation
- Vocabulary by topic

### 2. TOEIC Practice

Exam preparation.

- Practice by Part
- Full Mock Test

### 3. AI Study Planner

Generate personalized learning plans based on

- Current score
- Target score
- Available study time

Update plans continuously according to user progress.

### 4. AI Coach

An intelligent assistant capable of

- Explaining grammar
- Explaining vocabulary
- Reviewing completed exercises
- Identifying strengths and weaknesses
- Answering TOEIC-related questions

---

## 4. AI Capabilities

The project demonstrates the following AI Engineering concepts.

- Prompt Engineering
- Structured Output
- Tool Calling
- Retrieval Augmented Generation (RAG)
- Learning Memory
- LLM Routing
- Evaluation
- Observability

Each feature should reuse these capabilities instead of implementing independent AI logic.

---

## 5. System Overview

The project consists of five major layers.

Frontend

- Next.js

Backend

- FastAPI

Database

- PostgreSQL
- pgvector
- Redis

AI Layer

- LLM Router
- Prompt Engine
- RAG Engine
- Tool Registry
- Memory Service

Infrastructure

- Docker
- Docker Compose

---

## 6. Development Strategy

Development follows a specification-driven workflow.

PLAN.md serves as the single source of truth.

Implementation is divided into independent Epics.

Each Epic must be completed before moving to the next.

Claude Code (or Codex) should never implement features outside the current Epic.

---

## 7. Development Phases

Phase 1

Project scaffolding

- Monorepo
- Docker
- CI
- Basic authentication
- Shared packages

Phase 2

Learning Hub

- Vocabulary
- Dictation

Phase 3

TOEIC Practice

- Practice by Part
- Full Test

Phase 4

AI Layer

- RAG
- Structured Output
- Study Planner
- AI Coach

Phase 5

Analytics

- Dashboard
- Progress
- Learning Memory

Phase 6

Production

- Evaluation
- Monitoring
- Deployment

---

## 8. Success Criteria

The MVP is considered complete when

- Users can study English daily.
- Users can practice complete TOEIC exams.
- AI generates personalized study plans.
- AI explains grammar and vocabulary with contextual knowledge.
- AI analyzes user progress.
- The project demonstrates modern AI Engineering architecture suitable for production deployment.

---

## 9. Current status (2026-08-07)

- **Date:** 2026-08-07
- **Actions performed:**
	- Added project environment file: `.env` at repository root.
	- Updated `docker/docker-compose.yml` to make the `apps/api` volume writable (removed `:ro`).
	- Started the full stack with Docker Compose (Postgres, Redis, API, Web).
- **Containers / health:**
	- `postgres` (pgvector) — healthy
	- `redis` — healthy
	- `api` — running (Uvicorn, reload enabled)
	- `web` — running (Next.js dev server)
- **Local URLs:**
	- API: http://localhost:8000
	- Web: http://localhost:3000
- **Commands executed:**
	- `docker compose -f docker/docker-compose.yml up --build -d`
	- `docker compose -f docker/docker-compose.yml ps`
	- `docker logs docker-api-1 --tail 200`
	- `docker logs docker-web-1 --tail 200`
- **Notes / Next steps:**
	- Run API tests: `cd apps/api && python -m pytest -q` (requires Python deps).
	- Optionally tail logs: `docker compose -f docker/docker-compose.yml logs -f`.
	- Implement any DB migrations if needed (alembic).

---

## 10. Code progress (quick audit)

Summary of implemented functionality (codebase state):

- **Monorepo & tooling**: repository structured as monorepo with `apps/`, `packages/`, `docker/` and a `pnpm` workspace for frontend and shared packages.
- **Infrastructure**: Docker + Docker Compose configured for `postgres` (pgvector), `redis`, `api`, and `web`. `docker-compose` builds and runs the stack locally.
- **API (FastAPI)**:
	- Project scaffolded under `apps/api` with `pyproject.toml`, `uv`/uvicorn-based container image, and a working development virtualenv created at container startup.
	- Basic routes implemented: `health` (`/health`, `/ready`) and `auth` endpoints (`/api/v1/auth/register`, `/api/v1/auth/login`, `/api/v1/auth/me`).
	- `User` model implemented (`apps/api/app/models/user.py`) with UUID PK, email, hashed password, and created_at.
	- Security utilities: password hashing/verification and JWT creation/decoding (`app/core/security.py`).
	- Dependency for current user retrieval with bearer token support (`app/api/deps.py`).
	- Database connectivity via SQLAlchemy and `settings` configured (`app/core/database.py`, `app/core/config.py`).
	- Tests: basic health test present and passing inside the container (`apps/api/tests/test_health.py`).

- **Web (Next.js)**:
	- Frontend scaffold under `apps/web` using Next.js 16 and Turbopack.
	- Auth UI pages implemented: `/login`, `/register`, and a protected `/dashboard` that calls the API `me` endpoint.
	- Shared types/utilities consumed from `packages/shared`.

- **AI layer & product features:**
	- `apps/api/app/ai` exists as a placeholder — full AI capabilities (LLM router, RAG, prompt engine, memory service) are not yet implemented (Phase 4).
	- Learning modules, TOEIC practice, study planner, and AI coach functionalities are not implemented yet (Phase 2–4 work remaining).

Open items / Suggested next steps:

- Implement Alembic migrations and run migrations as part of startup (there is an `alembic/` folder with initial migration). Ensure migrations are applied in the `api` container on boot when required.
- Add seed data or admin account creation for dev convenience.
- Implement core Phase 2 features (Learning Hub) and Phase 3 (TOEIC Practice) on backend + frontend.
- Design and implement AI layer (Phase 4): RAG, LLM router, prompt engine, memory, tool registry.
- Add CI (tests, linting) and automated Docker image builds.
- Improve observability (metrics, tracing) and production deployment configuration.

Test & verification performed during this audit:

- Started Docker Compose stack and confirmed services healthy.
- Ran `pytest` inside the running `api` container: `1 passed, 2 warnings`.

