"""
Postgres access with the same call shape as supabase-py's table builder.

The services were written against Supabase (`client.table("x").select(...).eq(...)
.execute()`), and there are ~250 such calls. This module gives that exact surface
on top of a plain Postgres connection pool, so the data could move off Supabase
without rewriting every service. Only the subset the code uses is implemented:

    select(cols, count="exact") insert(row | rows) upsert(row | rows, on_conflict,
    ignore_duplicates) update(fields) delete()
    eq neq gt gte lt lte in_ is_ or_ contains match order limit range
    single maybe_single execute          and   rpc(name, params).execute()

Results look like PostgREST's: `.data` is a list of dicts (or one dict for
single(), a bare value for scalar functions), with UUIDs and timestamps as
strings and JSON columns as Python objects. Every value is sent as a query
parameter cast to its column's type; nothing from the caller is pasted into SQL.
Calls are synchronous; services run them in a thread through db.client.async_db.
"""

from __future__ import annotations

import datetime as _dt
import decimal
import re
import threading
import uuid
from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

from psycopg import sql
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb
from psycopg_pool import ConnectionPool


@dataclass
class Result:
    data: Any
    count: Optional[int] = None


class QueryError(Exception):
    pass


# ----------------------------------------------------------------------------- values

def _out(value: Any) -> Any:
    """A database value as PostgREST would return it in JSON."""
    if isinstance(value, uuid.UUID):
        return str(value)
    if isinstance(value, (_dt.datetime, _dt.date, _dt.time)):
        return value.isoformat()
    if isinstance(value, decimal.Decimal):
        return int(value) if value == value.to_integral_value() else float(value)
    if isinstance(value, list):
        return [_out(v) for v in value]
    return value


def _row_out(row: Dict[str, Any]) -> Dict[str, Any]:
    return {k: _out(v) for k, v in row.items()}


@dataclass(frozen=True)
class Column:
    name: str
    sql_type: str     # e.g. "uuid", "text[]", "timestamp with time zone"

    @property
    def is_json(self) -> bool:
        return self.sql_type in ("json", "jsonb")


class _Catalog:
    """Column types, primary keys and function signatures, looked up once per process."""

    def __init__(self, client: "PgClient"):
        self._client = client
        self._lock = threading.Lock()
        self._columns: Dict[str, Dict[str, Column]] = {}
        self._pkeys: Dict[str, List[str]] = {}
        self._funcs: Dict[str, Tuple[Dict[str, str], str, bool]] = {}

    def columns(self, table: str) -> Dict[str, Column]:
        if table not in self._columns:
            with self._client.pool.connection() as conn:
                rows = conn.execute(
                    """SELECT a.attname AS name, format_type(a.atttypid, a.atttypmod) AS type
                       FROM pg_attribute a JOIN pg_class c ON c.oid = a.attrelid
                       JOIN pg_namespace n ON n.oid = c.relnamespace
                       WHERE c.relname = %s AND n.nspname = current_schema()
                         AND a.attnum > 0 AND NOT a.attisdropped""", (table,)).fetchall()
            if not rows:
                raise QueryError(f'relation "{table}" does not exist')
            with self._lock:
                self._columns[table] = {
                    r["name"]: Column(r["name"], re.sub(r"\(.*?\)", "", r["type"])) for r in rows
                }
        return self._columns[table]

    def column(self, table: str, name: str) -> Column:
        cols = self.columns(table)
        if name not in cols:
            raise QueryError(f'column {table}.{name} does not exist')
        return cols[name]

    def primary_key(self, table: str) -> List[str]:
        if table not in self._pkeys:
            with self._client.pool.connection() as conn:
                rows = conn.execute(
                    """SELECT a.attname AS name FROM pg_index i
                       JOIN pg_attribute a ON a.attrelid = i.indrelid AND a.attnum = ANY(i.indkey)
                       WHERE i.indrelid = %s::regclass AND i.indisprimary""", (table,)).fetchall()
            with self._lock:
                self._pkeys[table] = [r["name"] for r in rows]
        return self._pkeys[table]

    def function(self, name: str) -> Tuple[Dict[str, str], str, bool]:
        """(argument name -> SQL type, return kind, returns a set)."""
        if name not in self._funcs:
            with self._client.pool.connection() as conn:
                row = conn.execute(
                    """SELECT p.proargnames AS names,
                              ARRAY(SELECT format_type(t, NULL) FROM unnest(p.proargtypes::oid[]) t) AS types,
                              rt.typtype AS kind, p.proretset AS setof, rt.typname AS rettype
                       FROM pg_proc p JOIN pg_namespace n ON n.oid = p.pronamespace
                       JOIN pg_type rt ON rt.oid = p.prorettype
                       WHERE p.proname = %s AND n.nspname = current_schema()""", (name,)).fetchone()
            if not row:
                raise QueryError(f"function {name} does not exist")
            names = list(row["names"] or [])[: len(row["types"])]
            kind = "void" if row["rettype"] == "void" else ("row" if row["kind"] == "c" else "scalar")
            with self._lock:
                self._funcs[name] = (dict(zip(names, row["types"])), kind, row["setof"])
        return self._funcs[name]


