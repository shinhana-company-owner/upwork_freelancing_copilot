# Upwork Copilot

> 🖥️ **Claude Code only.** This plugin needs a local shell: its skill runs a
> bundled Python CLI (`install.sh` → local virtualenv → browser OAuth → token
> cached under `~/.upwork_copilot/`). It is **not supported on claude.ai or
> Cowork**, which have no local environment to run it.

A Claude plugin that helps a freelancer work smarter on Upwork. It lets the Claude
host model **find and quality-score jobs** (flagging ghost/scam posts) to avoid burning and wasting Connects, **vet
clients**, and **draft proposals and cover letters** grounded in your real Upwork
profile — plus quick status checks on proposals, messages, contracts, Connects
balance, and earnings.

It is deliberately **read/draft-only**: it never submits proposals, sends
messages, or spends Connects. You stay in control (draft-and-confirm). See
[SECURITY.md](./SECURITY.md) for the full trust model and
[Privacy](./PRIVACY.md) for what data is handled.

> ⚠️ Use responsibly. Automating access to your Upwork account may be subject to
> Upwork's Terms of Service and API/MCP terms. You are responsible for compliant
> use.

## How it works

The plugin ships one skill, `upwork-copilot`, with:

- A small, **LLM-free** data CLI that talks to the **official Upwork MCP**
  (`https://mcp.upwork.com/mcp`) using your own account (browser OAuth), and
- A deterministic job scorer (0–100, tier, risk flags, recommend-apply).

There is **no bundled LLM** — the Claude host model is the brain. The skill only
provides data and scoring; Claude does the reasoning, writing, and presentation.

## Requirements

- An Upwork account (Freelancer Plus unlocks richer proposal/client insights, but
  is not required).
- Python 3.10–3.13 (for the skill's self-contained CLI venv).
- `uv` is used if present; otherwise it falls back to `python3 -m venv` + `pip`.

## Install

### 1. Add the marketplace and install the plugin

This plugin is published through the **ShinHana marketplace**:

```text
/plugin marketplace add pf2707/agentic_plugin_mobile_workflow
/plugin install upwork-copilot@shinhana-marketplace
```

(The plugin itself lives at `github.com/shinhana-company-owner/upwork_freelancing_copilot`;
the marketplace references it by a GitHub source, so you don't add that repo directly.)

### 2. One-time skill setup (builds the CLI venv + logs in)

The skill bundles its own code and installs into its own virtualenv (only the
`mcp` client and a `.env` loader — **no LLM libraries**). From the skill folder:

```bash
./install.sh                     # creates ./.venv and installs the bundled CLI
"$(pwd)/.venv/bin/python" -m upwork_agent.skill_cli login   # browser sign-in
```

`login` opens a browser so you sign in to **your own** Upwork account. The token
caches locally (`~/.upwork_copilot/`, mode `0600`) for ~24h and refreshes
automatically. No API key is ever needed.

## Usage

Just talk to Claude naturally — the skill triggers on Upwork intent:

- "Any good React jobs posted in the last few hours with budget over $500 and few
  proposals?" → scored, ranked results with apply/skip and risk flags.
- "Is this client safe to work with?" → client vetting from the job data.
- "Draft a proposal for the top one." → Claude pulls your profile first and writes
  a finished, copy-paste-ready draft (you review and submit yourself).
- "Give me a dashboard." → Connects balance, earnings, active proposals/contracts.

Under the hood each request runs the bundled CLI, which prints JSON:

```bash
"$SKILL_DIR/.venv/bin/python" -m upwork_agent.skill_cli jobs "react developer" --limit 10 --verified-only
```

## What it does *not* do

- No write actions are exposed at all — it cannot submit proposals, send messages,
  accept offers, or spend Connects.
- No LLM calls and no API keys inside the skill.
- No telemetry; the only network destination is the official Upwork MCP.

## Development

The Python under `skills/upwork-copilot/scripts/upwork_agent/` is **generated** from
the canonical source in the parent repo (`src/upwork_agent/`) by `build_skill.py`.
Don't hand-edit the bundle — fix the source and re-sync:

```bash
python build_skill.py            # sync the bundle
python build_skill.py --check    # CI: fail if the bundle is stale
```

## License

See the repository license.
