# Privacy Policy

_Last updated: 2026-10-12_

Upwork Copilot is a **local, read-only** Claude plugin. It runs entirely on the
user's own machine and talks only to Upwork. The author operates **no server,
backend, or analytics**, and therefore collects and retains **no data**.

## What data the plugin accesses

Through the user's own authenticated Upwork session (via the official Upwork
MCP), the plugin can read:

- The user's **own profile** (name, title, skills, work history, rate).
- The user's **proposals, messages, contracts, earnings, and Connects balance**.
- **Job listings and client information** used to score jobs and vet clients.

This data is returned to Claude **in-session only** so the model can score jobs,
vet clients, and draft proposals. The plugin does **not** write profiles,
messages, or client records to disk.

## What is stored, and where

The only item persisted is the user's **OAuth token**, stored **locally on the
user's own device** at `~/.upwork_copilot/` (file mode `0600`). It typically
expires within ~24 hours and can be deleted at any time with the skill's
`logout` command. The author never receives or sees this token.

## Where data goes

The plugin's only network destinations are **Upwork's own services**:

- the Upwork MCP (`https://mcp.upwork.com/mcp`), and
- Upwork's OAuth endpoints (`https://www.upwork.com/...`) during sign-in.

There is **no telemetry, no analytics, and no third-party service**. No data is
sold, shared, or sent anywhere other than Upwork and the Claude session running
the plugin.

## Data retention

The author retains **nothing** — there is no backend to retain it. Any local
cache lives only on the user's device under the user's control.

## Children

The plugin is intended for **adult freelancers (18+)**; Upwork's Terms of
Service require users to be 18 or older. It is not directed at children.

## Changes

Material changes to this policy will be reflected in this file with an updated
date above.

## Contact

Questions about privacy: **pf2707@gmail.com**.
