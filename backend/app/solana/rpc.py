from __future__ import annotations

from typing import Any

import httpx
from fastapi import HTTPException

DEFAULT_COMMITMENT = "confirmed"


async def get_transaction(rpc_url: str, signature: str) -> dict[str, Any]:
    payload = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "getTransaction",
        "params": [
            signature,
            {
                "encoding": "jsonParsed",
                "maxSupportedTransactionVersion": 0,
                "commitment": DEFAULT_COMMITMENT,
            },
        ],
    }
    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            resp = await client.post(rpc_url, json=payload)
            resp.raise_for_status()
        except httpx.HTTPError as exc:
            raise HTTPException(status_code=502, detail=f"Solana RPC request failed: {exc}") from exc

    body = resp.json()
    if "error" in body:
        raise HTTPException(status_code=502, detail=f"Solana RPC error: {body['error']}")

    result = body.get("result")
    if result is None:
        raise HTTPException(
            status_code=404,
            detail="Transaction not found. Check the signature and cluster.",
        )
    return result
