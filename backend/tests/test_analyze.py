from __future__ import annotations

import json
from unittest.mock import AsyncMock, patch

import httpx
import respx
from fastapi.testclient import TestClient

# Ensure settings load with a key before app import paths rebind
import os

os.environ.setdefault("OPENAI_API_KEY", "test-key-not-real")

from app.config import settings
from app.main import app

settings.openai_api_key = "test-key-not-real"

client = TestClient(app)

SAMPLE_TX = {
    "slot": 123,
    "transaction": {
        "message": {
            "accountKeys": [
                {"pubkey": "Sender1111111111111111111111111111111111111"},
                {"pubkey": "Receiver11111111111111111111111111111111111"},
                {"pubkey": "11111111111111111111111111111111"},
            ],
            "instructions": [
                {
                    "programId": "11111111111111111111111111111111",
                    "accounts": [
                        "Sender1111111111111111111111111111111111111",
                        "Receiver11111111111111111111111111111111111",
                    ],
                    "parsed": {
                        "type": "transfer",
                        "info": {
                            "source": "Sender1111111111111111111111111111111111111",
                            "destination": "Receiver11111111111111111111111111111111111",
                            "lamports": 1000,
                        },
                    },
                }
            ],
        }
    },
    "meta": {
        "err": None,
        "fee": 5000,
        "computeUnitsConsumed": 150,
        "logMessages": [
            "Program 11111111111111111111111111111111 invoke [1]",
            "Program 11111111111111111111111111111111 success",
        ],
        "innerInstructions": [],
    },
}


def test_health():
    res = client.get("/health")
    assert res.status_code == 200
    assert res.json()["service"] == "solana-explorer-ai"


@respx.mock
def test_analyze_success():
    respx.post("https://api.mainnet-beta.solana.com").mock(
        return_value=httpx.Response(200, json={"jsonrpc": "2.0", "id": 1, "result": SAMPLE_TX})
    )

    ai_payload = {
        "flow": "System transfer of 1000 lamports.",
        "error_summary": "Transaction succeeded.",
        "fixes": [],
    }

    mock_resp = AsyncMock()
    mock_resp.choices = [AsyncMock(message=AsyncMock(content=json.dumps(ai_payload)))]

    with patch("app.ai.explain.AsyncOpenAI") as mock_openai:
        instance = mock_openai.return_value
        instance.chat.completions.create = AsyncMock(return_value=mock_resp)

        res = client.post(
            "/analyze",
            json={
                "signature": "5VERv8NMvzbJMEkV8xnrLkEaWRtSz9CosKDYjCJjBhpZeBGGa8TZISbvZ4CsJwyDx3oWcAqPGmVMDqF87A7ZM4yg",
                "cluster": "mainnet-beta",
            },
        )

    assert res.status_code == 200
    body = res.json()
    assert body["status"] == "success"
    assert body["fee_lamports"] == 5000
    assert body["instructions"][0]["instruction_name"] == "transfer"
    assert body["ai"]["flow"].startswith("System transfer")


@respx.mock
def test_analyze_not_found():
    respx.post("https://api.mainnet-beta.solana.com").mock(
        return_value=httpx.Response(200, json={"jsonrpc": "2.0", "id": 1, "result": None})
    )
    res = client.post(
        "/analyze",
        json={
            "signature": "5VERv8NMvzbJMEkV8xnrLkEaWRtSz9CosKDYjCJjBhpZeBGGa8TZISbvZ4CsJwyDx3oWcAqPGmVMDqF87A7ZM4yg",
            "cluster": "mainnet-beta",
        },
    )
    assert res.status_code == 404


def test_analyze_requires_openai_key():
    prev = settings.openai_api_key
    settings.openai_api_key = ""
    try:
        res = client.post(
            "/analyze",
            json={
                "signature": "5VERv8NMvzbJMEkV8xnrLkEaWRtSz9CosKDYjCJjBhpZeBGGa8TZISbvZ4CsJwyDx3oWcAqPGmVMDqF87A7ZM4yg",
                "cluster": "mainnet-beta",
            },
        )
        assert res.status_code == 503
    finally:
        settings.openai_api_key = prev
