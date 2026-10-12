"""Configuration for the Upwork Copilot *skill*.

This is a deliberately slimmed, standalone copy — it is NOT generated from the
parent app's `src/upwork_agent/config.py`. The skill is LLM-free and reads **no
credentials from the environment**:

- No `MODEL` / `LLM_MAX_TOKENS` (the host model is the brain; the skill makes no
  LLM calls).
- No static `UPWORK_MCP_TOKEN` bearer read from the environment. The skill
  authenticates only through the interactive browser OAuth flow (Dynamic Client
  Registration), and the resulting token is cached locally at mode 0600 — it is
  never taken from the installer's environment or files.

Keeping this file free of credential-named environment reads is what keeps the
skill clear of the plugin directory's credential-forwarding review.
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


def _as_int(value: str | None, default: int) -> int:
    try:
        return int(value) if value else default
    except (ValueError, TypeError):
        return default


@dataclass(frozen=True)
class Settings:
    # The official Upwork MCP endpoint (a URL, not a credential).
    upwork_mcp_url: str = os.getenv("UPWORK_MCP_URL", "https://mcp.upwork.com/mcp")

    # The skill never reads a static bearer token from the environment; auth is
    # always the interactive browser OAuth flow. Kept as a constant so the rest
    # of the data layer keeps a stable attribute surface.
    upwork_token: str | None = None

    # --- OAuth (browser login to the user's own Upwork account) ---
    # No manual client id/secret: the app self-registers via Dynamic Client
    # Registration and the user logs in through the browser.
    oauth_scope: str | None = os.getenv("UPWORK_OAUTH_SCOPE") or None
    # Loopback redirect used during the browser login.
    oauth_redirect_port: int = _as_int(os.getenv("UPWORK_OAUTH_REDIRECT_PORT"), 8723)

    @property
    def auth_mode(self) -> str:
        """The skill always authenticates via browser OAuth."""
        return "oauth"

    @property
    def redirect_uri(self) -> str:
        return f"http://127.0.0.1:{self.oauth_redirect_port}/callback"

    @property
    def token_cache_path(self) -> Path:
        """OAuth tokens obtained via browser login, cached locally (mode 0600)."""
        return Path.home() / ".upwork_copilot" / "tokens.json"

    @property
    def client_cache_path(self) -> Path:
        """The dynamically-registered OAuth client, cached locally (mode 0600)."""
        return Path.home() / ".upwork_copilot" / "client.json"


settings = Settings()
