# Security & Trust Model

This document describes exactly what the Upwork Copilot plugin runs, what it can
access, and what it deliberately cannot do. It is intended to make the plugin safe
to review before you install it from any marketplace.

## TL;DR

- **Read/draft-only.** No write actions are exposed. The plugin cannot submit
  proposals, send messages, accept/decline offers, or spend Connects.
- **No bundled LLM, no API keys.** The skill's CLI does zero LLM calls; the Claude
  host model does all reasoning. No model provider key is ever stored or sent.
- **One network destination:** the official Upwork MCP, `https://mcp.upwork.com/mcp`.
- **Your own account, your own machine.** Auth is a browser OAuth login to *your*
  Upwork account; tokens are cached locally with `0600` permissions. No credentials
  are committed to the repo or transmitted anywhere except Upwork.

## What executes

Installing the plugin places a skill on disk. The skill's data CLI runs only after
you explicitly run `./install.sh`, which creates an **isolated virtualenv** inside
the skill folder and installs just two dependencies:

- `mcp` (the Model Context Protocol client), pinned to the `1.x` line.
- `python-dotenv` (optional `.env` loading).

No CrewAI/LLM stack is installed into the skill venv. The CLI prints JSON to stdout
and nothing else.

## Authentication & credential handling

- Login uses the **MCP authorization spec**: Dynamic Client Registration
  (RFC 7591) + PKCE, with tokens bound to the MCP resource (RFC 8707). There is no
  shipped client id/secret and no manually-created Upwork API key.
- `login` opens your browser to Upwork's own authorize page; the OAuth redirect is
  caught on a loopback address (`http://127.0.0.1:8723/callback`).
- Cached locally under `~/.upwork_copilot/` (override with env vars):
  - `tokens.json` — access/refresh tokens, written mode `0600`.
  - `client.json` — the registered OAuth client, mode `0600`.
  - `config.env` — optional per-user config.
- Tokens refresh automatically and can be cleared with
  `... skill_cli logout`.

## Network destinations

The skill talks to exactly these hosts, all Upwork-owned:

- `https://mcp.upwork.com/mcp` — the MCP endpoint (and its `.well-known` metadata).
- `https://www.upwork.com/...` — Upwork's OAuth authorize / token / registration
  endpoints during login only.

No analytics, telemetry, or third-party calls.

## Least privilege

The CLI only wires up **read/draft** queries (jobs, profile, proposals, contracts,
dashboard, messages). Write/mutating MCP operations are intentionally not exposed,
so the plugin cannot take irreversible or Connect-spending actions on your behalf.

## Supply chain

The bundled Python in `skills/upwork-copilot/scripts/upwork_agent/` is **generated**
from the canonical source (`src/upwork_agent/` in the parent project) by
`build_skill.py`, which also verifies the bundle imports nothing outside the
no-LLM closure. Run `python build_skill.py --check` to confirm the bundle matches
source. No secrets are committed; auth artifacts live only in `~/.upwork_copilot/`.

## Your responsibilities

Automating account access may be subject to Upwork's Terms of Service and
API/MCP terms. You are responsible for ensuring your use is compliant. The
draft-and-confirm design keeps a human in the loop for every outbound action.

## Reporting a vulnerability

Please report security issues privately to **pf2707@gmail.com** rather than
opening a public issue.
