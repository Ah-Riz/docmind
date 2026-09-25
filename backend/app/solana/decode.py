from __future__ import annotations

import base64
import struct
from typing import Any

from app.schemas import DecodedInstruction

SYSTEM_PROGRAM = "11111111111111111111111111111111"
TOKEN_PROGRAM = "TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA"
TOKEN_2022_PROGRAM = "TokenzQdBNbLqP5VEhdkAS6EPFLC1PHnBqCXEpPxuEb"
ASSOCIATED_TOKEN = "ATokenGPvbdGVxr1b2hvZbsiqW5xWH25efTNsLJA8knL"
COMPUTE_BUDGET = "ComputeBudget111111111111111111111111111111"
MEMO_PROGRAM = "MemoSq4gqABAXKb96qnH8TysNcWxMyWCqXgDLGmfcHr"

PROGRAM_NAMES: dict[str, str] = {
    SYSTEM_PROGRAM: "System Program",
    TOKEN_PROGRAM: "SPL Token",
    TOKEN_2022_PROGRAM: "SPL Token-2022",
    ASSOCIATED_TOKEN: "Associated Token Account",
    COMPUTE_BUDGET: "Compute Budget",
    MEMO_PROGRAM: "Memo",
}

SYSTEM_IX: dict[int, str] = {
    0: "CreateAccount",
    1: "Assign",
    2: "Transfer",
    3: "CreateAccountWithSeed",
    4: "AdvanceNonceAccount",
    5: "WithdrawNonceAccount",
    6: "InitializeNonceAccount",
    7: "AuthorizeNonceAccount",
    8: "Allocate",
    9: "AllocateWithSeed",
    10: "AssignWithSeed",
    11: "TransferWithSeed",
}

TOKEN_IX: dict[int, str] = {
    0: "InitializeMint",
    1: "InitializeAccount",
    3: "Transfer",
    4: "Approve",
    6: "MintTo",
    7: "Burn",
    8: "CloseAccount",
    9: "FreezeAccount",
    10: "ThawAccount",
    12: "TransferChecked",
    13: "ApproveChecked",
    14: "MintToChecked",
    15: "BurnChecked",
    16: "InitializeAccount2",
    18: "InitializeAccount3",
    20: "InitializeMint2",
}

COMPUTE_IX: dict[int, str] = {
    0: "RequestUnitsDeprecated",
    1: "RequestHeapFrame",
    2: "SetComputeUnitLimit",
    3: "SetComputeUnitPrice",
}


def _b64_or_bytes(data: Any) -> bytes | None:
    if data is None:
        return None
    if isinstance(data, list) and data:
        raw, _enc = data[0], data[1] if len(data) > 1 else "base64"
        if isinstance(raw, str):
            return base64.b64decode(raw)
        return None
    if isinstance(data, str):
        try:
            return base64.b64decode(data)
        except Exception:
            return None
    return None


def _u32(data: bytes, offset: int = 0) -> int | None:
    if len(data) < offset + 4:
        return None
    return struct.unpack_from("<I", data, offset)[0]


def _u64(data: bytes, offset: int = 0) -> int | None:
    if len(data) < offset + 8:
        return None
    return struct.unpack_from("<Q", data, offset)[0]


