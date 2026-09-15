"""
Backend regression + integration tests for THE LOST PROTOCOL.
Covers health, event, team login/state, admin CRUD, control endpoints,
offline tokens, final protocol, winner board, volunteer, and RBAC guards.
"""
import os
import time
import uuid
import requests
import pytest

BASE_URL = os.environ["REACT_APP_BACKEND_URL"].rstrip("/")
SUPABASE_URL = os.environ["SUPABASE_URL"].rstrip("/") if os.environ.get("SUPABASE_URL") else None
ANON_KEY = os.environ.get("REACT_APP_SUPABASE_ANON_KEY") or os.environ.get("SUPABASE_ANON_KEY")

# Load anon key from frontend .env if not in env
if not ANON_KEY:
    try:
        with open("/app/frontend/.env") as fh:
            for line in fh:
                if line.startswith("REACT_APP_SUPABASE_ANON_KEY"):
                    ANON_KEY = line.split("=", 1)[1].strip()
                if line.startswith("REACT_APP_SUPABASE_URL"):
                    SUPABASE_URL = line.split("=", 1)[1].strip().rstrip("/")
    except FileNotFoundError:
        pass

ADMIN_EMAIL = "admin@lostprotocol.dev"
ADMIN_PASSWORD = "LostProtocol#2026"
VOL_EMAIL = "volunteer1@lostprotocol.dev"
VOL_PASSWORD = "Volunteer#2026"


def supabase_login(email, password):
    resp = requests.post(
        f"{SUPABASE_URL}/auth/v1/token?grant_type=password",
        headers={"apikey": ANON_KEY, "Content-Type": "application/json"},
        json={"email": email, "password": password},
        timeout=15,
    )
    return resp


@pytest.fixture(scope="session")
def admin_token():
    r = supabase_login(ADMIN_EMAIL, ADMIN_PASSWORD)
    if r.status_code != 200:
        pytest.skip(f"Admin auth failed: {r.status_code} {r.text[:200]}")
    return r.json()["access_token"]


@pytest.fixture(scope="session")
def volunteer_token():
    r = supabase_login(VOL_EMAIL, VOL_PASSWORD)
    if r.status_code != 200:
        pytest.skip(f"Volunteer auth failed: {r.status_code} {r.text[:200]}")
    return r.json()["access_token"]


@pytest.fixture(scope="session")
def team_session():
    r = requests.post(f"{BASE_URL}/api/team/login",
                      json={"team_id": "LP-01", "pin": "0001"}, timeout=15)
    assert r.status_code == 200, r.text
    return r.json()["session_token"]


# ---------------- Public / health ----------------

def test_health():
    r = requests.get(f"{BASE_URL}/api/", timeout=15)
    assert r.status_code == 200
    data = r.json()
    assert data["status"] == "ready"
    assert "server_time" in data


def test_event_state():
    r = requests.get(f"{BASE_URL}/api/event", timeout=15)
    assert r.status_code == 200
    data = r.json()
    assert data["state"] in {"STANDBY", "LIVE", "PAUSED", "ENDED"}


# ---------------- Team auth ----------------

def test_team_login_success():
    r = requests.post(f"{BASE_URL}/api/team/login",
                      json={"team_id": "LP-01", "pin": "0001"}, timeout=15)
    assert r.status_code == 200
    body = r.json()
    assert body["team_id"] == "LP-01"
    assert body["session_token"].startswith("LP-01.")


def test_team_login_wrong_pin():
    r = requests.post(f"{BASE_URL}/api/team/login",
                      json={"team_id": "LP-01", "pin": "9999"}, timeout=15)
    assert r.status_code == 401


def test_team_state(team_session):
    r = requests.get(f"{BASE_URL}/api/team/state",
                     params={"session_token": team_session}, timeout=15)
    assert r.status_code == 200
    data = r.json()
    assert data["team"]["team_id"] == "LP-01"
    assert isinstance(data["route"], list)
    assert len(data["route"]) == 7
    assert data["event_state"] in {"STANDBY", "LIVE", "PAUSED", "ENDED"}
    assert "current" in data
    assert "fragments" in data
    assert "score" in data
    assert "completed" in data


# ---------------- Supabase auth ----------------

