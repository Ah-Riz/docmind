from __future__ import annotations

import asyncio
import json
import logging
from typing import Any

from fastapi import HTTPException
from google import genai
from google.genai import types

from app.schemas import AiExplanation, DecodedInstruction, TxError

logger = logging.getLogger("solana-explorer-ai")

FALLBACK_MODELS = (
    "gemini-3.8-flash",
    "gemini-3.7-flash",
    "gemini-3.6-flash",
    "gemini-3.5-flash",
    "gemini-3.5-flash-lite",
    "gemini-3.1-flash-lite",
)

SYSTEM_PROMPT = """You are a Solana developer tools engineer helping debug transactions.
Given decoded instructions, logs, and errors, respond with JSON only:
{
  "flow": "2-5 sentence explanation of what the transaction tried to do, step by step",
  "error_summary": "concise explanation of why it failed, or 'Transaction succeeded.' if status is success",
  "fixes": ["actionable fix recommendation", "..."]
}
Be specific to Solana/Anchor/SPL. No markdown. No prose outside JSON."""


def _payload(
    signature: str,
    status: str,
    instructions: list[DecodedInstruction],
    logs: list[str],
    errors: list[TxError],
) -> dict[str, Any]:
    return {
        "signature": signature,
        "status": status,
        "instructions": [i.model_dump() for i in instructions],
        "logs": logs[-40:],
        "errors": [e.model_dump() for e in errors],
    }


def _model_chain(primary: str) -> list[str]:
    ordered: list[str] = []
    for name in (primary.strip(), *FALLBACK_MODELS):
        if name and name not in ordered:
            ordered.append(name)
    return ordered


def _should_try_next_model(exc: BaseException) -> bool:
    text = str(exc).lower()
    code = getattr(exc, "code", None) or getattr(exc, "status_code", None)
    if code in (404, 429, 503):
        return True
    markers = (
        "503",
        "429",
        "404",
        "unavailable",
        "high demand",
        "resource_exhausted",
        "resource exhausted",
        "model_capacity_exhausted",
        "not_found",
        "no longer available",
    )
    return any(m in text for m in markers)


def _parse_ai_json(content: str) -> AiExplanation:
    try:
        data = json.loads(content or "{}")
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=502, detail="Gemini returned invalid JSON") from exc

    fixes = data.get("fixes") or []
    if isinstance(fixes, str):
        fixes = [fixes]
    if not isinstance(fixes, list):
        fixes = []

    return AiExplanation(
        flow=str(data.get("flow") or "Unable to summarize transaction flow."),
        error_summary=str(data.get("error_summary") or ""),
        fixes=[str(f) for f in fixes],
        model="",  # filled by caller
        fallback_used=False,
    )


async def explain_transaction(
    *,
    api_key: str,
    model: str,
    signature: str,
    status: str,
    instructions: list[DecodedInstruction],
    logs: list[str],
    errors: list[TxError],
) -> AiExplanation:
    if not api_key:
        raise HTTPException(
            status_code=503,
            detail="GEMINI_API_KEY is not configured on the server.",
        )

    client = genai.Client(api_key=api_key)
    user_content = json.dumps(
        _payload(signature, status, instructions, logs, errors),
        default=str,
    )
    chain = _model_chain(model)
    primary = chain[0]
    last_exc: BaseException | None = None
    tried: list[str] = []

    for idx, candidate in enumerate(chain):
        tried.append(candidate)
        try:
            resp = await client.aio.models.generate_content(
                model=candidate,
                contents=user_content,
                config=types.GenerateContentConfig(
                    system_instruction=SYSTEM_PROMPT,
                    temperature=0.2,
                    response_mime_type="application/json",
                ),
            )
        except Exception as exc:
            last_exc = exc
            if _should_try_next_model(exc) and idx < len(chain) - 1:
                logger.warning("Gemini model %s unavailable (%s); trying next", candidate, exc)
                await asyncio.sleep(0.4)
                continue
            raise HTTPException(status_code=502, detail=f"Gemini request failed: {exc}") from exc

        content = getattr(resp, "text", None) or "{}"
        explanation = _parse_ai_json(content)
        explanation.model = candidate
        explanation.fallback_used = candidate != primary
        return explanation

    raise HTTPException(
        status_code=502,
        detail=(
            f"Gemini unavailable for models tried: {', '.join(tried)}. "
            f"Last error: {last_exc}"
        ),
    )
