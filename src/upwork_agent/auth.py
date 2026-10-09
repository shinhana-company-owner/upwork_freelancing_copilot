"""Browser-based OAuth for the live Upwork MCP (the MCP authorization spec).

Designed for a *published, multi-user* app: the app registers itself with
Upwork's authorization server via Dynamic Client Registration (RFC 7591), so
there's NO manual Upwork app to create and no client id to ship. Each user logs
into their own Upwork account in the browser.

Why DCR: a manually-created key from /developer/keys/apply mints tokens for the
GraphQL API audience, which the MCP rejects as invalid_token. A dynamically
registered client gets tokens bound to the MCP's own audience (RFC 8707).

Flow:
  1. Discover Upwork's OAuth endpoints + resource from the MCP's well-known metadata.
  2. Register this client (DCR) — cached and reused across logins.
  3. Open the browser to Upwork's authorize page; user logs in + consents.
  4. Catch the redirect on 127.0.0.1:<port>, exchange the code (+ PKCE verifier)
     for tokens, binding them to the MCP resource.
  5. Cache tokens (0600) and refresh automatically when they expire.

Stdlib only — no extra dependencies.
"""
from __future__ import annotations

import base64
import hashlib
import json
import os
import secrets
import time
import urllib.error
import urllib.parse
import urllib.request
import webbrowser
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import Any

from .config import settings

# Fallbacks if discovery can't reach the network; kept in sync with the
# values published at Upwork's .well-known metadata.
_FALLBACK_META = {
    "authorization_endpoint": "https://www.upwork.com/ab/account-security/oauth2/authorize",
    "token_endpoint": "https://www.upwork.com/api/v3/oauth2/token",
    "registration_endpoint": "https://www.upwork.com/register",
    "resource": "https://mcp.upwork.com/mcp",
}
_PROTECTED_RESOURCE_META = (
    "https://mcp.upwork.com/.well-known/oauth-protected-resource/mcp"
)
_EXPIRY_MARGIN_SECONDS = 60
# Upwork sits behind Cloudflare, which 403s the default "Python-urllib" agent
# on some endpoints (notably /register). Present a normal browser UA.
_USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/129.0.0.0 Safari/537.36"
)


class AuthError(RuntimeError):
    pass


