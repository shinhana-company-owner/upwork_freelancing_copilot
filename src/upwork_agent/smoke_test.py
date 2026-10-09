#!/usr/bin/env python
"""Offline smoke test: mock Upwork MCP + deterministic scoring.

Proves the data + scoring pipeline works end-to-end WITHOUT an LLM key:
spins up the mock MCP server over stdio, calls every tool, then runs the real
scorer over the returned jobs and prints a ranked, flagged report.

Run with:  uv run smoke   (or)   .venv/bin/python -m upwork_agent.smoke_test
"""
from __future__ import annotations

import asyncio
import json
import sys

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from .config import settings
from .scoring import rank_jobs


def _text(result) -> str:
    """Pull plain text out of an MCP tool result."""
    parts = []
    for item in result.content:
        parts.append(getattr(item, "text", ""))
    return "".join(parts)


async def _run() -> int:
    params = StdioServerParameters(command=sys.executable, args=[settings.mock_server_path])

    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()

            tools = await session.list_tools()
            tool_names = sorted(t.name for t in tools.tools)
            print(f"✓ Mock MCP exposes {len(tool_names)} tools: {', '.join(tool_names)}\n")

            # 1) search_jobs
            search_raw = _text(await session.call_tool("search_jobs", {"query": ""}))
            jobs = json.loads(search_raw).get("jobs", [])
            print(f"✓ search_jobs returned {len(jobs)} jobs\n")

            # 2) score + rank them
            ranked = rank_jobs(jobs)
            print("── Ranked jobs (best first) ─────────────────────────────────")
            for s in ranked:
                flag_str = f"  flags: {', '.join(s.flags)}" if s.flags else ""
                verdict = "APPLY" if s.recommend_apply else "skip"
                print(f"[{s.score:>3}] {s.tier:<7} {verdict:<5} {s.title[:52]}{flag_str}")
            print()

            # 3) spot-check the other tools return parseable JSON
            for tool_name, args in [
                ("get_job_details", {"job_id": "job_005"}),
                ("get_client_history", {"client_id": "c_ghost"}),
                ("get_my_proposals", {}),
                ("get_recent_activity", {"hours": 24}),
                ("get_account_dashboard", {}),
                ("get_contracts", {}),
            ]:
                raw = _text(await session.call_tool(tool_name, args))
                json.loads(raw)  # raises if malformed
                print(f"✓ {tool_name} → valid JSON ({len(raw)} chars)")

    # sanity assertions on the scoring outcome
    titles_by_tier = {s.tier for s in ranked}
    assert ranked[0].tier == "strong", "expected a strong job at the top"
    assert any("payment_unverified" in s.flags for s in ranked), "expected a scam flag"
    print("\n✅ Smoke test passed: MCP connectivity + scoring pipeline healthy.")
    print(f"   Tiers observed: {', '.join(sorted(titles_by_tier))}")
    return 0


def main() -> None:
    raise SystemExit(asyncio.run(_run()))


if __name__ == "__main__":
    main()
