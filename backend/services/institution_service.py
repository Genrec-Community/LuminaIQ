"""
Institution plan: schools, colleges and coaching institutes (one tenant each).

Lifecycle
- A school admin signs up and creates an institution. It starts as
  approval_status = 'pending' and does nothing until a platform admin approves
  it (INSTITUTION_REQUIRE_APPROVAL, /platform console). Approval starts the free
  trial (INSTITUTION_TRIAL_DAYS) unless the school has already paid.
- The school buys student seats for a term (1, 3, 6 or 12 months) with Razorpay.
  The term runs from the payment date (or from the current end date when renewing
  early): paid_until.
- A school "works" only while it is approved AND paid_until is in the future
  (state() / is_live()). The moment paid_until passes, or a platform admin
  suspends it, every member loses the institution plan and school-created student
  accounts can no longer sign in or call the API. Nothing needs to run for this to
  happen; the hourly sweep only updates the status label for reporting.

People
- Teachers join with the institution's teacher code. Students either join a class
  with its invite code (their own account) or get an account created by the school
  (services/school_accounts.py: studentname-NN@luminaiq.fun, school-set password,
  reset by staff, changed by the student).
- Teachers publish books from their own projects to a class. Every student gets
  a copy in a "Class · <name>" project: the copy reuses the teacher's stored text
  and vectors, so no AI or embedding calls are made per student.

Tenancy
- Every read and write is scoped by the caller's membership row; ids from the
  request (class, member) are always checked against the caller's institution.
- Per-request checks use small in-process caches (60 s) so thousands of students
  don't each cost a database round trip per API call.
"""

from __future__ import annotations

import asyncio
import secrets
import time
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from fastapi import HTTPException

from config.settings import settings
from db.client import async_db, get_supabase_client
from services import school_accounts as accounts
from services.plans import PLANS
from services.usage_service import usage
from utils.logger import logger

TRIAL_SEATS = 25
MIN_PAID_SEATS = 100
GST_RATE = 0.18  # charged only once INSTITUTION_GSTIN is set


def gst_rate() -> float:
    """GST added to school prices: 0 until we have a GSTIN (INSTITUTION_GSTIN)."""
    return GST_RATE if (settings.INSTITUTION_GSTIN or "").strip() else 0.0
TERM_MONTHS = (1, 3, 6, 12)
MAX_BULK_STUDENTS = 500
_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"  # no 0/O/1/I
_CACHE_TTL = 60
_IN_CHUNK = 150  # ids per PostgREST in.() filter (keeps URLs short)

# state() values
ACTIVE, TRIAL, PENDING, SUSPENDED, EXPIRED = "active", "trial", "pending_approval", "suspended", "expired"
LIVE_STATES = (ACTIVE, TRIAL)

STATE_MESSAGES = {
    PENDING: "Your school's LuminaIQ account is waiting for approval.",
    SUSPENDED: "Your school's LuminaIQ access has been paused. Please contact your school.",
    EXPIRED: "Your school's LuminaIQ plan has ended. Please ask your school to renew.",
}


def _code(prefix: str) -> str:
    return f"{prefix}-" + "".join(secrets.choice(_ALPHABET) for _ in range(6))


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _parse(ts: Optional[str]) -> Optional[datetime]:
    if not ts:
        return None
    try:
        return datetime.fromisoformat(str(ts).replace("Z", "+00:00"))
    except ValueError:
        return None


def _search_text(q: Optional[str]) -> str:
    """User text made safe for a PostgREST or=(...ilike...) filter."""
    return "".join(ch for ch in (q or "") if ch not in ",()%*\"'\\:").strip()[:60]


def term_days(months: int) -> int:
    return 365 if months == 12 else months * 30


def seats_price_paise(seats: int, months: int = 12) -> Dict[str, int]:
    """Price for `seats` students for `months`: base, plus GST on top once we have a GSTIN."""
    base = seats * PLANS["institution"]["price_inr"] * months * 100
    gst = round(base * gst_rate())
    return {"base": base, "gst": gst, "total": base + gst}


def state(inst: Optional[Dict[str, Any]], now: Optional[datetime] = None) -> str:
    """Where a school stands. Only 'active' and 'trial' work."""
    if not inst:
        return EXPIRED
    approval = inst.get("approval_status") or "approved"  # rows from before migration 014
    if approval == "suspended":
        return SUSPENDED
    if approval != "approved":
        return PENDING
    end = _parse(inst.get("paid_until"))
    if not end or end <= (now or _now()):
        return EXPIRED
    return TRIAL if inst.get("status") == "trial" else ACTIVE


def is_live(inst: Optional[Dict[str, Any]]) -> bool:
    return state(inst) in LIVE_STATES