# --- small HTTP helpers -------------------------------------------------------
def _get_json(url: str, timeout: int = 15) -> dict[str, Any]:
    req = urllib.request.Request(
        url, headers={"Accept": "application/json", "User-Agent": _USER_AGENT}
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.load(resp)


def _post_form(
    url: str,
    data: dict[str, str],
    *,
    auth: tuple[str, str | None] | None = None,
    timeout: int = 20,
) -> dict[str, Any]:
    body = urllib.parse.urlencode(data).encode()
    headers = {
        "Content-Type": "application/x-www-form-urlencoded",
        "Accept": "application/json",
        "User-Agent": _USER_AGENT,
    }
    # Confidential client: authenticate with HTTP Basic (client_secret_basic).
    if auth and auth[1]:
        raw = f"{auth[0]}:{auth[1]}".encode()
        headers["Authorization"] = "Basic " + base64.b64encode(raw).decode()
    req = urllib.request.Request(url, data=body, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.load(resp)
    except urllib.error.HTTPError as e:  # surface the server's error body
        detail = e.read().decode(errors="replace")
        raise AuthError(f"token endpoint returned {e.code}: {detail}") from e


def _post_json(url: str, payload: dict[str, Any], timeout: int = 20) -> dict[str, Any]:
    body = json.dumps(payload).encode()
    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json",
        "User-Agent": _USER_AGENT,
    }
    req = urllib.request.Request(url, data=body, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.load(resp)
    except urllib.error.HTTPError as e:
        detail = e.read().decode(errors="replace")
        raise AuthError(f"registration endpoint returned {e.code}: {detail}") from e


# --- discovery ----------------------------------------------------------------
def discover_endpoints() -> dict[str, str]:
    """Resolve Upwork's authorize/token endpoints + resource via RFC 9728 metadata."""
    try:
        prm = _get_json(_PROTECTED_RESOURCE_META)
        issuer = prm["authorization_servers"][0].rstrip("/")
        meta = _get_json(f"{issuer}/.well-known/oauth-authorization-server")
        return {
            "authorization_endpoint": meta["authorization_endpoint"],
            "token_endpoint": meta["token_endpoint"],
            "registration_endpoint": meta.get("registration_endpoint")
            or _FALLBACK_META["registration_endpoint"],
            # RFC 8707 resource indicator — the token must be bound to this, or
            # the MCP rejects it as invalid_token.
            "resource": prm.get("resource") or settings.upwork_mcp_url,
        }
    except Exception:
        return dict(_FALLBACK_META)


# --- PKCE ---------------------------------------------------------------------
def _b64url(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode()


def _new_pkce() -> tuple[str, str]:
    verifier = _b64url(secrets.token_bytes(32))
    challenge = _b64url(hashlib.sha256(verifier.encode()).digest())
    return verifier, challenge


# --- loopback callback server -------------------------------------------------
class _CallbackHandler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:  # noqa: N802 (stdlib naming)
        parsed = urllib.parse.urlparse(self.path)
        if not parsed.path.startswith("/callback"):
            self.send_response(404)
            self.end_headers()
            return
        self.server.auth_query = urllib.parse.parse_qs(parsed.query)  # type: ignore[attr-defined]
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.end_headers()
        self.wfile.write(
            b"<html><body style='font-family:sans-serif;text-align:center;"
            b"padding-top:60px'><h2>Upwork login complete \xe2\x9c\x93</h2>"
            b"<p>You can close this tab and return to the terminal.</p>"
            b"</body></html>"
        )

    def log_message(self, *_args: Any) -> None:  # silence default logging
        pass


def _wait_for_callback(port: int, timeout: int = 300) -> dict[str, list[str]]:
    httpd = HTTPServer(("127.0.0.1", port), _CallbackHandler)
    httpd.auth_query = None  # type: ignore[attr-defined]
    httpd.timeout = 1
    deadline = time.time() + timeout
    try:
        while httpd.auth_query is None:  # type: ignore[attr-defined]
            if time.time() > deadline:
                raise AuthError("timed out waiting for the Upwork login callback")
            httpd.handle_request()
        return httpd.auth_query  # type: ignore[attr-defined]
    finally:
        httpd.server_close()


# --- token cache --------------------------------------------------------------
def _load_cache() -> dict[str, Any] | None:
    path = settings.token_cache_path
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text())
    except (json.JSONDecodeError, OSError):
        return None


def _save_cache(tokens: dict[str, Any]) -> None:
    path = settings.token_cache_path
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(tokens, indent=2))
    try:
        os.chmod(path, 0o600)
    except OSError:
        pass


def clear_cache() -> bool:
    """Delete cached tokens. Returns True if a cache existed."""
    path = settings.token_cache_path
    if path.exists():
        path.unlink()
        return True
    return False


# --- dynamically-registered client cache --------------------------------------
def _load_client() -> dict[str, Any] | None:
    path = settings.client_cache_path
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text())
    except (json.JSONDecodeError, OSError):
        return None


def _save_client(reg: dict[str, Any]) -> None:
    path = settings.client_cache_path
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(reg, indent=2))
    try:
        os.chmod(path, 0o600)
    except OSError:
        pass


def clear_client() -> bool:
    """Delete the cached dynamic client registration."""
    path = settings.client_cache_path
    if path.exists():
        path.unlink()
        return True
    return False


def _register_client(meta: dict[str, str]) -> dict[str, Any]:
    """Dynamically register this app with Upwork (RFC 7591) and cache it."""
    reg = _post_json(
        meta["registration_endpoint"],
        {
            "client_name": "Upwork Copilot",
            "redirect_uris": [settings.redirect_uri],
            "grant_types": ["authorization_code", "refresh_token"],
            "response_types": ["code"],
            "token_endpoint_auth_method": "none",  # public client + PKCE
            "application_type": "native",
        },
    )
    creds = {
        "client_id": reg["client_id"],
        "client_secret": reg.get("client_secret"),
        "redirect_uri": settings.redirect_uri,
        "registration_access_token": reg.get("registration_access_token"),
    }
    _save_client(creds)
    return creds


def _ensure_client(meta: dict[str, str]) -> tuple[str, str | None]:
    """Return (client_id, client_secret), registering dynamically if needed.

    Always uses Dynamic Client Registration. A manual /developer/keys/apply key
    is deliberately NOT supported here: it mints GraphQL-audience tokens the MCP
    rejects (401), which is a confusing footgun. Only DCR yields MCP-audience
    tokens. (Use UPWORK_MCP_TOKEN for a token you minted yourself out-of-band.)
    """
    cached = _load_client()
    if cached and cached.get("client_id") and cached.get("redirect_uri") == settings.redirect_uri:
        return cached["client_id"], cached.get("client_secret")
    creds = _register_client(meta)
    return creds["client_id"], creds["client_secret"]


