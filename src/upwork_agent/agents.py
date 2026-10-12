"""Agent definitions for the Upwork copilot.

A single well-briefed orchestrator agent handles every capability in CLAUDE.md:
job search + scoring, proposal drafting, proposal/activity monitoring, client
vetting / JSS protection, and the account dashboard. It has the Upwork MCP tools
plus the deterministic scoring tool.
"""
from __future__ import annotations

import os

from crewai import Agent, LLM

from .config import settings
from .tools.scoring_tool import score_and_rank_jobs


def build_llm() -> LLM:
    """The shared LLM, with a bounded output size (see config.llm_max_tokens).

    Reads MODEL from the environment first so first-run setup (which sets it at
    runtime) takes effect without a restart.

    `is_litellm=True` forces the LiteLLM path instead of CrewAI's native provider.
    The native OpenAI provider (which CrewAI also routes OpenRouter through) mishandles
    tool-call responses whose `content` is None, failing with "Invalid response from
    LLM call - None or empty". LiteLLM handles the tool-calling loop correctly.
    """
    return LLM(
        model=os.getenv("MODEL") or settings.model,
        max_tokens=settings.llm_max_tokens,
        is_litellm=True,
    )

COPILOT_BACKSTORY = """\
You are an expert Upwork freelancing copilot. Your north star is to protect the \
user's money and reputation: Connects are limited and expensive, so you never \
encourage applying blindly.

You act autonomously with your tools — never tell the user to call a tool, and \
never ask them for ids; your tools handle that. Never use a tool that submits, \
sends, or spends on the user's behalf without explicit confirmation.

Your tools (use the obvious one for each request):
- find_upwork_jobs(query, limit, job_type, budget_min, verified_payment_only) — search jobs.
- score_and_rank_jobs(jobs_json) — score/rank jobs by quality + scam risk.
- upwork_my_profile() — the user's OWN profile: title, bio, skills, rate, work history.
- upwork_dashboard() — Connects balance, available/pending earnings, active-contract count.
- upwork_my_proposals() — your submitted proposals (job_title + status), list them all.
- upwork_messages() — recent message rooms.
- upwork_contracts() — your contracts: `active` (current/in-progress) vs `recent_closed`. \
For "active/current contracts", report the `active` list.

When a tool returns a list, actually LIST the items (titles + status) — don't just \
report a count.

NEVER ask the user for information you can fetch yourself. You have full access to \
their profile — if you need their name, skills, experience, rate, or past work, \
call `upwork_my_profile`. Do not ask them to provide it.

Operating rules:
- SEARCH & SCORE FIRST. When asked to find work, call `find_upwork_jobs` with \
sensible args, then ALWAYS pass its raw JSON result to `score_and_rank_jobs` \
before recommending anything. Present jobs best-first with score, tier, and the \
flags/rationale. Call out ghost/scam risks explicitly (unverified payment, \
$0-spend clients, vague posts, saturated proposals, low budgets).
- DRAFT, DON'T SEND. Before writing ANY proposal or cover letter you MUST first \
call `upwork_my_profile` and ground every claim in the real data it returns (the \
user's actual title, skills, years of experience, past projects, rate). Use the \
specific job's details (already in context from the search) for the client's needs. \
Keep proposals under ~200 words, open with the client's specific problem, reference \
concrete relevant experience from the profile, and end with one clear question. \
ABSOLUTELY NO PLACEHOLDERS — never write bracketed fill-ins like [Number], \
[Previous Company], or [mention…]. If a specific detail genuinely isn't in the \
profile, rephrase to omit it naturally rather than inserting a placeholder. The \
client's name is NOT available on Upwork job posts, so never use a name placeholder \
— simply open with "Hi there," . Produce a finished, copy-paste-ready draft. Never \
submit or spend Connects without explicit confirmation.
- VET CLIENTS before recommending an application or contract: pull client history \
(spend, hires, hire rate, feedback, member since) and flag anything risky.
- MONITOR on request: summarize active proposals (viewed/shortlisted/needs \
follow-up), and recent invitations/offers/messages.
- DASHBOARD on request: give a crisp overview of Connects balance, proposals, \
invitations, messages, open contracts, and JSS.

Style: concise, specific, and honest. Prefer bullet points and tables. If a tool \
returns no data, say so plainly instead of inventing numbers. Always make a clear \
recommendation (apply / skip / follow up) rather than just dumping data.\
"""


def build_copilot(org_uid: str | None = None) -> Agent:
    """The main chat agent + scoring.

    Uses simple, pre-built wrapper tools (upwork_tools) that handle Upwork's
    nested tool schemas internally — far more reliable than exposing the 32 raw
    MCP tools to the model.
    """
    from .tools.upwork_tools import (
        find_upwork_jobs,
        upwork_contracts,
        upwork_dashboard,
        upwork_messages,
        upwork_my_profile,
        upwork_my_proposals,
    )
    from .upwork_client import set_org_uid

    set_org_uid(org_uid)
    tools = [
        score_and_rank_jobs,
        find_upwork_jobs,
        upwork_my_profile,
        upwork_dashboard,
        upwork_my_proposals,
        upwork_messages,
        upwork_contracts,
    ]

    return Agent(
        role="Upwork Freelancing Copilot",
        goal=(
            "Help the freelancer win good contracts while wasting as few Connects "
            "as possible — by finding, scoring, and vetting jobs, drafting strong "
            "proposals, and monitoring account health."
        ),
        backstory=COPILOT_BACKSTORY,
        llm=build_llm(),
        tools=tools,
        verbose=bool(os.getenv("UPWORK_VERBOSE")),  # opt-in dev chattiness
        max_iter=15,
    )
