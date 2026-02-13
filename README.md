# Data Lens

Upload structured data (CSV, TSV, Excel, JSON) into PostgreSQL or MongoDB and analyze it through natural language chat powered by LLM.

## Features

- **Data Upload** - Parse and ingest CSV, TSV, Excel, and JSON files
- **Smart Routing** - Auto-recommend Postgres (tabular) or MongoDB (nested) based on data shape
- **Chat Analysis** - Ask questions about your data in natural language
- **Query Transparency** - See the SQL/MongoDB query behind every answer
- **Visualizations** - Bar charts, pie charts, and line graphs from query results
- **Data Browser** - Browse collections/tables with schema and descriptions
- **Follow-up Suggestions** - AI-generated follow-up questions after each query

## Architecture

```
Frontend (React + Vite)  →  Backend (FastAPI BFF)  →  LiteLLM Proxy → LLM
                                    ↕
                          PostgreSQL / MongoDB
```

## Quick Start

```bash
cp .env.example .env
# Fill in your credentials in .env

docker-compose up -d          # Start Postgres, MongoDB, LiteLLM
cd backend && pip install -r requirements.txt && uvicorn app.main:app --reload
cd frontend && npm install && npm run dev
```

## Configuration

All configuration is via environment variables. See `.env.example` for the full list.

## AI Tools Used

**Claude Code** used for project scaffolding and iterative development through phases. 
**Claude chat** used for general guidance on architectural options and approaches. 
**Junie** (PyCharm internal assistant) for scanning for potential connection/resource/memory leaks and security issues. 

## Interesting Challenges

**First-user bootstrap for invite-only registration.** The invite system creates a chicken-and-egg problem: you need a registered user to generate invite codes, but registration requires one. The solution checks whether any user exists in the database — if none do, the first registration is allowed without a code.

**LLM model display names.** The LiteLLM proxy uses alias names like "default" internally, but users need to see the actual model (e.g. "claude-sonnet-4-5-20250929"). Fetching from the `/model/info` endpoint and extracting the real model name from `litellm_params` solved this, with provider prefix stripping for clean display.

**Two-step upload with schema sniffing.** Uploading data isn't a single action — the backend first "sniffs" the file (detects columns, types, row count) and returns a preview, then the user confirms. The sniff result is cached in MongoDB with a 30-minute TTL so users can review before committing. This avoids silently ingesting malformed data.

**SQL generation safety.** The LLM generates SQL queries, which is inherently risky. The backend enforces read-only execution (SELECT only), parameterized execution, and query timeouts to prevent injection and runaway queries.

## What I'd Improve With More Time

- **Streaming responses.** Currently chat waits for the full LLM response. Server-sent events would make the experience feel much more responsive.
- **Role-based access control.** Every authenticated user currently has identical permissions. Admin roles for managing users, revoking invites, and viewing usage metrics would be valuable.
- **Query result caching.** Identical questions against the same dataset could return cached results, reducing LLM calls and database load.
- **Broader file formats.** Adding Parquet, JSON Lines, and direct database connections would broaden utility.
- **E2E tests.** The unit test suite is solid (101 tests passing) but lacks browser-level end-to-end and integration tests against real databases.
- **Observability.** Structured logging, request tracing, and LLM token usage tracking for production debugging and cost management.

## Design Decisions

**Dual-database architecture.** Structured relational data (users, sessions, invite codes) lives in PostgreSQL, while uploaded datasets and chat histories go to MongoDB for flexible document storage. Services interact through a repository layer that keeps them database-agnostic.

**LiteLLM proxy abstraction.** All LLM requests go through a LiteLLM proxy rather than calling provider APIs directly. This decouples the app from any specific provider, enables model aliasing, and makes switching models a config change rather than a code change.

**Invitation-only registration.** Single-use invite codes with 24-hour expiry limit who can access the system while still allowing organic growth through existing users.

**JWT authentication with environment-based secrets.** Secrets load from a `.env` file via Pydantic settings, keeping credentials out of code. The auth flow uses short-lived access tokens with bcrypt password hashing.
