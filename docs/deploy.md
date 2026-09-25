# Deploy — Cloudflare Pages + Render

## Backend (Render free)

1. New Web Service from this GitHub repo.
2. Root directory: `backend` (or set Dockerfile path to `backend/Dockerfile`).
3. Runtime: Docker, or native Python:
   - Build: `pip install -r requirements.txt`
   - Start: `uvicorn app.main:app --host 0.0.0.0 --port $PORT`
4. Environment:
   - `OPENAI_API_KEY` (required)
   - `OPENAI_MODEL=gpt-4o-mini`
   - `CORS_ORIGINS=https://<your-pages-domain>.pages.dev,http://localhost:3001`
   - `SOLANA_RPC_URL` optional (custom RPC; otherwise public cluster endpoints)
5. Health check path: `/health`

If using `$PORT` on Render with Docker, change the CMD or set `PORT=8001` and map it in Render settings. Easiest: native Python start command with `$PORT`.

## Frontend (Cloudflare Pages)

1. New Pages project from the same repo.
2. Root directory: `frontend`
3. Build command: `npm ci && npm run build`
4. Build output: `out` (Next.js `output: 'export'`)
5. Environment:
   - `NEXT_PUBLIC_API_URL=https://<your-render-service>.onrender.com`

No Node server needed; static assets only.

## Local

```bash
cp .env.example .env
# set OPENAI_API_KEY

docker compose up --build
# API: http://localhost:8001

cd frontend && npm install && npm run dev
# UI: http://localhost:3001
```
