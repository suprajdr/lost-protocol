"""
Backend regression for THE LOST PROTOCOL mechanics (A–G).
Covers event state gate, team state safety (no hash leaks), each mechanic,
volunteer authorization, hint dedupe, offline tokens, final gate, RLS, cleanup.
"""
import os, uuid, requests, pytest, time

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")
SUPABASE_URL = os.environ.get("SUPABASE_URL", "").rstrip("/") or None
ANON_KEY = os.environ.get("REACT_APP_SUPABASE_ANON_KEY") or os.environ.get("SUPABASE_ANON_KEY")
try:
    with open("/app/frontend/.env") as fh:
        for line in fh:
            if not BASE_URL and line.startswith("REACT_APP_BACKEND_URL"):
                BASE_URL = line.split("=", 1)[1].strip().rstrip("/")
            if not SUPABASE_URL and line.startswith("REACT_APP_SUPABASE_URL"):
                SUPABASE_URL = line.split("=", 1)[1].strip().rstrip("/")
            if not ANON_KEY and line.startswith("REACT_APP_SUPABASE_ANON_KEY"):
                ANON_KEY = line.split("=", 1)[1].strip()
except FileNotFoundError:
    pass
assert BASE_URL and SUPABASE_URL and ANON_KEY, "Missing env config"

ADMIN_EMAIL = "admin@lostprotocol.dev"
ADMIN_PASSWORD = "LostProtocol#2026"
VOL_EMAIL = "volunteer1@lostprotocol.dev"
VOL_PASSWORD = "Volunteer#2026"

# ---- session-scoped helpers ----

def _sb_login(email, pw):
    return requests.post(f"{SUPABASE_URL}/auth/v1/token?grant_type=password",
                         headers={"apikey": ANON_KEY, "Content-Type": "application/json"},
                         json={"email": email, "password": pw}, timeout=15)

@pytest.fixture(scope="session")
def admin_token():
    r = _sb_login(ADMIN_EMAIL, ADMIN_PASSWORD)
    if r.status_code != 200:
        pytest.skip(f"Admin auth failed: {r.text[:200]}")
    return r.json()["access_token"]

@pytest.fixture(scope="session")
def volunteer_token():
    r = _sb_login(VOL_EMAIL, VOL_PASSWORD)
    if r.status_code != 200:
        pytest.skip(f"Volunteer auth failed: {r.text[:200]}")
    return r.json()["access_token"]

def team_login(tid, pin):
    return requests.post(f"{BASE_URL}/api/team/login",
                         json={"team_id": tid, "pin": pin}, timeout=15)

def get_state(token):
    return requests.get(f"{BASE_URL}/api/team/state",
                        params={"session_token": token}, timeout=15).json()

def set_event(admin, state):
    return requests.post(f"{BASE_URL}/api/control/event",
                         json={"access_token": admin, "state": state}, timeout=15)


@pytest.fixture(scope="session", autouse=True)
def _prep(admin_token):
    # Re-sync mechanics idempotently, then set event LIVE
    requests.post(f"{BASE_URL}/api/admin/apply-mechanics",
                  json={"access_token": admin_token}, timeout=20)
    set_event(admin_token, "LIVE")
    yield
    set_event(admin_token, "STANDBY")


# ------------------- Baseline -------------------

def test_health():
    r = requests.get(f"{BASE_URL}/api/", timeout=15)
    assert r.status_code == 200
    d = r.json()
    assert d["status"] == "ready" and "server_time" in d


# ------------------- Team login -------------------

@pytest.mark.parametrize("tid,pin", [("LP-01", "0001"), ("LP-02", "0002"), ("LP-07", "0007")])
def test_team_login_ok(tid, pin):
    r = team_login(tid, pin)
    assert r.status_code == 200
    assert r.json()["session_token"].startswith(tid + ".")

def test_team_login_wrong_pin():
    r = team_login("LP-01", "9999")
    assert r.status_code == 401


# ------------------- Event state gate -------------------