def _param(col: Column, value: Any) -> sql.Composable:
    """A placeholder for `value`, cast to the column's type."""
    if value is None:
        return sql.SQL("NULL")
    if col.is_json:
        return sql.SQL("{}::{}").format(sql.Literal(Jsonb(value)), sql.SQL(col.sql_type))
    return sql.SQL("{}::{}").format(sql.Placeholder(), sql.SQL(col.sql_type))


# ----------------------------------------------------------------------------- query builder

_OR_TERM = re.compile(r"^([A-Za-z_][A-Za-z0-9_]*)\.(eq|neq|gt|gte|lt|lte|like|ilike|is)\.(.*)$", re.S)
_CMP = {"eq": "=", "neq": "<>", "gt": ">", "gte": ">=", "lt": "<", "lte": "<=",
        "like": "LIKE", "ilike": "ILIKE"}


class Query:
    def __init__(self, client: "PgClient", table: str):
        self._client = client
        self._table = table
        self._op = "select"
        self._columns = "*"
        self._count: Optional[str] = None
        self._payload: Any = None
        self._on_conflict: Optional[str] = None
        self._ignore_duplicates = False
        self._where: List[Tuple[sql.Composable, List[Any]]] = []
        self._order: List[Tuple[str, bool]] = []
        self._limit: Optional[int] = None
        self._offset: Optional[int] = None
        self._single: Optional[str] = None   # "single" | "maybe"

    # -- operations
    def select(self, columns: str = "*", count: Optional[str] = None) -> "Query":
        self._op, self._columns, self._count = "select", columns or "*", count
        return self

    def insert(self, rows: Any) -> "Query":
        self._op, self._payload = "insert", rows
        return self

    def upsert(self, rows: Any, on_conflict: Optional[str] = None, ignore_duplicates: bool = False) -> "Query":
        self._op, self._payload = "upsert", rows
        self._on_conflict, self._ignore_duplicates = on_conflict, ignore_duplicates
        return self

    def update(self, fields: Dict[str, Any]) -> "Query":
        self._op, self._payload = "update", fields
        return self

    def delete(self) -> "Query":
        self._op = "delete"
        return self

    # -- filters
    def _cmp(self, column: str, op: str, value: Any) -> "Query":
        col = self._client.catalog.column(self._table, column)
        if op in ("LIKE", "ILIKE"):
            cond = sql.SQL("{}::text {} %s").format(sql.Identifier(column), sql.SQL(op))
            self._where.append((cond, [value]))
            return self
        cond = sql.SQL("{} {} {}").format(sql.Identifier(column), sql.SQL(op), _param(col, value))
        self._where.append((cond, [] if value is None or col.is_json else [value]))
        return self

    def eq(self, column: str, value: Any) -> "Query":
        return self._cmp(column, "=", value)

    def neq(self, column: str, value: Any) -> "Query":
        return self._cmp(column, "<>", value)

    def gt(self, column: str, value: Any) -> "Query":
        return self._cmp(column, ">", value)

    def gte(self, column: str, value: Any) -> "Query":
        return self._cmp(column, ">=", value)

    def lt(self, column: str, value: Any) -> "Query":
        return self._cmp(column, "<", value)

    def lte(self, column: str, value: Any) -> "Query":
        return self._cmp(column, "<=", value)

    def like(self, column: str, pattern: str) -> "Query":
        return self._cmp(column, "LIKE", pattern)

    def ilike(self, column: str, pattern: str) -> "Query":
        return self._cmp(column, "ILIKE", pattern)

    def in_(self, column: str, values: Iterable[Any]) -> "Query":
        col = self._client.catalog.column(self._table, column)
        values = list(values)
        if not values:
            self._where.append((sql.SQL("FALSE"), []))
            return self
        cond = sql.SQL("{} = ANY(%s::{}[])").format(sql.Identifier(column), sql.SQL(col.sql_type))
        self._where.append((cond, [values]))
        return self

    def is_(self, column: str, value: Any) -> "Query":
        self._client.catalog.column(self._table, column)
        self._where.append((self._is_sql(column, value), []))
        return self

    @staticmethod
    def _is_sql(column: str, value: Any) -> sql.Composable:
        word = {"null": "NULL", "none": "NULL", "true": "TRUE", "false": "FALSE"}.get(str(value).lower())
        if not word:
            raise QueryError(f"unsupported is_ value: {value!r}")
        return sql.SQL("{} IS {}").format(sql.Identifier(column), sql.SQL(word))

    def contains(self, column: str, value: Any) -> "Query":
        col = self._client.catalog.column(self._table, column)
        cond = sql.SQL("{} @> {}").format(sql.Identifier(column), _param(col, value))
        self._where.append((cond, [] if col.is_json else [value]))
        return self

    def match(self, criteria: Dict[str, Any]) -> "Query":
        for k, v in criteria.items():
            self.eq(k, v)
        return self

    def or_(self, expression: str) -> "Query":
        """PostgREST `or` syntax: "col.op.value,col.op.value" (eq neq gt gte lt lte like ilike is)."""
        parts, params = [], []
        for term in expression.split(","):
            m = _OR_TERM.match(term.strip())
            if not m:
                raise QueryError(f"unsupported or_ term: {term!r}")
            column, op, value = m.groups()
            col = self._client.catalog.column(self._table, column)
            if op == "is":
                parts.append(self._is_sql(column, value))
            elif op in ("like", "ilike"):
                parts.append(sql.SQL("{}::text {} %s").format(sql.Identifier(column), sql.SQL(_CMP[op])))
                params.append(value.replace("*", "%"))
            else:
                parts.append(sql.SQL("{} {} %s::{}").format(sql.Identifier(column), sql.SQL(_CMP[op]),
                                                            sql.SQL(col.sql_type)))
                params.append(value)
        self._where.append((sql.SQL("({})").format(sql.SQL(" OR ").join(parts)), params))
        return self

    # -- shaping
    def order(self, column: str, desc: bool = False) -> "Query":
        self._client.catalog.column(self._table, column)
        self._order.append((column, desc))
        return self

    def limit(self, n: int) -> "Query":
        self._limit = int(n)
        return self

    def range(self, start: int, end: int) -> "Query":
        self._offset, self._limit = int(start), int(end) - int(start) + 1
        return self

    def single(self) -> "Query":
        self._single = "single"
        return self

    def maybe_single(self) -> "Query":
        self._single = "maybe"
        return self

    # -- SQL building
    def _where_sql(self) -> Tuple[sql.Composable, List[Any]]:
        if not self._where:
            return sql.SQL(""), []
        params: List[Any] = []
        for _, p in self._where:
            params.extend(p)
        return sql.SQL(" WHERE ") + sql.SQL(" AND ").join(c for c, _ in self._where), params

    def _select_list(self) -> sql.Composable:
        cols = [c.strip() for c in self._columns.split(",") if c.strip()]
        if not cols or cols == ["*"]:
            return sql.SQL("*")
        for c in cols:
            self._client.catalog.column(self._table, c)
        return sql.SQL(", ").join(sql.Identifier(c) for c in cols)

    def _rows_payload(self) -> List[Dict[str, Any]]:
        rows = self._payload if isinstance(self._payload, list) else [self._payload]
        if not rows or not all(isinstance(r, dict) for r in rows):
            raise QueryError("insert/upsert needs a dict or a list of dicts")
        return rows

    def _values_sql(self, rows: List[Dict[str, Any]]) -> Tuple[List[str], sql.Composable, List[Any]]:
        names: List[str] = []
        for r in rows:
            for k in r:
                if k not in names:
                    names.append(k)
        cols = [self._client.catalog.column(self._table, n) for n in names]
        tuples, params = [], []
        for r in rows:
            items = []
            for col in cols:
                if col.name not in r:
                    items.append(sql.SQL("DEFAULT"))
                    continue
                v = r[col.name]
                items.append(_param(col, v))
                if v is not None and not col.is_json:
                    params.append(v)
            tuples.append(sql.SQL("({})").format(sql.SQL(", ").join(items)))
        return names, sql.SQL(", ").join(tuples), params

    def _build(self) -> Tuple[sql.Composable, List[Any]]:
        table = sql.Identifier(self._table)
        where, wparams = self._where_sql()
        if self._op == "select":
            q = sql.SQL("SELECT {} FROM {}").format(self._select_list(), table) + where
            if self._order:
                q += sql.SQL(" ORDER BY ") + sql.SQL(", ").join(
                    sql.SQL("{} {}").format(sql.Identifier(c), sql.SQL("DESC" if d else "ASC"))
                    for c, d in self._order)
            limit = 2 if self._single else self._limit
            if limit is not None:
                q += sql.SQL(" LIMIT {}").format(sql.Literal(limit))
            if self._offset:
                q += sql.SQL(" OFFSET {}").format(sql.Literal(self._offset))
            return q, wparams
        if self._op in ("insert", "upsert"):
            rows = self._rows_payload()
            names, values, params = self._values_sql(rows)
            q = sql.SQL("INSERT INTO {} ({}) VALUES {}").format(
                table, sql.SQL(", ").join(sql.Identifier(n) for n in names), values)
            if self._op == "upsert":
                target = ([c.strip() for c in self._on_conflict.split(",")] if self._on_conflict
                          else self._client.catalog.primary_key(self._table))
                q += sql.SQL(" ON CONFLICT ({})").format(sql.SQL(", ").join(sql.Identifier(c) for c in target))
                updates = [n for n in names if n not in target]
                if self._ignore_duplicates or not updates:
                    q += sql.SQL(" DO NOTHING")
                else:
                    q += sql.SQL(" DO UPDATE SET ") + sql.SQL(", ").join(
                        sql.SQL("{0} = EXCLUDED.{0}").format(sql.Identifier(n)) for n in updates)
            return q + sql.SQL(" RETURNING *"), params
        if self._op == "update":
            if not isinstance(self._payload, dict) or not self._payload:
                raise QueryError("update needs a non-empty dict")
            sets, params = [], []
            for name, v in self._payload.items():
                col = self._client.catalog.column(self._table, name)
                sets.append(sql.SQL("{} = {}").format(sql.Identifier(name), _param(col, v)))
                if v is not None and not col.is_json:
                    params.append(v)
            q = sql.SQL("UPDATE {} SET {}").format(table, sql.SQL(", ").join(sets)) + where
            return q + sql.SQL(" RETURNING *"), params + wparams
        if self._op == "delete":
            return sql.SQL("DELETE FROM {}").format(table) + where + sql.SQL(" RETURNING *"), wparams
        raise QueryError(f"unknown operation {self._op}")

    def execute(self) -> Result:
        q, params = self._build()
        with self._client.pool.connection() as conn:
            rows = [_row_out(r) for r in conn.execute(q, params).fetchall()]
            count = None
            if self._op == "select" and self._count:
                where, wparams = self._where_sql()
                count = conn.execute(
                    sql.SQL("SELECT count(*) AS n FROM {}").format(sql.Identifier(self._table)) + where,
                    wparams).fetchone()["n"]
        if self._single == "single":
            if len(rows) != 1:
                raise QueryError(f"expected exactly one row from {self._table}, got {len(rows)}")
            return Result(data=rows[0], count=count)
        if self._single == "maybe":
            if len(rows) > 1:
                raise QueryError(f"expected at most one row from {self._table}, got {len(rows)}")
            return Result(data=rows[0] if rows else None, count=count)
        return Result(data=rows, count=count)