def time_left(inst: Dict[str, Any]) -> Dict[str, Any]:
    """The subscription timer shown to the school."""
    end = _parse(inst.get("paid_until"))
    if not end:
        return {"ends_at": None, "days_left": None, "seconds_left": None}
    secs = max(0, int((end - _now()).total_seconds()))
    return {"ends_at": end.isoformat(), "days_left": secs // 86400, "seconds_left": secs}


def inactive_error(st: str) -> HTTPException:
    return HTTPException(403, {"code": "school_inactive", "state": st,
                               "message": STATE_MESSAGES.get(st, STATE_MESSAGES[EXPIRED])})


class InstitutionService:
    def __init__(self):
        self.client = get_supabase_client()
        self._inst_cache: Dict[str, tuple] = {}     # institution_id -> (expires, row)
        self._access_cache: Dict[str, tuple] = {}   # user_id -> (expires, result)
        self._id_lock = asyncio.Lock()

    # ------------------------------------------------------------ lookups

    async def _one(self, table: str, **eq) -> Optional[Dict[str, Any]]:
        q = self.client.table(table).select("*")
        for k, v in eq.items():
            q = q.eq(k, v)
        res = await async_db(lambda: q.limit(1).execute())
        return res.data[0] if res.data else None

    async def _all(self, table: str, **eq) -> List[Dict[str, Any]]:
        q = self.client.table(table).select("*")
        for k, v in eq.items():
            q = q.eq(k, v)
        res = await async_db(lambda: q.execute())
        return res.data or []

    async def _in(self, table: str, column: str, values: List[Any], select: str = "*", **eq) -> List[Dict[str, Any]]:
        """Rows where column is in values, fetched in chunks."""
        out: List[Dict[str, Any]] = []
        values = list(dict.fromkeys(v for v in values if v))
        for i in range(0, len(values), _IN_CHUNK):
            chunk = values[i:i + _IN_CHUNK]
            q = self.client.table(table).select(select).in_(column, chunk)
            for k, v in eq.items():
                q = q.eq(k, v)
            res = await async_db(lambda: q.execute())
            out.extend(res.data or [])
        return out

    async def audit(self, institution_id: str, actor: Optional[str], action: str, detail: Optional[dict] = None) -> None:
        try:
            await async_db(lambda: self.client.table("institution_audit").insert({
                "institution_id": institution_id, "actor_user_id": actor, "action": action, "detail": detail or {},
            }).execute())
        except Exception as e:  # never fail the action because of the log
            logger.warning(f"[Institution] audit {action} not recorded: {e}")

    async def institution(self, institution_id: str, fresh: bool = False) -> Optional[Dict[str, Any]]:
        cached = self._inst_cache.get(institution_id)
        if not fresh and cached and cached[0] > time.time():
            return cached[1]
        inst = await self._one("institutions", id=institution_id)
        self._inst_cache[institution_id] = (time.time() + _CACHE_TTL, inst)
        return inst

    def forget(self, institution_id: Optional[str] = None, user_id: Optional[str] = None) -> None:
        if institution_id:
            self._inst_cache.pop(institution_id, None)
            # members of this school re-check on their next request
            self._access_cache = {k: v for k, v in self._access_cache.items()
                                  if (v[1] or {}).get("institution_id") != institution_id}
        if user_id:
            self._access_cache.pop(user_id, None)
            usage.forget(user_id)

    async def membership(self, user_id: str) -> Optional[Dict[str, Any]]:
        res = await async_db(lambda: self.client.table("institution_members").select("*")
                             .eq("user_id", user_id).order("joined_at").limit(1).execute())
        return res.data[0] if res.data else None

    async def require_staff(self, user_id: str, write: bool = False, admin: bool = False) -> Dict[str, Any]:
        """The caller's membership if they are staff; write=True also needs a working school."""
        m = await self.membership(user_id)
        roles = ("admin",) if admin else ("admin", "teacher")
        if not m or m["role"] not in roles or m.get("disabled"):
            raise HTTPException(403, "Only your institution's admins can do this." if admin
                                else "Only your institution's admins and teachers can do this.")
        if write:
            st = state(await self.institution(m["institution_id"], fresh=True))
            if st not in LIVE_STATES:
                raise inactive_error(st)
        return m

    async def student_count(self, institution_id: str) -> int:
        res = await async_db(lambda: self.client.table("institution_members").select("user_id", count="exact")
                             .eq("institution_id", institution_id).eq("role", "student")
                             .eq("disabled", False).limit(1).execute())
        return res.count or 0

    @staticmethod
    def is_live(inst: Dict[str, Any]) -> bool:
        return is_live(inst)

    # ------------------------------------------------- per-request access gate

    async def managed_access(self, user_id: str) -> Dict[str, Any]:
        """
        For school-created accounts: may this user use LuminaIQ right now?
        {"ok": bool, "state", "message", "institution_id"}. Cached for a minute.
        Fails open on database errors (our outage shouldn't lock students out).
        """
        cached = self._access_cache.get(user_id)
        if cached and cached[0] > time.time():
            return cached[1]
        result: Dict[str, Any] = {"ok": True, "state": None, "institution_id": None}
        try:
            m = await self.membership(user_id)
            if m and m.get("managed"):
                inst = await self.institution(m["institution_id"])
                st = state(inst)
                result = {"ok": st in LIVE_STATES and not m.get("disabled"), "state": st,
                          "institution_id": m["institution_id"]}
                if m.get("disabled"):
                    result["state"] = "disabled"
                    result["message"] = "This account has been switched off by your school."
                elif not result["ok"]:
                    result["message"] = STATE_MESSAGES.get(st, STATE_MESSAGES[EXPIRED])
        except Exception as e:
            logger.warning(f"[Institution] access check failed for {user_id}, allowing: {e}")
            return result
        self._access_cache[user_id] = (time.time() + _CACHE_TTL, result)
        return result

    async def plan_is_live(self, institution_id: str) -> bool:
        """Used by usage_service: does an institution plan still apply?"""
        try:
            return is_live(await self.institution(institution_id))
        except Exception:
            return True  # fail open

    # ---------------------------------------------------------- plan grant

    async def _grant_plan(self, user_id: str, inst: Dict[str, Any]) -> None:
        """Give a member the institution plan (never downgrading a personal Topper)."""
        current = await usage.plan_row(user_id)
        if current.get("source") == "razorpay" and current.get("plan") == "topper":
            return
        row = {
            "user_id": user_id, "plan": "institution", "status": "active", "source": "institution",
            "institution_id": inst["id"], "current_period_end": inst.get("paid_until"),
            "updated_at": _now().isoformat(),
        }
        await async_db(lambda: self.client.table("user_plans").upsert(row, on_conflict="user_id").execute())
        usage.forget(user_id)

    async def _revoke_plan(self, user_id: str, institution_id: str) -> None:
        res = await async_db(lambda: self.client.table("user_plans").select("source, institution_id")
                             .eq("user_id", user_id).limit(1).execute())
        if res.data and res.data[0].get("source") == "institution" and res.data[0].get("institution_id") == institution_id:
            await async_db(lambda: self.client.table("user_plans").update({
                "plan": "free", "source": "default", "institution_id": None,
                "current_period_end": None, "updated_at": _now().isoformat(),
            }).eq("user_id", user_id).execute())
        usage.forget(user_id)

    async def refresh_member_plans(self, inst: Dict[str, Any]) -> None:
        """After a renewal or extension: move every member's plan end to the new paid-up date."""
        await async_db(lambda: self.client.table("user_plans").update({
            "current_period_end": inst["paid_until"], "status": "active", "updated_at": _now().isoformat(),
        }).eq("institution_id", inst["id"]).eq("source", "institution").execute())
        self.forget(institution_id=inst["id"])
        res = await async_db(lambda: self.client.table("institution_members").select("user_id")
                             .eq("institution_id", inst["id"]).execute())
        for m in res.data or []:
            usage.forget(m["user_id"])

    # ------------------------------------------------------------ actions

    async def create(self, user: dict, name: str, contact_email: str, billing_name: str,
                     gstin: str, display_name: str) -> Dict[str, Any]:
        if await self.membership(user["id"]):
            raise HTTPException(409, "You're already part of an institution.")
        if accounts.is_school_login(user.get("email")):
            raise HTTPException(403, "Student accounts can't create an institution.")
        needs_approval = settings.INSTITUTION_REQUIRE_APPROVAL
        trial_days = max(0, settings.INSTITUTION_TRIAL_DAYS)
        row = {
            "name": name.strip()[:120], "owner_user_id": user["id"],
            "contact_email": (contact_email or user.get("email") or "")[:200],
            "billing_name": (billing_name or name).strip()[:200], "gstin": (gstin or "").strip().upper()[:15] or None,
            "seats": TRIAL_SEATS, "status": "trial",
            "approval_status": "pending" if needs_approval else "approved",
            "paid_until": None if needs_approval or not trial_days else (_now() + timedelta(days=trial_days)).isoformat(),
            "teacher_code": _code("T"),
        }
        if not needs_approval:
            row["approved_at"] = _now().isoformat()
        inst = (await async_db(lambda: self.client.table("institutions").insert(row).execute())).data[0]
        await async_db(lambda: self.client.table("institution_members").insert({
            "institution_id": inst["id"], "user_id": user["id"], "role": "admin",
            "display_name": display_name, "email": user.get("email"),
        }).execute())
        await self._grant_plan(user["id"], inst)
        await self.audit(inst["id"], user["id"], "created", {"name": inst["name"]})
        logger.info(f"[Institution] created {inst['name']} ({inst['id']}), approval={inst.get('approval_status')}")
        return inst

    async def create_class(self, user: dict, name: str) -> Dict[str, Any]:
        m = await self.require_staff(user["id"], write=True)
        return (await async_db(lambda: self.client.table("institution_classes").insert({
            "institution_id": m["institution_id"], "name": name.strip()[:80],
            "invite_code": _code("C"), "created_by": user["id"],
        }).execute())).data[0]

    async def join(self, user: dict, code: str, display_name: str) -> Dict[str, Any]:
        code = (code or "").strip().upper()
        inst = await self._one("institutions", teacher_code=code)
        if inst:
            st = state(inst)
            if st not in LIVE_STATES:
                raise inactive_error(st)
            other = await self.membership(user["id"])
            if other and other["institution_id"] != inst["id"]:
                raise HTTPException(409, "You're already part of another institution.")
            if other and other["role"] == "admin":
                return {"role": "admin", "institution": inst["name"]}
            if other and other.get("managed"):
                raise HTTPException(403, "Student accounts can't join as teachers.")
            await async_db(lambda: self.client.table("institution_members").upsert({
                "institution_id": inst["id"], "user_id": user["id"], "role": "teacher",
                "display_name": display_name, "email": user.get("email"),
            }, on_conflict="institution_id,user_id").execute())
            await self._grant_plan(user["id"], inst)
            await self.audit(inst["id"], user["id"], "teacher_joined", {"email": user.get("email")})
            return {"role": "teacher", "institution": inst["name"]}

        cls = await self._one("institution_classes", invite_code=code)
        if not cls:
            raise HTTPException(404, "That code doesn't match any class. Check it with your teacher.")
        inst = await self._one("institutions", id=cls["institution_id"])
        st = state(inst)
        if st not in LIVE_STATES:
            raise inactive_error(st)

        existing = await self._one("institution_members", institution_id=inst["id"], user_id=user["id"])
        if existing and existing.get("disabled"):
            raise HTTPException(403, "Your account has been switched off by your school.")
        if not existing:
            other = await self.membership(user["id"])
            if other and other["institution_id"] != inst["id"]:
                raise HTTPException(409, "You're already part of another institution.")
            if await self.student_count(inst["id"]) >= inst["seats"]:
                raise HTTPException(403, "This institution has no free seats left. Ask your admin to add seats.")
            await async_db(lambda: self.client.table("institution_members").insert({
                "institution_id": inst["id"], "user_id": user["id"], "role": "student",
                "display_name": display_name, "email": user.get("email"),
            }).execute())
        await self._grant_plan(user["id"], inst)
        project_id = await self._enroll(cls, user["id"])
        return {"role": "student", "institution": inst["name"], "class": cls["name"], "project_id": project_id}

    async def _enroll(self, cls: Dict[str, Any], user_id: str) -> str:
        """Put a student in a class: their class project plus copies of its books (idempotent)."""
        cm = await self._one("class_members", class_id=cls["id"], user_id=user_id)
        project_id = cm.get("project_id") if cm else None
        if not project_id:
            from services.project_service import project_service
            project = await project_service.create_project(user_id, f"Class · {cls['name']}")
            project_id = project["id"]
            await async_db(lambda: self.client.table("class_members").upsert({
                "class_id": cls["id"], "user_id": user_id, "project_id": project_id,
            }, on_conflict="class_id,user_id").execute())
        for book in await self._all("class_books", class_id=cls["id"]):
            await self._copy_book_to(book, user_id, project_id)
        return project_id

    async def _class_in(self, institution_id: str, class_id: str) -> Dict[str, Any]:
        cls = await self._one("institution_classes", id=class_id)
        if not cls or cls["institution_id"] != institution_id:
            raise HTTPException(404, "Class not found.")
        return cls

    async def publish_book(self, user: dict, class_id: str, document_id: str) -> Dict[str, Any]:
        m = await self.require_staff(user["id"], write=True)
        await self._class_in(m["institution_id"], class_id)
        doc = await self._one("documents", id=document_id)
        project = await self._one("projects", id=doc["project_id"]) if doc else None
        if not doc or not project or project["user_id"] != user["id"]:
            raise HTTPException(404, "You can only publish books from your own projects.")
        if doc.get("upload_status") != "completed":
            raise HTTPException(409, "That book is still processing. Publish it once it's ready.")
        book = (await async_db(lambda: self.client.table("class_books").upsert({
            "class_id": class_id, "source_document_id": document_id,
            "title": doc["filename"], "published_by": user["id"],
        }, on_conflict="class_id,source_document_id").execute())).data[0]
        copied = 0
        for member in await self._all("class_members", class_id=class_id):
            if member.get("project_id") and await self._copy_book_to(book, member["user_id"], member["project_id"]):
                copied += 1
        return {"book": book, "copied_to": copied}

    async def _copy_book_to(self, book: Dict[str, Any], user_id: str, project_id: str) -> bool:
        """Give one student a copy of a class book (idempotent)."""
        if await self._one("class_book_copies", class_book_id=book["id"], user_id=user_id):
            return False
        src = await self._one("documents", id=book["source_document_id"])
        if not src:
            return False
        copy = (await async_db(lambda: self.client.table("documents").insert({
            "project_id": project_id, "user_id": user_id, "filename": src["filename"],
            "file_type": src.get("file_type"), "file_size": src.get("file_size"),
            "upload_status": "completed", "topics": src.get("topics"),
            "topic_outline": src.get("topic_outline") or [],
            "text_storage_path": src.get("text_storage_path"),
            "file_url": src.get("file_url"),  # students read the teacher's original PDF
        }).execute())).data[0]
        await async_db(lambda: self.client.table("class_book_copies").insert({
            "class_book_id": book["id"], "user_id": user_id, "document_id": copy["id"],
        }).execute())
        # Search index: copy the teacher's vectors (no embedding calls). If the
        # source isn't indexed, the normal self-heal re-indexes the copy on first use.
        try:
            from services.qdrant_service import qdrant_service
            await qdrant_service.copy_document_vectors(
                f"project_{src['project_id']}", src["id"], f"project_{project_id}", copy["id"], src["filename"])
        except Exception as e:
            logger.warning(f"[Institution] vector copy failed for {copy['id']}: {e}")
        # Learning-path links between this book's topics
        try:
            topics = set(src.get("topics") or [])
            rels = [r for r in await self._all("topic_relations", project_id=src["project_id"])
                    if r["from_topic"] in topics and r["to_topic"] in topics]
            if rels:
                await async_db(lambda: self.client.table("topic_relations").insert([
                    {"project_id": project_id, "from_topic": r["from_topic"], "to_topic": r["to_topic"],
                     "relation_type": r["relation_type"], "weight": r.get("weight")} for r in rels
                ]).execute())
        except Exception as e:
            logger.warning(f"[Institution] topic links not copied: {e}")
        return True

    async def _member_in(self, institution_id: str, member_user_id: str) -> Dict[str, Any]:
        target = await self._one("institution_members", institution_id=institution_id, user_id=member_user_id)
        if not target:
            raise HTTPException(404, "That person isn't part of your institution.")
        return target

    async def remove_member(self, user: dict, member_user_id: str) -> Dict[str, Any]:
        """
        Remove someone. School-created student accounts are switched off instead
        (their sign-in ID stays reserved and their work is kept; the seat is freed).
        """
        m = await self.require_staff(user["id"], admin=True)
        if member_user_id == user["id"]:
            raise HTTPException(400, "You can't remove yourself.")
        target = await self._member_in(m["institution_id"], member_user_id)
        inst = await self.institution(m["institution_id"], fresh=True)
        if member_user_id == inst.get("owner_user_id"):
            raise HTTPException(400, "The institution's owner can't be removed.")
        if target.get("managed"):
            return await self.set_disabled(user, member_user_id, True)
        await async_db(lambda: self.client.table("institution_members").delete()
                       .eq("institution_id", m["institution_id"]).eq("user_id", member_user_id).execute())
        class_ids = [c["id"] for c in await self._all("institution_classes", institution_id=m["institution_id"])]
        for i in range(0, len(class_ids), _IN_CHUNK):
            chunk = class_ids[i:i + _IN_CHUNK]
            await async_db(lambda: self.client.table("class_members").delete()
                           .in_("class_id", chunk).eq("user_id", member_user_id).execute())
        await self._revoke_plan(member_user_id, m["institution_id"])
        self.forget(user_id=member_user_id)
        await self.audit(m["institution_id"], user["id"], "member_removed", {"user_id": member_user_id})
        return {"removed": member_user_id}

    # ---------------------------------------------- school-created student accounts

    async def _taken_ids(self, ids: List[str]) -> set:
        rows = await self._in("institution_members", "login_id", ids, select="login_id")
        return {r["login_id"].lower() for r in rows if r.get("login_id")}

    async def _reserve_login_id(self, name: str, reg_no: str, reserved: set) -> List[str]:
        """Free candidate IDs in order (checked against every school, then Supabase on create)."""
        out: List[str] = []
        start = 1
        while len(out) < 3 and start <= accounts.MAX_SUFFIX_TRIES:
            batch = accounts.candidate_ids(name, reg_no, start, 20)
            taken = await self._taken_ids(batch) | reserved
            out.extend(c for c in batch if c not in taken)
            start += 20
        return out

    async def _create_auth_user(self, login_id: str, password: str, name: str) -> Optional[str]:
        """Create the Supabase login; None if the ID is already registered there."""
        try:
            res = await async_db(lambda: self.client.auth.admin.create_user({
                "email": login_id, "password": password, "email_confirm": True,
                "user_metadata": {"full_name": name, "school_managed": True},
            }))
        except Exception as e:
            text = str(e).lower()
            if "already" in text or "exists" in text or "registered" in text:
                return None
            raise
        return res.user.id if res and res.user else None

    async def _create_one_student(self, actor: str, inst: Dict[str, Any], item: Dict[str, Any],
                                  reserved: set, classes: Dict[str, Dict[str, Any]]) -> Dict[str, Any]:
        name = (item.get("name") or "").strip()[:80]
        reg_no = (item.get("reg_no") or "").strip()[:40]
        result: Dict[str, Any] = {"name": name, "reg_no": reg_no}
        if not name:
            return {**result, "error": "Name is missing."}
        if not reg_no:
            return {**result, "error": "Register number is missing."}
        password = item.get("password") or accounts.generate_password()
        problem = accounts.password_problem(password)
        if problem:
            return {**result, "error": problem}
        cls = None
        if item.get("class_id"):
            cls = classes.get(item["class_id"])
            if not cls:
                return {**result, "error": "Class not found."}

        try:
            async with self._id_lock:
                if item.get("login_id"):
                    wanted = [accounts.custom_login_id(item["login_id"])]
                    if await self._taken_ids(wanted) or wanted[0] in reserved:
                        return {**result, "error": f"{wanted[0]} is already taken."}
                    candidates = wanted
                else:
                    candidates = await self._reserve_login_id(name, reg_no, reserved)
                    if not candidates:
                        return {**result, "error": "Couldn't find a free sign-in ID. Set one by hand."}
                reserved.update(candidates[:1])
        except ValueError as e:
            return {**result, "error": str(e)}

        user_id, login_id = None, None
        for cand in candidates:
            user_id = await self._create_auth_user(cand, password, name)
            if user_id:
                login_id = cand
                break
            reserved.add(cand)
            if item.get("login_id"):
                return {**result, "error": f"{cand} is already taken."}
        if not user_id:
            return {**result, "error": "Couldn't find a free sign-in ID. Try again."}

        try:
            await async_db(lambda: self.client.table("institution_members").insert({
                "institution_id": inst["id"], "user_id": user_id, "role": "student",
                "display_name": name, "email": login_id, "login_id": login_id, "reg_no": reg_no,
                "managed": True, "must_change_password": True, "created_by": actor,
            }).execute())
        except Exception as e:
            # Don't leave a login behind that belongs to no school
            try:
                await async_db(lambda: self.client.auth.admin.delete_user(user_id))
            except Exception:
                pass
            text = str(e).lower()
            if "reg_no" in text or "duplicate" in text:
                return {**result, "error": "A student with this register number already exists."}
            raise
        await self._grant_plan(user_id, inst)
        if cls:
            try:
                await self._enroll(cls, user_id)
            except Exception as e:
                logger.warning(f"[Institution] could not enrol {user_id} in {cls['id']}: {e}")
        return {**result, "user_id": user_id, "login_id": login_id, "password": password,
                "class": cls["name"] if cls else None}

    async def create_students(self, user: dict, items: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Create school-managed student accounts. Returns each new sign-in ID with its
        password (shown once, for the school to hand out). Rows that fail say why;
        the rest are still created.
        """
        m = await self.require_staff(user["id"], write=True)
        if not items:
            raise HTTPException(400, "Add at least one student.")
        if len(items) > MAX_BULK_STUDENTS:
            raise HTTPException(400, f"Add at most {MAX_BULK_STUDENTS} students at a time.")
        inst = await self.institution(m["institution_id"], fresh=True)
        free = inst["seats"] - await self.student_count(inst["id"])
        if len(items) > free:
            raise HTTPException(403, f"Only {max(free, 0)} free seats left. Ask your admin to add seats.")

        # Duplicate register numbers: inside the upload and already in the school
        regs = [(i.get("reg_no") or "").strip().lower() for i in items]
        existing = {(r.get("reg_no") or "").lower() for r in
                    await self._in("institution_members", "reg_no", [i.get("reg_no", "").strip() for i in items],
                                   select="reg_no", institution_id=inst["id"])}
        classes = {c["id"]: c for c in await self._all("institution_classes", institution_id=inst["id"])}
        reserved: set = set()
        sem = asyncio.Semaphore(5)
        seen: set = set()

        async def run(idx: int, item: Dict[str, Any]) -> Dict[str, Any]:
            reg = regs[idx]
            if reg and (reg in existing or reg in seen):
                return {"name": item.get("name"), "reg_no": item.get("reg_no"),
                        "error": "A student with this register number already exists."}
            if reg:
                seen.add(reg)
            async with sem:
                try:
                    return await self._create_one_student(user["id"], inst, item, reserved, classes)
                except Exception as e:
                    logger.error(f"[Institution] create student failed: {e}")
                    return {"name": item.get("name"), "reg_no": item.get("reg_no"),
                            "error": "Couldn't create this account. Try again."}

        results = await asyncio.gather(*(run(i, it) for i, it in enumerate(items)))
        created = [r for r in results if r.get("user_id")]
        await self.audit(inst["id"], user["id"], "students_created",
                         {"count": len(created), "login_ids": [r["login_id"] for r in created][:50]})
        return {"created": created, "failed": [r for r in results if not r.get("user_id")]}

    async def list_students(self, user: dict, q: str = "", class_id: Optional[str] = None,
                            page: int = 1, page_size: int = 50) -> Dict[str, Any]:
        m = await self.require_staff(user["id"])
        page_size = max(1, min(page_size, 200))
        start = (max(page, 1) - 1) * page_size
        query = (self.client.table("institution_members")
                 .select("user_id, display_name, email, login_id, reg_no, managed, disabled, must_change_password, joined_at",
                         count="exact")
                 .eq("institution_id", m["institution_id"]).eq("role", "student"))
        if class_id:
            await self._class_in(m["institution_id"], class_id)
            ids = [r["user_id"] for r in await self._all("class_members", class_id=class_id)]
            if not ids:
                return {"students": [], "total": 0, "page": page, "page_size": page_size}
            query = query.in_("user_id", ids[:1000])
        q = _search_text(q)
        if q:
            query = query.or_(f"display_name.ilike.%{q}%,login_id.ilike.%{q}%,reg_no.ilike.%{q}%,email.ilike.%{q}%")
        res = await async_db(lambda: query.order("display_name").range(start, start + page_size - 1).execute())
        rows = res.data or []
        # Which classes each student is in (one query for the page)
        cms = await self._in("class_members", "user_id", [r["user_id"] for r in rows], select="user_id, class_id")
        names = {c["id"]: c["name"] for c in await self._all("institution_classes", institution_id=m["institution_id"])}
        by_user: Dict[str, List[str]] = {}
        for cm in cms:
            if cm["class_id"] in names:
                by_user.setdefault(cm["user_id"], []).append(names[cm["class_id"]])
        for r in rows:
            r["classes"] = sorted(by_user.get(r["user_id"], []))
        return {"students": rows, "total": res.count or 0, "page": page, "page_size": page_size}

    async def reset_password(self, user: dict, member_user_id: str, password: Optional[str] = None) -> Dict[str, Any]:
        """A forgotten password: staff set a new one; the student must change it at next sign-in."""
        m = await self.require_staff(user["id"])
        target = await self._member_in(m["institution_id"], member_user_id)
        if not target.get("managed"):
            raise HTTPException(400, "This student signed up with their own email. They can reset it from the sign-in page.")
        password = password or accounts.generate_password()
        problem = accounts.password_problem(password)
        if problem:
            raise HTTPException(400, problem)
        await async_db(lambda: self.client.auth.admin.update_user_by_id(member_user_id, {"password": password}))
        await async_db(lambda: self.client.table("institution_members").update({
            "must_change_password": True,
        }).eq("institution_id", m["institution_id"]).eq("user_id", member_user_id).execute())
        await self.audit(m["institution_id"], user["id"], "password_reset", {"user_id": member_user_id})
        return {"user_id": member_user_id, "login_id": target.get("login_id"), "password": password}

    async def set_disabled(self, user: dict, member_user_id: str, disabled: bool) -> Dict[str, Any]:
        m = await self.require_staff(user["id"], admin=True)
        target = await self._member_in(m["institution_id"], member_user_id)
        if target["role"] != "student":
            raise HTTPException(400, "Only student accounts can be switched off.")
        if not disabled and target.get("disabled"):
            inst = await self.institution(m["institution_id"], fresh=True)
            if await self.student_count(inst["id"]) >= inst["seats"]:
                raise HTTPException(403, "No free seats left. Add seats first.")
        await async_db(lambda: self.client.table("institution_members").update({"disabled": disabled})
                       .eq("institution_id", m["institution_id"]).eq("user_id", member_user_id).execute())
        if disabled:
            await self._revoke_plan(member_user_id, m["institution_id"])
        else:
            await self._grant_plan(member_user_id, await self.institution(m["institution_id"], fresh=True))
        self.forget(user_id=member_user_id)
        await self.audit(m["institution_id"], user["id"], "student_disabled" if disabled else "student_enabled",
                         {"user_id": member_user_id})
        return {"user_id": member_user_id, "disabled": disabled}

    async def add_to_class(self, user: dict, member_user_id: str, class_id: str) -> Dict[str, Any]:
        m = await self.require_staff(user["id"], write=True)
        cls = await self._class_in(m["institution_id"], class_id)
        target = await self._member_in(m["institution_id"], member_user_id)
        if target["role"] != "student" or target.get("disabled"):
            raise HTTPException(400, "Only active students can be added to a class.")
        project_id = await self._enroll(cls, member_user_id)
        return {"user_id": member_user_id, "class_id": class_id, "project_id": project_id}

    async def account_info(self, user_id: str) -> Dict[str, Any]:
        """What the app needs to know about a signed-in user's school account."""
        m = await self.membership(user_id)
        if not m:
            return {"managed": False, "must_change_password": False}
        inst = await self.institution(m["institution_id"])
        return {
            "managed": bool(m.get("managed")), "must_change_password": bool(m.get("must_change_password")),
            "login_id": m.get("login_id"), "role": m["role"], "institution": (inst or {}).get("name"),
            "state": state(inst),
        }

    async def mark_password_changed(self, user_id: str) -> None:
        await async_db(lambda: self.client.table("institution_members").update({
            "must_change_password": False, "password_changed_at": _now().isoformat(),
        }).eq("user_id", user_id).execute())

    # ---------------------------------------------------------- read views

    def _school_view(self, inst: Dict[str, Any]) -> Dict[str, Any]:
        st = state(inst)
        return {
            **{k: inst.get(k) for k in ("id", "name", "status", "seats", "paid_until", "billing_name", "gstin",
                                        "contact_email", "approval_status", "approval_note", "last_payment_at")},
            "state": st, "timer": time_left(inst),
        }

    async def overview(self, user: dict) -> Dict[str, Any]:
        m = await self.membership(user["id"])
        if not m:
            return {"member": False}
        inst = await self.institution(m["institution_id"], fresh=True)
        out: Dict[str, Any] = {
            "member": True, "role": m["role"], "managed": bool(m.get("managed")),
            "institution": self._school_view(inst), "live": is_live(inst),
            "state_message": STATE_MESSAGES.get(state(inst)),
            "login_domain": accounts.login_domain(),
        }
        if m["role"] == "student":
            res = await async_db(lambda: self.client.table("class_members").select("class_id, project_id")
                                 .eq("user_id", user["id"]).execute())
            projects = {r["class_id"]: r["project_id"] for r in res.data or []}
            out["classes"] = [
                {"id": c["id"], "name": c["name"], "project_id": projects[c["id"]]}
                for c in await self._in("institution_classes", "id", list(projects), institution_id=inst["id"])
            ]
            return out
        out["institution"]["teacher_code"] = inst["teacher_code"]
        out["students"] = await self.student_count(inst["id"])
        staff = await async_db(lambda: self.client.table("institution_members")
                               .select("user_id, display_name, email, role")
                               .eq("institution_id", inst["id"]).neq("role", "student").execute())
        out["teachers"] = [{"user_id": x["user_id"], "name": x.get("display_name"), "email": x.get("email"), "role": x["role"]}
                           for x in staff.data or []]
        classes = sorted(await self._all("institution_classes", institution_id=inst["id"]), key=lambda c: c["created_at"])
        counts: Dict[str, int] = {}
        for r in await self._in("class_members", "class_id", [c["id"] for c in classes], select="class_id"):
            counts[r["class_id"]] = counts.get(r["class_id"], 0) + 1
        out["classes"] = [{"id": c["id"], "name": c["name"], "invite_code": c["invite_code"], "students": counts.get(c["id"], 0)}
                          for c in classes]
        from services import razorpay_service as rzp
        out["pricing"] = {"per_seat_inr": PLANS["institution"]["price_inr"], "min_seats": MIN_PAID_SEATS,
                          "gst_rate": gst_rate(), "terms": list(TERM_MONTHS),
                          "payments_enabled": rzp.configured(), "test_mode": rzp.test_mode()}
        return out

    async def class_dashboard(self, user: dict, class_id: str) -> Dict[str, Any]:
        m = await self.require_staff(user["id"])
        cls = await self._class_in(m["institution_id"], class_id)
        books = await self._all("class_books", class_id=class_id)
        all_topics = set()
        for d in await self._in("documents", "id", [b["source_document_id"] for b in books], select="id, topics"):
            all_topics |= set(d.get("topics") or [])
        cms = await self._all("class_members", class_id=class_id)
        uids = [cm["user_id"] for cm in cms]
        pids = [cm["project_id"] for cm in cms if cm.get("project_id")]
        members = {x["user_id"]: x for x in await self._in(
            "institution_members", "user_id", uids, select="user_id, display_name, email, login_id, reg_no, managed, disabled",
            institution_id=m["institution_id"])}
        # One query per table for the whole class instead of three per student
        lp_rows = await self._in("learning_progress", "project_id", pids, select="user_id, project_id, completed_topics")
        perf_rows = await self._in("user_performance", "project_id", pids,
                                   select="user_id, project_id, topic, correct_count, wrong_count")
        since = (_now() - timedelta(days=90)).date().isoformat()
        act_rows = []
        for i in range(0, len(pids), _IN_CHUNK):
            chunk = pids[i:i + _IN_CHUNK]
            res = await async_db(lambda: self.client.table("study_activity").select("user_id, project_id, activity_date, total")
                                 .in_("project_id", chunk).gte("activity_date", since).execute())
            act_rows.extend(res.data or [])
        key = lambda r: (r.get("user_id"), r.get("project_id"))  # noqa: E731
        lp = {key(r): r for r in lp_rows}
        perf: Dict[tuple, List[dict]] = {}
        for r in perf_rows:
            perf.setdefault(key(r), []).append(r)
        acts: Dict[tuple, List[dict]] = {}
        for r in act_rows:
            acts.setdefault(key(r), []).append(r)

        week_ago = (_now() - timedelta(days=7)).date().isoformat()
        rows, weak_counts = [], {}
        for cm in cms:
            uid, pid = cm["user_id"], cm.get("project_id")
            info = members.get(uid, {})
            mastered, correct, wrong, weak, active_days, last_active = 0, 0, 0, [], 0, None
            if pid:
                mastered = len((lp.get((uid, pid)) or {}).get("completed_topics") or [])
                for p in perf.get((uid, pid), []):
                    c, w = p.get("correct_count") or 0, p.get("wrong_count") or 0
                    correct, wrong = correct + c, wrong + w
                    if c + w >= 3 and c / (c + w) < 0.6:
                        weak.append(p["topic"])
                        weak_counts[p["topic"]] = weak_counts.get(p["topic"], 0) + 1
                days = sorted({a["activity_date"] for a in acts.get((uid, pid), []) if (a.get("total") or 0) > 0})
                active_days = len([d for d in days if d >= week_ago])
                last_active = days[-1] if days else None
            rows.append({
                "user_id": uid, "name": info.get("display_name") or (info.get("email") or "Student").split("@")[0],
                "email": info.get("email"), "login_id": info.get("login_id"), "reg_no": info.get("reg_no"),
                "managed": bool(info.get("managed")), "disabled": bool(info.get("disabled")),
                "mastered": mastered, "total_topics": len(all_topics),
                "accuracy": round(100 * correct / (correct + wrong)) if correct + wrong else None,
                "weak_topics": weak[:5], "active_days_7": active_days, "last_active": last_active,
            })
        rows.sort(key=lambda r: (r["last_active"] or "", r["mastered"]), reverse=True)
        return {
            "class": {"id": cls["id"], "name": cls["name"], "invite_code": cls["invite_code"]},
            "books": [{"id": b["id"], "title": b["title"], "document_id": b["source_document_id"]} for b in books],
            "students": rows,
            "class_weak_topics": sorted(weak_counts.items(), key=lambda kv: -kv[1])[:8],
        }

    async def publishable_documents(self, user: dict) -> List[Dict[str, Any]]:
        await self.require_staff(user["id"])
        projects = await async_db(lambda: self.client.table("projects").select("id, name")
                                  .eq("user_id", user["id"]).execute())
        names = {p["id"]: p["name"] for p in projects.data or []}
        if not names:
            return []
        docs = await self._in("documents", "project_id", list(names), select="id, filename, project_id, upload_status",
                              upload_status="completed")
        return [{"id": d["id"], "filename": d["filename"], "project": names[d["project_id"]]}
                for d in docs if not names[d["project_id"]].startswith("Class · ")]

    # ------------------------------------------------------------- billing

    async def activate_seats(self, institution_id: str, seats: int, months: int = 12,
                             actor: Optional[str] = None, source: str = "razorpay",
                             payment_id: Optional[str] = None) -> Dict[str, Any]:
        """
        A paid term: the timer runs from now, or from the current end date when
        renewing a paid-up school early (unused paid time is never lost).
        """
        inst = await self.institution(institution_id, fresh=True)
        start = _now()
        end = _parse(inst.get("paid_until"))
        if inst.get("status") == "active" and end and end > start:
            start = end
        fields = {"status": "active", "seats": seats,
                  "paid_until": (start + timedelta(days=term_days(months))).isoformat(),
                  "last_payment_at": _now().isoformat(), "updated_at": _now().isoformat()}
        inst = (await async_db(lambda: self.client.table("institutions").update(fields)
                               .eq("id", institution_id).execute())).data[0]
        await self.refresh_member_plans(inst)
        await self.audit(institution_id, actor, "paid", {"seats": seats, "months": months, "source": source,
                                                         "payment_id": payment_id, "paid_until": inst["paid_until"]})
        logger.info(f"[Institution] {institution_id} paid ({source}): {seats} seats until {inst['paid_until']}")
        return inst

    # ------------------------------------------------------- platform admin

    async def platform_list(self, status: str = "", q: str = "", page: int = 1, page_size: int = 50) -> Dict[str, Any]:
        page_size = max(1, min(page_size, 200))
        start = (max(page, 1) - 1) * page_size
        query = self.client.table("institutions").select("*", count="exact")
        now = _now().isoformat()
        if status in ("pending", "suspended"):
            query = query.eq("approval_status", status)
        elif status == "live":
            query = query.eq("approval_status", "approved").gt("paid_until", now)
        elif status == "expired":
            query = query.eq("approval_status", "approved").or_(f"paid_until.is.null,paid_until.lte.{now}")
        q = _search_text(q)
        if q:
            query = query.or_(f"name.ilike.%{q}%,contact_email.ilike.%{q}%,billing_name.ilike.%{q}%")
        res = await async_db(lambda: query.order("created_at", desc=True).range(start, start + page_size - 1).execute())
        rows = res.data or []
        counts: Dict[str, int] = {}
        for inst in rows:
            counts[inst["id"]] = await self.student_count(inst["id"])
        return {
            "institutions": [{**self._school_view(i), "teacher_code": i.get("teacher_code"),
                              "owner_user_id": i.get("owner_user_id"), "created_at": i.get("created_at"),
                              "students": counts.get(i["id"], 0)} for i in rows],
            "total": res.count or 0, "page": page, "page_size": page_size,
        }

    async def _platform_update(self, institution_id: str, fields: Dict[str, Any]) -> Dict[str, Any]:
        fields["updated_at"] = _now().isoformat()
        res = await async_db(lambda: self.client.table("institutions").update(fields).eq("id", institution_id).execute())
        if not res.data:
            raise HTTPException(404, "Institution not found.")
        self.forget(institution_id=institution_id)
        return res.data[0]

    async def approve(self, actor: dict, institution_id: str, note: str = "") -> Dict[str, Any]:
        inst = await self.institution(institution_id, fresh=True)
        if not inst:
            raise HTTPException(404, "Institution not found.")
        fields: Dict[str, Any] = {"approval_status": "approved", "approval_note": note or None,
                                  "approved_at": _now().isoformat(), "approved_by": actor["id"]}
        trial_days = max(0, settings.INSTITUTION_TRIAL_DAYS)
        if not inst.get("paid_until") and inst.get("status") == "trial" and trial_days:
            fields["paid_until"] = (_now() + timedelta(days=trial_days)).isoformat()
        inst = await self._platform_update(institution_id, fields)
        if inst.get("paid_until"):
            await self.refresh_member_plans(inst)
        await self.audit(institution_id, actor["id"], "approved", {"note": note})
        return self._school_view(inst)

    async def suspend(self, actor: dict, institution_id: str, note: str = "") -> Dict[str, Any]:
        inst = await self._platform_update(institution_id, {"approval_status": "suspended", "approval_note": note or None})
        await self.audit(institution_id, actor["id"], "suspended", {"note": note})
        return self._school_view(inst)

    async def extend(self, actor: dict, institution_id: str, days: Optional[int] = None,
                     paid_until: Optional[str] = None, seats: Optional[int] = None, note: str = "") -> Dict[str, Any]:
        """Manual term change by us: offline payment (bank transfer, cheque), goodwill days or a fix."""
        inst = await self.institution(institution_id, fresh=True)
        if not inst:
            raise HTTPException(404, "Institution not found.")
        fields: Dict[str, Any] = {}
        if paid_until:
            end = _parse(paid_until)
            if not end:
                raise HTTPException(400, "paid_until must be an ISO date.")
            fields["paid_until"] = (end if end.tzinfo else end.replace(tzinfo=timezone.utc)).isoformat()
        elif days:
            current = _parse(inst.get("paid_until"))
            start = current if current and current > _now() else _now()
            fields["paid_until"] = (start + timedelta(days=days)).isoformat()
        if seats:
            fields["seats"] = seats
        if not fields:
            raise HTTPException(400, "Give days, paid_until or seats.")
        if "paid_until" in fields and inst.get("status") != "trial":
            fields["status"] = "active"
        inst = await self._platform_update(institution_id, fields)
        await self.refresh_member_plans(inst)
        await self.audit(institution_id, actor["id"], "extended", {**fields, "note": note})
        return self._school_view(inst)

    async def set_trial(self, actor: dict, institution_id: str, is_trial: bool) -> Dict[str, Any]:
        inst = await self._platform_update(institution_id, {"status": "trial" if is_trial else "active"})
        await self.audit(institution_id, actor["id"], "status_changed", {"status": inst["status"]})
        return self._school_view(inst)

    async def audit_log(self, institution_id: str, limit: int = 100) -> List[Dict[str, Any]]:
        res = await async_db(lambda: self.client.table("institution_audit").select("*")
                             .eq("institution_id", institution_id).order("created_at", desc=True)
                             .limit(min(limit, 500)).execute())
        return res.data or []

    async def expire_overdue(self) -> int:
        """Hourly: label schools whose term has ended as expired (access already stops on its own)."""
        now = _now().isoformat()
        res = await async_db(lambda: self.client.table("institutions").update({"status": "expired", "updated_at": now})
                             .in_("status", ["trial", "active"]).lt("paid_until", now).execute())
        for inst in res.data or []:
            self.forget(institution_id=inst["id"])
            await self.audit(inst["id"], None, "expired", {"paid_until": inst.get("paid_until")})
        if res.data:
            logger.info(f"[Institution] {len(res.data)} school(s) expired")
        return len(res.data or [])


institutions = InstitutionService()


async def expiry_loop(interval_seconds: int = 3600) -> None:
    """Background task started in main.py."""
    while True:
        try:
            await institutions.expire_overdue()
        except Exception as e:
            logger.warning(f"[Institution] expiry sweep failed: {e}")
        await asyncio.sleep(interval_seconds)
