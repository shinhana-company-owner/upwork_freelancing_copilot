"""A local mock of the official Upwork MCP server.

Runs over stdio and exposes the same *shape* of tools we expect from
https://mcp.upwork.com/mcp, returning realistic fixtures. This lets you build
and test the agent end-to-end without credentials and without spending Connects.

Swap to the real server by setting UPWORK_MCP_TOKEN in `.env` (see config.py).

Run standalone:  python src/upwork_agent/mock_upwork_mcp.py
"""
from __future__ import annotations

import json
from datetime import date, datetime, timedelta
from typing import Any

from mcp.server.fastmcp import FastMCP

mcp = FastMCP("upwork-mock")


def _iso_days_ago(days: int) -> str:
    return (datetime.now() - timedelta(days=days)).isoformat(timespec="seconds")


# --- fixtures -----------------------------------------------------------------
# A spread of qualities so scoring/ranking has something to chew on.
_CLIENTS: dict[str, dict[str, Any]] = {
    "c_acme": {
        "client_id": "c_acme",
        "name": "Acme Analytics",
        "payment_verified": True,
        "client_total_spent": 184_500,
        "client_total_hires": 73,
        "client_hire_rate": 0.86,
        "client_member_since": "2017-03-11",
        "client_open_jobs": 1,
        "avg_feedback_to_freelancers": 4.9,
        "country": "United States",
    },
    "c_brightml": {
        "client_id": "c_brightml",
        "name": "BrightML Studio",
        "payment_verified": True,
        "client_total_spent": 12_300,
        "client_total_hires": 9,
        "client_hire_rate": 0.55,
        "client_member_since": "2021-09-02",
        "client_open_jobs": 2,
        "avg_feedback_to_freelancers": 4.6,
        "country": "United Kingdom",
    },
    "c_ghost": {
        "client_id": "c_ghost",
        "name": "QuickWin LLC",
        "payment_verified": False,
        "client_total_spent": 0,
        "client_total_hires": 0,
        "client_hire_rate": 0.0,
        "client_member_since": _iso_days_ago(4)[:10],
        "client_open_jobs": 6,
        "avg_feedback_to_freelancers": None,
        "country": "Unknown",
    },
    "c_churner": {
        "client_id": "c_churner",
        "name": "Everpost Media",
        "payment_verified": True,
        "client_total_spent": 2_100,
        "client_total_hires": 2,
        "client_hire_rate": 0.06,
        "client_member_since": "2019-01-20",
        "client_open_jobs": 11,
        "avg_feedback_to_freelancers": 3.4,
        "country": "Cyprus",
    },
}

_JOBS: list[dict[str, Any]] = [
    {
        "id": "job_001",
        "client_id": "c_acme",
        "title": "Senior Python engineer to build a data pipeline (Airflow + dbt)",
        "description": (
            "We are a Series B analytics company and need an experienced Python "
            "engineer to design and build a production data pipeline using Airflow "
            "and dbt on top of Snowflake. You'll own ingestion from 5 REST APIs, "
            "write tested transformations, and set up CI. ~20 hrs/week for 3 months "
            "with a strong chance of extension. Please share a similar pipeline you built."
        ),
        "skills": ["Python", "Airflow", "dbt", "Snowflake"],
        "budget": None,
        "hourly_min": 55,
        "hourly_max": 85,
        "proposals": 4,
        "posted_at": _iso_days_ago(0),
        "category": "Data Engineering",
    },
    {
        "id": "job_002",
        "client_id": "c_brightml",
        "title": "Fine-tune an LLM for customer-support classification",
        "description": (
            "Looking for an ML engineer to fine-tune an open LLM to classify support "
            "tickets into 12 categories. We have ~8k labeled examples. Deliverables: "
            "training script, eval report, and a small inference API. Fixed scope."
        ),
        "skills": ["Machine Learning", "LLM", "PyTorch"],
        "budget": 3500,
        "proposals": 12,
        "posted_at": _iso_days_ago(1),
        "category": "AI / ML",
    },
    {
        "id": "job_003",
        "client_id": "c_ghost",
        "title": "Need developer ASAP!!!",
        "description": "Build app fast. Good pay. Contact me.",
        "skills": [],
        "budget": 40,
        "proposals": 2,
        "posted_at": _iso_days_ago(0),
        "category": "Web Development",
    },
    {
        "id": "job_004",
        "client_id": "c_churner",
        "title": "WordPress blog posts (ongoing)",
        "description": (
            "We publish daily and need help maintaining our WordPress site and "
            "formatting posts. Simple, repetitive work. Low budget but steady."
        ),
        "skills": ["WordPress"],
        "budget": 60,
        "proposals": 58,
        "posted_at": _iso_days_ago(2),
        "category": "Web Development",
    },
    {
        "id": "job_005",
        "client_id": "c_acme",
        "title": "Build a Retrieval-Augmented Generation (RAG) service",
        "description": (
            "Design and ship a RAG microservice: document ingestion, chunking, vector "
            "store (pgvector), and a FastAPI endpoint with evals. You'll work with our "
            "senior team. Clear spec attached, 6-week fixed milestone plan."
        ),
        "skills": ["Python", "RAG", "FastAPI", "Vector DB"],
        "budget": 9000,
        "proposals": 7,
        "posted_at": _iso_days_ago(0),
        "category": "AI / ML",
    },
]

