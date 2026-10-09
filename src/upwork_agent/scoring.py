"""Deterministic job-quality scoring and scam/ghost-post detection.

This is intentionally plain Python (no LLM): ranking jobs by client spend,
reputation and payment verification is a rules problem, and keeping it
deterministic makes it cheap, testable and consistent. The agent *explains* the
score; this module *computes* it.

Handles two input shapes transparently via `normalize_job`:
  • the live Upwork MCP `find_jobs` schema (client{} block, budget/proposals as
    strings, client.rating instead of a hire rate), and
  • the local mock schema (flat fields, numeric hire rate).
"""
from __future__ import annotations

import math
import re
from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Any


# --- tunables (sane defaults; override per-call if you like) -------------------
DEFAULT_MIN_DESCRIPTION_CHARS = 120
DEFAULT_SATURATED_PROPOSALS = 50
DEFAULT_LOW_BUDGET_USD = 50  # fixed-price floor
DEFAULT_LOW_HOURLY_RATE = 15  # $/hr floor


@dataclass
class JobScore:
    job_id: str
    title: str
    score: int  # 0-100
    tier: str  # "strong" | "decent" | "risky" | "avoid"
    recommend_apply: bool
    flags: list[str] = field(default_factory=list)
    rationale: list[str] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        return {
            "job_id": self.job_id,
            "title": self.title,
            "score": self.score,
            "tier": self.tier,
            "recommend_apply": self.recommend_apply,
            "flags": self.flags,
            "rationale": self.rationale,
        }


# --- parsing helpers ----------------------------------------------------------
def _parse_money(value: Any) -> float | None:
    """'$2,777,398.20' -> 2777398.2 ; numbers pass through."""
    if value in (None, ""):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    nums = re.findall(r"[\d,]+(?:\.\d+)?", str(value))
    if not nums:
        return None
    try:
        return float(nums[0].replace(",", ""))
    except ValueError:
        return None


def _parse_budget(value: Any) -> tuple[float | None, bool]:
    """Return (usd_value, is_hourly). Handles '20.00–40.00/hr', '$500', ranges."""
    if value in (None, ""):
        return None, False
    if isinstance(value, (int, float)):
        return float(value), False
    s = str(value)
    is_hourly = "/hr" in s or "hour" in s.lower()
    nums = [float(n.replace(",", "")) for n in re.findall(r"[\d,]+(?:\.\d+)?", s)]
    if not nums:
        return None, is_hourly
    return (sum(nums) / len(nums)), is_hourly  # midpoint for ranges


def _proposals_from_tier(value: Any) -> int | None:
    """Map Upwork's proposal tier string to a representative count.

    e.g. 'Less than 5' -> 3, '5 to 10' -> 7, '20 to 50' -> 35, '50+' -> 60.
    """
    if value in (None, ""):
        return None
    if isinstance(value, (int, float)):
        return int(value)
    s = str(value).lower()
    nums = [int(n) for n in re.findall(r"\d+", s)]
    if "+" in s and nums:
        return nums[0] + 10
    if "less than" in s and nums:
        return max(0, nums[0] - 2)
    if len(nums) >= 2:
        return (nums[0] + nums[1]) // 2
    if nums:
        return nums[0]
    return None


_TAG_RE = re.compile(r"</?[a-z_]+>", re.IGNORECASE)


def _clean_description(value: Any) -> tuple[str, bool]:
    """Strip wrapper tags; return (text, truncated?)."""
    text = _TAG_RE.sub("", str(value or "")).strip()
    truncated = text.endswith("...") or text.endswith("…")
    return text, truncated


def normalize_job(job: dict[str, Any]) -> dict[str, Any]:
    """Map either schema onto the flat fields the scorer uses."""
    client = job.get("client")
    if not isinstance(client, dict):
        # Already flat (mock) — still normalize a couple of derived fields.
        out = dict(job)
    else:
        # Live Upwork `find_jobs` shape.
        desc, truncated = _clean_description(job.get("description_snippet"))
        out = {
            "id": job.get("id"),
            "title": job.get("title"),
            "description": desc,
            "_description_truncated": truncated,
            # keep the raw budget string so hourly vs fixed is detectable later
            "budget": job.get("budget"),
            "proposals": _proposals_from_tier(job.get("proposals_tier")),
            "payment_verified": str(client.get("verification_status", "")).upper()
            == "VERIFIED",
            "client_total_spent": _parse_money(client.get("total_spent")),
            "client_total_hires": client.get("total_hires"),
            "client_total_reviews": client.get("total_reviews"),
            "client_total_jobs": client.get("total_posted_jobs"),
            "client_rating": client.get("rating"),
            "client_open_jobs": client.get("total_posted_jobs"),
        }
    # Shared numeric coercions.
    if isinstance(out.get("proposals"), str):
        out["proposals"] = _proposals_from_tier(out["proposals"])
    out["client_total_spent"] = _parse_money(out.get("client_total_spent"))
    return out


def _years_since(value: Any) -> float | None:
    if value in (None, ""):
        return None
    try:
        if isinstance(value, (int, float)):
            member = date(int(value), 1, 1)
        else:
            member = datetime.fromisoformat(str(value)[:10]).date()
    except (ValueError, TypeError):
        return None
    return max(0.0, (date.today() - member).days / 365.25)


