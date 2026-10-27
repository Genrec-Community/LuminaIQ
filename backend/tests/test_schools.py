"""School structure: sign-in IDs, approval gate, subscription timer, tenancy."""

import asyncio
import uuid
from datetime import datetime, timedelta, timezone

import pytest
from fastapi import HTTPException

from services import school_accounts as accounts
from services import institution_service as isvc
from tests.fake_supabase import FakeClient


def run(coro):
    return asyncio.run(coro)


# ----------------------------------------------------------------- pure helpers

def test_login_id_format():
    assert accounts.name_slug("Arun Kumar") == "arunkumar"
    assert accounts.name_slug("Zoë D'Souza") == "zoedsouza"
    assert accounts.name_slug("  ") == "student"
    assert accounts.reg_suffix("21CS107") == "07"
    assert accounts.reg_suffix("A5") == "05"
    assert accounts.local_part("Arun Kumar", "21CS107") == "arunkumar-07"
    assert accounts.local_part("Arun Kumar", "21CS107", 2) == "arunkumar2-07"
    assert accounts.candidate_ids("Arun", "12", 1, 2) == ["arun-12@luminaiq.fun", "arun2-12@luminaiq.fun"]
    with pytest.raises(ValueError):
        accounts.reg_suffix("ABC")


def test_custom_login_id_and_domain_check():
    assert accounts.custom_login_id("Arun.K") == "arun.k@luminaiq.fun"
    assert accounts.custom_login_id("arun@luminaiq.fun") == "arun@luminaiq.fun"
    with pytest.raises(ValueError):
        accounts.custom_login_id("arun@gmail.com")
    with pytest.raises(ValueError):
        accounts.custom_login_id("a b")
    assert accounts.is_school_login("X-07@LuminaIQ.fun")
    assert not accounts.is_school_login("x@gmail.com")


def test_passwords():
    assert accounts.password_problem("short1")
    assert accounts.password_problem("onlyletters")
    assert accounts.password_problem("abcd1234") is None
    for _ in range(50):
        assert accounts.password_problem(accounts.generate_password()) is None


def test_state_and_timer():
    future = (datetime.now(timezone.utc) + timedelta(days=3)).isoformat()
    past = (datetime.now(timezone.utc) - timedelta(days=1)).isoformat()
    assert isvc.state({"approval_status": "pending", "paid_until": future}) == isvc.PENDING
    assert isvc.state({"approval_status": "suspended", "paid_until": future}) == isvc.SUSPENDED
    assert isvc.state({"approval_status": "approved", "paid_until": past}) == isvc.EXPIRED
    assert isvc.state({"approval_status": "approved", "paid_until": None}) == isvc.EXPIRED
    assert isvc.state({"approval_status": "approved", "paid_until": future, "status": "trial"}) == isvc.TRIAL
    assert isvc.state({"approval_status": "approved", "paid_until": future, "status": "active"}) == isvc.ACTIVE
    # rows from before the approval gate keep working
    assert isvc.state({"paid_until": future, "status": "active"}) == isvc.ACTIVE
    t = isvc.time_left({"paid_until": future})
    assert t["days_left"] in (2, 3) and t["seconds_left"] > 0


def test_price_by_term():
    yearly = isvc.seats_price_paise(100, 12)
    assert yearly["base"] == 100 * 179 * 12 * 100
    assert yearly["total"] == yearly["base"] + round(yearly["base"] * 0.18)
    assert isvc.seats_price_paise(100, 3)["base"] == 100 * 179 * 3 * 100
    assert isvc.term_days(12) == 365 and isvc.term_days(6) == 180


def test_parse_seats_plan_back_compat():
    from api.v1.endpoints.billing import parse_seats_plan
    assert parse_seats_plan("institution:abc:150") == ("abc", 150, 12)
    assert parse_seats_plan("institution:abc:150:3") == ("abc", 150, 3)


# ------------------------------------------------------------- service flows

