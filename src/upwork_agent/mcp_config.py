"""Human-readable summary of how we're connected to the live Upwork MCP.

Auth modes (see config.Settings.auth_mode):
- "static" → live HTTP MCP using a pre-obtained UPWORK_MCP_TOKEN as bearer.
- "oauth"  → live HTTP MCP using a token from the browser login flow (auth.py),
             refreshed automatically. This is the path published users take.

The standalone agent reaches the MCP through the simple wrapper tools in
`tools/upwork_tools.py` (which call `upwork_client.py` directly), so there's no
CrewAI MCP binding to construct here.
"""
from __future__ import annotations

from .config import settings


def connection_summary() -> str:
    if settings.auth_mode == "static":
        return f"LIVE Upwork MCP at {settings.upwork_mcp_url} (static token)"
    return f"LIVE Upwork MCP at {settings.upwork_mcp_url} (OAuth browser login)"
