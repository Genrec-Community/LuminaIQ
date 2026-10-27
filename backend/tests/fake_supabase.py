"""
A tiny in-memory stand-in for the supabase-py client: enough of the PostgREST
query builder and auth admin API for the school tests. Not a general fake.
"""

from __future__ import annotations

import copy
import uuid
from datetime import datetime, timezone
from types import SimpleNamespace
from typing import Any, Dict, List


class Result(SimpleNamespace):
    pass


def _cmp_val(v):
    return v if v is not None else ""


class Query:
    def __init__(self, db: "FakeClient", table: str):
        self.db, self.table, self.filters, self.op, self.payload = db, table, [], "select", None
        self.count, self._limit, self._range, self._order, self.on_conflict = None, None, None, None, None

    # --- builders
    def select(self, cols="*", count=None):
        self.op, self.count = "select", count
        return self

    def insert(self, row):
        self.op, self.payload = "insert", row
        return self

    def upsert(self, row, on_conflict=None):
        self.op, self.payload, self.on_conflict = "upsert", row, on_conflict
        return self

    def update(self, fields):
        self.op, self.payload = "update", fields
        return self

    def delete(self):
        self.op = "delete"
        return self

    def eq(self, k, v):
        self.filters.append(lambda r: r.get(k) == v)
        return self

    def neq(self, k, v):
        self.filters.append(lambda r: r.get(k) != v)
        return self

    def in_(self, k, vals):
        vals = list(vals)
        self.filters.append(lambda r: r.get(k) in vals)
        return self

    def gt(self, k, v):
        self.filters.append(lambda r: r.get(k) is not None and str(r.get(k)) > str(v))
        return self

    def gte(self, k, v):
        self.filters.append(lambda r: r.get(k) is not None and str(r.get(k)) >= str(v))
        return self

    def lt(self, k, v):
        self.filters.append(lambda r: r.get(k) is not None and str(r.get(k)) < str(v))
        return self

    def lte(self, k, v):
        self.filters.append(lambda r: r.get(k) is not None and str(r.get(k)) <= str(v))
        return self

    def or_(self, expr):
        terms = []
        for part in expr.split(","):
            col, op, val = part.split(".", 2)
            terms.append((col, op, val))

        def f(r):
            for col, op, val in terms:
                v = r.get(col)
                if op == "ilike" and v is not None and val.strip("%").lower() in str(v).lower():
                    return True
                if op == "is" and val == "null" and v is None:
                    return True
                if op == "lte" and v is not None and str(v) <= val:
                    return True
            return False
        self.filters.append(f)
        return self

    def order(self, col, desc=False):
        self._order = (col, desc)
        return self

    def limit(self, n):
        self._limit = n
        return self

    def range(self, a, b):
        self._range = (a, b)
        return self

    # --- execution
    def _rows(self):
        return self.db.tables.setdefault(self.table, [])

    def _match(self, r):
        return all(f(r) for f in self.filters)

    def _check_unique(self, row, ignore=None):
        for cols in self.db.unique.get(self.table, []):
            key = tuple((row.get(c) or "").lower() if isinstance(row.get(c), str) else row.get(c) for c in cols)
            if any(v is None for v in key):
                continue
            for other in self._rows():
                if other is ignore:
                    continue
                okey = tuple((other.get(c) or "").lower() if isinstance(other.get(c), str) else other.get(c) for c in cols)
                if okey == key:
                    raise Exception(f"duplicate key value violates unique constraint ({','.join(cols)})")

    def _defaults(self, row):
        row = dict(row)
        row.setdefault("id", str(uuid.uuid4()))
        now = datetime.now(timezone.utc).isoformat()
        for k in ("created_at", "joined_at"):
            row.setdefault(k, now)
        for k, v in self.db.defaults.get(self.table, {}).items():
            row.setdefault(k, v)
        return row

    def execute(self):
        rows = self._rows()
        if self.op == "select":
            out = [r for r in rows if self._match(r)]
            if self._order:
                col, desc = self._order
                out.sort(key=lambda r: _cmp_val(r.get(col)), reverse=desc)
            total = len(out)
            if self._range:
                out = out[self._range[0]:self._range[1] + 1]
            if self._limit is not None:
                out = out[:self._limit]
            return Result(data=copy.deepcopy(out), count=total if self.count else None)
        if self.op == "insert":
            items = self.payload if isinstance(self.payload, list) else [self.payload]
            new = []
            for item in items:
                row = self._defaults(item)
                self._check_unique(row)
                pk = self.db.pk.get(self.table)
                if pk and any(all(o.get(c) == row.get(c) for c in pk) for o in rows):
                    raise Exception("duplicate key value violates primary key")
                rows.append(row)
                new.append(copy.deepcopy(row))
            return Result(data=new, count=None)
        if self.op == "upsert":
            items = self.payload if isinstance(self.payload, list) else [self.payload]
            cols = (self.on_conflict or "id").split(",")
            out = []
            for item in items:
                existing = next((r for r in rows if all(r.get(c) == item.get(c) for c in cols)), None)
                if existing:
                    existing.update(item)
                    out.append(copy.deepcopy(existing))
                else:
                    row = self._defaults(item)
                    rows.append(row)
                    out.append(copy.deepcopy(row))
            return Result(data=out, count=None)
        if self.op == "update":
            out = []
            for r in rows:
                if self._match(r):
                    r.update(self.payload)
                    out.append(copy.deepcopy(r))
            return Result(data=out, count=None)
        if self.op == "delete":
            keep = [r for r in rows if not self._match(r)]
            gone = [r for r in rows if self._match(r)]
            self.db.tables[self.table] = keep
            return Result(data=gone, count=None)
        raise NotImplementedError(self.op)


class FakeAdmin:
    def __init__(self, db):
        self.db = db
        self.users: Dict[str, Dict[str, Any]] = {}

    def create_user(self, attrs):
        email = attrs["email"].lower()
        if any(u["email"] == email for u in self.users.values()):
            raise Exception("A user with this email address has already been registered")
        uid = str(uuid.uuid4())
        self.users[uid] = {"id": uid, "email": email, "password": attrs.get("password"),
                           "user_metadata": attrs.get("user_metadata") or {}}
        return SimpleNamespace(user=SimpleNamespace(id=uid, email=email))

    def update_user_by_id(self, uid, attrs):
        self.users[uid].update(attrs)
        return SimpleNamespace(user=SimpleNamespace(id=uid, email=self.users[uid]["email"]))

    def delete_user(self, uid):
        self.users.pop(uid, None)

    def get_user_by_id(self, uid):
        u = self.users.get(uid)
        return SimpleNamespace(user=SimpleNamespace(id=uid, email=u["email"]) if u else None)


class FakeClient:
    def __init__(self):
        self.tables: Dict[str, List[Dict[str, Any]]] = {}
        self.unique = {
            "institution_members": [("login_id",), ("institution_id", "reg_no")],
            "institutions": [("teacher_code",)],
            "billing_events": [("event_id",)],
        }
        self.pk = {"institution_members": ("institution_id", "user_id"), "billing_events": ("event_id",)}
        self.defaults = {
            "institution_members": {"managed": False, "disabled": False, "must_change_password": False,
                                    "login_id": None, "reg_no": None},
            "institutions": {"approval_status": "pending", "status": "trial", "paid_until": None},
        }
        self.auth = SimpleNamespace(admin=FakeAdmin(self))

    def table(self, name):
        return Query(self, name)

    def rpc(self, *a, **k):
        return SimpleNamespace(execute=lambda: Result(data=0))
