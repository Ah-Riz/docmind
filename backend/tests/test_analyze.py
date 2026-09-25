from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import respx
from fastapi.testclient import TestClient

# Ensure settings load with a key before app import paths rebind
import os

TEST_GEMINI_KEY = "AIzaSyDummyTestKeyForUnitTestsOnlyZZ"

os.environ.setdefault("GEMINI_API_KEY", TEST_GEMINI_KEY)

from app.config import settings
from app.main import app

settings.gemini_api_key = TEST_GEMINI_KEY

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

    mock_resp = MagicMock()
    mock_resp.text = json.dumps(ai_payload)

    mock_client = MagicMock()
    mock_client.aio.models.generate_content = AsyncMock(return_value=mock_resp)

    with patch("app.ai.explain.genai.Client", return_value=mock_client):
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
    assert body["ai"]["model"] == settings.gemini_model
    assert body["ai"]["fallback_used"] is False


@respx.mock
def test_analyze_falls_back_on_overload():
    respx.post("https://api.mainnet-beta.solana.com").mock(
        return_value=httpx.Response(200, json={"jsonrpc": "2.0", "id": 1, "result": SAMPLE_TX})
    )

    ai_payload = {
        "flow": "Fell back successfully.",
        "error_summary": "Transaction succeeded.",
        "fixes": [],
    }
    mock_resp = MagicMock()
    mock_resp.text = json.dumps(ai_payload)

    overload = Exception("503 UNAVAILABLE. high demand")
    mock_client = MagicMock()
    mock_client.aio.models.generate_content = AsyncMock(side_effect=[overload, mock_resp])

    with patch("app.ai.explain.genai.Client", return_value=mock_client):
        with patch("app.ai.explain.asyncio.sleep", new_callable=AsyncMock):
            res = client.post(
                "/analyze",
                json={
                    "signature": "5VERv8NMvzbJMEkV8xnrLkEaWRtSz9CosKDYjCJjBhpZeBGGa8TZISbvZ4CsJwyDx3oWcAqPGmVMDqF87A7ZM4yg",
                    "cluster": "mainnet-beta",
                },
            )

    assert res.status_code == 200
    body = res.json()
    assert body["ai"]["fallback_used"] is True
    assert body["ai"]["model"] == "gemini-2.5-flash"
    assert body["ai"]["flow"].startswith("Fell back")


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


def test_analyze_requires_gemini_key():
    prev = settings.gemini_api_key
    settings.gemini_api_key = ""
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
        settings.gemini_api_key = prev
