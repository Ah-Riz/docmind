from __future__ import annotations

import json
from typing import Any

from fastapi import HTTPException
from openai import AsyncOpenAI

from app.schemas import AiExplanation, DecodedInstruction, TxError


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
            detail="OPENAI_API_KEY is not configured on the server.",
        )

    client = AsyncOpenAI(api_key=api_key)
    user_content = json.dumps(
        _payload(signature, status, instructions, logs, errors),
        default=str,
    )

    try:
        resp = await client.chat.completions.create(
            model=model,
            temperature=0.2,
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_content},
            ],
        )
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"OpenAI request failed: {exc}") from exc

    content = resp.choices[0].message.content or "{}"
    try:
        data = json.loads(content)
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=502, detail="OpenAI returned invalid JSON") from exc

    fixes = data.get("fixes") or []
    if isinstance(fixes, str):
        fixes = [fixes]
    if not isinstance(fixes, list):
        fixes = []

    return AiExplanation(
        flow=str(data.get("flow") or "Unable to summarize transaction flow."),
        error_summary=str(data.get("error_summary") or ""),
        fixes=[str(f) for f in fixes],
    )