def test_event_state_gate(admin_token):
    tok = team_login("LP-01", "0001").json()["session_token"]
    st = get_state(tok)
    current = st.get("current")
    if not current:
        pytest.skip("LP-01 has no active node")
    code = current["code"]

    # STANDBY -> reject
    set_event(admin_token, "STANDBY")
    r = requests.post(f"{BASE_URL}/api/team/answer",
                      json={"session_token": tok, "checkpoint_code": code, "answer": "x"}, timeout=15)
    assert r.status_code == 423

    # LIVE -> pass gate (may return valid:false but not 423)
    set_event(admin_token, "LIVE")
    r = requests.post(f"{BASE_URL}/api/team/answer",
                      json={"session_token": tok, "checkpoint_code": code, "answer": "bad-guess-zzz"}, timeout=15)
    assert r.status_code != 423

    # PAUSED -> reject
    set_event(admin_token, "PAUSED")
    r = requests.post(f"{BASE_URL}/api/team/answer",
                      json={"session_token": tok, "checkpoint_code": code, "answer": "x"}, timeout=15)
    assert r.status_code == 423

    # ENDED -> reject
    set_event(admin_token, "ENDED")
    r = requests.post(f"{BASE_URL}/api/team/answer",
                      json={"session_token": tok, "checkpoint_code": code, "answer": "x"}, timeout=15)
    assert r.status_code == 423

    # restore LIVE
    set_event(admin_token, "LIVE")


# ------------------- State safety: no hash leak -------------------

def test_state_no_answer_hash_leak():
    tok = team_login("LP-01", "0001").json()["session_token"]
    r = requests.get(f"{BASE_URL}/api/team/state",
                     params={"session_token": tok}, timeout=15)
    assert r.status_code == 200
    raw = r.text.lower()
    assert "answer_hash" not in raw, "answer_hash leaked in /api/team/state"
    assert "pin_hash" not in raw, "pin_hash leaked in /api/team/state"
    # Ensure no bcrypt-looking hashes ($2b$)
    assert "$2b$" not in raw and "$2a$" not in raw

def test_state_missing_session():
    r = requests.get(f"{BASE_URL}/api/team/state", timeout=15)
    # FastAPI missing query param -> 422; still not 200
    assert r.status_code in (401, 422)

def test_state_invalid_session():
    r = requests.get(f"{BASE_URL}/api/team/state",
                     params={"session_token": "LP-01.badsig"}, timeout=15)
    assert r.status_code == 401


# ------------------- Helper: find a team currently at code -------------------

def _team_at(code, teams=None):
    teams = teams or [(f"LP-{i:02d}", f"{i:04d}") for i in range(1, 13)]
    for tid, pin in teams:
        r = team_login(tid, pin)
        if r.status_code != 200: continue
        tok = r.json()["session_token"]
        st = get_state(tok)
        cur = st.get("current") or {}
        if cur.get("code") == code:
            return tid, tok, st
    return None


# ------------------- Checkpoint A: cipher -------------------

def test_checkpoint_A_cipher(admin_token):
    found = _team_at("A")
    if not found:
        pytest.skip("No team at A")
    tid, tok, st = found
    # Wrong answer
    r = requests.post(f"{BASE_URL}/api/team/answer",
                      json={"session_token": tok, "checkpoint_code": "A", "answer": "zz"}, timeout=15)
    assert r.status_code == 200 and r.json()["valid"] is False
    # Correct (case-insensitive)
    r = requests.post(f"{BASE_URL}/api/team/answer",
                      json={"session_token": tok, "checkpoint_code": "A", "answer": "A7"}, timeout=15)
    assert r.status_code == 200 and r.json()["valid"] is True
    # Second submission on completed A -> 403
    r2 = requests.post(f"{BASE_URL}/api/team/answer",
                      json={"session_token": tok, "checkpoint_code": "A", "answer": "a7"}, timeout=15)
    assert r2.status_code == 403
    # Fragment '7' awarded
    st2 = get_state(tok)
    frag_vals = [f["value"] for f in st2["fragments"]]
    assert "7" in frag_vals


# ------------------- Checkpoint B: answer -------------------

def test_checkpoint_B_answer():
    found = _team_at("B")
    if not found:
        pytest.skip("No team at B")
    tid, tok, st = found
    # Try submitting for A (not active for this team) -> 403 (unless A is done and B active, still A completed)
    # Actually A on this team is likely already 'completed', so answer to A -> 403 'not on active route'
    r = requests.post(f"{BASE_URL}/api/team/answer",
                      json={"session_token": tok, "checkpoint_code": "A", "answer": "a7"}, timeout=15)
    assert r.status_code == 403
    # Correct B
    r = requests.post(f"{BASE_URL}/api/team/answer",
                      json={"session_token": tok, "checkpoint_code": "B", "answer": "42"}, timeout=15)
    assert r.status_code == 200 and r.json()["valid"] is True


