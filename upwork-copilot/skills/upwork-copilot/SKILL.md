---
name: upwork-copilot
description: >-
  Help a freelancer on Upwork: find and quality-score marketplace jobs (flagging
  ghost/scam posts), vet clients, draft proposals and cover letters grounded in
  the user's real profile, and check proposals, messages, contracts, Connects
  balance and earnings. Use whenever the user mentions Upwork, finding freelance
  work/jobs, writing an Upwork proposal or cover letter, or checking their Upwork
  account. Connects to the user's own Upwork account via the bundled CLI.
---

# Upwork Copilot (skill)

You (the host model) are the brain. This skill gives you an Upwork data CLI plus
a deterministic job scorer. There is **no separate LLM** — you do the reasoning,
writing, and presentation.

## Installation (one-time)

This skill is self-contained — it bundles its own code and installs into its own
virtualenv (only the `mcp` client; **no LLM libraries**). From the skill folder:

```bash
./install.sh                       # creates ./.venv and installs the bundled CLI
export SKILL_DIR="$(pwd)"          # where this skill lives
"$SKILL_DIR/.venv/bin/python" -m upwork_agent.skill_cli login   # browser sign-in
```

`login` opens a browser so the user signs in to **their own** Upwork account; the
token caches for ~24h and refreshes automatically. No LLM key is ever needed.

## Running the CLI

All commands run through the skill's own venv and print **JSON** to stdout
(errors as `{"error": "..."}`):

```bash
"$SKILL_DIR/.venv/bin/python" -m upwork_agent.skill_cli <command> [args]
```

If `SKILL_DIR` isn't set, it is this skill's own directory.

### Commands

| Command | Returns |
|---|---|
| `login` / `logout` / `status` | Manage/inspect the Upwork session. |
| `jobs "<query>" [--limit N] [--job-type fixed\|hourly] [--min-budget N] [--verified-only]` | Jobs **already scored & ranked** (0–100, tier, flags, recommend_apply). |
| `profile` | The user's own profile (title, skills, experience, rate, work history). |
| `proposals` | The user's submitted proposals + statuses. |
| `contracts` | `active` (in-progress) vs `recent_closed` contracts. |
| `dashboard` | Connects balance, available/pending earnings, active-contract count. |
| `messages` | Recent message rooms. |

## How to handle common requests

- **Find work / "any good jobs?"** → run `jobs "<keywords>"`. Present results
  best-first as a short table with score, tier, apply/skip, and the flags.
  Explicitly call out risky posts (unverified payment, unproven/low-rated client,
  saturated, low budget). The scoring is already done — don't re-rank arbitrarily;
  explain it.
- **Vet a client / "is this one safe?"** → use the `flags` and `rationale` already
  in the `jobs` output; recommend apply or skip.
- **Write a proposal / cover letter** → FIRST run `profile` and ground every claim
  in the real data (title, years, skills, past company/projects, rate). Use the
  chosen job's details for the client's needs. Keep it under ~200 words, open with
  "Hi there," (Upwork hides the client's name), reference concrete relevant
  experience, end with one question. **Never leave bracketed placeholders** like
  `[Number]` or `[Company]`; omit a detail rather than fake it. Produce a finished,
  copy-paste-ready draft and let the user review — **never submit it for them**.
- **Status checks** → `proposals`, `messages`, `contracts`, `dashboard`. When a
  command returns a list, actually list the items (titles + status), not just a count.

## Rules

- **Draft-and-confirm.** This skill is read/draft only; it never submits proposals,
  sends messages, or spends Connects. (Those write actions aren't exposed.)
- **Don't ask the user for info you can fetch** — pull it from `profile`/the job data.
- If a command returns `{"error": ...}`, relay it plainly (e.g. tell them to run
  `login` if not authenticated) rather than inventing data.

## Relationship to the standalone app

The parent repo also ships a **standalone** version (`uv run chat`) that bundles
its own LLM for users who want a self-contained CLI. This skill uses the exact
same data layer — the Python under `scripts/upwork_agent/` is a copy generated
from the repo's `src/upwork_agent/` by `build_skill.py` (don't hand-edit it; fix
the source and re-run the sync). The one exception is `config.py`, which is
hand-maintained for the skill: a slimmed, LLM-free, credential-free config (no
`MODEL`/`LLM_MAX_TOKENS`, no static token env read). The skill just lets *you* be
the model instead.
