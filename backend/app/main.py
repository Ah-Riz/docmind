from __future__ import annotations

import logging

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from app.ai.explain import explain_transaction
from app.config import gemini_key_is_plausible, settings
from app.schemas import AnalyzeRequest, AnalyzeResponse
from app.solana.decode import decode_transaction
from app.solana.logs import extract_errors, status_from_meta
from app.solana.rpc import get_transaction

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("solana-explorer-ai")

app = FastAPI(title="Solana Explorer AI", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list or ["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health() -> dict[str, object]:
    """Liveness for Render. Always 200 when the process is up; Gemini is checked at /analyze."""
    return {
        "status": "ok",
        "service": "solana-explorer-ai",
        "gemini_configured": gemini_key_is_plausible(settings.gemini_api_key),
    }


@app.post("/analyze", response_model=AnalyzeResponse)
async def analyze(body: AnalyzeRequest) -> AnalyzeResponse:
    if not settings.gemini_api_key:
        raise HTTPException(
            status_code=503,
            detail="GEMINI_API_KEY is not configured on the server.",
        )
    if not gemini_key_is_plausible(settings.gemini_api_key):
        raise HTTPException(
            status_code=503,
            detail=(
                "GEMINI_API_KEY is not a valid Google AI Studio key. "
                "Create a key at https://aistudio.google.com/apikey "
                "(typically starts with AIza), set it on Render, and redeploy."
            ),
        )

    rpc_url = settings.rpc_for(body.cluster)
    logger.info("analyze sig=%s cluster=%s", body.signature, body.cluster)

    tx = await get_transaction(rpc_url, body.signature.strip())
    instructions, accounts = decode_transaction(tx)
    logs, errors = extract_errors(tx)
    status = status_from_meta(tx)

    meta = tx.get("meta") or {}
    ai = await explain_transaction(
        api_key=settings.gemini_api_key,
        model=settings.gemini_model,
        signature=body.signature,
        status=status,
        instructions=instructions,
        logs=logs,
        errors=errors,
    )

    return AnalyzeResponse(
        signature=body.signature,
        cluster=body.cluster,
        status=status,  # type: ignore[arg-type]
        slot=tx.get("slot"),
        fee_lamports=meta.get("fee"),
        compute_units=meta.get("computeUnitsConsumed"),
        accounts=accounts,
        instructions=instructions,
        logs=logs,
        errors=errors,
        ai=ai,
    )
