# AI Director Agent

Autonomous AI Director for short-form video — sports-first creator self-serve SaaS.

The full architecture and build plan lives at `~/.claude/plans/i-want-to-build-dazzling-pelican.md` (v2). Read it before working on this repo.

## What's here

```
apps/
  api/          FastAPI control plane (auth, tenants, jobs, billing, R2 presigning)
  web/          Next.js 15 dashboard (App Router) + Clerk
workers/        Modal serverless workers (analyzer, director, renderers)
packages/
  intel/        Git submodule → github.com/winmican26-cmyk/OmegaClips
                145-module football intelligence + render engine
infra/          IaC, Modal app definitions, R2 lifecycle policies
```

## Local setup

```bash
# 1. Clone with submodules
git clone --recurse-submodules <this repo>
# Or if already cloned:
git submodule update --init --recursive

# 2. Copy env file
cp .env.example .env.local
# Fill in: Neon, Upstash, R2, Clerk, Stripe, Anthropic, Deepgram, Modal

# 3. Install deps
pnpm install                              # Node workspaces
uv sync                                   # Python workspaces (root + apps/api + workers)

# 4. DB migrations
cd apps/api && alembic upgrade head

# 5. Run dev servers (separate terminals)
pnpm --filter @aidirector/web dev         # Next.js on :3000
uv run --package api uvicorn api.main:app --reload --port 8000
modal serve workers/src/workers/modal_app.py
```

## Updating the OmegaClips engine

OmegaClips is the intelligence + render engine. Edits happen in the OmegaClips repo (clone at `c:\Users\mican\Documents\OmegaClips`), pushed to its master, then pulled into this repo's submodule:

```bash
cd packages/intel
git fetch origin && git checkout master && git pull
cd ../..
git add packages/intel
git commit -m "bump intel to <short-sha>"
```

## Conventions

- `tenant_id` on every row. Every API handler resolves the current tenant via the Clerk JWT and a single FastAPI dependency.
- Director Agent output is **always** strict Pydantic JSON. See `apps/api/schemas/director_plan.py`.
- Renderers read `RenderPlan` JSON, write a `RenderResult` row. Nothing else flows between them.
- OmegaClips' 272 tests must stay green when the submodule SHA bumps. Run them in CI for the submodule before accepting the bump.