# ------------------- Checkpoint C: volunteer_verify -------------------

def test_checkpoint_C_volunteer(admin_token):
    found = _team_at("C")
    if not found:
        pytest.skip("No team at C")
    tid, tok, st = found
    # Text answer must be rejected 400
    r = requests.post(f"{BASE_URL}/api/team/answer",
                      json={"session_token": tok, "checkpoint_code": "C", "answer": "anything"}, timeout=15)
    assert r.status_code == 400
    # Admin FAIL -> penalty applied
    penalty_before = st["current"].get("penalty", 0)
    r = requests.post(f"{BASE_URL}/api/control/verify-team",
                      json={"access_token": admin_token, "team_id": tid, "checkpoint_code": "C", "result": "FAIL"}, timeout=15)
    assert r.status_code == 200
    st2 = get_state(tok)
    pen2 = st2["current"].get("penalty", 0)
    assert pen2 <= penalty_before - 20, f"expected -20 penalty; before={penalty_before} after={pen2}"
    # Admin PASS -> completes
    r = requests.post(f"{BASE_URL}/api/control/verify-team",
                      json={"access_token": admin_token, "team_id": tid, "checkpoint_code": "C", "result": "PASS"}, timeout=15)
    assert r.status_code == 200
    st3 = get_state(tok)
    # C should not be current anymore
    if st3.get("current"):
        assert st3["current"]["code"] != "C"
    # Fragment '△' awarded
    assert any(f["value"] == "△" for f in st3["fragments"])


# ------------------- Checkpoint D: qr_answer -------------------

def test_checkpoint_D_qr():
    found = _team_at("D")
    if not found:
        pytest.skip("No team at D")
    tid, tok, st = found
    # Answer before scan -> 409
    r = requests.post(f"{BASE_URL}/api/team/answer",
                      json={"session_token": tok, "checkpoint_code": "D", "answer": "north"}, timeout=15)
    assert r.status_code == 409
    # Wrong token
    r = requests.post(f"{BASE_URL}/api/team/scan-node",
                      json={"session_token": tok, "checkpoint_code": "D", "node_token": "LP-NODE-WRONG-XXX"}, timeout=15)
    assert r.status_code == 403
    # Correct token
    r = requests.post(f"{BASE_URL}/api/team/scan-node",
                      json={"session_token": tok, "checkpoint_code": "D", "node_token": "LP-NODE-D-9F2A"}, timeout=15)
    assert r.status_code == 200 and r.json()["scanned"] is True
    # Now answer 'north'
    r = requests.post(f"{BASE_URL}/api/team/answer",
                      json={"session_token": tok, "checkpoint_code": "D", "answer": "north"}, timeout=15)
    assert r.status_code == 200 and r.json()["valid"] is True


# ------------------- Checkpoint E: keeper -------------------

def test_checkpoint_E_keeper_authz(admin_token, volunteer_token):
    found = _team_at("E")
    if not found:
        pytest.skip("No team at E")
    tid, tok, st = found
    # volunteer1 is assigned to C only -> 403 at E
    r = requests.post(f"{BASE_URL}/api/control/verify-team",
                      json={"access_token": volunteer_token, "team_id": tid, "checkpoint_code": "E", "result": "PASS"}, timeout=15)
    assert r.status_code == 403
    # Admin PASS
    r = requests.post(f"{BASE_URL}/api/control/verify-team",
                      json={"access_token": admin_token, "team_id": tid, "checkpoint_code": "E", "result": "PASS"}, timeout=15)
    assert r.status_code == 200


# ------------------- Checkpoint F: risk_choice -------------------

def test_checkpoint_F_safe():
    found = _team_at("F")
    if not found:
        pytest.skip("No team at F for SAFE test")
    tid, tok, st = found
    # Answer before choice -> 409
    r = requests.post(f"{BASE_URL}/api/team/answer",
                      json={"session_token": tok, "checkpoint_code": "F", "answer": "orion"}, timeout=15)
    assert r.status_code == 409
    # Choose SAFE
    r = requests.post(f"{BASE_URL}/api/team/choice",
                      json={"session_token": tok, "checkpoint_code": "F", "choice": "safe"}, timeout=15)
    assert r.status_code == 200 and r.json()["locked"] is True
    # Second choice with risk -> locked, choice unchanged
    r = requests.post(f"{BASE_URL}/api/team/choice",
                      json={"session_token": tok, "checkpoint_code": "F", "choice": "risk"}, timeout=15)
    assert r.status_code == 200 and r.json()["locked"] is True and r.json()["choice"] == "safe"
    # SAFE answer
    r = requests.post(f"{BASE_URL}/api/team/answer",
                      json={"session_token": tok, "checkpoint_code": "F", "answer": "orion"}, timeout=15)
    assert r.status_code == 200 and r.json()["valid"] is True


