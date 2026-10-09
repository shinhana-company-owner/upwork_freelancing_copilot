#!/usr/bin/env python
"""Interactive CLI chat for the Upwork copilot.

Run with:  crewai run     (or)   uv run chat

Each turn calls the copilot agent, which has the Upwork MCP (live or mock) plus
the deterministic job scorer. Conversation history is kept in-process so you can
have a back-and-forth ("find me RAG jobs" -> "draft a proposal for #1").
"""
from __future__ import annotations

import contextlib
import getpass
import io
import itertools
import logging
import os
import sys
import threading
import time
from pathlib import Path

try:
    from dotenv import load_dotenv

    load_dotenv()
except Exception:  # dotenv is optional; env may already be set
    pass


def _user_config_file() -> Path:
    override = os.getenv("UPWORK_USER_CONFIG")
    if override:
        return Path(override).expanduser()
    return Path.home() / ".upwork_copilot" / "config.env"


def _load_user_config() -> None:
    """Load the per-user saved config (LLM provider + key) into the environment.

    Does not overwrite values already set in the real environment / .env.
    """
    path = _user_config_file()
    if not path.exists():
        return
    try:
        for line in path.read_text().splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            key, value = key.strip(), value.strip()
            if key and not os.getenv(key):
                os.environ[key] = value
    except OSError:
        pass


# Persisted user config must load before anything reads settings/MODEL.
_load_user_config()


def _silence_frameworks() -> None:
    """Quiet CrewAI/LiteLLM/MCP logging so the chat shows only results + errors."""
    for name in ("LiteLLM", "litellm", "crewai", "httpx", "httpcore", "mcp", "asyncio"):
        logging.getLogger(name).setLevel(logging.ERROR)
    try:
        import litellm

        litellm.suppress_debug_info = True
        litellm.set_verbose = False
    except Exception:
        pass
    # CrewAI's event listener hardcodes a verbose ConsoleFormatter that prints the
    # big "LiteAgent"/tool panels. It's a singleton — flip its formatter off.
    try:
        from crewai.events.event_listener import EventListener

        EventListener().formatter.verbose = False
    except Exception:
        pass


@contextlib.contextmanager
def _quiet():
    """Swallow a block's stdout/stderr (CrewAI's panels, tool-call traces, etc.)."""
    sink = io.StringIO()
    with contextlib.redirect_stdout(sink), contextlib.redirect_stderr(sink):
        yield


class _Spinner:
    """A tiny terminal spinner shown while the agent works.

    Writes to the real stdout captured at construction, so it stays visible even
    when the worker's stdout is redirected by `_quiet`.
    """

    _FRAMES = "⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏"

    def __init__(self, text: str = "copilot is working…") -> None:
        self.text = text
        self._out = sys.stdout  # real terminal, captured before _quiet swaps it
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._tty = bool(getattr(self._out, "isatty", lambda: False)())

    def __enter__(self) -> _Spinner:
        if self._tty:
            self._thread = threading.Thread(target=self._spin, daemon=True)
            self._thread.start()
        return self

    def _spin(self) -> None:
        for frame in itertools.cycle(self._FRAMES):
            if self._stop.is_set():
                break
            self._out.write(f"\r{frame} {self.text}")
            self._out.flush()
            time.sleep(0.1)

    def __exit__(self, *exc: object) -> None:
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=1)
        if self._tty:
            self._out.write("\r" + " " * (len(self.text) + 4) + "\r")
            self._out.flush()

from .agents import build_copilot
from .config import settings
from .mcp_config import connection_summary

BANNER = """\
┌────────────────────────────────────────────────────────────┐
│  Upwork Copilot                                              │
│  find & score jobs · draft proposals · vet clients · stats  │
└────────────────────────────────────────────────────────────┘"""

HELP = """\
Try things like:
  • "Find Python/AI jobs posted recently and rank them by quality"
  • "Give me full details and red flags for job_005"
  • "Draft a proposal for the top job"
  • "Show my active proposals and which need follow-up"
  • "Summarize invitations and messages from the last 24 hours"
  • "Give me my account dashboard"
Commands:  help · reset · exit"""

# Keep recent turns so the agent has context without unbounded prompt growth.
_MAX_HISTORY_TURNS = 8


