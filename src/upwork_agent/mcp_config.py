"""Returns the right Upwork MCP server for the current environment.

Auth modes (see config.Settings.auth_mode):
- "mock"   → spawn the local mock MCP over stdio (offline, no Connects).
- "static" → live HTTP MCP using a pre-obtained UPWORK_MCP_TOKEN as bearer.
- "oauth"  → live HTTP MCP using a token from the browser login flow (auth.py),
             refreshed automatically. This is the path published users take.
"""
from __future__ import annotations

import sys

from crewai.mcp import MCPServerHTTP, MCPServerStdio

from .config import settings


def upwork_mcp(*, interactive: bool = True) -> MCPServerHTTP | MCPServerStdio:
    if settings.use_mock:
        # Run the mock with the *same* interpreter so it uses this venv.
        return MCPServerStdio(
            command=sys.executable,
            args=[settings.mock_server_path],
            cache_tools_list=True,
        )

    if settings.auth_mode == "static":
        token = settings.upwork_token
    else:  # oauth
        from .auth import get_access_token

        token = get_access_token(interactive=interactive)

    return MCPServerHTTP(
        url=settings.upwork_mcp_url,
        headers={"Authorization": f"Bearer {token}"},
        streamable=True,
        cache_tools_list=True,
    )


def connection_summary() -> str:
    mode = settings.auth_mode
    if mode == "mock":
        reason = "UPWORK_MOCK=true" if settings.mock_mode else "no Upwork auth configured"
        return f"MOCK Upwork MCP (local fixtures) — {reason}"
    if mode == "static":
        return f"LIVE Upwork MCP at {settings.upwork_mcp_url} (static token)"
    return f"LIVE Upwork MCP at {settings.upwork_mcp_url} (OAuth browser login)"
