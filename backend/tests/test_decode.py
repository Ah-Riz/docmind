from __future__ import annotations

from app.solana.decode import (
    COMPUTE_BUDGET,
    SYSTEM_PROGRAM,
    TOKEN_PROGRAM,
    decode_instruction,
    decode_transaction,
)


def test_system_transfer_decode():
    # tag=2 Transfer, lamports=1000
    data = bytes([2, 0, 0, 0, 232, 3, 0, 0, 0, 0, 0, 0])
    import base64

    ix = decode_instruction(
        0,
        SYSTEM_PROGRAM,
        ["from", "to"],
        [base64.b64encode(data).decode(), "base64"],
    )
    assert ix.instruction_name == "Transfer"
    assert ix.args.get("lamports") == 1000
    assert ix.program_name == "System Program"


def test_token_transfer_checked():
    import base64

    # tag=12 TransferChecked, amount=5
    data = bytes([12]) + (5).to_bytes(8, "little") + bytes([9])
    ix = decode_instruction(
        1,
        TOKEN_PROGRAM,
        ["src", "mint", "dst", "owner"],
        [base64.b64encode(data).decode(), "base64"],
    )
    assert ix.instruction_name == "TransferChecked"
    assert ix.args.get("amount") == 5


def test_compute_budget_limit():
    import base64

    data = bytes([2]) + (200_000).to_bytes(4, "little")
    ix = decode_instruction(
        0,
        COMPUTE_BUDGET,
        [],
        [base64.b64encode(data).decode(), "base64"],
    )
    assert ix.instruction_name == "SetComputeUnitLimit"
    assert ix.args.get("units") == 200_000


def test_json_parsed_instruction():
    ix = decode_instruction(
        0,
        SYSTEM_PROGRAM,
        ["a", "b"],
        None,
        parsed={"type": "transfer", "info": {"lamports": 42, "source": "a", "destination": "b"}},
    )
    assert ix.instruction_name == "transfer"
    assert ix.args["lamports"] == 42


def test_decode_transaction_message():
    tx = {
        "transaction": {
            "message": {
                "accountKeys": [
                    {"pubkey": "11111111111111111111111111111111", "signer": False},
                    "TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA",
                ],
                "instructions": [
                    {
                        "programId": "11111111111111111111111111111111",
                        "accounts": ["11111111111111111111111111111111"],
                        "parsed": {"type": "advanceNonce", "info": {}},
                    }
                ],
            }
        },
        "meta": {"innerInstructions": []},
    }
    instructions, accounts = decode_transaction(tx)
    assert len(accounts) == 2
    assert instructions[0].instruction_name == "advanceNonce"
