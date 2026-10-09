"""Simple, foolproof CrewAI tools wrapping the live Upwork MCP.

Each handles the nested `{action, org_uid, params}` plumbing internally AND
flattens the (often deeply nested) responses into clean JSON, so the LLM can
report them accurately instead of mis-summarizing raw payloads.
"""
from __future__ import annotations

import json
from typing import Any

from crewai.tools import tool

from ..upwork_client import call, call_batch, org_uid


def _loads(raw: str) -> dict[str, Any]:
    try:
        return json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        return {}


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
    params: dict = {"query": query or "", "limit": max(1, min(int(limit or 10), 10))}
    if job_type in ("fixed", "hourly"):
        params["job_type"] = job_type
    if budget_min:
        params["budget_min"] = float(budget_min)
    if verified_payment_only:
        params["verified_payment_only"] = True
    return call("upwork__find_jobs", {"action": "search", "org_uid": org_uid(), "params": params})


@tool("upwork_my_profile")
def upwork_my_profile() -> str:
    """Your own Upwork freelancer profile as JSON: title, overview/bio, skills,
    hourly rate, work history, education, and availability. Call this before
    drafting a proposal or cover letter so it's grounded in your real background."""
    profile = call("upwork__get_profile", {"action": "get", "org_uid": org_uid()})
    highlights = call("upwork__get_profile", {"action": "list_highlights", "org_uid": org_uid()})
    return '{"profile": ' + profile + ', "highlights": ' + highlights + "}"


@tool("upwork_my_proposals")
def upwork_my_proposals() -> str:
    """Your submitted job proposals as clean JSON: each with job_title, status,
    submitted date, and whether it was boosted."""
    raw = _loads(call("upwork__list_freelancer_proposals", {"action": "list", "org_uid": org_uid()}))
    edges = (((raw.get("data") or {}).get("vendorProposals") or {}).get("edges")) or []
    items = []
    for e in edges:
        node = e.get("node") or {}
        content = ((node.get("marketplaceJobPosting") or {}).get("content")) or {}
        items.append(
            {
                "job_title": content.get("title"),
                "status": node.get("status"),
                "submitted": ((node.get("auditDetails") or {}).get("createdDateTime") or {}).get("displayValue"),
                "boosted": node.get("boosted"),
            }
        )
    return json.dumps({"count": len(items), "proposals": items})


@tool("upwork_contracts")
def upwork_contracts() -> str:
    """Your Upwork contracts as clean JSON, split into currently ACTIVE
    (in-progress) contracts and recent closed ones. Use `active` for
    "my active/current contracts"."""
    org = org_uid()
    dash_raw, hist_raw = call_batch(
        [
            ("upwork__get_freelancer_dashboard", {"action": "check", "org_uid": org}),
            ("upwork__list_contracts", {"action": "search", "org_uid": org}),
        ]
    )
    ac = ((_loads(dash_raw).get("data") or {}).get("active_contracts")) or {}
    active = [
        {
            "title": c.get("title"),
            "client": c.get("client"),
            "status": c.get("status"),
            "start_date": c.get("start_date"),
        }
        for c in (ac.get("contracts") or [])
    ]
    closed = (((_loads(hist_raw).get("data") or {}).get("vendorContracts") or {}).get("contracts")) or []
    recent_closed = [
        {"title": c.get("title"), "status": c.get("status"), "end_date": c.get("endDate")}
        for c in closed[:10]
    ]
    return json.dumps(
        {
            "active_count": ac.get("total_count", len(active)),
            "active": active,
            "recent_closed": recent_closed,
        }
    )


@tool("upwork_dashboard")
def upwork_dashboard() -> str:
    """Account health as clean JSON: Connects balance, available/pending earnings,
    number of active contracts, and an earnings note. Use for "dashboard",
    "Connects balance", or "earnings"."""
    org = org_uid()
    dash_raw, bal_raw, summary_raw = call_batch(
        [
            ("upwork__get_freelancer_dashboard", {"action": "check", "org_uid": org}),
            ("upwork__get_freelancer_financials", {"action": "available_balance", "org_uid": org}),
            ("upwork__get_freelancer_financials", {"action": "summary", "org_uid": org}),
        ]
    )
    data = _loads(dash_raw).get("data") or {}
    connects = ((data.get("connects") or {}).get("balance")) or {}
    bal = _loads(bal_raw)
    summary = _loads(summary_raw)
    ac = (data.get("active_contracts") or {})
    return json.dumps(
        {
            "connects_balance": connects.get("connectsBalance"),
            "connects_free": connects.get("connectsBalanceFree"),
            "connects_paid": connects.get("connectsBalancePaid"),
            "available_balance": (bal.get("available_now") or {}).get("displayValue"),
            "pending_balance": (bal.get("pending_balance") or {}).get("displayValue"),
            "earnings_note": summary.get("note"),
            "active_contracts_count": ac.get("total_count"),
        }
    )


@tool("upwork_messages")
def upwork_messages() -> str:
    """Your Upwork message rooms / recent conversations as JSON."""
    return call("upwork__get_messages", {"action": "list_rooms", "org_uid": org_uid()})