def test_supabase_admin_auth():
    r = supabase_login(ADMIN_EMAIL, ADMIN_PASSWORD)
    assert r.status_code == 200, r.text[:300]
    assert "access_token" in r.json()


def test_supabase_volunteer_auth():
    r = supabase_login(VOL_EMAIL, VOL_PASSWORD)
    assert r.status_code == 200, r.text[:300]


# ---------------- Admin lists ----------------

def test_admin_teams(admin_token):
    r = requests.get(f"{BASE_URL}/api/admin/teams",
                     params={"access_token": admin_token}, timeout=15)
    assert r.status_code == 200
    data = r.json()
    assert isinstance(data, list)
    assert len(data) >= 12


def test_admin_checkpoints(admin_token):
    r = requests.get(f"{BASE_URL}/api/admin/checkpoints",
                     params={"access_token": admin_token}, timeout=15)
    assert r.status_code == 200
    data = r.json()
    assert len(data) == 7
    codes = sorted(row["code"] for row in data)
    assert codes == ["A", "B", "C", "D", "E", "F", "G"]


def test_admin_hints(admin_token):
    r = requests.get(f"{BASE_URL}/api/admin/hints",
                     params={"access_token": admin_token}, timeout=15)
    assert r.status_code == 200
    assert len(r.json()) >= 7


def test_admin_audit_log(admin_token):
    r = requests.get(f"{BASE_URL}/api/admin/audit-log",
                     params={"access_token": admin_token}, timeout=15)
    assert r.status_code == 200
    assert isinstance(r.json(), list)


def test_admin_settings(admin_token):
    r = requests.get(f"{BASE_URL}/api/admin/settings",
                     params={"access_token": admin_token}, timeout=15)
    assert r.status_code == 200
    rows = r.json()
    keys = {row["key"] for row in rows}
    assert "final_answer_hash" in keys


# ---------------- Admin CRUD ----------------

def test_admin_create_and_delete_team(admin_token):
    tid = f"TEST-{uuid.uuid4().hex[:6].upper()}"
    r = requests.post(f"{BASE_URL}/api/admin/teams",
                      json={"access_token": admin_token,
                            "payload": {"team_id": tid, "team_name": "TEST_Team",
                                        "status": "active", "pin": "9911"}},
                      timeout=15)
    assert r.status_code == 200, r.text
    created = r.json()
    row = created[0] if isinstance(created, list) else created
    row_id = row["id"]
    # verify pin bcrypt-hashed via login
    login = requests.post(f"{BASE_URL}/api/team/login",
                          json={"team_id": tid, "pin": "9911"}, timeout=15)
    assert login.status_code == 200
    # cleanup delete
    d = requests.delete(f"{BASE_URL}/api/admin/teams/{row_id}",
                        params={"access_token": admin_token}, timeout=15)
    assert d.status_code == 200


def test_admin_patch_checkpoint(admin_token):
    lst = requests.get(f"{BASE_URL}/api/admin/checkpoints",
                       params={"access_token": admin_token}, timeout=15).json()
    target = next(cp for cp in lst if cp["code"] == "B")
    original_clue = target["clue"]
    new_clue = original_clue + " "  # trailing space marker
    r = requests.patch(f"{BASE_URL}/api/admin/checkpoints/{target['id']}",
                       json={"access_token": admin_token,
                             "payload": {"clue": new_clue}}, timeout=15)
    assert r.status_code == 200, r.text
    # revert
    requests.patch(f"{BASE_URL}/api/admin/checkpoints/{target['id']}",
                   json={"access_token": admin_token,
                         "payload": {"clue": original_clue}}, timeout=15)


def test_admin_announcement_create_and_delete(admin_token):
    c = requests.post(f"{BASE_URL}/api/admin/announcements",
                      json={"access_token": admin_token,
                            "payload": {"message": "TEST_msg", "active": True}}, timeout=15)
    assert c.status_code == 200, c.text
    body = c.json()
    row = body[0] if isinstance(body, list) else body
    row_id = row["id"]
    d = requests.delete(f"{BASE_URL}/api/admin/announcements/{row_id}",
                        params={"access_token": admin_token}, timeout=15)
    assert d.status_code == 200


# ---------------- Event control ----------------