def test_checkpoint_F_risk_penalty_then_correct():
    found = _team_at("F")
    if not found:
        pytest.skip("No team at F for RISK test")
    tid, tok, st = found
    # Choose RISK
    r = requests.post(f"{BASE_URL}/api/team/choice",
                      json={"session_token": tok, "checkpoint_code": "F", "choice": "risk"}, timeout=15)
    if r.json().get("choice") != "risk":
        pytest.skip("Choice already locked to safe on this team")
    pen_before = get_state(tok)["current"].get("penalty", 0)
    # Wrong risk answer -> -40 penalty
    r = requests.post(f"{BASE_URL}/api/team/answer",
                      json={"session_token": tok, "checkpoint_code": "F", "answer": "wrongstar"}, timeout=15)
    assert r.status_code == 200 and r.json()["valid"] is False
    pen_after = get_state(tok)["current"].get("penalty", 0)
    assert pen_after <= pen_before - 40
    # Correct risk answer
    r = requests.post(f"{BASE_URL}/api/team/answer",
                      json={"session_token": tok, "checkpoint_code": "F", "answer": "mintaka"}, timeout=15)
    assert r.status_code == 200 and r.json()["valid"] is True


# ------------------- Checkpoint G: grid_memory -------------------

def test_checkpoint_G_grid(admin_token):
    found = _team_at("G")
    if not found:
        pytest.skip("No team at G")
    tid, tok, st = found
    # Text answer rejected
    r = requests.post(f"{BASE_URL}/api/team/answer",
                      json={"session_token": tok, "checkpoint_code": "G", "answer": "9"}, timeout=15)
    assert r.status_code == 400
    # DISPLAY -> grid_visible True
    r = requests.post(f"{BASE_URL}/api/control/grid",
                      json={"access_token": admin_token, "team_id": tid, "checkpoint_code": "G", "action": "DISPLAY"}, timeout=15)
    assert r.status_code == 200 and r.json()["grid_visible"] is True
    st1 = get_state(tok)
    assert st1["current"].get("grid_visible") is True
    assert st1["current"].get("grid")  # present when visible
    # HIDE -> False
    r = requests.post(f"{BASE_URL}/api/control/grid",
                      json={"access_token": admin_token, "team_id": tid, "checkpoint_code": "G", "action": "HIDE"}, timeout=15)
    assert r.status_code == 200 and r.json()["grid_visible"] is False
    st2 = get_state(tok)
    assert st2["current"].get("grid_visible") is False
    assert not st2["current"].get("grid")  # grid absent when hidden
    # FAIL -> -20 penalty
    pen_before = st2["current"].get("penalty", 0)
    r = requests.post(f"{BASE_URL}/api/control/verify-team",
                      json={"access_token": admin_token, "team_id": tid, "checkpoint_code": "G", "result": "FAIL"}, timeout=15)
    assert r.status_code == 200
    pen_after = get_state(tok)["current"].get("penalty", 0)
    assert pen_after <= pen_before - 20
    # PASS
    r = requests.post(f"{BASE_URL}/api/control/verify-team",
                      json={"access_token": admin_token, "team_id": tid, "checkpoint_code": "G", "result": "PASS"}, timeout=15)
    assert r.status_code == 200


# ------------------- Hint dedupe -------------------

