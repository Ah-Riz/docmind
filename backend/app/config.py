from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict

CLUSTER_RPC: dict[str, str] = {
    "mainnet-beta": "https://api.mainnet-beta.solana.com",
    "devnet": "https://api.devnet.solana.com",
    "testnet": "https://api.testnet.solana.com",
}


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    openai_api_key: str = ""
    openai_model: str = "gpt-4o-mini"
    solana_rpc_url: str = ""
    cors_origins: str = "http://localhost:3001"

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    def rpc_for(self, cluster: str) -> str:
        if self.solana_rpc_url:
            return self.solana_rpc_url
        return CLUSTER_RPC.get(cluster, CLUSTER_RPC["mainnet-beta"])


settings = Settings()
