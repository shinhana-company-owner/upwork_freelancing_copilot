"""A CrewAI tool wrapping the deterministic job scorer.

The agent fetches jobs via the Upwork MCP, then passes them here to get an
objective, consistent quality score and scam flags instead of eyeballing them.
"""
from __future__ import annotations

import json
from typing import Any

from crewai.tools import tool

from ..scoring import rank_jobs


@tool("score_and_rank_jobs")
def score_and_rank_jobs(jobs_json: str) -> str:
    """Score and rank Upwork jobs by quality and scam risk.

    Pass the raw JSON returned by the Upwork `search_jobs` tool (either the full
    object with a `jobs` array, or a bare JSON array of job objects). Returns a
    JSON array of scored jobs sorted best-first, each with: job_id, title, score
    (0-100), tier (strong/decent/risky/avoid), recommend_apply (bool), flags, and
    a human-readable rationale. Use this before recommending the user spend any
    Connects.
    """
    try:
        data: Any = json.loads(jobs_json)
    except (json.JSONDecodeError, TypeError):
        return json.dumps({"error": "jobs_json was not valid JSON"})

    if isinstance(data, dict):
        jobs = data.get("jobs", [])
    elif isinstance(data, list):
        jobs = data
    else:
        jobs = []

    if not jobs:
        return json.dumps({"error": "no jobs found in input", "ranked": []})

    ranked = [s.as_dict() for s in rank_jobs(jobs)]
    return json.dumps({"count": len(ranked), "ranked": ranked}, default=str)