def _build_prompt(history: list[tuple[str, str]], user_message: str) -> str:
    if not history:
        return user_message
    recent = history[-_MAX_HISTORY_TURNS * 2 :]
    transcript = "\n".join(f"{role}: {text}" for role, text in recent)
    return (
        "Conversation so far (for context):\n"
        f"{transcript}\n\n"
        f"User's new message: {user_message}"
    )


# model prefix -> the env var that must hold its API key
_PROVIDER_KEYS: list[tuple[tuple[str, ...], str]] = [
    (("openrouter/",), "OPENROUTER_API_KEY"),
    (("anthropic/", "claude-"), "ANTHROPIC_API_KEY"),
    (("openai/", "gpt-"), "OPENAI_API_KEY"),
    (("gemini/", "google/"), "GEMINI_API_KEY"),
    (("groq/",), "GROQ_API_KEY"),
]


# Errors that are usually a transient provider hiccup (OpenRouter returning a
# finish_reason='error' / empty body) — worth retrying the whole turn.
_TRANSIENT_MARKERS = ("none or empty", "invalid response", "finish_reason", "timeout", "rate limit")


def _run_turn(copilot, prompt: str, attempts: int = 3) -> str:
    """Run one agent turn, retrying transient empty/error responses."""
    last = ""
    for i in range(attempts):
        try:
            with _Spinner(), _quiet():  # spinner on the real terminal; hide framework noise
                reply = (copilot.kickoff(prompt).raw or "").strip()
            if reply:
                return reply
            last = "empty response"
        except Exception as e:  # noqa: BLE001
            last = str(e)
            if not any(m in last.lower() for m in _TRANSIENT_MARKERS):
                return f"⚠ Something went wrong this turn: {e}"
        if i < attempts - 1:
            print(f"  (provider returned an empty/error response — retrying {i + 2}/{attempts}…)")
            time.sleep(1.5 * (i + 1))
    return (
        "⚠ The model provider kept returning an empty/error response "
        f"({attempts} tries). This is usually a transient OpenRouter hiccup or a "
        "low credit balance. Try again in a moment, top up credit, or switch MODEL "
        f"in .env. [last: {last}]"
    )


def _active_model() -> str:
    return os.getenv("MODEL") or settings.model


# Provider menu for first-run setup: label -> (env var, example model).
_SETUP_PROVIDERS = [
    ("OpenRouter (many models, one key)", "OPENROUTER_API_KEY", "openrouter/openai/gpt-4o-mini"),
    ("OpenAI", "OPENAI_API_KEY", "openai/gpt-4o-mini"),
    ("Anthropic", "ANTHROPIC_API_KEY", "anthropic/claude-sonnet-4-6"),
]


def _save_user_config(updates: dict[str, str]) -> None:
    """Merge key=value pairs into the per-user config file (mode 600)."""
    path = _user_config_file()
    existing: dict[str, str] = {}
    if path.exists():
        for line in path.read_text().splitlines():
            if "=" in line and not line.strip().startswith("#"):
                k, _, v = line.partition("=")
                existing[k.strip()] = v.strip()
    existing.update(updates)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(f"{k}={v}" for k, v in existing.items()) + "\n")
    try:
        os.chmod(path, 0o600)
    except OSError:
        pass


def _prompt_llm_setup() -> str | None:
    """Interactively collect the user's LLM provider + key; persist them.

    Returns None on success, or an error string if it couldn't be configured.
    """
    if not sys.stdin.isatty():
        return _check_llm_key() or "No LLM key configured (set MODEL + an API key in .env)."

    print("\nLet's set up your AI model (one-time).")
    for i, (label, _var, _model) in enumerate(_SETUP_PROVIDERS, 1):
        print(f"  {i}) {label}")
    choice = (input("Choose a provider [1]: ").strip() or "1")
    try:
        label, env_var, default_model = _SETUP_PROVIDERS[int(choice) - 1]
    except (ValueError, IndexError):
        label, env_var, default_model = _SETUP_PROVIDERS[0]

    model = input(f"Model id [{default_model}]: ").strip() or default_model
    key = getpass.getpass(f"Paste your {label.split(' ')[0]} API key (input hidden): ").strip()
    if not key:
        return "No API key entered — cannot continue."

    os.environ["MODEL"] = model
    os.environ[env_var] = key
    _save_user_config({"MODEL": model, env_var: key})
    print(f"✓ Saved to {_user_config_file()} — you won't be asked again.\n")
    return None


