"""A clean pre-flight connectivity check for the live Upwork MCP.

CrewAI's MCP layer dumps a wall of async-teardown tracebacks when the server
returns 401. We instead probe the connection ourselves with the MCP SDK, catch
everything, and return a single tidy result — so the chat can give the user a
legible message instead of a stack-trace avalanche.
"""
from __future__ import annotations

import asyncio
import contextlib
import io
import json

from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client

from .auth import _USER_AGENT


async def _probe(url: str, token: str) -> list[str]:
    headers = {"Authorization": f"Bearer {token}", "User-Agent": _USER_AGENT}
    async with streamablehttp_client(url, headers=headers) as (read, write, _):
        async with ClientSession(read, write) as session:
            await session.initialize()
            tools = await session.list_tools()
            return [t.name for t in tools.tools]


def _summarize(exc: BaseException) -> str:
    """Flatten nested ExceptionGroups and surface the most useful message."""
    text = str(exc)
    stack: list[BaseException] = [exc]
    seen = set()
    while stack:
        e = stack.pop()
        if id(e) in seen:
            continue
        seen.add(id(e))
        s = str(e)
        if "401" in s or "invalid_token" in s:
            return "401 Unauthorized — the Upwork MCP rejected the access token."
        if "403" in s or "insufficient_scope" in s:
            return "403 Forbidden — token is missing a required scope."
        subs = getattr(e, "exceptions", None)
        if subs:
            stack.extend(subs)
        if e.__cause__:
            stack.append(e.__cause__)
    return text or "connection failed"


def check_live_connection(url: str, token: str, timeout: float = 30) -> tuple[bool, object]:
    """Return (ok, tool_names) on success, or (False, reason_str) on failure.

    Suppresses the MCP/anyio teardown noise that prints during a failed probe.
    """

    async def _run() -> list[str]:
        return await asyncio.wait_for(_probe(url, token), timeout)

    # The async-generator cleanup can emit noise to stderr even when we catch
    # the exception; swallow it since we report a clean result ourselves.
    with contextlib.redirect_stderr(io.StringIO()):
        try:
            return True, asyncio.run(_run())
        except BaseException as e:  # noqa: BLE001 — we want everything, incl. groups
            return False, _summarize(e)


def get_org_uid(url: str, token: str, timeout: float = 30) -> str | None:
    """Fetch the user's Upwork org_uid via list_accounts (first account).

    Many live tools require org_uid; resolving it up front lets the agent pass it
    directly instead of relying on the LLM to chain an extra call.
    """

    async def _run() -> str | None:
        headers = {"Authorization": f"Bearer {token}", "User-Agent": _USER_AGENT}
        async with streamablehttp_client(url, headers=headers) as (read, write, _):
            async with ClientSession(read, write) as session:
                await session.initialize()
                res = await session.call_tool("upwork__list_accounts", {})
                text = "".join(getattr(i, "text", "") for i in res.content)
                accounts = json.loads(text).get("accounts") or []
                return accounts[0].get("org_uid") if accounts else None

    with contextlib.redirect_stderr(io.StringIO()):
        try:
            return asyncio.run(asyncio.wait_for(_run(), timeout))
        except BaseException:
            return None
