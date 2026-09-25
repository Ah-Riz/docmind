from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


Cluster = Literal["mainnet-beta", "devnet", "testnet"]


class AnalyzeRequest(BaseModel):
    signature: str = Field(..., min_length=32, max_length=128)
    cluster: Cluster = "mainnet-beta"


class DecodedInstruction(BaseModel):
    index: int
    program_id: str
    program_name: str
    instruction_name: str
    accounts: list[str] = Field(default_factory=list)
    args: dict[str, Any] = Field(default_factory=dict)
    raw_data: str | None = None


class TxError(BaseModel):
    kind: str
    message: str
    instruction_index: int | None = None
    custom_code: int | None = None


class AiExplanation(BaseModel):
    flow: str
    error_summary: str
    fixes: list[str] = Field(default_factory=list)
    model: str = ""
    fallback_used: bool = False


class AnalyzeResponse(BaseModel):
    signature: str
    cluster: str
    status: Literal["success", "failed", "unknown"]
    slot: int | None = None
    fee_lamports: int | None = None
    compute_units: int | None = None
    accounts: list[str] = Field(default_factory=list)
    instructions: list[DecodedInstruction] = Field(default_factory=list)
    logs: list[str] = Field(default_factory=list)
    errors: list[TxError] = Field(default_factory=list)
    ai: AiExplanation