@pytest.fixture
def svc(monkeypatch):
    from services.usage_service import usage
    fake = FakeClient()
    service = isvc.InstitutionService.__new__(isvc.InstitutionService)
    service.client = fake
    service._inst_cache, service._access_cache = {}, {}
    service._id_lock = asyncio.Lock()
    monkeypatch.setattr(isvc, "institutions", service)
    monkeypatch.setattr(usage, "client", fake)
    usage._plans.clear()

    async def create_project(user_id, name):
        row = {"id": str(uuid.uuid4()), "user_id": user_id, "name": name}
        fake.tables.setdefault("projects", []).append(row)
        return row
    from services.project_service import project_service
    monkeypatch.setattr(project_service, "create_project", create_project)
    return service


def _user(email="admin@school.in"):
    return {"id": str(uuid.uuid4()), "email": email}


def _approved_school(svc, admin=None):
    admin = admin or _user()
    inst = run(svc.create(admin, "Green Valley School", "", "", "", "Principal"))
    run(svc.approve({"id": "platform"}, inst["id"]))
    return admin, inst


def test_new_school_waits_for_approval(svc):
    admin = _user()
    inst = run(svc.create(admin, "Green Valley School", "", "", "", "Principal"))
    assert inst["approval_status"] == "pending" and inst["paid_until"] is None
    with pytest.raises(HTTPException) as e:
        run(svc.create_class(admin, "10 A"))
    assert e.value.status_code == 403 and e.value.detail["code"] == "school_inactive"

    view = run(svc.approve({"id": "platform"}, inst["id"]))
    assert view["state"] == isvc.TRIAL and view["timer"]["days_left"] >= 13
    assert run(svc.create_class(admin, "10 A"))["name"] == "10 A"


def test_create_students_ids_collisions_and_seats(svc):
    admin, inst = _approved_school(svc)
    cls = run(svc.create_class(admin, "10 A"))
    out = run(svc.create_students(admin, [
        {"name": "Arun Kumar", "reg_no": "21CS107", "class_id": cls["id"]},
        {"name": "Arun Kumar", "reg_no": "22CS207"},          # same name, same last 2 digits
        {"name": "Priya", "reg_no": "21CS107"},               # duplicate reg no in the upload
        {"name": "Meena", "reg_no": "X9", "password": "Meena2026"},
    ]))
    ids = sorted(r["login_id"] for r in out["created"])
    assert ids == ["arunkumar-07@luminaiq.fun", "arunkumar2-07@luminaiq.fun", "meena-09@luminaiq.fun"]
    assert len(out["failed"]) == 1 and "register number" in out["failed"][0]["error"]
    meena = next(r for r in out["created"] if r["name"] == "Meena")
    assert meena["password"] == "Meena2026"
    # the class student got a class project
    arun = next(r for r in out["created"] if r["login_id"].startswith("arunkumar-"))
    assert arun["class"] == "10 A"

    # another school: IDs are unique across the whole platform
    admin2, _ = _approved_school(svc, _user("head@other.in"))
    out2 = run(svc.create_students(admin2, [{"name": "Arun Kumar", "reg_no": "107"}]))
    assert out2["created"][0]["login_id"] == "arunkumar3-07@luminaiq.fun"

    # seats: trial has 25; 3 used
    with pytest.raises(HTTPException) as e:
        run(svc.create_students(admin, [{"name": f"S{i}", "reg_no": str(100 + i)} for i in range(23)]))
    assert e.value.status_code == 403

    listing = run(svc.list_students(admin, q="arun"))
    assert listing["total"] == 2 and all(s["managed"] for s in listing["students"])
    # tenancy: school 2 only sees its own student
    assert run(svc.list_students(admin2))["total"] == 1


def test_access_gate_reset_and_disable(svc):
    admin, inst = _approved_school(svc)
    created = run(svc.create_students(admin, [{"name": "Ravi", "reg_no": "45"}]))["created"][0]
    uid = created["user_id"]
    assert run(svc.managed_access(uid))["ok"]

    reset = run(svc.reset_password(admin, uid, None))
    assert svc.client.auth.admin.users[uid]["password"] == reset["password"]
    assert run(svc.account_info(uid))["must_change_password"]

    run(svc.set_disabled(admin, uid, True))
    a = run(svc.managed_access(uid))
    assert not a["ok"] and a["state"] == "disabled"
    run(svc.set_disabled(admin, uid, False))
    assert run(svc.managed_access(uid))["ok"]

    run(svc.suspend({"id": "platform"}, inst["id"], "unpaid"))
    a = run(svc.managed_access(uid))
    assert not a["ok"] and a["state"] == isvc.SUSPENDED


