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
