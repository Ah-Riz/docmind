from __future__ import annotations

from app.solana.logs import extract_errors, status_from_meta


def test_success_status():
    assert status_from_meta({"meta": {"err": None}}) == "success"


def test_failed_status():
    assert status_from_meta({"meta": {"err": {"InstructionError": [1, {"Custom": 6001}]}}}) == "failed"


def test_custom_instruction_error():
    tx = {
        "meta": {
            "err": {"InstructionError": [2, {"Custom": 6001}]},
            "logMessages": [
                "Program log: AnchorError thrown in programs/foo/src/lib.rs:42.",
                "Program log: Error Code: InsufficientFunds. Error Number: 6001. Error Message: Not enough tokens.",
                "Program Foo failed: custom program error: 0x1771",
            ],
        }
    }
    logs, errors = extract_errors(tx)
    assert len(logs) == 3
    assert any(e.custom_code == 6001 for e in errors)
    assert any(e.kind == "anchor" for e in errors)
    assert any("Custom program error" in e.message for e in errors)


def test_no_meta():
    assert status_from_meta({}) == "unknown"
    logs, errors = extract_errors({})
    assert logs == []
    assert errors == []
