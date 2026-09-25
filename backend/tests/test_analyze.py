from __future__ import annotations

import json
from pathlib import Path
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
settings.solana_rpc_url = ""

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
    body = res.json()
    assert body["service"] == "solana-explorer-ai"
    assert body["status"] == "ok"
    assert body["gemini_configured"] is True


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
    assert body["ai"]["model"] == "gemini-3.7-flash"
    assert body["ai"]["flow"].startswith("Fell back")


@respx.mock
def test_analyze_skips_retired_model_404():
    respx.post("https://api.mainnet-beta.solana.com").mock(
        return_value=httpx.Response(200, json={"jsonrpc": "2.0", "id": 1, "result": SAMPLE_TX})
    )

    ai_payload = {
        "flow": "Skipped retired model.",
        "error_summary": "Transaction succeeded.",
        "fixes": [],
    }
    mock_resp = MagicMock()
    mock_resp.text = json.dumps(ai_payload)

    retired = Exception(
        "404 NOT_FOUND. This model models/gemini-2.5-flash is no longer available to new users."
    )
    mock_client = MagicMock()
    mock_client.aio.models.generate_content = AsyncMock(side_effect=[retired, mock_resp])

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
    assert body["ai"]["model"] == "gemini-3.7-flash"


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


@respx.mock
def test_analyze_rpc_error_message_is_clear():
    respx.post("https://api.mainnet-beta.solana.com").mock(
        return_value=httpx.Response(
            200,
            json={
                "jsonrpc": "2.0",
                "id": 1,
                "error": {"code": -32602, "message": "Invalid param: Invalid"},
            },
        )
    )
    res = client.post(
        "/analyze",
        json={
            "signature": "5VERv8NMvzbJMEkV8xnrLkEaWRtSz9CosKDYjCJjBhpZeBGGa8TZISbvZ4CsJwyDx3oWcAqPGmVMDqF87A7ZM4yg",
            "cluster": "mainnet-beta",
        },
    )
    assert res.status_code == 502
    detail = res.json()["detail"]
    assert "Solana RPC error" in detail
    assert "Invalid param: Invalid" in detail
    assert "{" not in detail


@respx.mock
def test_golden_failed_spl_transfer_errors():
    """Known failed Token transfer: InstructionError Custom 1 → expected error fields."""
    fixture_path = Path(__file__).parent / "fixtures" / "failed_spl_transfer.json"
    failed_tx = json.loads(fixture_path.read_text())

    respx.post("https://api.mainnet-beta.solana.com").mock(
        return_value=httpx.Response(200, json={"jsonrpc": "2.0", "id": 1, "result": failed_tx})
    )

    ai_payload = {
        "flow": "SPL Token transfer attempted.",
        "error_summary": "Insufficient funds (custom program error 0x1).",
        "fixes": ["Fund the source token account before retrying."],
    }
    mock_resp = MagicMock()
    mock_resp.text = json.dumps(ai_payload)
    mock_client = MagicMock()
    mock_client.aio.models.generate_content = AsyncMock(return_value=mock_resp)

    with patch("app.ai.explain.genai.Client", return_value=mock_client):
        res = client.post(
            "/analyze",
            json={
                "signature": "64jDk9vkg1yJ57jvrR3ejqiZpKCzRh3Xwm2NCBbMnhmVXVFYvjSY3PtDmw9ZjMKxhK3jjVnNXnK1h9hWWnGi8Wve",
                "cluster": "mainnet-beta",
            },
        )

    assert res.status_code == 200
    body = res.json()
    assert body["status"] == "failed"
    assert body["fee_lamports"] == 5000
    assert body["instructions"][0]["program_name"] == "SPL Token"
    assert body["instructions"][0]["instruction_name"] == "transfer"

    tx_errs = [e for e in body["errors"] if e["kind"] == "transaction"]
    assert len(tx_errs) == 1
    assert tx_errs[0]["custom_code"] == 1
    assert tx_errs[0]["instruction_index"] == 0
    assert "0x1" in tx_errs[0]["message"]

    log_errs = [e for e in body["errors"] if e["kind"] == "log"]
    assert any(e.get("custom_code") == 1 for e in log_errs)
    assert any("insufficient funds" in line.lower() for line in body["logs"])
    assert body["ai"]["error_summary"].startswith("Insufficient funds")
