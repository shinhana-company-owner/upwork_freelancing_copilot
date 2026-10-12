#!/usr/bin/env python
"""No-LLM command-line interface for the Upwork Copilot *skill*.

The host model (Claude) is the brain; this CLI just exposes Upwork data and the
deterministic job scorer as JSON commands. It needs an Upwork login but NO LLM
key. Each command prints JSON to stdout (errors as {"error": "..."}).

Usage:
    python -m upwork_agent.skill_cli <command> [args]

Commands:
    login                 Browser login to Upwork (one-time; caches token ~24h).
    logout                Clear the cached Upwork token.
    status                Print auth/connection status.
    jobs <query> [--limit N] [--job-type fixed|hourly] [--min-budget N] [--verified-only]
                          Search + deterministically score/rank jobs.
    profile               The user's own freelancer profile (for writing proposals).
    proposals             The user's submitted proposals + statuses.
    contracts             Active + recently-closed contracts.
    dashboard             Connects balance, earnings, active-contract count.
    messages              Recent message rooms.
"""
from __future__ import annotations

import argparse
import json
import sys

try:
    from dotenv import load_dotenv

    load_dotenv()
except Exception:
    pass


def _emit(obj: object) -> None:
    print(json.dumps(obj, indent=2, default=str))


def _ensure_logged_in() -> str | None:
    """Return None if we have a usable token, else an error dict-ready message."""
    from .auth import AuthError, get_access_token

    try:
        get_access_token(interactive=False)
        return None
    except AuthError:
        return "Not logged in. Run: python -m upwork_agent.skill_cli login"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="upwork-skill", add_help=True)
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("login")
    sub.add_parser("logout")
    sub.add_parser("status")
    p_jobs = sub.add_parser("jobs")
    p_jobs.add_argument("query")
    p_jobs.add_argument("--limit", type=int, default=10)
    p_jobs.add_argument("--job-type", default="", choices=["", "fixed", "hourly"])
    p_jobs.add_argument("--min-budget", type=float, default=0)
    p_jobs.add_argument("--verified-only", action="store_true")
    for name in ("profile", "proposals", "contracts", "dashboard", "messages"):
        sub.add_parser(name)

    args = parser.parse_args(argv)

    # --- auth management commands ---
    if args.command == "login":
        from .auth import AuthError, get_access_token, login_status

        try:
            get_access_token(force_login=True, interactive=True)
            _emit({"status": "ok", "detail": login_status()})
            return 0
        except AuthError as e:
            _emit({"error": str(e)})
            return 1

    if args.command == "logout":
        from .auth import clear_cache

        _emit({"status": "ok", "cleared": clear_cache()})
        return 0

    if args.command == "status":
        from .auth import login_status
        from .config import settings

        _emit({"auth_mode": settings.auth_mode, "login": login_status(), "mcp_url": settings.upwork_mcp_url})
        return 0

    # --- data commands (require login) ---
    err = _ensure_logged_in()
    if err:
        _emit({"error": err})
        return 1

    from . import queries

    try:
        if args.command == "jobs":
            result = queries.search_and_rank(
                args.query,
                limit=args.limit,
                job_type=args.job_type,
                budget_min=args.min_budget,
                verified_payment_only=args.verified_only,
            )
        elif args.command == "profile":
            result = queries.my_profile()
        elif args.command == "proposals":
            result = queries.my_proposals()
        elif args.command == "contracts":
            result = queries.contracts()
        elif args.command == "dashboard":
            result = queries.dashboard()
        elif args.command == "messages":
            result = queries.messages()
        else:  # pragma: no cover
            _emit({"error": f"unknown command {args.command}"})
            return 1
    except Exception as e:  # noqa: BLE001 — surface a clean error to the host
        _emit({"error": f"{type(e).__name__}: {e}"})
        return 1

    _emit(result)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