_PROPOSALS: list[dict[str, Any]] = [
    {
        "proposal_id": "p_1001",
        "job_id": "job_777",
        "job_title": "Python automation for e-commerce reporting",
        "submitted_at": _iso_days_ago(6),
        "connects_spent": 12,
        "status": "active",
        "viewed_by_client": True,
        "shortlisted": True,
        "client_messaged": False,
    },
    {
        "proposal_id": "p_1002",
        "job_id": "job_778",
        "job_title": "Data cleaning for marketing dataset",
        "submitted_at": _iso_days_ago(3),
        "connects_spent": 8,
        "status": "active",
        "viewed_by_client": True,
        "shortlisted": False,
        "client_messaged": False,
    },
    {
        "proposal_id": "p_1003",
        "job_id": "job_779",
        "job_title": "LLM chatbot MVP",
        "submitted_at": _iso_days_ago(10),
        "connects_spent": 16,
        "status": "active",
        "viewed_by_client": False,
        "shortlisted": False,
        "client_messaged": False,
    },
]


def _enrich(job: dict[str, Any]) -> dict[str, Any]:
    """Merge client stats onto a job so one lookup is enough to score it."""
    client = _CLIENTS.get(job["client_id"], {})
    merged = {**job}
    for key in (
        "payment_verified",
        "client_total_spent",
        "client_total_hires",
        "client_hire_rate",
        "client_member_since",
        "client_open_jobs",
    ):
        merged[key] = client.get(key)
    merged["client_name"] = client.get("name")
    return merged


# --- tools (mirror the expected Upwork MCP surface) ---------------------------
@mcp.tool()
def search_jobs(
    query: str = "",
    min_budget: float = 0,
    max_proposals: int = 1000,
    posted_within_hours: int = 720,
) -> str:
    """Search Upwork job posts. Returns jobs enriched with client stats as JSON.

    Filter by free-text query (matched against title/skills/description), a
    minimum budget, a maximum number of existing proposals, and recency.
    """
    q = query.lower().strip()
    cutoff = datetime.now() - timedelta(hours=posted_within_hours)
    results: list[dict[str, Any]] = []
    for job in _JOBS:
        hay = " ".join(
            [job["title"], job["description"], " ".join(job.get("skills", []))]
        ).lower()
        if q and not any(term in hay for term in q.split()):
            continue
        if (job.get("proposals") or 0) > max_proposals:
            continue
        budget = job.get("budget") or job.get("hourly_max") or 0
        if budget and budget < min_budget:
            continue
        try:
            if datetime.fromisoformat(job["posted_at"]) < cutoff:
                continue
        except ValueError:
            pass
        results.append(_enrich(job))
    return json.dumps({"count": len(results), "jobs": results}, default=str)


@mcp.tool()
def get_job_details(job_id: str) -> str:
    """Get the full detail for one job, including the client's history, as JSON."""
    for job in _JOBS:
        if job["id"] == job_id:
            enriched = _enrich(job)
            enriched["client"] = _CLIENTS.get(job["client_id"], {})
            return json.dumps(enriched, default=str)
    return json.dumps({"error": f"job {job_id} not found"})


@mcp.tool()
def get_client_history(client_id: str) -> str:
    """Get a client's hiring history and red-flag indicators as JSON."""
    client = _CLIENTS.get(client_id)
    if not client:
        return json.dumps({"error": f"client {client_id} not found"})
    return json.dumps(client, default=str)


@mcp.tool()
def get_my_proposals() -> str:
    """List my active proposals with view / shortlist / message status as JSON."""
    return json.dumps({"count": len(_PROPOSALS), "proposals": _PROPOSALS}, default=str)


@mcp.tool()
def get_recent_activity(hours: int = 24) -> str:
    """Summarize new invitations, offers and messages in the last N hours as JSON."""
    activity = {
        "window_hours": hours,
        "invitations": [
            {
                "from_client": "Acme Analytics",
                "job_title": "Streaming ETL consultant",
                "received_at": _iso_days_ago(0),
            }
        ],
        "offers": [],
        "messages": [
            {
                "from_client": "BrightML Studio",
                "job_title": "Fine-tune an LLM for customer-support classification",
                "preview": "Thanks for the proposal — can you start next week?",
                "received_at": _iso_days_ago(0),
                "unread": True,
            }
        ],
    }
    return json.dumps(activity, default=str)


@mcp.tool()
def get_account_dashboard() -> str:
    """One-call overview: Connects balance, proposals, invitations, contracts as JSON."""
    dashboard = {
        "connects_balance": 58,
        "connects_spent_this_month": 96,
        "active_proposals": len(_PROPOSALS),
        "pending_invitations": 1,
        "unread_messages": 1,
        "open_contracts": 2,
        "job_success_score": 97,
        "available_this_month_earnings": 4200,
        "as_of": datetime.now().isoformat(timespec="seconds"),
    }
    return json.dumps(dashboard, default=str)


@mcp.tool()
def get_contracts() -> str:
    """List active contracts and their current milestones as JSON."""
    contracts = [
        {
            "contract_id": "k_501",
            "client": "Acme Analytics",
            "title": "Data pipeline (Airflow + dbt)",
            "type": "hourly",
            "rate": 70,
            "status": "active",
            "current_milestone": "Ingestion layer",
            "started_at": _iso_days_ago(28)[:10],
        },
        {
            "contract_id": "k_502",
            "client": "BrightML Studio",
            "title": "LLM eval harness",
            "type": "fixed",
            "budget": 2500,
            "status": "active",
            "current_milestone": "Baseline metrics (due in 5 days)",
            "started_at": _iso_days_ago(12)[:10],
        },
    ]
    return json.dumps({"count": len(contracts), "contracts": contracts}, default=str)


if __name__ == "__main__":
    mcp.run()
