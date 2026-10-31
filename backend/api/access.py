"""
Ownership checks for projects and documents.

The backend talks to Supabase with the service key, which skips the database's
row-level security, so the API itself must check that the caller owns what they
ask for. `enforce_resource_access` is attached to every authenticated router
(see api/v1/api.py). It finds project and document IDs wherever a request
carries them (path, query string, JSON or form body) and answers 404 for
anything the caller doesn't own. It's 404 rather than 403 so the API never
reveals which IDs exist.
"""

import json
import time
import uuid
from typing import Any, Dict, Iterable, List, Optional, Set, Tuple

from fastapi import Depends, HTTPException, Request

from api.deps import get_current_user
from db.client import async_db, get_supabase_client

PROJECT_KEYS = {"project_id"}
DOCUMENT_KEYS = {"document_id", "selected_documents", "document_ids"}

# Ownership never changes, so a confirmed (user, project) pair is safe to reuse briefly.
_CACHE_TTL = 60.0
_owned: Dict[Tuple[str, str], float] = {}


def clear_cache() -> None:
    _owned.clear()


def _not_found() -> HTTPException:
    return HTTPException(status_code=404, detail="Not found")


def _valid_ids(values: Iterable[Any]) -> List[str]:
    """IDs as strings; any value that isn't a UUID can't belong to anyone, so it's a 404."""
    out = []
    for v in values:
        try:
            out.append(str(uuid.UUID(str(v))))
        except (ValueError, TypeError, AttributeError):
            raise _not_found()
    return out


def _collect(data: Any, projects: Set[Any], documents: Set[Any]) -> None:
    """Gather project and document IDs from nested dicts and lists."""
    if isinstance(data, dict):
        for key, value in data.items():
            if value is None:
                continue
            if key in PROJECT_KEYS:
                projects.add(value) if not isinstance(value, list) else projects.update(value)
            elif key in DOCUMENT_KEYS:
                documents.add(value) if not isinstance(value, list) else documents.update(value)
            elif isinstance(value, (dict, list)):
                _collect(value, projects, documents)
    elif isinstance(data, list):
        for item in data:
            _collect(item, projects, documents)


async def assert_project_owner(project_id: str, user_id: str) -> None:
    await _assert_projects_owned(_valid_ids([project_id]), user_id)


async def _assert_projects_owned(project_ids: List[str], user_id: str) -> None:
    now = time.monotonic()
    missing = [p for p in set(project_ids) if _owned.get((user_id, p), 0) < now]
    if not missing:
        return
    client = get_supabase_client()
    res = await async_db(lambda: client.table("projects").select("id, user_id")
                         .in_("id", missing).execute())
    owned = {r["id"] for r in (res.data or []) if r.get("user_id") == user_id}
    if owned != set(missing):
        raise _not_found()
    for p in owned:
        _owned[(user_id, p)] = now + _CACHE_TTL


async def assert_documents_in_project(document_ids: List[str], user_id: str,
                                      project_id: Optional[str]) -> None:
    """Every document must belong to one of the user's projects (and to `project_id`, when given)."""
    ids = _valid_ids(document_ids)
    if not ids:
        return
    client = get_supabase_client()
    res = await async_db(lambda: client.table("documents").select("id, project_id")
                         .in_("id", list(set(ids))).execute())
    rows = res.data or []
    if len(rows) != len(set(ids)):
        raise _not_found()
    parents = {r["project_id"] for r in rows}
    if project_id is not None and parents != {project_id}:
        raise _not_found()
    await _assert_projects_owned(list(parents), user_id)


async def _request_body(request: Request) -> Any:
    content_type = request.headers.get("content-type", "")
    try:
        if content_type.startswith("application/json"):
            raw = await request.body()
            return json.loads(raw) if raw else None
        if content_type.startswith(("multipart/form-data", "application/x-www-form-urlencoded")):
            form = await request.form()
            return {k: v for k, v in form.items() if isinstance(v, str)}
    except (ValueError, UnicodeDecodeError):
        return None  # malformed body: FastAPI's own validation rejects it
    return None


async def enforce_resource_access(request: Request,
                                  current_user: dict = Depends(get_current_user)) -> None:
    projects: Set[Any] = set()
    documents: Set[Any] = set()
    _collect(dict(request.path_params), projects, documents)
    _collect({k: request.query_params.getlist(k) for k in request.query_params.keys()},
             projects, documents)
    _collect(await _request_body(request), projects, documents)
    if not projects and not documents:
        return

    user_id = current_user["id"]
    project_ids = _valid_ids(projects)
    if project_ids:
        await _assert_projects_owned(project_ids, user_id)
    if documents:
        # With exactly one project in play, documents must belong to that project.
        scope = project_ids[0] if len(set(project_ids)) == 1 else None
        await assert_documents_in_project(list(documents), user_id, scope)