def score_job(
    job: dict[str, Any],
    *,
    min_description_chars: int = DEFAULT_MIN_DESCRIPTION_CHARS,
    saturated_proposals: int = DEFAULT_SATURATED_PROPOSALS,
    low_budget_usd: int = DEFAULT_LOW_BUDGET_USD,
    low_hourly_rate: int = DEFAULT_LOW_HOURLY_RATE,
) -> JobScore:
    """Score a single job (either the live Upwork or mock shape)."""
    job = normalize_job(job)
    flags: list[str] = []
    rationale: list[str] = []
    score = 50.0  # neutral baseline

    job_id = str(job.get("id") or job.get("job_id") or "?")
    title = str(job.get("title") or "(untitled)")

    # --- payment verification (biggest single signal) ---
    verified = bool(job.get("payment_verified"))
    if verified:
        score += 18
        rationale.append("Payment method verified (+18).")
    else:
        score -= 22
        flags.append("payment_unverified")
        rationale.append("Payment NOT verified (-22) — common in ghost/scam posts.")

    # --- client reputation: rating freelancers gave this client (0..5) ---
    rating = job.get("client_rating")
    reviews = job.get("client_total_reviews") or 0
    if isinstance(rating, (int, float)) and reviews >= 3:
        if rating >= 4.9:
            score += 12
            rationale.append(f"Client rated {rating:.2f}/5 by freelancers (+12).")
        elif rating >= 4.7:
            score += 8
            rationale.append(f"Client rated {rating:.2f}/5 (+8).")
        elif rating >= 4.3:
            rationale.append(f"Client rated {rating:.2f}/5 (neutral).")
        else:
            score -= 15
            flags.append("low_client_rating")
            rationale.append(
                f"Client rated only {rating:.2f}/5 across {reviews} reviews — "
                "freelancers report bad experiences (-15)."
            )

    # --- legacy numeric hire rate (mock data only) ---
    hire_rate = job.get("client_hire_rate")
    if isinstance(hire_rate, (int, float)):
        contribution = round(hire_rate * 25)
        score += contribution
        rationale.append(f"Client hire rate {hire_rate:.0%} (+{contribution}).")
        if hire_rate < 0.10 and (job.get("client_open_jobs") or 0) >= 3:
            flags.append("low_hire_rate")
            score -= 18
            rationale.append("Very low hire rate while posting many jobs (-18).")

    # --- total client spend (trust via history), log-scaled to +25 ---
    spent = job.get("client_total_spent")
    hires = job.get("client_total_hires") or 0
    if isinstance(spent, (int, float)) and spent > 0:
        contribution = round(min(25, 5 * math.log10(spent + 1)))
        score += contribution
        rationale.append(f"Client has spent ${spent:,.0f} historically (+{contribution}).")
    elif (spent in (0, None)) and hires == 0 and reviews == 0:
        flags.append("unproven_client")
        score -= 8
        rationale.append("Client has no spend/hires/reviews — unproven (-8).")

    # --- proposal saturation (fewer = better odds) ---
    proposals = job.get("proposals")
    if isinstance(proposals, (int, float)):
        if proposals <= 5:
            score += 12
            rationale.append(f"~{proposals} proposals so far (+12).")
        elif proposals <= 15:
            score += 5
            rationale.append(f"~{proposals} proposals — still reasonable (+5).")
        elif proposals >= saturated_proposals:
            flags.append("saturated")
            score -= 12
            rationale.append(f"~{proposals}+ proposals — saturated (-12).")
        else:
            rationale.append(f"~{proposals} proposals.")

    # --- budget adequacy (hourly rate vs fixed-price use different floors) ---
    budget, is_hourly = _parse_budget(job.get("budget"))
    if budget is None and (job.get("hourly_min") or job.get("hourly_max")):
        rates = [float(r) for r in (job.get("hourly_min"), job.get("hourly_max")) if r]
        budget = sum(rates) / len(rates) if rates else None
        is_hourly = True
    if budget is not None:
        floor = low_hourly_rate if is_hourly else low_budget_usd
        unit = "/hr" if is_hourly else ""
        if budget < floor:
            flags.append("low_budget")
            score -= 8
            rationale.append(f"Budget ~${budget:,.0f}{unit} is low (-8).")
        else:
            score += 8
            rationale.append(f"Budget ~${budget:,.0f}{unit} is workable (+8).")

    # --- description detail (vague posts waste Connects) ---
    description = str(job.get("description") or "")
    truncated = bool(job.get("_description_truncated"))
    if not truncated and len(description.strip()) < min_description_chars:
        flags.append("vague_description")
        score -= 12
        rationale.append(
            f"Description is only {len(description.strip())} chars — vague/low-detail (-12)."
        )

    # --- account age (mock) ---
    years = _years_since(job.get("client_member_since"))
    if years is not None and years < 0.08 and not verified:
        flags.append("brand_new_unverified_client")
        score -= 6
        rationale.append("Brand-new unverified account (-6).")

    score_int = int(max(0, min(100, round(score))))

    if score_int >= 75:
        tier = "strong"
    elif score_int >= 55:
        tier = "decent"
    elif score_int >= 35:
        tier = "risky"
    else:
        tier = "avoid"

    # Flags that, regardless of score, mean "don't spend Connects here".
    hard_blockers = {
        "payment_unverified",
        "vague_description",
        "low_hire_rate",
        "unproven_client",
        "low_client_rating",
    }
    recommend_apply = (
        score_int >= 60
        and tier in {"strong", "decent"}
        and not (hard_blockers & set(flags))
    )

    return JobScore(
        job_id=job_id,
        title=title,
        score=score_int,
        tier=tier,
        recommend_apply=recommend_apply,
        flags=flags,
        rationale=rationale,
    )


def rank_jobs(jobs: list[dict[str, Any]], **kwargs: Any) -> list[JobScore]:
    """Score and sort jobs best-first."""
    scored = [score_job(j, **kwargs) for j in jobs]
    scored.sort(key=lambda s: s.score, reverse=True)
    return scored
