"""Central configuration for the Upwork agent.

Everything that depends on the environment lives here so the rest of the code
stays clean. Reads from environment variables (populated from `.env` by crewAI).
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


def _as_bool(value: str | None, default: bool = False) -> bool:
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _as_int(value: str | None, default: int) -> int:
    try:
        return int(value) if value else default
    except (ValueError, TypeError):
        return default


@dataclass(frozen=True)
class Settings:
    # LLM used by every agent. Override with MODEL in .env.
    # Examples: "anthropic/claude-sonnet-4-6", "openai/gpt-4o".
    model: str = os.getenv("MODEL", "anthropic/claude-sonnet-4-6")
    # Cap on output tokens per LLM call — keeps cost/credit use predictable and
    # avoids providers reserving a huge default (e.g. OpenRouter's 65k).
    llm_max_tokens: int = _as_int(os.getenv("LLM_MAX_TOKENS"), 4096)

    # Upwork MCP connection.
    upwork_mcp_url: str = os.getenv("UPWORK_MCP_URL", "https://mcp.upwork.com/mcp")

    # Power-user escape hatch: a pre-obtained access token used directly as a
    # bearer. Normal users authenticate via the browser OAuth flow instead.
    upwork_token: str | None = os.getenv("UPWORK_MCP_TOKEN") or None

    # Force the local mock MCP server (no account, no Connects spent).
    mock_mode: bool = _as_bool(os.getenv("UPWORK_MOCK"), default=False)
    # Raw value, so we can tell "UPWORK_MOCK=false" (go live) from "unset" (default mock).
    mock_env_raw: str | None = os.getenv("UPWORK_MOCK")

    # --- OAuth (browser login to the user's own Upwork account) ---
    # No manual client id/secret: the app self-registers via Dynamic Client
    # Registration. A manual /developer/keys/apply key does NOT work (its tokens
    # are for the GraphQL API, not the MCP).
    oauth_scope: str | None = os.getenv("UPWORK_OAUTH_SCOPE") or None
    # Loopback redirect used during the browser login.
    oauth_redirect_port: int = _as_int(os.getenv("UPWORK_OAUTH_REDIRECT_PORT"), 8723)

    @property
    def auth_mode(self) -> str:
        """How we talk to Upwork: 'mock' | 'static' | 'oauth'.

        OAuth uses Dynamic Client Registration, so it needs no pre-set client id —
        setting UPWORK_MOCK=false is enough to go live.
        """
        if self.mock_mode:
            return "mock"
        if self.upwork_token:
            return "static"
        if self.mock_env_raw is not None:
            return "oauth"
        return "mock"

    @property
    def use_mock(self) -> bool:
        return self.auth_mode == "mock"

    @property
    def redirect_uri(self) -> str:
        return f"http://127.0.0.1:{self.oauth_redirect_port}/callback"

    @property
    def token_cache_path(self) -> Path:
        override = os.getenv("UPWORK_TOKEN_CACHE")
        if override:
            return Path(override).expanduser()
        return Path.home() / ".upwork_copilot" / "tokens.json"

    @property
    def user_config_path(self) -> Path:
        """Per-user config (LLM provider + key) written by first-run setup."""
        override = os.getenv("UPWORK_USER_CONFIG")
        if override:
            return Path(override).expanduser()
        return Path.home() / ".upwork_copilot" / "config.env"

    @property
    def client_cache_path(self) -> Path:
        """Where the dynamically-registered OAuth client is cached."""
        override = os.getenv("UPWORK_CLIENT_CACHE")
        if override:
            return Path(override).expanduser()
        return Path.home() / ".upwork_copilot" / "client.json"

    @property
    def mock_server_path(self) -> str:
        return str(Path(__file__).with_name("mock_upwork_mcp.py"))


settings = Settings()