def test_control_event_flip(admin_token):
    r = requests.post(f"{BASE_URL}/api/control/event",
                      json={"access_token": admin_token, "state": "LIVE"}, timeout=15)
    assert r.status_code == 200
    assert r.json()["state"] == "LIVE"
    # verify
    ev = requests.get(f"{BASE_URL}/api/event", timeout=15).json()
    assert ev["state"] == "LIVE"


def test_control_announce_and_read(admin_token):
    msg = f"TEST_ANN_{uuid.uuid4().hex[:6]}"
    r = requests.post(f"{BASE_URL}/api/control/announce",
                      json={"access_token": admin_token, "message": msg}, timeout=15)
    assert r.status_code == 200
    time.sleep(1)
    ann = requests.get(f"{BASE_URL}/api/event/announcements", timeout=15).json()
    messages = [row["message"] for row in ann]
    assert msg in messages
    # cleanup: find and delete
    found = next((row for row in ann if row["message"] == msg), None)
    if found:
        requests.delete(f"{BASE_URL}/api/admin/announcements/{found['id']}",
                        params={"access_token": admin_token}, timeout=15)


# ---------------- Team answer / offline token (LIVE required) ----------------

def test_team_hint(team_session):
    r = requests.post(f"{BASE_URL}/api/team/hint",
                      json={"session_token": team_session, "checkpoint_code": "A"}, timeout=15)
    assert r.status_code == 200
    d = r.json()
    assert "content" in d
    assert "penalty" in d


def test_offline_token_flow(admin_token, team_session):
    # ensure LIVE
    requests.post(f"{BASE_URL}/api/control/event",
                  json={"access_token": admin_token, "state": "LIVE"}, timeout=15)
    # find LP-01's current active checkpoint
    state = requests.get(f"{BASE_URL}/api/team/state",
                        params={"session_token": team_session}, timeout=15).json()
    current = state.get("current")
    if not current:
        pytest.skip("LP-01 has no active checkpoint (already finished)")
    cp_code = current["code"]
    # issue
    issue = requests.post(f"{BASE_URL}/api/control/offline-token",
                          json={"access_token": admin_token,
                                "team_id": "LP-01", "checkpoint_code": cp_code}, timeout=15)
    assert issue.status_code == 200, issue.text
    tok = issue.json()["token"]
    # redeem
    red = requests.post(f"{BASE_URL}/api/team/redeem-token",
                        json={"session_token": team_session, "token": tok,
                              "checkpoint_code": cp_code}, timeout=15)
    assert red.status_code == 200, red.text
    assert red.json()["valid"] is True
    # second redeem must fail (used_at set)
    red2 = requests.post(f"{BASE_URL}/api/team/redeem-token",
                         json={"session_token": team_session, "token": tok,
                               "checkpoint_code": cp_code}, timeout=15)
    # Reuse is blocked either because token.used_at is set (409) or because
    # the node is no longer active for this team (403). Both prevent double redemption.
    assert red2.status_code in (403, 409)


def test_team_answer_and_progress(admin_token, team_session):
    # ensure LIVE
    requests.post(f"{BASE_URL}/api/control/event",
                  json={"access_token": admin_token, "state": "LIVE"}, timeout=15)
    state = requests.get(f"{BASE_URL}/api/team/state",
                         params={"session_token": team_session}, timeout=15).json()
    current = state.get("current")
    if not current:
        pytest.skip("No active checkpoint for LP-01")
    cp = current["code"]
    ans_map = {"A": "1897", "B": "42", "C": "echo", "D": "north",
               "E": "cedar", "F": "orion", "G": "begin"}
    r = requests.post(f"{BASE_URL}/api/team/answer",
                      json={"session_token": team_session, "checkpoint_code": cp,
                            "answer": ans_map[cp]}, timeout=15)
    assert r.status_code == 200, r.text
    assert r.json()["valid"] is True


# ---------------- Final protocol ----------------

def test_final_rejects_when_incomplete():
    # use LP-12 which is likely not fully completed
    login = requests.post(f"{BASE_URL}/api/team/login",
                          json={"team_id": "LP-12", "pin": "0012"}, timeout=15).json()
    tok = login["session_token"]
    state = requests.get(f"{BASE_URL}/api/team/state",
                         params={"session_token": tok}, timeout=15).json()
    if state["completed"] >= 7:
        pytest.skip("LP-12 already completed all nodes")
    r = requests.post(f"{BASE_URL}/api/team/final",
                      json={"session_token": tok, "answer": "protocol"}, timeout=15)
    assert r.status_code == 200
    assert r.json()["valid"] is False