class RpcCall:
    def __init__(self, client: "PgClient", name: str, params: Optional[Dict[str, Any]]):
        self._client, self._name, self._params = client, name, params or {}

    def execute(self) -> Result:
        arg_types, kind, setof = self._client.catalog.function(self._name)
        args, values = [], []
        for k, v in self._params.items():
            if k not in arg_types:
                raise QueryError(f"function {self._name} has no argument {k}")
            args.append(sql.SQL("{} => %s::{}").format(sql.Identifier(k), sql.SQL(arg_types[k])))
            values.append(v)
        call = sql.SQL("{}({})").format(sql.Identifier(self._name), sql.SQL(", ").join(args))
        with self._client.pool.connection() as conn:
            if kind == "row" or setof:
                rows = [_row_out(r) for r in conn.execute(sql.SQL("SELECT * FROM ") + call, values).fetchall()]
                return Result(data=rows if setof else (rows[0] if rows else None))
            value = conn.execute(sql.SQL("SELECT ") + call + sql.SQL(" AS v"), values).fetchone()["v"]
        return Result(data=None if kind == "void" else _out(value))


class PgClient:
    """`table()` and `rpc()` over a connection pool (opened on first use)."""

    def __init__(self, conninfo: str, min_size: int = 1, max_size: int = 10):
        if not conninfo:
            raise QueryError("DATABASE_URL is not set")
        self._pool = ConnectionPool(
            conninfo, min_size=min_size, max_size=max_size, open=False,
            kwargs={"autocommit": True, "row_factory": dict_row},
        )
        self._opened = False
        self._open_lock = threading.Lock()
        self.catalog = _Catalog(self)

    @property
    def pool(self) -> ConnectionPool:
        """The connection pool, opened on first use."""
        self._ensure_open()
        return self._pool

    def _ensure_open(self) -> None:
        if not self._opened:
            with self._open_lock:
                if not self._opened:
                    self._pool.open(wait=True, timeout=10)
                    self._opened = True

    def table(self, name: str) -> Query:
        self._ensure_open()
        return Query(self, name)

    def rpc(self, name: str, params: Optional[Dict[str, Any]] = None) -> RpcCall:
        self._ensure_open()
        return RpcCall(self, name, params)

    def fetch(self, query: str, params: Sequence[Any] = ()) -> List[Dict[str, Any]]:
        """Run hand-written SQL (with %s placeholders); returns rows shaped like table() results."""
        self._ensure_open()
        with self.pool.connection() as conn:
            cur = conn.execute(query, params)
            return [_row_out(r) for r in cur.fetchall()] if cur.description else []

    def close(self) -> None:
        if self._opened:
            self._pool.close()
            self._opened = False
