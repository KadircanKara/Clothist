# Clothist

AI-native fashion meta-commerce platform. Aggregates products across retailers and
adds semantic search, AI review intelligence, and personalization on top.

This repo is the first vertical slice: scrape one retailer (H&M), store products
in Postgres, expose a keyword search API, render results in a Next.js UI.
See `PROJECT_PLAN.md` for the full CTO architecture document.

## Stack (this slice)

- **Frontend**: Next.js 15 (App Router) + TypeScript + Tailwind + shadcn/ui + TanStack Query
- **Backend**: FastAPI (Python 3.11+) + SQLAlchemy 2 (async) + asyncpg + Pydantic v2
- **Database**: Postgres 16 (local via docker-compose; Supabase in cloud)
- **Scraping**: httpx + selectolax, Tier-3 structured extraction (JSON-LD, `__NEXT_DATA__`)

## Layout

```
clothist/
├── apps/
│   ├── api/       # FastAPI backend
│   └── web/       # Next.js frontend
├── data/
│   └── seed/      # Hand-curated seed products
├── docker-compose.yml
├── package.json   # pnpm workspace root
└── PROJECT_PLAN.md
```

## Quickstart

```bash
# 1. One-time tooling
npm i -g pnpm
curl -LsSf https://astral.sh/uv/install.sh | sh

# 2. Env
cp .env.example .env

# 3. Database
pnpm db:up                       # docker compose up postgres

# 4. API
cd apps/api
uv sync
uv run alembic upgrade head
uv run python -m clothist_api.scripts.seed   # load seed data
uv run uvicorn clothist_api.main:app --reload

# 5. Web (separate terminal)
cd apps/web
pnpm install
pnpm dev
```

Open `http://localhost:3000` — search box should return seed data, and
`uv run python -m clothist_api.scripts.scrape_hm <listing-url>` will pull H&M
products into the DB.

## Status

MVP slice in progress. See `PROJECT_PLAN.md` §23 for what's intentionally out of scope.
