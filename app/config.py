"""Centralized configuration loaded from environment variables."""
import os
from dataclasses import dataclass

from dotenv import load_dotenv

load_dotenv()


@dataclass(frozen=True)
class Settings:
    verify_token: str
    meta_api_key: str
    graph_meta_id: str
    graph_api_version: str
    default_language: str

    @property
    def graph_base_url(self) -> str:
        return f"https://graph.facebook.com/{self.graph_api_version}/{self.graph_meta_id}"


def _require(name: str, default: str | None = None) -> str:
    value = os.getenv(name, default)
    if not value:
        raise RuntimeError(
            f"Missing required environment variable: {name}. "
            "Check your .env file (see .env.example)."
        )
    return value


settings = Settings(
    verify_token=_require("VERIFY_TOKEN", "mi_token_dummy"),
    meta_api_key=os.getenv("META_API_KEY", ""),
    graph_meta_id=os.getenv("GRAPH_META_ID", ""),
    graph_api_version=os.getenv("GRAPH_API_VERSION", "v25.0"),
    default_language=os.getenv("DEFAULT_TEMPLATE_LANGUAGE", "es_US"),
)
