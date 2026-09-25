# Solana Explorer AI — Architecture

## Flow

1. User submits a transaction signature and cluster from the Next.js dashboard.
2. `POST /analyze` on FastAPI resolves the RPC URL (cluster public endpoint or `SOLANA_RPC_URL`).
3. `getTransaction` (jsonParsed) returns the confirmed transaction.
4. Decoder maps System / SPL Token / Compute Budget / ATA / Memo; unknown programs expose Anchor discriminator hex.
5. Log parser extracts `meta.err`, custom program errors, and Anchor error lines.
6. Gemini (`GEMINI_MODEL`, default `gemini-3.8-flash`) returns JSON: flow, error_summary, fixes.
   On 503/429/404 (retired) it tries `gemini-3.7-flash` → `gemini-3.5-flash-lite`
   and reports which model answered.
7. Dashboard renders status, AI panel, instruction timeline, errors, and logs.

## Stateless design

No database. Each request is independent. Suitable for Render free tier and Cloudflare Pages static export.

## Components

| Piece | Location |
|-------|----------|
| RPC client | `backend/app/solana/rpc.py` |
| Instruction decode | `backend/app/solana/decode.py` |
| Log / error extract | `backend/app/solana/logs.py` |
| Gemini explain | `backend/app/ai/explain.py` |
| API | `backend/app/main.py` |
| UI | `frontend/app/page.tsx` |

## Error handling

- Missing tx → 404
- RPC / Gemini transport failures → 502
- Missing or invalid `GEMINI_API_KEY` → 503