def _missing(var: str) -> bool:
    value = (os.getenv(var) or "").strip()
    return not value or value.upper().startswith("YOUR_")


def _check_llm_key() -> str | None:
    """Return an error string if the configured model has no API key, else None."""
    model = _active_model().lower()
    for prefixes, env_var in _PROVIDER_KEYS:
        if model.startswith(prefixes):
            if _missing(env_var):
                return f"{env_var} is not set (required for model '{settings.model}')."
            return None
    return None  # unknown provider — let LiteLLM surface any auth error itself


def chat() -> None:
    _silence_frameworks()
    print(BANNER)
    print(f"Connection : {connection_summary()}")
    print(f"Model      : {_active_model()}")
    if settings.auth_mode == "oauth":
        from .auth import login_status

        print(f"Upwork auth: {login_status()} (a browser may open on first use)")

    if _check_llm_key() is not None:
        # First run (or missing key): walk the user through setup interactively.
        err = _prompt_llm_setup()
        if err:
            print(f"\n⚠  {err}")
            return

    # Pre-flight the live connection so auth failures are legible (not a wall of
    # async tracebacks) and we don't enter the loop with a broken connection.
    org_uid: str | None = None
    if settings.auth_mode != "mock":
        from .auth import AuthError, get_access_token
        from .health import check_live_connection, get_org_uid

        try:
            token = get_access_token(interactive=True)  # browser login if needed
        except AuthError as e:
            print(f"\n⚠  Upwork login failed: {e}")
            return

        print("\nChecking the Upwork MCP connection…")
        ok, detail = check_live_connection(settings.upwork_mcp_url, token)
        if not ok:
            print(f"⚠  Could not connect to the live Upwork MCP: {detail}\n")
            print("   Try `logout` then `login` for a fresh token. If a 401")
            print("   persists, the token isn't accepted by the MCP for this")
            print("   account/app — see the README 'Live connection' notes.")
            print("   To keep working now, set UPWORK_MOCK=true in .env.")
            return
        print(f"✓ Connected — {len(detail)} Upwork tools available.")
        org_uid = get_org_uid(settings.upwork_mcp_url, token)
        if org_uid:
            print(f"✓ Account resolved (org_uid …{org_uid[-6:]}).")

    print("\n" + HELP + "\n")

    with _quiet():
        copilot = build_copilot(org_uid)
    history: list[tuple[str, str]] = []
    interactive = sys.stdin.isatty()

    while True:
        try:
            user_message = input("you › ").strip() if interactive else sys.stdin.readline()
        except (EOFError, KeyboardInterrupt):
            print("\nbye 👋")
            break

        if not interactive:
            if user_message == "":  # EOF on piped input
                break
            user_message = user_message.strip()
            if user_message:
                print(f"you › {user_message}")

        if not user_message:
            continue
        if user_message.lower() in {"exit", "quit", ":q"}:
            print("bye 👋")
            break
        if user_message.lower() == "help":
            print(HELP)
            continue
        if user_message.lower() == "reset":
            history.clear()
            print("(conversation cleared)")
            continue

        reply = _run_turn(copilot, _build_prompt(history, user_message))
        print(f"\ncopilot › {reply}\n")
        history.append(("User", user_message))
        history.append(("Copilot", reply))


def login() -> None:
    """Force a fresh browser login to Upwork and cache the token."""
    if settings.use_mock:
        print(
            "Running in MOCK mode — no Upwork login needed.\n"
            "To connect a real account, set UPWORK_MOCK=false in .env, then run"
            " `uv run login` again."
        )
        return
    if settings.auth_mode == "static":
        print("A static UPWORK_MCP_TOKEN is configured — OAuth login is not used.")
        return

    from .auth import AuthError, get_access_token, login_status

    try:
        get_access_token(force_login=True)
        print(f"Status: {login_status()}")
    except AuthError as e:
        print(f"⚠ Login failed: {e}")


def logout() -> None:
    """Clear any cached Upwork token."""
    from .auth import clear_cache

    print("Logged out (token cache cleared)." if clear_cache() else "No cached token to clear.")


def setup() -> None:
    """(Re)configure the LLM provider + API key, saved to the user config file."""
    _silence_frameworks()
    err = _prompt_llm_setup()
    print(f"⚠  {err}" if err else "Setup complete. Run `chat` to start.")


def main() -> None:
    chat()


if __name__ == "__main__":
    main()
