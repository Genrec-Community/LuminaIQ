"""
Institution plan: schools and coaching institutes.

- An admin creates an institution: 14-day trial for up to TRIAL_SEATS students,
  then buys student seats yearly (₹179 per student per month + GST).
- Teachers join with the institution's teacher code; students join a class with
  its invite code. Members get the "institution" plan (services/plans.py).
- Teachers publish books from their own projects to a class. Every student gets
  a copy in a "Class · <name>" project: the copy reuses the teacher's stored text
  and vectors, so no AI or embedding calls are made per student.
- The class dashboard shows each student's progress, accuracy and weak topics.
"""

from __future__ import annotations

import secrets
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from fastapi import HTTPException

from db.client import async_db, get_supabase_client
from services.plans import PLANS
from services.usage_service import usage
from utils.logger import logger

TRIAL_DAYS = 14
TRIAL_SEATS = 25
MIN_PAID_SEATS = 100
GST_RATE = 0.18
_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"  # no 0/O/1/I


def _code(prefix: str) -> str:
    return f"{prefix}-" + "".join(secrets.choice(_ALPHABET) for _ in range(6))


def _now() -> datetime:
    return datetime.now(timezone.utc)


def seats_price_paise(seats: int) -> Dict[str, int]:
    """Yearly price for `seats` students: base + 18% GST (B2B, GST on top)."""
    base = seats * PLANS["institution"]["price_inr"] * 12 * 100
    gst = round(base * GST_RATE)
    return {"base": base, "gst": gst, "total": base + gst}