def _store_token_response(payload: dict[str, Any], *, keep_refresh: str | None = None) -> dict[str, Any]:
    expires_in = int(payload.get("expires_in", 3600))
    tokens = {
        "access_token": payload["access_token"],
        "refresh_token": payload.get("refresh_token") or keep_refresh,
        "expires_at": int(time.time()) + expires_in,
        "scope": payload.get("scope"),
        "token_type": payload.get("token_type", "Bearer"),
    }
    _save_cache(tokens)
    return tokens


# --- the flow -----------------------------------------------------------------
def _run_browser_flow(meta: dict[str, str]) -> dict[str, Any]:
    client_id, client_secret = _ensure_client(meta)
    verifier, challenge = _new_pkce()
    state = secrets.token_urlsafe(24)

    params = {
        "response_type": "code",
        "client_id": client_id,
        "redirect_uri": settings.redirect_uri,
        "state": state,
        "code_challenge": challenge,
        "code_challenge_method": "S256",
        "resource": meta["resource"],
    }
    if settings.oauth_scope:
        params["scope"] = settings.oauth_scope
    auth_url = meta["authorization_endpoint"] + "?" + urllib.parse.urlencode(params)

    print("\nOpening your browser to log in to Upwork…")
    print("If it doesn't open, paste this URL into your browser:\n")
    print(f"  {auth_url}\n")
    try:
        webbrowser.open(auth_url)
    except Exception:
        pass

    query = _wait_for_callback(settings.oauth_redirect_port)

    if "error" in query:
        raise AuthError(
            f"Upwork returned an error: {query['error'][0]} "
            f"{query.get('error_description', [''])[0]}"
        )
    if query.get("state", [None])[0] != state:
        raise AuthError("OAuth state mismatch — possible CSRF, aborting.")
    code = query.get("code", [None])[0]
    if not code:
        raise AuthError("no authorization code in the callback")

    exchange = {
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": settings.redirect_uri,
        "client_id": client_id,
        "code_verifier": verifier,
        "resource": meta["resource"],
    }
    payload = _post_form(
        meta["token_endpoint"], exchange, auth=(client_id, client_secret)
    )
    tokens = _store_token_response(payload)
    print("✓ Logged in to Upwork and cached your token.\n")
    return tokens


def _refresh(meta: dict[str, str], refresh_token: str) -> dict[str, Any]:
    client_id, client_secret = _ensure_client(meta)
    data = {
        "grant_type": "refresh_token",
        "refresh_token": refresh_token,
        "client_id": client_id,
        "resource": meta["resource"],
    }
    payload = _post_form(meta["token_endpoint"], data, auth=(client_id, client_secret))
    return _store_token_response(payload, keep_refresh=refresh_token)


def _is_valid(tokens: dict[str, Any]) -> bool:
    return bool(tokens.get("access_token")) and (
        int(tokens.get("expires_at", 0)) - _EXPIRY_MARGIN_SECONDS > time.time()
    )


def get_access_token(*, force_login: bool = False, interactive: bool = True) -> str:
    """Return a valid bearer token, logging in / refreshing as needed.

    - `force_login=True` ignores the cache and runs a fresh browser login.
    - `interactive=False` refuses to open a browser (refresh/cache only), raising
      AuthError if a login would be required — useful for headless contexts.
    """
    # Power-user static token wins and needs no OAuth at all.
    if settings.upwork_token:
        return settings.upwork_token

    meta = discover_endpoints()

    if not force_login:
        cached = _load_cache()
        if cached and _is_valid(cached):
            return cached["access_token"]
        if cached and cached.get("refresh_token"):
            try:
                return _refresh(meta, cached["refresh_token"])["access_token"]
            except AuthError:
                pass  # refresh failed → fall through to a fresh login

    if not interactive:
        raise AuthError("login required but interactive browser flow is disabled")

    return _run_browser_flow(meta)["access_token"]


def login_status() -> str:
    cached = _load_cache()
    if settings.upwork_token:
        return "using a static UPWORK_MCP_TOKEN (no OAuth)"
    if not cached:
        return "not logged in"
    if _is_valid(cached):
        remaining = int(cached["expires_at"] - time.time())
        return f"logged in (token valid for ~{remaining // 60} min)"
    if cached.get("refresh_token"):
        return "token expired (will refresh on next use)"
    return "token expired (re-login required)"
