"""Simple, foolproof CrewAI tools wrapping the live Upwork MCP.

Thin wrappers over `queries.py` (the shared, LLM-free data layer) — they just
serialize the clean dicts to JSON for the agent. The nested Upwork schemas and
response flattening all live in `queries.py`.
"""
from __future__ import annotations

import json

from crewai.tools import tool

from .. import queries


@tool("find_upwork_jobs")
def find_upwork_jobs(
    query: str,
    limit: int = 10,
    job_type: str = "",
    budget_min: float = 0,
    verified_payment_only: bool = False,
) -> str:
    """Search the Upwork marketplace for jobs. Returns JSON {"jobs":[...]} — feed
    that straight into `score_and_rank_jobs`.

    Args:
      query: keywords, e.g. "flutter" or "python data pipeline".
      limit: how many jobs (1-10).
      job_type: "fixed" or "hourly" (optional; omit for both).
      budget_min: minimum fixed-price budget in USD (optional).
      verified_payment_only: true to only include payment-verified clients.
    """
    return json.dumps(
        queries.find_jobs(
            query,
            limit=limit,
            job_type=job_type,
            budget_min=budget_min,
            verified_payment_only=verified_payment_only,
        )
    )


@tool("upwork_my_profile")
def upwork_my_profile() -> str:
    """Your own Upwork freelancer profile as JSON: title, overview/bio, skills,
    hourly rate, work history, education, and availability. Call this before
    drafting a proposal or cover letter so it's grounded in your real background."""
    return json.dumps(queries.my_profile())


@tool("upwork_my_proposals")
def upwork_my_proposals() -> str:
    """Your submitted job proposals as clean JSON: each with job_title, status,
    submitted date, and whether it was boosted."""
    return json.dumps(queries.my_proposals())


@tool("upwork_contracts")
def upwork_contracts() -> str:
    """Your Upwork contracts as clean JSON, split into currently ACTIVE
    (in-progress) contracts and recent closed ones. Use `active` for
    "my active/current contracts"."""
    return json.dumps(queries.contracts())


@tool("upwork_dashboard")
def upwork_dashboard() -> str:
    """Account health as clean JSON: Connects balance, available/pending earnings,
    number of active contracts, and an earnings note. Use for "dashboard",
    "Connects balance", or "earnings"."""
    return json.dumps(queries.dashboard())


@tool("upwork_messages")
def upwork_messages() -> str:
    """Your Upwork message rooms / recent conversations as JSON."""
    return json.dumps(queries.messages())
