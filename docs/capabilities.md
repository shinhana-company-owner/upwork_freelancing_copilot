# Upwork Copilot — Capabilities & Test Checklist

A pre-release checklist of everything the agent can do. Run each item in the
chat and confirm the "Expected result". All read actions are free — **no Connects
are spent** unless you explicitly confirm a submission.

---

## 0. Setup & run

**Prerequisites**
- An LLM key in `.env` (e.g. `OPENROUTER_API_KEY`) with some credit, and `MODEL`
  set (default `openrouter/openai/gpt-4o-mini`).
- For live Upwork: `UPWORK_MOCK=false` in `.env` (no manual Upwork key needed).

**Commands**

| Command | What it does |
|---|---|
| `uv run setup` | Choose your AI provider and paste your API key (saved to `~/.upwork_copilot/config.env`, mode 600). |
| `uv run login` | Browser login to your Upwork account (self-registers; caches token ~24h). |
| `uv run chat` | Start the interactive copilot (alias: `crewai run`). |
| `uv run logout` | Clear the cached Upwork token. |
| `uv run smoke` | Offline test of the scoring pipeline (no account, no LLM key). |

**First-run key prompt:** if no LLM key is configured, `chat` automatically runs
setup — it asks which provider (OpenRouter / OpenAI / Anthropic), the model id,
and your API key (hidden input), then saves it to `~/.upwork_copilot/config.env`
so it's never asked again and never committed to the repo. This is how published
users supply **their own** key — you ship none.

**In-chat commands:** `help`, `reset` (clear conversation), `exit`.

**Startup checklist**
- [ ] `uv run login` opens the browser and ends with "✓ Logged in".
- [ ] `uv run chat` prints `✓ Connected — N Upwork tools available` and
      `✓ Account resolved`.
- [ ] Output is clean — no tool-call panels or framework logs, only results.

---

## 1. Find & score jobs (the biggest win)

Search the marketplace and rank every job 0–100 on client spend, rating,
payment verification, proposal saturation and budget — so you don't waste
Connects on low-quality or ghost posts.

**Try:**
- `find flutter jobs posted within the last day and rank them by quality and budget`
- `find python data engineering jobs, hourly, verified clients only`
- `show me the top 5 react native jobs with budget over $1000`

**Expected result**
- [ ] A table ranked best-first with **score**, **tier** (strong/decent/risky/avoid),
      **apply/skip** recommendation, and **flags**.
- [ ] A clear recommendation per job, not just raw data.

---

## 2. Vet clients & flag scams / ghost posts

Protects your Connects and JSS by calling out risky posts.

**Try:**
- `which of these are risky and why?`
- `vet the client on the top job`

**Expected result**
- [ ] Risky posts flagged with reasons: `payment_unverified`, `unproven_client`,
      `low_client_rating`, `saturated`, `low_budget`, `vague_description`.
- [ ] Unverified / unproven / low-rated clients are recommended **skip**.

---

## 3. Draft proposals & cover letters

Writes a finished, ready-to-send draft grounded in **your real profile** — it
fetches your title, skills, experience, past work and rate automatically.

**Try:**
- `write me a proposal for the top flutter job`
- `draft a cover letter for the digital wallet job`

**Expected result**
- [ ] It does **not** ask you for your experience/skills — it pulls them itself.
- [ ] **No `[placeholders]`** — real company/experience, opens with "Hi there,".
- [ ] Under ~200 words, references the job's specifics, ends with one question.
- [ ] It presents a **draft** and asks before sending — never auto-submits.

---

## 4. Monitor your proposals

**Try:**
- `show my active proposals`
- `which of my proposals need follow-up?`

**Expected result**
- [ ] Lists your submitted proposals and their status; highlights ones to follow up.

---

## 5. Messages & invitations

**Try:**
- `any new messages?`
- `summarize my recent Upwork conversations`

**Expected result**
- [ ] Summarizes recent message rooms / unread threads.

---

## 6. Contracts & account health

**Try:**
- `list my active contracts`
- `give me my account dashboard`
- `what's my Connects balance and earnings?`

**Expected result**
- [ ] Dashboard: Connects balance, active contracts, proposals, earnings.
- [ ] Contracts list with client and status.

---

## 7. Multi-turn flow (end to end)

**Try, in sequence:**
1. `find flutter jobs posted in the last day, rank by quality`
2. `vet the top one`
3. `write me a proposal for it`
4. `make it shorter and more technical`

**Expected result**
- [ ] It remembers context across turns (the "top one" refers to step 1's result).
- [ ] Refinements apply to the previous draft.

---

## Safety guarantees (verify)

- [ ] No Connects are spent by searching, scoring, vetting, drafting, or monitoring.
- [ ] Proposals are **draft-and-confirm** — nothing is submitted/sent without you
      explicitly saying so.
- [ ] Errors show as a single `⚠ …` line (not a stack trace); transient provider
      blips auto-retry up to 3×.

---

## Modes

| Mode | How | Use |
|---|---|---|
| **Live** | `UPWORK_MOCK=false` + `uv run login` | Real account via browser OAuth. |
| **Mock** | `UPWORK_MOCK=true` | Offline fixtures — demo/dev without an account or Connects. |

Multi-user: each user runs `login` and signs into **their own** account; the app
self-registers with Upwork, so you ship **no credentials**. Each user supplies
their own LLM key (or you front an LLM gateway).

---

## Known limitations / notes

- **Client name** is hidden on Upwork job posts, so proposals open with "Hi there,".
- **Scoring** is deterministic (client spend, rating, verification, proposals,
  budget). It uses `client.rating` (freelancer→client reviews), not a hire rate,
  since the live API doesn't expose hire rate.
- **Model matters:** small models can stumble on multi-step turns. `gpt-4o-mini`
  is a reliable, cheap default; a stronger model gives better proposals.
- **Submitting proposals** from chat is intentionally not enabled yet (draft-only).
  Can be added behind an explicit confirmation step on request.
- Token auto-refreshes (~24h). If a turn ever fails repeatedly, check OpenRouter
  credit or run `logout` then `login`.
