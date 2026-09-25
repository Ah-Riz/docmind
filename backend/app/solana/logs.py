from __future__ import annotations

import re
from typing import Any

from app.schemas import TxError

CUSTOM_ERR_RE = re.compile(r"custom program error:\s*(0x[0-9a-fA-F]+|\d+)")
FAILED_IX_RE = re.compile(r"failed:\s*(.+)$", re.IGNORECASE)
ANCHOR_ERR_RE = re.compile(r"Error Code:\s*(\w+)\.\s*Error Number:\s*(\d+)\.\s*Error Message:\s*(.+)")


def _parse_custom_code(raw: str) -> int | None:
    if raw.startswith("0x"):
        return int(raw, 16)
    try:
        return int(raw)
    except ValueError:
        return None


def extract_errors(tx_result: dict[str, Any]) -> tuple[list[str], list[TxError]]:
    meta = tx_result.get("meta") or {}
    logs: list[str] = list(meta.get("logMessages") or [])
    errors: list[TxError] = []

    err = meta.get("err")
    if err is not None:
        ix_index: int | None = None
        custom_code: int | None = None
        message = str(err)

        if isinstance(err, dict):
            if "InstructionError" in err:
                pair = err["InstructionError"]
                if isinstance(pair, list) and len(pair) >= 2:
                    ix_index = pair[0] if isinstance(pair[0], int) else None
                    detail = pair[1]
                    message = f"InstructionError at index {ix_index}: {detail}"
                    if isinstance(detail, dict) and "Custom" in detail:
                        custom_code = detail["Custom"] if isinstance(detail["Custom"], int) else None
                        message = (
                            f"Custom program error {custom_code} "
                            f"(0x{custom_code:x}) at instruction {ix_index}"
                        )
            else:
                message = str(err)

        errors.append(
            TxError(
                kind="transaction",
                message=message,
                instruction_index=ix_index,
                custom_code=custom_code,
            )
        )

    for line in logs:
        anchor = ANCHOR_ERR_RE.search(line)
        if anchor:
            errors.append(
                TxError(
                    kind="anchor",
                    message=f"{anchor.group(1)} ({anchor.group(2)}): {anchor.group(3).strip()}",
                    custom_code=int(anchor.group(2)),
                )
            )
            continue

        custom = CUSTOM_ERR_RE.search(line)
        if custom:
            code = _parse_custom_code(custom.group(1))
            errors.append(
                TxError(
                    kind="log",
                    message=line.strip(),
                    custom_code=code,
                )
            )
            continue

        if "failed" in line.lower() and "Program" in line:
            failed = FAILED_IX_RE.search(line)
            errors.append(
                TxError(
                    kind="log",
                    message=failed.group(1).strip() if failed else line.strip(),
                )
            )

    # Deduplicate by message
    seen: set[str] = set()
    unique: list[TxError] = []
    for e in errors:
        if e.message in seen:
            continue
        seen.add(e.message)
        unique.append(e)

    return logs, unique


def status_from_meta(tx_result: dict[str, Any]) -> str:
    meta = tx_result.get("meta")
    if meta is None:
        return "unknown"
    return "failed" if meta.get("err") is not None else "success"
