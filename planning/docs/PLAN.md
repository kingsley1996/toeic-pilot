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

**Execution order differs from this list, deliberately.** The phases above describe
what the product contains. The order the work is actually done in — Learning Hub
and TOEIC Practice first, the AI layer last — is decided in
[`ROADMAP.md`](ROADMAP.md) §2, which also records what that ordering costs:
the riskiest part of the product stays unproven until roughly 70% of the way in.

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

## 9. Status and progress

Deliberately **not** in this document. `PLAN.md` is the product specification; a
status log mixed into it goes stale on contact and dilutes the "single source of
truth" claim made in section 6 (the problem `REVIEW-OPUS.md` §7h named).

Current progress, the sprint plan and the open task list live in one place:

**→ [`ROADMAP.md`](ROADMAP.md)**

Architecture decisions and their reasoning live in the ADRs:
[`ADR-001-DATA-MODEL.md`](../adr/ADR-001-DATA-MODEL.md) ·
[`PHASE2-AUDIO.md`](PHASE2-AUDIO.md) (audio, ADR-002) ·
[`ADR-004-IMAGES.md`](../adr/ADR-004-IMAGES.md) ·
[`ADR-005-CONTENT-TOOLING.md`](../adr/ADR-005-CONTENT-TOOLING.md)

