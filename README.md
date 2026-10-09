# Upwork Copilot

An AI agent (built on [CrewAI](https://docs.crewai.com)) that connects to the
official **Upwork MCP** (`https://mcp.upwork.com/mcp`) to help you freelance
smarter — without burning Connects on ghost/low-quality jobs.

It does everything in [`CLAUDE.md`](./CLAUDE.md):

- **Find & score jobs before you spend Connects** — searches, then scores every
  job (0–100) on client spend, hire rate, payment verification, proposal
  saturation and budget, and flags ghost/scam posts.
- **Draft proposals** (draft-and-confirm — it never submits for you).
- **Monitor** your proposals (viewed / shortlisted / needs follow-up) and recent
  invitations, offers and messages.
- **Vet clients / protect your JSS** before you apply or accept.
- **Account dashboard** — Connects balance, proposals, messages, contracts, JSS.

## How it works

```
CLI chat (main.py)  →  Copilot Agent (agents.py)
                           ├── Upwork MCP tools         (mcp_config.py → live or mock)
                           └── score_and_rank_jobs tool (scoring.py — deterministic)
```

Job scoring is **plain Python** (`scoring.py`), not the LLM: ranking by spend,
hire rate and verification is a rules problem, so it stays cheap, consistent and
testable. The agent *explains* the scores and drives the conversation.

## Quick start

```bash
crewai install            # creates .venv and installs deps
# edit .env with your keys (see below)
crewai run                # starts the interactive chat   (alias: uv run chat)
```

Then chat:

```
you › Find Python/AI jobs posted recently and rank them by quality
you › Give me full details and red flags for job_005
you › Draft a proposal for the top one
you › Show my proposals that need follow-up
```

### Configuration (`.env`)

| Variable | Purpose |
|---|---|
| `MODEL` | LLM for the agent. e.g. `anthropic/claude-sonnet-4-6`, `openai/gpt-4o`, or OpenRouter `openrouter/<vendor>/<model>` (the `openrouter/` prefix is required). |
| `ANTHROPIC_API_KEY` / `OPENAI_API_KEY` / `OPENROUTER_API_KEY` | Key for the chosen provider. **Required.** |
| `LLM_MAX_TOKENS` | Max output tokens per call (default `4096`) — caps cost/credit use. |
| `UPWORK_MOCK` | `true` → local mock (default). Set `false` to go live via browser OAuth. |
| `UPWORK_OAUTH_SCOPE` | Optional OAuth scope(s); usually leave blank. |
| `UPWORK_OAUTH_REDIRECT_PORT` | Loopback port for the OAuth callback (default `8723`). |
| `UPWORK_MCP_TOKEN` | Power-user: a token you minted yourself; skips the browser flow. |
| `UPWORK_MCP_URL` | Live MCP URL (default `https://mcp.upwork.com/mcp`). |

The agent picks its connection in this order: `UPWORK_MOCK=true` → **mock**;
else a `UPWORK_MCP_TOKEN` → **static token**; else `UPWORK_MOCK=false` →
**browser OAuth** (self-registering); else → **mock**.

### Mock mode (no Upwork account needed)

The default. The agent talks to a local mock MCP server (`mock_upwork_mcp.py`)
with realistic fixtures, so you can build and demo everything without an account
or spending Connects. Going live doesn't change any agent code — only the env.

### Connect a real Upwork account (OAuth browser login)

The live Upwork MCP authenticates with **OAuth 2.0 (authorization code + PKCE)**
and the MCP authorization spec. **No manual Upwork app or API key is needed** —
the client **self-registers** via Dynamic Client Registration on first login, so
you ship *zero credentials*. Each user logs into *their own* Upwork account in the
browser. Ideal for a published, multi-user app.

> ⚠️ Do **not** use a key from `https://www.upwork.com/developer/keys/apply`. That
> is a GraphQL-API credential; its tokens (`oauth2v2_pub_…`) are **rejected by the
> MCP with 401**. Only a dynamically-registered client gets MCP-audience tokens
> (`oauth2v2_pmc_…`). This is why there is no `UPWORK_OAUTH_CLIENT_ID` setting.

**To go live:**
```bash
# in .env: set UPWORK_MOCK=false  (nothing else needed)
uv run login     # self-registers, opens the browser, you log in, token cached
uv run chat      # now talks to your real account
uv run logout    # clears the cached token
```
`crewai run` also triggers the browser login automatically on first use. Tokens
are cached at `~/.upwork_copilot/tokens.json` (mode `600`) and refreshed
automatically (~24h tokens); the self-registered client is cached at
`~/.upwork_copilot/client.json`. Each user authenticates on their own machine.

## Testing

```bash
uv run smoke   # offline: starts the mock MCP, calls every tool, runs the scorer
```

The smoke test needs **no API key** — it validates MCP connectivity and the
scoring/ranking pipeline end-to-end. The interactive chat additionally needs an
LLM key for the agent's reasoning.

## Project layout

```
src/upwork_agent/
├── main.py             # interactive CLI chat (REPL)
├── agents.py           # the copilot Agent (MCP tools + scorer)
├── auth.py             # Upwork OAuth (browser login + PKCE + token cache)
├── scoring.py          # deterministic job scoring + scam detection
├── mcp_config.py       # live Upwork MCP vs local mock selector
├── mock_upwork_mcp.py  # local mock MCP server (fixtures)
├── config.py           # env-driven settings
├── smoke_test.py       # offline end-to-end test
└── tools/
    └── scoring_tool.py # CrewAI tool wrapping scoring.py
```
