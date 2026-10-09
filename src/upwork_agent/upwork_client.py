"""Thin synchronous client for the live Upwork MCP.

CrewAI's generic MCP binding exposes all 32 Upwork tools with their raw, nested
`{action, org_uid, params}` schemas — which small models cannot construct
reliably (they drop `org_uid`/`action` and loop on errors). This module calls the
MCP directly with the correct arguments, so our agent can use a handful of simple,
foolproof wrapper tools instead.
"""
from __future__ import annotations

import asyncio
import contextlib
import io
import json
from typing import Any

from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client

from .auth import _USER_AGENT, get_access_token
from .config import settings

_org_uid_cache: str | None = None


def set_org_uid(value: str | None) -> None:
    """Pre-seed the org_uid (resolved once at startup) to skip a lookup."""
    global _org_uid_cache
    if value:
        _org_uid_cache = value


async def _acall_many(calls: list[tuple[str, dict[str, Any]]]) -> list[str]:
    """Run one or more tool calls over a SINGLE MCP connection/session."""
    token = get_access_token(interactive=False)
    headers = {"Authorization": f"Bearer {token}", "User-Agent": _USER_AGENT}
    out: list[str] = []
    async with streamablehttp_client(settings.upwork_mcp_url, headers=headers) as (r, w, _):
        async with ClientSession(r, w) as session:
            await session.initialize()
            for name, args in calls:
                res = await session.call_tool(name, args)
                out.append("".join(getattr(i, "text", "") for i in res.content))
    return out


def call_batch(calls: list[tuple[str, dict[str, Any]]]) -> list[str]:
    """Run several Upwork MCP tool calls over one connection; returns raw texts."""
    with contextlib.redirect_stderr(io.StringIO()):
        return asyncio.run(_acall_many(calls))


def call(name: str, args: dict[str, Any]) -> str:
    """Call a single Upwork MCP tool and return its raw text (JSON) result."""
    return call_batch([(name, args)])[0]


def org_uid() -> str:
    global _org_uid_cache
    if _org_uid_cache:
        return _org_uid_cache
    try:
        data = json.loads(call("upwork__list_accounts", {}))
        accounts = data.get("accounts") or []
        _org_uid_cache = (accounts[0].get("org_uid") if accounts else "") or ""
    except Exception:
        _org_uid_cache = ""
    return _org_uid_cache