def test_final_full_flow(admin_token):
    """Complete all 7 nodes for a fresh team and submit final."""
    # ensure LIVE
    requests.post(f"{BASE_URL}/api/control/event",
                  json={"access_token": admin_token, "state": "LIVE"}, timeout=15)
    ans_map = {"A": "1897", "B": "42", "C": "echo", "D": "north",
               "E": "cedar", "F": "orion", "G": "begin"}
    # try teams to find one not yet finished
    chosen_token = None
    for idx in range(2, 13):
        tid = f"LP-{idx:02d}"
        pin = f"{idx:04d}"
        login = requests.post(f"{BASE_URL}/api/team/login",
                              json={"team_id": tid, "pin": pin}, timeout=15)
        if login.status_code != 200:
            continue
        tok = login.json()["session_token"]
        st = requests.get(f"{BASE_URL}/api/team/state",
                          params={"session_token": tok}, timeout=15).json()
        already = requests.post(f"{BASE_URL}/api/team/final",
                                json={"session_token": tok, "answer": "protocol"}, timeout=15).json()
        if already.get("already"):
            continue
        chosen_token = tok
        chosen_team = tid
        break
    if not chosen_token:
        pytest.skip("No available fresh team")
    # complete remaining nodes
    for _ in range(8):
        st = requests.get(f"{BASE_URL}/api/team/state",
                          params={"session_token": chosen_token}, timeout=15).json()
        cur = st.get("current")
        if not cur:
            break
        code = cur["code"]
        requests.post(f"{BASE_URL}/api/team/answer",
                      json={"session_token": chosen_token,
                            "checkpoint_code": code,
                            "answer": ans_map[code]}, timeout=15)
    r = requests.post(f"{BASE_URL}/api/team/final",
                      json={"session_token": chosen_token, "answer": "protocol"}, timeout=15)
    assert r.status_code == 200
    body = r.json()
    assert body["valid"] is True, f"Final rejected for {chosen_team}: {body}"


def test_winner_board(admin_token):
    r = requests.get(f"{BASE_URL}/api/control/winner",
                     params={"access_token": admin_token}, timeout=15)
    assert r.status_code == 200
    data = r.json()
    assert "finish_order" in data
    assert "server_time" in data
    if data["finish_order"]:
        first = data["finish_order"][0]
        assert "team" in first
        assert "score" in first


# ---------------- Volunteer flows ----------------

def test_volunteer_action(volunteer_token):
    r = requests.post(f"{BASE_URL}/api/control/volunteer",
                      json={"access_token": volunteer_token, "action": "START",
                            "team_id": "LP-01", "checkpoint_code": "C"}, timeout=15)
    assert r.status_code == 200
    assert r.json()["recorded"] is True


def test_volunteer_cannot_flip_event(volunteer_token):
    r = requests.post(f"{BASE_URL}/api/control/event",
                      json={"access_token": volunteer_token, "state": "LIVE"}, timeout=15)
    assert r.status_code == 403


# ---------------- RBAC / auth guards ----------------

def test_admin_route_unauthenticated():
    r = requests.get(f"{BASE_URL}/api/admin/teams",
                     params={"access_token": "bogus"}, timeout=15)
    assert r.status_code == 401


def test_control_route_unauthenticated():
    r = requests.post(f"{BASE_URL}/api/control/event",
                      json={"access_token": "bogus", "state": "LIVE"}, timeout=15)
    assert r.status_code == 401


def test_dev_seed_operator_wrong_key():
    r = requests.post(f"{BASE_URL}/api/dev/seed-operator",
                      json={"email": "x@y.z", "password": "abc",
                            "role": "admin", "setup_key": "wrong"}, timeout=15)
    assert r.status_code == 403


# ---------------- Teardown: reset event to STANDBY ----------------

def test_zzz_reset_event_to_standby(admin_token):
    r = requests.post(f"{BASE_URL}/api/control/event",
                      json={"access_token": admin_token, "state": "STANDBY"}, timeout=15)
    assert r.status_code == 200