class InstitutionService:
    def __init__(self):
        self.client = get_supabase_client()

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

    async def membership(self, user_id: str) -> Optional[Dict[str, Any]]:
        res = await async_db(lambda: self.client.table("institution_members").select("*")
                             .eq("user_id", user_id).order("joined_at").limit(1).execute())
        return res.data[0] if res.data else None

    async def require_staff(self, user_id: str) -> Dict[str, Any]:
        m = await self.membership(user_id)
        if not m or m["role"] not in ("admin", "teacher"):
            raise HTTPException(403, "Only your institution's admins and teachers can do this.")
        return m

    async def student_count(self, institution_id: str) -> int:
        res = await async_db(lambda: self.client.table("institution_members").select("user_id", count="exact")
                             .eq("institution_id", institution_id).eq("role", "student").execute())
        return res.count or 0

    @staticmethod
    def is_live(inst: Dict[str, Any]) -> bool:
        end = inst.get("paid_until")
        if not end:
            return False
        return datetime.fromisoformat(end.replace("Z", "+00:00")) > _now()

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
        """After a renewal: move every member's plan end to the new paid-up date."""
        await async_db(lambda: self.client.table("user_plans").update({
            "current_period_end": inst["paid_until"], "status": "active", "updated_at": _now().isoformat(),
        }).eq("institution_id", inst["id"]).eq("source", "institution").execute())
        for m in await self._all("institution_members", institution_id=inst["id"]):
            usage.forget(m["user_id"])

    # ------------------------------------------------------------ actions

    async def create(self, user: dict, name: str, contact_email: str, billing_name: str,
                     gstin: str, display_name: str) -> Dict[str, Any]:
        if await self.membership(user["id"]):
            raise HTTPException(409, "You're already part of an institution.")
        inst = (await async_db(lambda: self.client.table("institutions").insert({
            "name": name.strip()[:120], "owner_user_id": user["id"],
            "contact_email": (contact_email or user.get("email") or "")[:200],
            "billing_name": (billing_name or name).strip()[:200], "gstin": (gstin or "").strip().upper()[:15] or None,
            "seats": TRIAL_SEATS, "status": "trial",
            "paid_until": (_now() + timedelta(days=TRIAL_DAYS)).isoformat(),
            "teacher_code": _code("T"),
        }).execute())).data[0]
        await async_db(lambda: self.client.table("institution_members").insert({
            "institution_id": inst["id"], "user_id": user["id"], "role": "admin",
            "display_name": display_name, "email": user.get("email"),
        }).execute())
        await self._grant_plan(user["id"], inst)
        logger.info(f"[Institution] created {inst['name']} ({inst['id']})")
        return inst

    async def create_class(self, user: dict, name: str) -> Dict[str, Any]:
        m = await self.require_staff(user["id"])
        return (await async_db(lambda: self.client.table("institution_classes").insert({
            "institution_id": m["institution_id"], "name": name.strip()[:80],
            "invite_code": _code("C"), "created_by": user["id"],
        }).execute())).data[0]

    async def join(self, user: dict, code: str, display_name: str) -> Dict[str, Any]:
        code = (code or "").strip().upper()
        inst = await self._one("institutions", teacher_code=code)
        if inst:
            if not self.is_live(inst):
                raise HTTPException(403, "This institution's plan has ended. Ask your admin to renew.")
            await async_db(lambda: self.client.table("institution_members").upsert({
                "institution_id": inst["id"], "user_id": user["id"], "role": "teacher",
                "display_name": display_name, "email": user.get("email"),
            }, on_conflict="institution_id,user_id").execute())
            await self._grant_plan(user["id"], inst)
            return {"role": "teacher", "institution": inst["name"]}

        cls = await self._one("institution_classes", invite_code=code)
        if not cls:
            raise HTTPException(404, "That code doesn't match any class. Check it with your teacher.")
        inst = await self._one("institutions", id=cls["institution_id"])
        if not inst or not self.is_live(inst):
            raise HTTPException(403, "This institution's plan has ended. Ask your teacher.")

        existing = await self._one("institution_members", institution_id=inst["id"], user_id=user["id"])
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

        cm = await self._one("class_members", class_id=cls["id"], user_id=user["id"])
        project_id = cm.get("project_id") if cm else None
        if not project_id:
            from services.project_service import project_service
            project = await project_service.create_project(user["id"], f"Class · {cls['name']}")
            project_id = project["id"]
            await async_db(lambda: self.client.table("class_members").upsert({
                "class_id": cls["id"], "user_id": user["id"], "project_id": project_id,
            }, on_conflict="class_id,user_id").execute())
        for book in await self._all("class_books", class_id=cls["id"]):
            await self._copy_book_to(book, user["id"], project_id)
        return {"role": "student", "institution": inst["name"], "class": cls["name"], "project_id": project_id}

    async def publish_book(self, user: dict, class_id: str, document_id: str) -> Dict[str, Any]:
        m = await self.require_staff(user["id"])
        cls = await self._one("institution_classes", id=class_id)
        if not cls or cls["institution_id"] != m["institution_id"]:
            raise HTTPException(404, "Class not found.")
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

    async def remove_member(self, user: dict, member_user_id: str) -> None:
        m = await self.membership(user["id"])
        if not m or m["role"] != "admin":
            raise HTTPException(403, "Only admins can remove members.")
        if member_user_id == user["id"]:
            raise HTTPException(400, "You can't remove yourself.")
        await async_db(lambda: self.client.table("institution_members").delete()
                       .eq("institution_id", m["institution_id"]).eq("user_id", member_user_id).execute())
        classes = await self._all("institution_classes", institution_id=m["institution_id"])
        for c in classes:
            await async_db(lambda: self.client.table("class_members").delete()
                           .eq("class_id", c["id"]).eq("user_id", member_user_id).execute())
        await self._revoke_plan(member_user_id, m["institution_id"])

    # ---------------------------------------------------------- read views

    async def overview(self, user: dict) -> Dict[str, Any]:
        m = await self.membership(user["id"])
        if not m:
            return {"member": False}
        inst = await self._one("institutions", id=m["institution_id"])
        out: Dict[str, Any] = {
            "member": True, "role": m["role"],
            "institution": {k: inst.get(k) for k in ("id", "name", "status", "seats", "paid_until", "billing_name", "gstin", "contact_email")},
            "live": self.is_live(inst),
        }
        if m["role"] == "student":
            res = await async_db(lambda: self.client.table("class_members").select("class_id, project_id")
                                 .eq("user_id", user["id"]).execute())
            class_ids = [r["class_id"] for r in res.data or []]
            out["classes"] = [
                {"id": c["id"], "name": c["name"], "project_id": next(r["project_id"] for r in res.data if r["class_id"] == c["id"])}
                for c in await self._all("institution_classes", institution_id=inst["id"]) if c["id"] in class_ids
            ]
            return out
        out["institution"]["teacher_code"] = inst["teacher_code"]
        out["students"] = await self.student_count(inst["id"])
        members = await self._all("institution_members", institution_id=inst["id"])
        out["teachers"] = [{"user_id": x["user_id"], "name": x.get("display_name"), "email": x.get("email"), "role": x["role"]}
                           for x in members if x["role"] != "student"]
        classes = await self._all("institution_classes", institution_id=inst["id"])
        counts: Dict[str, int] = {}
        for c in classes:
            res = await async_db(lambda: self.client.table("class_members").select("user_id", count="exact")
                                 .eq("class_id", c["id"]).execute())
            counts[c["id"]] = res.count or 0
        out["classes"] = [{"id": c["id"], "name": c["name"], "invite_code": c["invite_code"], "students": counts[c["id"]]}
                          for c in sorted(classes, key=lambda c: c["created_at"])]
        out["pricing"] = {"per_seat_inr": PLANS["institution"]["price_inr"], "min_seats": MIN_PAID_SEATS, "gst_rate": GST_RATE}
        return out

    async def class_dashboard(self, user: dict, class_id: str) -> Dict[str, Any]:
        m = await self.require_staff(user["id"])
        cls = await self._one("institution_classes", id=class_id)
        if not cls or cls["institution_id"] != m["institution_id"]:
            raise HTTPException(404, "Class not found.")
        books = await self._all("class_books", class_id=class_id)
        all_topics = set()
        for b in books:
            d = await self._one("documents", id=b["source_document_id"])
            all_topics |= set((d or {}).get("topics") or [])
        members = {x["user_id"]: x for x in await self._all("institution_members", institution_id=m["institution_id"])}
        week_ago = (_now() - timedelta(days=7)).date().isoformat()
        rows, weak_counts = [], {}
        for cm in await self._all("class_members", class_id=class_id):
            uid, pid = cm["user_id"], cm.get("project_id")
            info = members.get(uid, {})
            mastered, correct, wrong, weak, active_days, last_active = 0, 0, 0, [], 0, None
            if pid:
                lp = await self._one("learning_progress", user_id=uid, project_id=pid)
                mastered = len((lp or {}).get("completed_topics") or [])
                for p in await self._all("user_performance", user_id=uid, project_id=pid):
                    c, w = p.get("correct_count") or 0, p.get("wrong_count") or 0
                    correct, wrong = correct + c, wrong + w
                    if c + w >= 3 and c / (c + w) < 0.6:
                        weak.append(p["topic"])
                        weak_counts[p["topic"]] = weak_counts.get(p["topic"], 0) + 1
                acts = await self._all("study_activity", user_id=uid, project_id=pid)
                days = sorted({a["activity_date"] for a in acts if (a.get("total") or 0) > 0})
                active_days = len([d for d in days if d >= week_ago])
                last_active = days[-1] if days else None
            rows.append({
                "user_id": uid, "name": info.get("display_name") or (info.get("email") or "Student").split("@")[0],
                "email": info.get("email"), "mastered": mastered, "total_topics": len(all_topics),
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
        docs = await async_db(lambda: self.client.table("documents").select("id, filename, project_id, upload_status")
                              .in_("project_id", list(names)).eq("upload_status", "completed").execute())
        return [{"id": d["id"], "filename": d["filename"], "project": names[d["project_id"]]}
                for d in docs.data or [] if not names[d["project_id"]].startswith("Class · ")]

    # ------------------------------------------------------------- billing

    async def activate_seats(self, institution_id: str, seats: int) -> Dict[str, Any]:
        inst = await self._one("institutions", id=institution_id)
        start = _now()
        if inst.get("status") == "active" and self.is_live(inst):
            start = datetime.fromisoformat(inst["paid_until"].replace("Z", "+00:00"))
        fields = {"status": "active", "seats": seats, "paid_until": (start + timedelta(days=365)).isoformat()}
        inst = (await async_db(lambda: self.client.table("institutions").update(fields)
                               .eq("id", institution_id).execute())).data[0]
        await self.refresh_member_plans(inst)
        logger.info(f"[Institution] {institution_id} paid: {seats} seats until {inst['paid_until']}")
        return inst


institutions = InstitutionService()