def decode_instruction(
    index: int,
    program_id: str,
    accounts: list[str],
    data: Any,
    parsed: dict[str, Any] | None = None,
) -> DecodedInstruction:
    program_name = PROGRAM_NAMES.get(program_id, "Unknown Program")
    instruction_name = "Unknown"
    args: dict[str, Any] = {}
    raw_hex: str | None = None

    if parsed:
        instruction_name = str(parsed.get("type") or parsed.get("info", {}).get("type") or "Parsed")
        info = parsed.get("info")
        if isinstance(info, dict):
            args = {k: v for k, v in info.items() if k != "type"}
        return DecodedInstruction(
            index=index,
            program_id=program_id,
            program_name=program_name,
            instruction_name=instruction_name,
            accounts=accounts,
            args=args,
        )

    raw = _b64_or_bytes(data)
    if raw is not None:
        raw_hex = raw.hex()

    if program_id == SYSTEM_PROGRAM and raw is not None:
        tag = _u32(raw)
        if tag is not None:
            instruction_name = SYSTEM_IX.get(tag, f"SystemIx({tag})")
            if tag == 2 and len(raw) >= 12:
                lamports = _u64(raw, 4)
                if lamports is not None:
                    args["lamports"] = lamports

    elif program_id in (TOKEN_PROGRAM, TOKEN_2022_PROGRAM) and raw is not None and raw:
        tag = raw[0]
        instruction_name = TOKEN_IX.get(tag, f"TokenIx({tag})")
        if tag in (3, 12) and len(raw) >= 9:
            amount = _u64(raw, 1)
            if amount is not None:
                args["amount"] = amount

    elif program_id == COMPUTE_BUDGET and raw is not None and raw:
        tag = raw[0]
        instruction_name = COMPUTE_IX.get(tag, f"ComputeBudgetIx({tag})")
        if tag == 2 and len(raw) >= 5:
            args["units"] = _u32(raw, 1)
        elif tag == 3 and len(raw) >= 9:
            args["micro_lamports"] = _u64(raw, 1)

    elif program_id == ASSOCIATED_TOKEN:
        instruction_name = "CreateAssociatedTokenAccount"

    elif program_id == MEMO_PROGRAM and raw is not None:
        try:
            instruction_name = "Memo"
            args["memo"] = raw.decode("utf-8")
        except UnicodeDecodeError:
            instruction_name = "Memo"

    elif raw is not None and len(raw) >= 8:
        # Anchor: first 8 bytes = sha256("global:<name>")[:8]; name needs IDL
        disc = raw[:8]
        program_name = PROGRAM_NAMES.get(program_id, "Anchor/Custom Program")
        instruction_name = "anchor_ix"
        args["discriminator"] = disc.hex()

    return DecodedInstruction(
        index=index,
        program_id=program_id,
        program_name=program_name,
        instruction_name=instruction_name,
        accounts=accounts,
        args=args,
        raw_data=raw_hex,
    )


def decode_transaction(tx_result: dict[str, Any]) -> tuple[list[DecodedInstruction], list[str]]:
    message = tx_result.get("transaction", {}).get("message", {})
    account_keys = message.get("accountKeys", [])
    accounts: list[str] = []
    for key in account_keys:
        if isinstance(key, str):
            accounts.append(key)
        elif isinstance(key, dict):
            accounts.append(str(key.get("pubkey", "")))

    instructions_out: list[DecodedInstruction] = []
    for i, ix in enumerate(message.get("instructions", [])):
        if not isinstance(ix, dict):
            continue
        program_id = str(ix.get("programId") or "")
        if not program_id and "programIdIndex" in ix:
            idx = ix["programIdIndex"]
            if isinstance(idx, int) and idx < len(accounts):
                program_id = accounts[idx]

        accs: list[str] = []
        if "accounts" in ix:
            for a in ix["accounts"]:
                if isinstance(a, str):
                    accs.append(a)
                elif isinstance(a, int) and a < len(accounts):
                    accs.append(accounts[a])
        elif "accountKeyIndexes" in ix:
            for a in ix["accountKeyIndexes"]:
                if isinstance(a, int) and a < len(accounts):
                    accs.append(accounts[a])

        parsed = ix.get("parsed") if isinstance(ix.get("parsed"), dict) else None
        instructions_out.append(
            decode_instruction(i, program_id, accs, ix.get("data"), parsed)
        )

    # Inner instructions from meta
    meta = tx_result.get("meta") or {}
    for group in meta.get("innerInstructions") or []:
        if not isinstance(group, dict):
            continue
        outer = group.get("index", 0)
        for j, ix in enumerate(group.get("instructions") or []):
            if not isinstance(ix, dict):
                continue
            program_id = str(ix.get("programId") or "")
            accs = [a for a in ix.get("accounts", []) if isinstance(a, str)]
            parsed = ix.get("parsed") if isinstance(ix.get("parsed"), dict) else None
            instructions_out.append(
                decode_instruction(
                    index=outer * 1000 + j + 1,
                    program_id=program_id,
                    accounts=accs,
                    data=ix.get("data"),
                    parsed=parsed,
                )
            )

    return instructions_out, [a for a in accounts if a]
