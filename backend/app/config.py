from __future__ import annotations

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

CLUSTER_RPC: dict[str, str] = {
    "mainnet-beta": "https://api.mainnet-beta.solana.com",
    "devnet": "https://api.devnet.solana.com",
    "testnet": "https://api.testnet.solana.com",
}


def normalize_gemini_key(raw: str) -> str:
    """Strip whitespace/quotes; drop inline comments (dotenv may keep them)."""
    key = (raw or "").strip().strip("'").strip('"')
    if " #" in key:
        key = key.split(" #", 1)[0].strip()
    return key


def gemini_key_is_plausible(key: str) -> bool:
    """Google AI Studio keys typically start with AIza and are long."""
    if not key.startswith("AIza"):
        return False
    if len(key) < 20:
        return False
    low = key.lower()
    if any(p in low for p in ("1234", "xxxx", "your_api", "placeholder", "example")):
        return False
    return True


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    gemini_api_key: str = ""
    gemini_model: str = "gemini-2.0-flash"
    solana_rpc_url: str = ""
    cors_origins: str = "http://localhost:3001"

    @field_validator("gemini_api_key", mode="before")
    @classmethod
    def _clean_gemini_key(cls, v: object) -> str:
        return normalize_gemini_key(str(v or ""))

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    def rpc_for(self, cluster: str) -> str:
        if self.solana_rpc_url:
            return self.solana_rpc_url
        return CLUSTER_RPC.get(cluster, CLUSTER_RPC["mainnet-beta"])


settings = Settings()