def test_other_school_cannot_touch_students(svc):
    admin, _ = _approved_school(svc)
    uid = run(svc.create_students(admin, [{"name": "Ravi", "reg_no": "45"}]))["created"][0]["user_id"]
    admin2, _ = _approved_school(svc, _user("head@other.in"))
    with pytest.raises(HTTPException) as e:
        run(svc.reset_password(admin2, uid))
    assert e.value.status_code == 404
    with pytest.raises(HTTPException):
        run(svc.set_disabled(admin2, uid, True))


def test_expiry_stops_plan_and_payment_restarts_timer(svc):
    from services.usage_service import usage
    admin, inst = _approved_school(svc)
    uid = run(svc.create_students(admin, [{"name": "Ravi", "reg_no": "45"}]))["created"][0]["user_id"]
    assert run(usage.plan(uid)) == "institution"

    # term ends
    past = (datetime.now(timezone.utc) - timedelta(minutes=1)).isoformat()
    svc.client.tables["institutions"][0]["paid_until"] = past
    svc.forget(institution_id=inst["id"])
    usage._plans.clear()
    assert run(usage.plan(uid)) == "free"
    assert not run(svc.managed_access(uid))["ok"]
    assert run(svc.expire_overdue()) == 1

    # payment: timer starts from the payment date
    paid = run(svc.activate_seats(inst["id"], 120, 3))
    end = datetime.fromisoformat(paid["paid_until"])
    assert timedelta(days=89) < end - datetime.now(timezone.utc) <= timedelta(days=90)
    usage._plans.clear()
    assert run(usage.plan(uid)) == "institution"
    assert run(svc.managed_access(uid))["ok"]

    # early renewal stacks on the current end date
    again = run(svc.activate_seats(inst["id"], 120, 12))
    assert datetime.fromisoformat(again["paid_until"]) - end == timedelta(days=365)


def test_teacher_cannot_join_two_schools(svc):
    _, inst1 = _approved_school(svc)
    _, inst2 = _approved_school(svc, _user("head@other.in"))
    teacher = _user("t@x.in")
    run(svc.join(teacher, inst1["teacher_code"], "T"))
    with pytest.raises(HTTPException) as e:
        run(svc.join(teacher, inst2["teacher_code"], "T"))
    assert e.value.status_code == 409


def test_managed_token_blocked_when_school_paused(svc):
    from api import deps
    from services.auth_service import auth_service
    admin, inst = _approved_school(svc)
    uid = run(svc.create_students(admin, [{"name": "Ravi", "reg_no": "45"}]))["created"][0]["user_id"]
    session = run(auth_service.issue_session(uid, "ravi-45@luminaiq.fun", "Ravi"))
    assert session["user"]["managed"] and session["user"]["must_change_password"]
    assert run(deps.get_current_user(session["access_token"]))["id"] == uid

    run(svc.suspend({"id": "platform"}, inst["id"]))
    with pytest.raises(HTTPException) as e:
        run(deps.get_current_user(session["access_token"]))
    assert e.value.status_code == 403 and e.value.detail["code"] == "school_inactive"


def test_student_changes_own_password(svc, monkeypatch):
    from services.auth_service import auth_service
    admin, _ = _approved_school(svc)
    c = run(svc.create_students(admin, [{"name": "Ravi", "reg_no": "45", "password": "First1234"}]))["created"][0]
    users = svc.client.auth.admin.users

    async def grant(email, password):
        u = next(u for u in users.values() if u["email"] == email)
        if u["password"] != password:
            raise accounts.InvalidCredentials("Invalid login credentials")
        return u
    monkeypatch.setattr(accounts, "password_grant", grant)
    monkeypatch.setattr(auth_service, "client", svc.client)

    with pytest.raises(ValueError):
        run(auth_service.change_password(c["user_id"], "wrong", "Second1234"))
    run(auth_service.change_password(c["user_id"], "First1234", "Second1234"))
    assert users[c["user_id"]]["password"] == "Second1234"
    assert not run(svc.account_info(c["user_id"]))["must_change_password"]
