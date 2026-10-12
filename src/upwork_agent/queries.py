"""Shared, LLM-free Upwork data operations.

Single source of truth used by BOTH distributions:
- the standalone CrewAI agent (via `tools/upwork_tools.py`), and
- the Claude skill CLI (`skill_cli.py`), where the host model is the brain.

Everything here is plain Python + the Upwork MCP + the deterministic scorer — no
LLM calls.
"""
from __future__ import annotations

import json
from typing import Any

from .scoring import rank_jobs
from .upwork_client import call, call_batch, org_uid


def _loads(raw: str) -> dict[str, Any]:
    try:
        return json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        return {}


def find_jobs(
    query: str,
    limit: int = 10,
    job_type: str = "",
    budget_min: float = 0,
    verified_payment_only: bool = False,
) -> dict[str, Any]:
    """Raw marketplace search — returns {"jobs": [...]} as Upwork provides it."""
    params: dict[str, Any] = {"query": query or "", "limit": max(1, min(int(limit or 10), 10))}
    if job_type in ("fixed", "hourly"):
        params["job_type"] = job_type
    if budget_min:
        params["budget_min"] = float(budget_min)
    if verified_payment_only:
        params["verified_payment_only"] = True
    return _loads(call("upwork__find_jobs", {"action": "search", "org_uid": org_uid(), "params": params}))


def search_and_rank(query: str, **kwargs: Any) -> dict[str, Any]:
    """Search + deterministically score/rank. Returns {"count", "ranked":[...]}."""
    jobs = find_jobs(query, **kwargs).get("jobs", [])
    ranked = [s.as_dict() for s in rank_jobs(jobs)]
    return {"count": len(ranked), "ranked": ranked}


def my_profile() -> dict[str, Any]:
    prof, high = call_batch(
        [
            ("upwork__get_profile", {"action": "get", "org_uid": org_uid()}),
            ("upwork__get_profile", {"action": "list_highlights", "org_uid": org_uid()}),
        ]
    )
    return {"profile": _loads(prof), "highlights": _loads(high)}


def my_proposals() -> dict[str, Any]:
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
    return {"count": len(items), "proposals": items}


def contracts() -> dict[str, Any]:
    org = org_uid()
    dash_raw, hist_raw = call_batch(
        [
            ("upwork__get_freelancer_dashboard", {"action": "check", "org_uid": org}),
            ("upwork__list_contracts", {"action": "search", "org_uid": org}),
        ]
    )
    ac = ((_loads(dash_raw).get("data") or {}).get("active_contracts")) or {}
    active = [
        {"title": c.get("title"), "client": c.get("client"), "status": c.get("status"), "start_date": c.get("start_date")}
        for c in (ac.get("contracts") or [])
    ]
    closed = (((_loads(hist_raw).get("data") or {}).get("vendorContracts") or {}).get("contracts")) or []
    recent_closed = [
        {"title": c.get("title"), "status": c.get("status"), "end_date": c.get("endDate")} for c in closed[:10]
    ]
    return {"active_count": ac.get("total_count", len(active)), "active": active, "recent_closed": recent_closed}


def dashboard() -> dict[str, Any]:
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
    ac = data.get("active_contracts") or {}
    return {
        "connects_balance": connects.get("connectsBalance"),
        "connects_free": connects.get("connectsBalanceFree"),
        "connects_paid": connects.get("connectsBalancePaid"),
        "available_balance": (bal.get("available_now") or {}).get("displayValue"),
        "pending_balance": (bal.get("pending_balance") or {}).get("displayValue"),
        "earnings_note": summary.get("note"),
        "active_contracts_count": ac.get("total_count"),
    }


def messages() -> dict[str, Any]:
    raw = _loads(call("upwork__get_messages", {"action": "list_rooms", "org_uid": org_uid()}))
    rooms = (raw.get("data") or {}).get("rooms") or []
    return {"count": len(rooms), "rooms": rooms}
