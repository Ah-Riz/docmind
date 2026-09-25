# Deploy — Cloudflare Pages + Render

## Backend (Render)

Connect the GitHub repo as a Web Service (not via this Actions workflow).

1. Root directory: `backend` (or Dockerfile `backend/Dockerfile`).
2. Native Python:
   - Build: `pip install -r requirements.txt`
   - Start: `uvicorn app.main:app --host 0.0.0.0 --port $PORT`
3. Environment on Render:
   - `GEMINI_API_KEY` (required — from https://aistudio.google.com/apikey)
   - `GEMINI_MODEL=gemini-3.8-flash` (falls back automatically if overloaded)
   - `CORS_ORIGINS=https://docmind.ahmadmaulana.net,https://docmind-dbw.pages.dev,http://localhost:3001`
   - `SOLANA_RPC_URL` optional
4. Health check: `/health`

Remove any old `OPENAI_API_KEY` / `OPENAI_MODEL` env vars.

Production Pages URL: **https://docmind-dbw.pages.dev** (and custom domain if configured). Keep `CORS_ORIGINS` aligned with the production host.

## Frontend (GitHub Actions → Cloudflare Pages)

On every push to `main`, [`.github/workflows/ci.yml`](../.github/workflows/ci.yml):

1. Runs backend pytest
2. Builds `frontend` with `NEXT_PUBLIC_API_URL`
3. Ensures Pages project **`docmind`** exists, then deploys `frontend/out` via Wrangler

### GitHub Actions secrets

| Secret | Used by |
|--------|---------|
| `CLOUDFLARE_API_TOKEN` | Wrangler Pages deploy |
| `CLOUDFLARE_ACCOUNT_ID` | Wrangler Pages deploy |
| `NEXT_PUBLIC_API_URL` | Next.js build (Render API base URL) |

Backend secrets (`GEMINI_API_KEY`, etc.) belong on Render; they are unused by the Pages job.

Cloudflare API token needs **Account → Cloudflare Pages → Edit**.

Pull requests run pytest only (no Pages deploy).

## Local

```bash
cp .env.example .env
# set GEMINI_API_KEY

docker compose up --build
# API: http://localhost:8001

cd frontend && npm install && npm run dev
# UI: http://localhost:3001
```
