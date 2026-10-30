"""
School-created student sign-ins.

A school creates accounts for its students instead of asking them to sign up.
Each account gets a sign-in ID of the form

    <studentname>-<last 2 digits of the register number>@<STUDENT_LOGIN_DOMAIN>
    e.g. Arun Kumar, reg. no. 21CS107  ->  arunkumar-07@luminaiq.fun

The ID is only a sign-in name: there is no mailbox behind it and nothing is ever
emailed to it. When two students would get the same ID (anywhere on the platform,
since the domain is shared by every school) a number is added to the name part:
arunkumar-07, arunkumar2-07, arunkumar3-07, ...

Passwords are checked with Supabase Auth's REST endpoint directly instead of the
shared supabase-py client: signing in on the shared client switches every later
database call of the whole backend to that user's token (supabase-py listens to
its own SIGNED_IN event), which breaks backend-only tables.
"""

from __future__ import annotations

import re
import secrets
import unicodedata
from typing import Any, Dict, Iterable, List, Optional

import httpx

from config.settings import settings

MAX_NAME_PART = 24
MAX_SUFFIX_TRIES = 200
_PW_ALPHABET_LOWER = "abcdefghjkmnpqrstuvwxyz"
_PW_ALPHABET_UPPER = "ABCDEFGHJKLMNPQRSTUVWXYZ"
_PW_DIGITS = "23456789"


class InvalidCredentials(Exception):
    """Wrong ID or password (or the account can't sign in with a password)."""


class AuthUnavailable(Exception):
    """Supabase Auth could not be reached."""


# ------------------------------------------------------------------ sign-in IDs

def login_domain() -> str:
    return (settings.STUDENT_LOGIN_DOMAIN or "luminaiq.fun").strip().lower().lstrip("@")


def is_school_login(email: Optional[str]) -> bool:
    """True for IDs on the student sign-in domain (which nobody may sign up with)."""
    return bool(email) and email.strip().lower().endswith("@" + login_domain())


def name_slug(name: str) -> str:
    """'Arun Kumar' -> 'arunkumar'; 'Zoë D'Souza' -> 'zoedsouza'. Never empty."""
    text = unicodedata.normalize("NFKD", name or "").encode("ascii", "ignore").decode("ascii")
    slug = re.sub(r"[^a-z0-9]", "", text.lower())[:MAX_NAME_PART]
    return slug or "student"


def reg_suffix(reg_no: str) -> str:
    """Last two digits of the register number ('21CS107' -> '07', 'A5' -> '05')."""
    digits = re.sub(r"\D", "", reg_no or "")
    if not digits:
        raise ValueError("The register number needs at least one digit.")
    return digits[-2:].rjust(2, "0")


def local_part(name: str, reg_no: str, n: int = 1) -> str:
    """The part before @. n > 1 is used when the plain one is taken."""
    base = name_slug(name)
    return f"{base}{n if n > 1 else ''}-{reg_suffix(reg_no)}"


def candidate_ids(name: str, reg_no: str, start: int = 1, count: int = 20) -> List[str]:
    return [f"{local_part(name, reg_no, n)}@{login_domain()}" for n in range(start, start + count)]


_CUSTOM_LOCAL = re.compile(r"^[a-z0-9](?:[a-z0-9._-]{0,38}[a-z0-9])?$")


def custom_login_id(local: str) -> str:
    """A school's own choice of ID (letters, digits, . _ -)."""
    local = (local or "").strip().lower()
    if "@" in local:
        local, _, domain = local.partition("@")
        if domain and domain != login_domain():
            raise ValueError(f"Sign-in IDs must end with @{login_domain()}.")
    if not _CUSTOM_LOCAL.match(local):
        raise ValueError("Use 2-40 letters, digits, dots, dashes or underscores for the ID.")
    return f"{local}@{login_domain()}"


# -------------------------------------------------------------------- passwords

def password_problem(password: str) -> Optional[str]:
    """Why a password isn't acceptable, or None."""
    if not password or len(password) < 8:
        return "Passwords need at least 8 characters."
    if len(password) > 72:
        return "Passwords can be at most 72 characters."
    if not re.search(r"[A-Za-z]", password) or not re.search(r"\d", password):
        return "Passwords need at least one letter and one number."
    return None


def generate_password() -> str:
    """Easy to read out in class: no 0/O, 1/l/I. e.g. 'Kemu-4827-tapd'."""
    pick = lambda alphabet, n: "".join(secrets.choice(alphabet) for _ in range(n))  # noqa: E731
    return f"{pick(_PW_ALPHABET_UPPER, 1)}{pick(_PW_ALPHABET_LOWER, 3)}-{pick(_PW_DIGITS, 4)}-{pick(_PW_ALPHABET_LOWER, 4)}"


# -------------------------------------------------------- Supabase Auth (REST)

def _auth_key() -> str:
    return settings.SUPABASE_KEY or settings.SUPABASE_SERVICE_KEY


async def password_grant(email: str, password: str) -> Dict[str, Any]:
    """
    Check an email/ID + password with Supabase Auth without touching the shared
    client. Returns the Supabase user object.
    """
    url = f"{settings.SUPABASE_URL.rstrip('/')}/auth/v1/token?grant_type=password"
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            r = await client.post(url, json={"email": email, "password": password},
                                  headers={"apikey": _auth_key(), "Content-Type": "application/json"})
    except httpx.HTTPError as e:
        raise AuthUnavailable(str(e))
    if r.status_code >= 500:
        raise AuthUnavailable(f"Supabase Auth returned {r.status_code}")
    if r.status_code != 200:
        try:
            body = r.json()
        except ValueError:
            body = {}
        msg = body.get("error_description") or body.get("msg") or body.get("message") or "Invalid login credentials"
        raise InvalidCredentials(msg)
    data = r.json()
    user = data.get("user") or {}
    if not user.get("id"):
        raise InvalidCredentials("Invalid login credentials")
    return user


async def rest_signup(email: str, password: str, data: Dict[str, Any]) -> Dict[str, Any]:
    """Supabase sign-up (sends the confirmation email if enabled) without the shared client."""
    url = f"{settings.SUPABASE_URL.rstrip('/')}/auth/v1/signup"
    try:
        async with httpx.AsyncClient(timeout=20) as client:
            r = await client.post(url, json={"email": email, "password": password, "data": data},
                                  headers={"apikey": _auth_key(), "Content-Type": "application/json"})
    except httpx.HTTPError as e:
        raise AuthUnavailable(str(e))
    if r.status_code >= 500:
        raise AuthUnavailable(f"Supabase Auth returned {r.status_code}")
    try:
        body = r.json()
    except ValueError:
        body = {}
    if r.status_code >= 400:
        raise Exception(body.get("msg") or body.get("error_description") or body.get("message") or "Sign-up failed")
    # With confirmations on, the body is the user; with them off it's a session with .user
    return body.get("user") or body


def dedupe_preserving_order(items: Iterable[str]) -> List[str]:
    seen, out = set(), []
    for x in items:
        if x not in seen:
            seen.add(x)
            out.append(x)
    return out