def test_hint_dedupe():
    # Find any team with an active checkpoint
    tok = None; code = None
    for i in range(1, 13):
        r = team_login(f"LP-{i:02d}", f"{i:04d}")
        if r.status_code != 200: continue
        t = r.json()["session_token"]
        st = get_state(t)
        cur = st.get("current")
        if cur:
            tok = t; code = cur["code"]; break
    if not tok:
        pytest.skip("No team with active checkpoint")
    # First call idx=0
    r1 = requests.post(f"{BASE_URL}/api/team/hint",
                       json={"session_token": tok, "checkpoint_code": code, "hint_index": 0}, timeout=15).json()
    # Second call idx=0 - must not charge again
    r2 = requests.post(f"{BASE_URL}/api/team/hint",
                       json={"session_token": tok, "checkpoint_code": code, "hint_index": 0}, timeout=15).json()
    assert r2["charged"] is False, f"Second hint charged again: {r2}"
    # hint_index=1 - charges independently
    r3 = requests.post(f"{BASE_URL}/api/team/hint",
                       json={"session_token": tok, "checkpoint_code": code, "hint_index": 1}, timeout=15).json()
    # r3 may or may not be first time depending on state; not strict-assert but log
    assert "charged" in r3


# ------------------- Final gate -------------------

def test_final_gate_locked_incomplete():
    # Find a team not yet completed all 7
    for i in range(1, 13):
        r = team_login(f"LP-{i:02d}", f"{i:04d}")
        if r.status_code != 200: continue
        tok = r.json()["session_token"]
        st = get_state(tok)
        if st["completed"] < 7:
            resp = requests.post(f"{BASE_URL}/api/team/final",
                                 json={"session_token": tok, "answer": "protocol"}, timeout=15)
            assert resp.status_code == 423
            body = resp.json()
            assert "detail" in body and "/7" in body["detail"]
            return
    pytest.skip("All teams completed")


# ------------------- Offline token flow -------------------

def test_offline_token_double_redeem(admin_token):
    # Pick any team with a valid non-volunteer active node (A or B or D via manual scan?), fallback any active
    for i in range(1, 13):
        r = team_login(f"LP-{i:02d}", f"{i:04d}")
        if r.status_code != 200: continue
        tok = r.json()["session_token"]
        st = get_state(tok)
        cur = st.get("current")
        if not cur: continue
        code = cur["code"]
        # Issue token
        issue = requests.post(f"{BASE_URL}/api/control/offline-token",
                              json={"access_token": admin_token, "team_id": f"LP-{i:02d}", "checkpoint_code": code}, timeout=15)
        if issue.status_code != 200:
            continue
        tk = issue.json()["token"]
        # Redeem #1
        r1 = requests.post(f"{BASE_URL}/api/team/redeem-token",
                           json={"session_token": tok, "token": tk, "checkpoint_code": code}, timeout=15)
        assert r1.status_code == 200 and r1.json()["valid"] is True
        # Redeem #2 must block
        r2 = requests.post(f"{BASE_URL}/api/team/redeem-token",
                           json={"session_token": tok, "token": tk, "checkpoint_code": code}, timeout=15)
        assert r2.status_code in (403, 409)
        return
    pytest.skip("No suitable team for offline token flow")


# ------------------- RLS via anon -------------------

@pytest.mark.parametrize("table", ["teams", "hints", "fragments", "team_routes", "offline_tokens"])
def test_rls_anon_denied(table):
    r = requests.get(f"{SUPABASE_URL}/rest/v1/{table}",
                     headers={"apikey": ANON_KEY, "Authorization": f"Bearer {ANON_KEY}"},
                     params={"select": "*", "limit": "5"}, timeout=15)
    # RLS should return empty or error - not real data
    if r.status_code >= 400:
        return  # blocked by RLS
    data = r.json()
    assert data == [] or (isinstance(data, dict) and "error" in data), f"RLS breach on {table}: got {str(data)[:200]}"


# ------------------- Cleanup TEST- team -------------------

def test_cleanup_test_prefix(admin_token):
    tid = f"TEST-{uuid.uuid4().hex[:6].upper()}"
    c = requests.post(f"{BASE_URL}/api/admin/teams",
                      json={"access_token": admin_token,
                            "payload": {"team_id": tid, "team_name": "TEST_Cleanup",
                                        "status": "active", "pin": "9911"}}, timeout=15)
    assert c.status_code == 200, c.text
    # cleanup
    r = requests.post(f"{BASE_URL}/api/admin/cleanup-test",
                      json={"access_token": admin_token, "prefix": "TEST-"}, timeout=15)
    assert r.status_code == 200 and tid in r.json()["removed"]
    # Ensure LP-01..LP-12 intact
    remain = requests.get(f"{BASE_URL}/api/admin/teams",
                          params={"access_token": admin_token}, timeout=15).json()
    lp_ids = {t["team_id"] for t in remain if t["team_id"].startswith("LP-")}
    assert len(lp_ids) >= 12
