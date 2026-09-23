from fastapi import FastAPI, APIRouter, HTTPException, Header
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv
from pydantic import BaseModel, Field
from pathlib import Path
from datetime import datetime, timezone
import os, requests, bcrypt, secrets, hashlib, hmac, random
import random

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / ".env")
SUPABASE_URL = os.environ["SUPABASE_URL"].rstrip("/")
SERVICE_KEY = os.environ["SUPABASE_SERVICE_ROLE_KEY"]
app = FastAPI(title="The Lost Protocol Mission Control")
api = APIRouter(prefix="/api")

# ------------------------- Schemas -------------------------

class TeamLogin(BaseModel):
    team_id: str = Field(min_length=3, max_length=20)
    pin: str = Field(min_length=4, max_length=12)

class TeamAction(BaseModel):
    session_token: str
    checkpoint_code: str
    answer: str = ""

class HintRequest(BaseModel):
    session_token: str
    checkpoint_code: str
    hint_index: int = 0  # 0 = first available (highest penalty i.e. cheapest reveal), 1 = second

class FinalSubmission(BaseModel):
    session_token: str
    answer: str

class ScanNode(BaseModel):
    session_token: str
    checkpoint_code: str
    node_token: str

class RiskChoice(BaseModel):
    session_token: str
    checkpoint_code: str
    choice: str  # 'safe' or 'risk'

class EventAction(BaseModel):
    state: str
    access_token: str

class VolunteerAction(BaseModel):
    access_token: str
    action: str
    team_id: str
    checkpoint_code: str

class VerifyTeam(BaseModel):
    access_token: str
    team_id: str
    checkpoint_code: str
    result: str  # 'START', 'PASS', 'FAIL'

class GridControl(BaseModel):
    access_token: str
    team_id: str
    checkpoint_code: str
    action: str  # 'START', 'DISPLAY', 'HIDE'
class ClassroomAnswers(BaseModel):
    session_token: str
    checkpoint_code: str
    answers: list[str]

CLASSROOM_G_QUESTIONS = [
    {"id": "g1", "question": "What number appeared alone?", "answer": "47"},
    {"id": "g2", "question": "What time was displayed?", "answer": "06:07"},
    {"id": "g3", "question": "Which word was upside down?", "answer": "protocol"},
    {"id": "g4", "question": "How many cups were stacked?", "answer": "3"},
    {"id": "g5", "question": "What three-character sequence appeared?", "answer": "7-k-3"},
    {"id": "g6", "question": "Which word appeared by itself?", "answer": "echo"},
    {"id": "g7", "question": "Which letter appeared alone?", "answer": "k"},
    {"id": "g8", "question": "Which two geometric symbols were present?", "answer": "triangle diamond"},
    {"id": "g9", "question": "What colour was the folder?", "answer": "red"},
    {"id": "g10", "question": "Which letter was placed near the door?", "answer": "r"},
    {"id": "g11", "question": "Which single digit appeared separately?", "answer": "9"},
    {"id": "g12", "question": "What object appeared in a stack?", "answer": "cups"},
]

def select_classroom_questions(count=4):
    selected = random.sample(
        CLASSROOM_G_QUESTIONS,
        min(count, len(CLASSROOM_G_QUESTIONS))
    )

    return [
        {
            "id": item["id"],
            "question": item["question"]
        }
        for item in selected
    ]

def normalize_classroom_answer(value):
    value = value.strip().lower()

    replacements = {
        "△": "triangle",
        "♢": "diamond",
        "◇": "diamond",
    }

    for symbol, word in replacements.items():
        value = value.replace(symbol, word)

    value = value.replace("-", "")
    value = value.replace(":", "")
    value = value.replace(" ", "")
    value = value.replace(",", "")
    value = value.replace("and", "")

    return value


def check_classroom_answer(question_id, submitted):
    question = next(
        (item for item in CLASSROOM_G_QUESTIONS if item["id"] == question_id),
        None
    )

    if not question:
        return False

    expected = normalize_classroom_answer(question["answer"])
    received = normalize_classroom_answer(submitted)

    return received == expected   

class SeedRequest(BaseModel):
    access_token: str

class ResourceRequest(BaseModel):
    access_token: str
    payload: dict

class TokenRequest(BaseModel):
    access_token: str
    team_id: str
    checkpoint_code: str

class RedeemToken(BaseModel):
    session_token: str
    token: str
    checkpoint_code: str

class OperatorSeed(BaseModel):
    access_token: str
    email: str
    password: str
    role: str = "volunteer"
    display_name: str = ""
    checkpoint_code: str | None = None

class DevOperatorSeed(BaseModel):
    email: str
    password: str
    role: str = "admin"
    display_name: str = "Operator"
    checkpoint_code: str | None = None
    setup_key: str

class AnnouncementBroadcast(BaseModel):
    access_token: str
    message: str

class CleanupRequest(BaseModel):
    access_token: str
    prefix: str = "TEST-"

# ------------------------- Supabase helpers -------------------------

def _headers(json_body=False, prefer=None):
    h = {"apikey": SERVICE_KEY, "Authorization": f"Bearer {SERVICE_KEY}"}
    if json_body:
        h["Content-Type"] = "application/json"
    if prefer:
        h["Prefer"] = prefer
    return h


def sb_get(table, params):
    r = requests.get(f"{SUPABASE_URL}/rest/v1/{table}", headers=_headers(), params=params, timeout=12)
    if r.status_code >= 400:
        raise HTTPException(503, f"DB unavailable: {r.text[:180]}")
    return r.json()


def sb_post(table, payload):
    r = requests.post(f"{SUPABASE_URL}/rest/v1/{table}", headers=_headers(True, "return=minimal"), json=payload, timeout=12)
    if r.status_code >= 400:
        # Ignore duplicate-key on hint_usage etc. — surfacing as caller's responsibility
        return


def sb_post_return(table, payload, prefer="return=representation"):
    r = requests.post(f"{SUPABASE_URL}/rest/v1/{table}", headers=_headers(True, prefer), json=payload, timeout=12)
    if r.status_code >= 400:
        raise HTTPException(503, f"DB unavailable: {r.text[:180]}")
    if not r.text:
        return []
    try:
        return r.json()
    except ValueError:
        return []


def sb_upsert(table, payload, on_conflict=None, prefer="resolution=merge-duplicates,return=representation"):
    params = {"on_conflict": on_conflict} if on_conflict else {}
    r = requests.post(f"{SUPABASE_URL}/rest/v1/{table}", headers=_headers(True, prefer), params=params, json=payload, timeout=12)
    if r.status_code >= 400:
        raise HTTPException(503, f"DB unavailable: {r.text[:180]}")
    if not r.text:
        return []
    try:
        return r.json()
    except ValueError:
        return []


def sb_patch(table, params, payload):
    r = requests.patch(f"{SUPABASE_URL}/rest/v1/{table}", headers=_headers(True, "return=minimal"), params=params, json=payload, timeout=12)
    if r.status_code >= 400:
        raise HTTPException(503, f"DB unavailable: {r.text[:180]}")


def sb_patch_return(table, params, payload):
    r = requests.patch(f"{SUPABASE_URL}/rest/v1/{table}", headers=_headers(True, "return=representation"), params=params, json=payload, timeout=12)
    if r.status_code >= 400:
        raise HTTPException(503, f"DB unavailable: {r.text[:180]}")
    return r.json()


def sb_delete(table, params):
    r = requests.delete(f"{SUPABASE_URL}/rest/v1/{table}", headers=_headers(), params=params, timeout=12)
    if r.status_code >= 400:
        text = r.text[:200] if r.text else ""
        if "foreign key" in text.lower() or "violates" in text.lower():
            raise HTTPException(409, "Cannot delete — this record is referenced by other data (audit logs, progress, etc.)")
        raise HTTPException(503, f"Delete rejected: {text}")

# ------------------------- Auth helpers -------------------------

def sign_team(team_id):
    return f"{team_id.upper()}.{hmac.new(SERVICE_KEY.encode(), team_id.upper().encode(), hashlib.sha256).hexdigest()}"


def verify_team_token(token):
    try:
        team_id, signature = token.split(".", 1)
    except ValueError:
        raise HTTPException(401, "Invalid team session")
    expected = hmac.new(SERVICE_KEY.encode(), team_id.encode(), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(signature, expected):
        raise HTTPException(401, "Invalid team session")
    return team_id

def verify_operator(access_token):
    r = requests.get(
        f"{SUPABASE_URL}/auth/v1/user",
        headers={
            "apikey": SERVICE_KEY,
            "Authorization": f"Bearer {access_token}",
        },
        timeout=12,
    )

    if r.status_code >= 400:
        print("SUPABASE AUTH ERROR:", r.status_code, r.text)
        raise HTTPException(401, "Operator session expired")

    return r.json()

def require_role(access_token, roles):
    user = verify_operator(access_token)
    metadata = {**user.get("app_metadata", {}), **user.get("user_metadata", {})}
    role = metadata.get("role", "")
    if role not in roles:
        raise HTTPException(403, "This operator role cannot perform that action")
    return {**user, "_role": role}


def volunteer_assigned_to(user, checkpoint_id):
    """Admins bypass; volunteers must be assigned to this checkpoint."""
    if user.get("_role") in {"admin", "super_admin", "event_control"}:
        return True
    rows = sb_get("volunteer_assignments", {"volunteer_id": f"eq.{user['id']}", "checkpoint_id": f"eq.{checkpoint_id}", "select": "checkpoint_id", "limit": "1"})
    if not rows:
        # Fallback: check volunteers.checkpoint_id
        vol = sb_get("volunteers", {"id": f"eq.{user['id']}", "select": "checkpoint_id", "limit": "1"})
        if vol and vol[0].get("checkpoint_id") == checkpoint_id:
            return True
        return False
    return True


def upsert_auth_user(email, password, role, display_name):
    listing = requests.get(f"{SUPABASE_URL}/auth/v1/admin/users", headers=_headers(), params={"per_page": 200}, timeout=12).json()
    users = listing.get("users") if isinstance(listing, dict) else listing
    existing = next((u for u in (users or []) if u.get("email", "").lower() == email.lower()), None)
    body = {"email": email, "password": password, "email_confirm": True,
            "app_metadata": {"role": role}, "user_metadata": {"role": role, "display_name": display_name}}
    if existing:
        r = requests.put(f"{SUPABASE_URL}/auth/v1/admin/users/{existing['id']}", headers=_headers(True), json=body, timeout=12)
    else:
        r = requests.post(f"{SUPABASE_URL}/auth/v1/admin/users", headers=_headers(True), json=body, timeout=12)
    if r.status_code >= 400:
        raise HTTPException(400, f"Auth API rejected: {r.text[:200]}")
    payload = r.json()
    return payload.get("id") or payload.get("user", {}).get("id") or (existing and existing["id"])


def attach_volunteer(user_id, display_name, checkpoint_code):
    checkpoint_id = None
    if checkpoint_code:
        cps = sb_get("checkpoints", {"code": f"eq.{checkpoint_code.upper()}", "select": "id", "limit": "1"})
        checkpoint_id = cps[0]["id"] if cps else None
    requests.post(f"{SUPABASE_URL}/rest/v1/volunteers", headers=_headers(True, "resolution=merge-duplicates,return=minimal"),
                  json={"id": user_id, "checkpoint_id": checkpoint_id, "display_name": display_name, "role": "volunteer"}, timeout=12)
    if checkpoint_id:
        requests.post(f"{SUPABASE_URL}/rest/v1/volunteer_assignments", headers=_headers(True, "resolution=merge-duplicates"),
                      json={"volunteer_id": user_id, "checkpoint_id": checkpoint_id}, timeout=12)

# ------------------------- Event state gate -------------------------

def get_event_state():
    rows = sb_get("events", {"select": "state", "order": "created_at.desc", "limit": "1"})
    return rows[0]["state"] if rows else "STANDBY"


def require_live_event():
    state = get_event_state()
    if state == "LIVE":
        return state
    if state == "PAUSED":
        raise HTTPException(423, "Event is PAUSED. Submissions are locked.")
    if state == "ENDED":
        raise HTTPException(423, "Event has ENDED. Submissions are closed.")
    raise HTTPException(423, f"Event is {state}. Mission is not LIVE yet.")

# ------------------------- Progress helpers -------------------------

def get_team(team_id):
    rows = sb_get("teams", {"team_id": f"eq.{team_id}", "select": "id,team_id,team_name,status", "limit": "1"})
    if not rows:
        raise HTTPException(404, "Team not found")
    return rows[0]


def get_checkpoint(code):
    rows = sb_get("checkpoints", {"code": f"eq.{code.upper()}", "select": "*", "limit": "1"})
    if not rows:
        raise HTTPException(404, "Mission node unavailable")
    return rows[0]


def get_active_progress(team_id, checkpoint_id):
    rows = sb_get("team_progress", {"team_id": f"eq.{team_id}", "checkpoint_id": f"eq.{checkpoint_id}", "status": "eq.active", "select": "id,route_position,attempts,penalty,metadata,volunteer_state,score", "limit": "1"})
    return rows[0] if rows else None


def complete_progress(progress_row, team_id, checkpoint, points_override=None):
    """Mark completed, award points/fragment, activate next node. Idempotent guard: only if still active."""
    now = datetime.now(timezone.utc).isoformat()

    sb_patch(
        "team_progress",
        {"id": f"eq.{progress_row['id']}", "status": "eq.active"},
        {
            "status": "completed",
            "score": points_override if points_override is not None else checkpoint["points"],
            "completed_at": now,
            "volunteer_state": "passed"
        }
    )

    # Award fragment (idempotent)
    frag_rows = sb_get(
        "fragments",
        {
            "checkpoint_id": f"eq.{checkpoint['id']}",
            "select": "id",
            "limit": "1"
        }
    )

    if frag_rows:
        sb_upsert(
            "team_fragments",
            {"team_id": team_id, "fragment_id": frag_rows[0]["id"]},
            on_conflict="team_id,fragment_id",
            prefer="resolution=ignore-duplicates,return=minimal"
        )

    # Advance route
    next_pos = progress_row["route_position"] + 1

    next_row = sb_get(
        "team_progress",
        {
            "team_id": f"eq.{team_id}",
            "route_position": f"eq.{next_pos}",
            "select": "id",
            "limit": "1"
        }
    )

    if next_row:
        sb_patch(
            "team_progress",
            {"id": f"eq.{next_row[0]['id']}"},
            {"status": "active"}
        )
def apply_penalty(progress_row, penalty_delta, note):
    """Increment attempts and apply penalty. Never negative below configured floor."""
    new_penalty = progress_row.get("penalty", 0) + penalty_delta
    sb_patch("team_progress", {"id": f"eq.{progress_row['id']}"},
             {"attempts": progress_row.get("attempts", 0) + 1, "penalty": new_penalty, "volunteer_state": note})


def public_checkpoint_config(cp, team_metadata):
    """Return the subset of config safe to expose to the team (never answers/hashes)."""
    m = cp.get("mechanic", "answer")
    cfg = cp.get("config") or {}
    public = {"mechanic": m}
    if m == "cipher":
        public["cipher_display"] = cp.get("cipher_display")
        public["cipher_hint"] = cfg.get("cipher_hint")
    elif m == "qr_answer":
        public["images"] = cfg.get("images", [])
        public["asset_urls"] = cp.get("asset_urls") or []
        public["node_scanned"] = bool(team_metadata.get("node_scanned"))
        public["post_scan_clue"] = cfg.get("post_scan_clue")
    elif m == "risk_choice":
        choice = team_metadata.get("choice")
        public["choice"] = choice
        public["timer_seconds"] = cfg.get("timer_seconds", 60)
        public["safe_points"] = cfg.get("safe", {}).get("points", 100)
        public["risk_points"] = cfg.get("risk", {}).get("points", 180)
        public["risk_penalty"] = cfg.get("risk", {}).get("penalty", -40)
        if choice == "safe":
            public["path_clue"] = cfg.get("safe", {}).get("clue")
        elif choice == "risk":
            public["path_clue"] = cfg.get("risk", {}).get("clue")
    elif m == "keeper":
        public["symbol"] = cfg.get("symbol", "♜")
        public["phrase"] = cfg.get("phrase", "Did the protocol survive?")
    elif m == "classroom_memory":
        public["observation_seconds"] = cfg.get("observation_seconds", 30)
        public["answer_seconds"] = cfg.get("answer_seconds", 45)
        public["questions_per_attempt"] = cfg.get("questions_per_attempt", 4)
        public["threshold"] = cfg.get("threshold", 3)
        public["room_started"] = bool(team_metadata.get("room_started"))
        public["questions_unlocked"] = bool(team_metadata.get("questions_unlocked"))

        if team_metadata.get("questions_unlocked"):
            public["classroom_questions"] = team_metadata.get("classroom_questions", [])
    elif m == "volunteer_verify":
        public["retry_penalty"] = cfg.get("retry_penalty", -20)
    return public


def verify_answer(cp, mechanic, choice, submitted):
    """Return True if answer valid based on mechanic. Never leaks the hash."""
    submitted_clean = submitted.strip().lower().encode()
    if mechanic == "risk_choice":
        cfg = cp.get("config") or {}
        target = (cfg.get(choice) or {}).get("answer_hash", "")
        return bool(target and bcrypt.checkpw(submitted_clean, target.encode()))
    ah = cp.get("answer_hash") or ""
    return bool(ah and bcrypt.checkpw(submitted_clean, ah.encode()))

# ------------------------- Public endpoints -------------------------

@api.get("/")
async def health():
    return {"service": "the-lost-protocol", "status": "ready", "server_time": datetime.now(timezone.utc).isoformat()}


@api.get("/event")
async def event_endpoint():
    rows = sb_get("events", {"select": "id,name,state,starts_at,ends_at", "order": "created_at.desc", "limit": "1"})
    return rows[0] if rows else {"state": "STANDBY", "name": "THE LOST PROTOCOL"}


@api.get("/event/announcements")
async def announcements():
    return sb_get("announcements", {"active": "eq.true", "select": "id,message,created_at", "order": "created_at.desc", "limit": "5"})

# ------------------------- Team endpoints -------------------------

@api.post("/team/login")
async def team_login(payload: TeamLogin):
    team_id = payload.team_id.strip().upper()
    rows = sb_get("teams", {"team_id": f"eq.{team_id}", "select": "id,team_id,team_name,pin_hash,status", "limit": "1"})
    if not rows or rows[0].get("status") == "disabled":
        raise HTTPException(401, "Team ID or PIN rejected")
    team = rows[0]
    stored = team.get("pin_hash", "")
    if not stored or not bcrypt.checkpw(payload.pin.encode(), stored.encode()):
        raise HTTPException(401, "Team ID or PIN rejected")
    sb_post("audit_logs", {"action": "login", "actor_type": "team", "team_id": team["id"], "metadata": {"team_id": team_id}})
    return {"team_id": team["team_id"], "team_name": team["team_name"], "session_token": sign_team(team_id)}


@api.get("/team/state")
async def team_state(session_token: str):
    team_id = verify_team_token(session_token)
    team = get_team(team_id)
    progress = sb_get("team_progress", {"team_id": f"eq.{team['id']}", "select": "checkpoint_id,route_position,status,score,penalty,attempts,metadata,volunteer_state,completed_at", "order": "route_position.asc"})
    cps = sb_get("checkpoints", {"select": "id,code,name,clue,challenge,fragment,points,mechanic,config,cipher_display,asset_urls"})
    cps_by_id = {cp["id"]: cp for cp in cps}
    fragments = []
    completed_count = 0
    current = None
    ordered = []
    for row in progress:
        cp = cps_by_id.get(row["checkpoint_id"], {})
        ordered.append({"code": cp.get("code"), "name": cp.get("name"), "status": row["status"], "score": row.get("score", 0), "completed_at": row.get("completed_at")})
        if row["status"] == "completed":
            completed_count += 1
            fragments.append({"code": cp.get("code"), "value": cp.get("fragment")})
        if row["status"] == "active" and not current:
            meta = row.get("metadata") or {}
            current = {
                "code": cp.get("code"),
                "name": cp.get("name"),
                "clue": cp.get("clue"),
                "challenge": cp.get("challenge"),
                "points": cp.get("points"),
                "position": row["route_position"],
                "attempts": row.get("attempts", 0),
                "penalty": row.get("penalty", 0),
                "volunteer_state": row.get("volunteer_state", "idle"),
                "metadata": meta,
                **public_checkpoint_config(cp, meta),
            }
    total_score = sum((row.get("score") or 0) + (row.get("penalty") or 0) for row in progress)
    return {"team": team, "event_state": get_event_state(), "route": ordered, "current": current, "fragments": fragments, "completed": completed_count, "total": len(progress) or 7, "score": total_score, "ready_for_final": completed_count >= 7}

@api.post("/team/answer")
async def submit_answer(payload: TeamAction):
    require_live_event()
    team_id = verify_team_token(payload.session_token)
    team = get_team(team_id)
    cp = get_checkpoint(payload.checkpoint_code)
    progress = get_active_progress(team["id"], cp["id"])

    if not progress:
        raise HTTPException(403, "That node is not on your active route")

    mechanic = cp.get("mechanic", "answer")
    metadata = progress.get("metadata") or {}

    # Reject text answer for volunteer-only mechanics
    if mechanic in {"volunteer_verify", "keeper", "classroom_memory"}:
        raise HTTPException(
            400,
            "This checkpoint is verified by a volunteer, not by a submitted answer."
        )

    # QR gate for D
    if mechanic == "qr_answer" and not metadata.get("node_scanned"):
        raise HTTPException(
            409,
            "Scan the checkpoint node QR before submitting the verification."
        )

    # Risk choice: require choice first
    choice = metadata.get("choice")

    if mechanic == "risk_choice" and choice not in {"safe", "risk"}:
        raise HTTPException(
            409,
            "Choose SAFE or RISK before submitting."
        )

    valid = verify_answer(cp, mechanic, choice, payload.answer)

    sb_post(
        "audit_logs",
        {
            "action": "answer_attempt",
            "actor_type": "team",
            "team_id": team["id"],
            "metadata": {
                "checkpoint": cp["code"],
                "mechanic": mechanic,
                "valid": valid
            }
        }
    )

    if valid:
        points_override = None

        if mechanic == "risk_choice":
            points_override = (
                (cp.get("config") or {})
                .get(choice, {})
                .get("points", cp["points"])
            )

        complete_progress(
            progress,
            team["id"],
            cp,
            points_override=points_override
        )

        return {
            "valid": True,
            "message": "Node recovered",
            "code": cp["code"]
        }

    # RISK failure penalty — charged on every wrong RISK attempt
    if mechanic == "risk_choice" and choice == "risk":
        penalty = (
            (cp.get("config") or {})
            .get("risk", {})
            .get("penalty", -40)
        )
        apply_penalty(progress, penalty, "risk_failed")
    else:
        apply_penalty(progress, 0, "wrong")

    return {
        "valid": False,
        "message": "Signal rejected"
    }

@api.post("/team/classroom-answers")
async def submit_classroom_answers(payload: ClassroomAnswers):
    require_live_event()

    team_id = verify_team_token(payload.session_token)
    team = get_team(team_id)
    cp = get_checkpoint(payload.checkpoint_code)

    if cp.get("mechanic") != "classroom_memory":
        raise HTTPException(
            400,
            "This checkpoint is not a classroom memory challenge."
        )

    progress = get_active_progress(team["id"], cp["id"])

    if not progress:
        raise HTTPException(
            409,
            "This checkpoint is not currently active."
        )

    meta = progress.get("metadata") or {}

    if not meta.get("questions_unlocked"):
        raise HTTPException(
            409,
            "The classroom questions have not been unlocked yet."
        )

    questions = meta.get("classroom_questions") or []

    if not questions:
        raise HTTPException(
            409,
            "No classroom questions are available for this attempt."
        )

    if len(payload.answers) != len(questions):
        raise HTTPException(
            400,
            f"Exactly {len(questions)} answers are required."
        )

    correct = 0

    for question, submitted in zip(questions, payload.answers):
        if check_classroom_answer(
            question["id"],
            submitted
        ):
            correct += 1

    threshold = (cp.get("config") or {}).get("threshold", 3)
    passed = correct >= threshold

    # PASS — complete G and award fragment 9
    if passed:
        complete_progress(
            progress,
            team["id"],
            cp
        )

        sb_post(
            "audit_logs",
            {
                "action": "classroom_passed",
                "actor_type": "team",
                "team_id": team["id"],
                "metadata": {
                    "checkpoint": cp["code"],
                    "correct": correct,
                    "total": len(questions)
                }
            }
        )

        return {
            "correct": correct,
            "total": len(questions),
            "passed": True,
            "fragment": cp.get("fragment"),
            "message": "Final signal recovered."
        }

    # FAIL — apply retry penalty and reset G
    retry_penalty = (cp.get("config") or {}).get(
        "retry_penalty",
        -20
    )

    apply_penalty(
        progress,
        retry_penalty,
        "classroom_failed_attempt"
    )

    reset_meta = {
        **meta,
        "room_started": False,
        "questions_unlocked": False,
        "classroom_questions": [],
        "classroom_answers": None,
        "classroom_score": correct,
        "started_at": None,
        "questions_unlocked_at": None,
    }

    sb_patch(
        "team_progress",
        {"id": f"eq.{progress['id']}"},
        {
            "metadata": reset_meta,
            "volunteer_state": "waiting"
        }
    )

    sb_post(
        "audit_logs",
        {
            "action": "classroom_failed",
            "actor_type": "team",
            "team_id": team["id"],
            "metadata": {
                "checkpoint": cp["code"],
                "correct": correct,
                "total": len(questions),
                "penalty": retry_penalty
            }
        }
    )

    return {
        "correct": correct,
        "total": len(questions),
        "passed": False,
        "penalty": retry_penalty,
        "message": "Signal recovery failed. Retry required."
    }

@api.post("/team/scan-node")
async def scan_node(payload: ScanNode):
    require_live_event()
    team_id = verify_team_token(payload.session_token)
    team = get_team(team_id)
    cp = get_checkpoint(payload.checkpoint_code)
    if cp.get("mechanic") != "qr_answer":
        raise HTTPException(400, "This checkpoint does not use QR scanning.")
    progress = get_active_progress(team["id"], cp["id"])
    if not progress:
        raise HTTPException(403, "This checkpoint is not currently active for your team.")
    expected = (cp.get("config") or {}).get("node_token")
    if not expected or payload.node_token.strip() != expected:
        # Determine if the token matches ANY other checkpoint for a helpful error message
        others = sb_get("checkpoints", {"select": "code,config", "limit": "50"})
        matched = next((o["code"] for o in others if (o.get("config") or {}).get("node_token") == payload.node_token.strip()), None)
        sb_post("audit_logs", {"action": "qr_rejected", "actor_type": "team", "team_id": team["id"], "metadata": {"checkpoint": cp["code"], "matched": matched}})
        if matched:
            raise HTTPException(403, "INVALID NODE — This node is not part of your current mission.")
        raise HTTPException(403, "INVALID NODE — Unknown checkpoint code.")
    metadata = {**(progress.get("metadata") or {}), "node_scanned": True}
    sb_patch("team_progress", {"id": f"eq.{progress['id']}"}, {"metadata": metadata})
    sb_post("audit_logs", {"action": "qr_scanned", "actor_type": "team", "team_id": team["id"], "metadata": {"checkpoint": cp["code"]}})
    return {"scanned": True, "message": "Node recognized. Enter the verification to complete this checkpoint."}


@api.post("/team/choice")
async def team_choice(payload: RiskChoice):
    require_live_event()
    team_id = verify_team_token(payload.session_token)
    team = get_team(team_id)
    cp = get_checkpoint(payload.checkpoint_code)
    if cp.get("mechanic") != "risk_choice":
        raise HTTPException(400, "This checkpoint does not offer a choice.")
    progress = get_active_progress(team["id"], cp["id"])
    if not progress:
        raise HTTPException(403, "This checkpoint is not active for your team.")
    metadata = progress.get("metadata") or {}
    if metadata.get("choice"):
        return {"choice": metadata["choice"], "locked": True, "message": "Choice already locked."}
    choice = payload.choice.strip().lower()
    if choice not in {"safe", "risk"}:
        raise HTTPException(400, "Choice must be 'safe' or 'risk'.")
    new_meta = {**metadata, "choice": choice, "choice_at": datetime.now(timezone.utc).isoformat()}
    sb_patch("team_progress", {"id": f"eq.{progress['id']}"}, {"metadata": new_meta})
    sb_post("audit_logs", {"action": "risk_choice", "actor_type": "team", "team_id": team["id"], "metadata": {"checkpoint": cp["code"], "choice": choice}})
    return {"choice": choice, "locked": True}


@api.post("/team/hint")
async def request_hint(payload: HintRequest):
    require_live_event()
    team_id = verify_team_token(payload.session_token)
    team = get_team(team_id)
    cp = get_checkpoint(payload.checkpoint_code)
    hints = sb_get("hints", {"checkpoint_id": f"eq.{cp['id']}", "select": "id,name,content,penalty", "order": "penalty.desc"})
    if not hints:
        raise HTTPException(404, "No hints configured for this node.")
    idx = max(0, min(payload.hint_index, len(hints) - 1))
    hint = hints[idx]
    # Check if already charged
    already = sb_get("hint_usage", {"team_id": f"eq.{team['id']}", "hint_id": f"eq.{hint['id']}", "select": "id", "limit": "1"})
    charged = not already
    if charged:
        # Insert usage; unique index prevents duplicates in race
        try:
            sb_post_return("hint_usage", {"team_id": team["id"], "hint_id": hint["id"]}, prefer="return=minimal")
        except HTTPException:
            charged = False  # Duplicate slipped through — do not charge
        if charged:
            # Apply penalty to current active progress row
            progress = get_active_progress(team["id"], cp["id"])
            if progress:
                new_penalty = progress.get("penalty", 0) + hint["penalty"]
                sb_patch("team_progress", {"id": f"eq.{progress['id']}"}, {"penalty": new_penalty})
    sb_post("audit_logs", {"action": "hint_usage", "actor_type": "team", "team_id": team["id"], "metadata": {"checkpoint": cp["code"], "hint": hint["name"], "charged": charged}})
    return {"name": hint["name"], "content": hint["content"], "penalty": hint["penalty"], "charged": charged, "message": "Hint charged" if charged else "Hint already revealed — no additional penalty."}


@api.post("/team/final")
async def submit_final(payload: FinalSubmission):
    require_live_event()
    team_id = verify_team_token(payload.session_token)
    team = get_team(team_id)
    settings = sb_get("event_settings", {"key": "eq.final_answer_hash", "select": "value", "limit": "1"})
    completed = sb_get("team_progress", {"team_id": f"eq.{team['id']}", "status": "eq.completed", "select": "id"})
    final_hash = settings[0]["value"].get("hash", "") if settings else ""
    already = sb_get("final_attempts", {"team_id": f"eq.{team['id']}", "is_valid": "eq.true", "select": "id", "limit": "1"})
    if already:
        return {"valid": True, "message": "Final protocol already recorded", "already": True}
    if len(completed) < 7:
        sb_post("final_attempts", {"team_id": team["id"], "answer_hash": hashlib.sha256(payload.answer.encode()).hexdigest(), "is_valid": False})
        sb_post("audit_logs", {"action": "final_submission", "actor_type": "team", "team_id": team["id"], "metadata": {"valid": False, "reason": "not_ready"}})
        raise HTTPException(423, f"Final protocol locked — {len(completed)}/7 nodes recovered.")
    valid = bool(final_hash and bcrypt.checkpw(payload.answer.strip().lower().encode(), final_hash.encode()))
    sb_post("final_attempts", {"team_id": team["id"], "answer_hash": hashlib.sha256(payload.answer.encode()).hexdigest(), "is_valid": valid})
    if valid:
        sb_patch("teams", {"id": f"eq.{team['id']}"}, {"status": "finished"})
    sb_post("audit_logs", {"action": "final_submission", "actor_type": "team", "team_id": team["id"], "metadata": {"valid": valid}})
    return {"valid": valid, "message": "Final protocol complete" if valid else "Master key rejected"}


@api.post("/team/redeem-token")
async def redeem_offline_token(payload: RedeemToken):
    require_live_event()
    team_id = verify_team_token(payload.session_token)
    team = get_team(team_id)
    cp = get_checkpoint(payload.checkpoint_code)
    progress = get_active_progress(team["id"], cp["id"])
    if not progress:
        raise HTTPException(403, "That node is not active for this team")
    rows = sb_patch_return("offline_tokens", {"token": f"eq.{payload.token.upper()}", "team_id": f"eq.{team['id']}", "checkpoint_id": f"eq.{cp['id']}", "used_at": "is.null"}, {"used_at": datetime.now(timezone.utc).isoformat()})
    if not rows:
        raise HTTPException(409, "Token is invalid, already used, or for another node")
    complete_progress(progress, team["id"], cp)
    sb_post("audit_logs", {"action": "offline_token_redeemed", "actor_type": "team", "team_id": team["id"], "metadata": {"checkpoint": cp["code"]}})
    return {"valid": True, "message": "Offline verification accepted"}

# ------------------------- Control endpoints -------------------------
@api.post("/control/event")
async def control_event(payload: EventAction):
    operator = require_role(
        payload.access_token,
        {"admin", "super_admin", "event_control"}
    )

    if payload.state not in {
        "DRAFT", "READY", "STANDBY",
        "LIVE", "PAUSED", "ENDED"
    }:
        raise HTTPException(400, "Invalid event state")

    events = sb_get(
        "events",
        {
            "select": "id,state",
            "order": "created_at.desc",
            "limit": "1"
        }
    )

    if not events:
        raise HTTPException(404, "Event not configured")

    event = events[0]
    previous_state = event.get("state")

    # Start a fresh event
    if payload.state == "LIVE" and previous_state in {
        "DRAFT", "READY", "STANDBY"
    }:
        teams = sb_get(
            "teams",
            {
                "status": "eq.active",
                "select": "id"
            }
        )

        for team in teams:
            progress = sb_get(
                "team_progress",
                {
                    "team_id": f"eq.{team['id']}",
                    "select": "id,route_position,status",
                    "order": "route_position.asc"
                }
            )

            if not progress:
                continue

            # Don't accidentally restart a team that has already begun.
            already_started = any(
                row.get("status") in {"active", "completed"}
                for row in progress
            )

            if already_started:
                continue

            first = progress[0]

            sb_patch(
                "team_progress",
                {"id": f"eq.{first['id']}"},
                {
                    "status": "active",
                    "volunteer_state": "idle"
                }
            )

    sb_patch(
        "events",
        {"id": f"eq.{event['id']}"},
        {"state": payload.state}
    )

    sb_post(
        "audit_logs",
        {
            "action": "event_control",
            "actor_type": "operator",
            "actor_id": operator.get("id"),
            "metadata": {
                "state": payload.state,
                "previous_state": previous_state
            }
        }
    )

    return {
        "state": payload.state,
        "previous_state": previous_state
    }

@api.post("/control/volunteer")
async def volunteer_action(payload: VolunteerAction):
    operator = require_role(payload.access_token, {"admin", "super_admin", "volunteer"})
    if payload.action not in {"START", "PASS", "FAIL", "CALL_CONTROL"}:
        raise HTTPException(400, "Invalid checkpoint action")
    sb_post("audit_logs", {"action": f"volunteer_{payload.action.lower()}", "actor_type": "volunteer", "actor_id": operator.get("id"), "metadata": {"team_id": payload.team_id, "checkpoint": payload.checkpoint_code}})
    return {"action": payload.action, "recorded": True}


@api.post("/control/verify-team")
async def verify_team(payload: VerifyTeam):
    """Complete or fail a volunteer-verified checkpoint (C/E/G). Enforces assignment."""
    require_live_event()
    operator = require_role(payload.access_token, {"admin", "super_admin", "volunteer"})
    cp = get_checkpoint(payload.checkpoint_code)
    if not volunteer_assigned_to(operator, cp["id"]):
        raise HTTPException(403, f"This volunteer is not authorized for checkpoint {cp['code']}.")
    if cp.get("mechanic") not in {"volunteer_verify", "keeper", "classroom_memory"}:
        raise HTTPException(400, "This checkpoint is not volunteer-verified.")
    team = get_team(payload.team_id.upper())
    progress = get_active_progress(team["id"], cp["id"])
    if not progress:
        raise HTTPException(409, "That team is not currently at this checkpoint.")
    
    result = payload.result.upper()

    if result not in {"START", "PASS", "FAIL"}:
        raise HTTPException(400, "Result must be START, PASS, or FAIL")

    # Classroom Memory (G) must be completed only through
    # the automatic classroom question validation.
    if cp.get("mechanic") == "classroom_memory" and result in {"PASS", "FAIL"}:
        raise HTTPException(
            400,
            "Classroom memory checkpoints cannot be manually passed or failed."
        )

    now = datetime.now(timezone.utc).isoformat()
        # Prevent restarting G after the classroom attempt has already begun.
   if (
    cp.get("mechanic") == "classroom_memory"
    and result == "START"
    and progress.get("volunteer_state") not in {"idle", "waiting", None}
):
    raise HTTPException(
        409,
        "This classroom attempt has already started."
    )
    if result == "START":
        meta = {
            **(progress.get("metadata") or {}),
            "started_at": now,
        }

        if cp.get("mechanic") == "classroom_memory":
            question_count = (cp.get("config") or {}).get(
                "questions_per_attempt", 4
            )

            meta.update({
                "room_started": True,
                "questions_unlocked": False,
                "classroom_questions": select_classroom_questions(question_count),
                "classroom_answers": None,
                "classroom_score": None,
            })

        sb_patch(
            "team_progress",
            {"id": f"eq.{progress['id']}"},
            {
                "volunteer_state": "in_progress",
                "metadata": meta
            }
        )

        outcome = "started"

    elif result == "PASS":
        complete_progress(progress, team["id"], cp)
        outcome = "passed"

    else:
        retry_penalty = (cp.get("config") or {}).get("retry_penalty", -20)
        apply_penalty(progress, retry_penalty, "failed_retry")
        outcome = "failed"

    sb_post(
        "audit_logs",
        {
            "action": f"verify_{outcome}",
            "actor_type": "volunteer",
            "actor_id": operator.get("id"),
            "team_id": team["id"],
            "metadata": {
                "checkpoint": cp["code"],
                "result": result
            }
        }
    )

    return {
        "result": result,
        "outcome": outcome,
        "checkpoint": cp["code"]
    }


@api.post("/control/classroom")
async def classroom_control(payload: GridControl):
    """G-only: unlock classroom questions after the observation period."""
    require_live_event()

    operator = require_role(
        payload.access_token,
        {"admin", "super_admin", "volunteer"}
    )

    cp = get_checkpoint(payload.checkpoint_code)

    if cp.get("mechanic") != "classroom_memory":
        raise HTTPException(
            400,
            "This checkpoint is not a classroom memory challenge."
        )

    if not volunteer_assigned_to(operator, cp["id"]):
        raise HTTPException(
            403,
            f"This volunteer is not authorized for checkpoint {cp['code']}."
        )

    team = get_team(payload.team_id.upper())
    progress = get_active_progress(team["id"], cp["id"])

    if not progress:
        raise HTTPException(
            409,
            "That team is not currently at this checkpoint."
        )

    action = payload.action.upper()
    meta = progress.get("metadata") or {}

    if action != "UNLOCK":
        raise HTTPException(
            400,
            "Action must be UNLOCK."
        )

    if meta.get("questions_unlocked"):
        raise HTTPException(
            409,
            "Classroom questions have already been unlocked."
        )

        started_at = meta.get("started_at")

    if started_at:
        started_time = datetime.fromisoformat(started_at)
        elapsed = (datetime.now(timezone.utc) - started_time).total_seconds()
        observation_seconds = (cp.get("config") or {}).get(
            "observation_seconds", 30
        )

        if elapsed < observation_seconds:
            remaining = int(observation_seconds - elapsed) + 1
            raise HTTPException(
                409,
                f"Observation period still active. Wait {remaining} more seconds."
            )    

    if not meta.get("room_started"):
        raise HTTPException(
            409,
            "Start the classroom observation before unlocking questions."
        )

    if not meta.get("classroom_questions"):
        raise HTTPException(
            409,
            "No classroom questions were generated for this attempt."
        )

    now = datetime.now(timezone.utc).isoformat()

    meta = {
        **meta,
        "questions_unlocked": True,
        "questions_unlocked_at": now,
    }

    sb_patch(
        "team_progress",
        {"id": f"eq.{progress['id']}"},
        {
            "metadata": meta,
            "volunteer_state": "questions_unlocked"
        }
    )

    sb_post(
        "audit_logs",
        {
            "action": "classroom_questions_unlocked",
            "actor_type": "volunteer",
            "actor_id": operator.get("id"),
            "team_id": team["id"],
            "metadata": {
                "checkpoint": cp["code"]
            }
        }
    )

    return {
        "action": "UNLOCK",
        "questions_unlocked": True
    }


@api.post("/control/offline-token")
async def issue_offline_token(payload: TokenRequest):
    operator = require_role(payload.access_token, {"admin", "super_admin", "volunteer"})
    team = get_team(payload.team_id.upper())
    cp = get_checkpoint(payload.checkpoint_code)
  

@api.post("/control/announce")
async def broadcast_announcement(payload: AnnouncementBroadcast):
    operator = require_role(payload.access_token, {"admin", "super_admin", "event_control"})
    row = sb_post_return("announcements", {"message": payload.message, "active": True})
    sb_post("audit_logs", {"action": "announcement", "actor_type": "operator", "actor_id": operator.get("id"), "metadata": {"message": payload.message}})
    return row[0] if row else {"message": payload.message}

@api.get("/control/winner")
async def winner_board(authorization: str = Header(None)):
    access_token = (authorization or "").replace("Bearer ", "", 1).strip()

    if not access_token:
        raise HTTPException(401, "AUTH REQUIRED")

    require_role(access_token, {"admin", "super_admin", "event_control"})
    attempts = sb_get("final_attempts", {"is_valid": "eq.true", "select": "id,team_id,attempted_at", "order": "attempted_at.asc", "limit": "50"})
    winners = []
    for attempt in attempts:
        team = sb_get("teams", {"id": f"eq.{attempt['team_id']}", "select": "team_id,team_name", "limit": "1"})
        scores = sb_get("team_progress", {"team_id": f"eq.{attempt['team_id']}", "select": "score,penalty"})
        total = sum((row.get("score") or 0) + (row.get("penalty") or 0) for row in scores)
        winners.append({**attempt, "team": team[0] if team else {}, "score": total})
    winners.sort(key=lambda w: (w["attempted_at"], -w["score"]))
    return {"winner": winners[0] if winners else None, "finish_order": winners, "server_time": datetime.now(timezone.utc).isoformat()}


@api.get("/control/volunteer-view")
async def volunteer_view(
    access_token: str = "",
    authorization: str = Header(None),
):
    """Volunteer sees only teams currently active at their assigned checkpoint."""

    token = access_token or (authorization or "").replace("Bearer ", "", 1).strip()

    if not token:
        raise HTTPException(401, "AUTH REQUIRED")

    operator = require_role(
        token,
        {"volunteer", "admin", "super_admin", "event_control"},
    )


    assignment = sb_get(
        "volunteer_assignments",
        {
            "volunteer_id": f"eq.{operator['id']}",
            "select": "checkpoint_id",
            "limit": "1",
        },
    )

    if assignment and assignment[0].get("checkpoint_id"):
        checkpoint_id = assignment[0]["checkpoint_id"]

    elif operator.get("_role") == "volunteer":
        return {"assigned_checkpoint": None, "teams": []}

    else:
        # Admin/event control fallback when no volunteer assignment exists
        cps = sb_get(
            "checkpoints",
            {
                "select": "id,code",
                "order": "code.asc",
                "limit": "1",
            },
        )
        checkpoint_id = cps[0]["id"] if cps else None

    if not checkpoint_id:
        return {"assigned_checkpoint": None, "teams": []}

    cp = sb_get(
        "checkpoints",
        {
            "id": f"eq.{checkpoint_id}",
            "select": "id,code,name,mechanic,config",
            "limit": "1",
        },
    )[0]

    active = sb_get(
        "team_progress",
        {
            "checkpoint_id": f"eq.{checkpoint_id}",
            "status": "eq.active",
            "select": "team_id,attempts,penalty,volunteer_state,metadata",
        },
    )

    teams_data = []

    if active:
        team_ids = [row["team_id"] for row in active]

        teams = sb_get(
            "teams",
            {
                "id": f"in.({','.join(team_ids)})",
                "select": "id,team_id,team_name",
            },
        )

        teams_by_id = {team["id"]: team for team in teams}

        for row in active:
            team = teams_by_id.get(row["team_id"])

            if team:
                teams_data.append(
                    {
                        "team_id": team["team_id"],
                        "team_name": team["team_name"],
                        "attempts": row.get("attempts", 0),
                        "penalty": row.get("penalty", 0),
                        "volunteer_state": row.get("volunteer_state"),
                        "grid_visible": (row.get("metadata") or {}).get(
                            "grid_visible", False
                        ),
                    }
                )

    return {
        "assigned_checkpoint": {
            "code": cp["code"],
            "name": cp["name"],
            "mechanic": cp["mechanic"],
        },
        "teams": teams_data,
    }
# ------------------------- Admin endpoints -------------------------

CHECKPOINT_MECHANICS = [
    # code, name, clue, challenge, answer, fragment, mechanic, cipher_display, config
   ("A", "CIPHER TRANSMISSION",
     "A corrupted transmission has been intercepted. Recover the message and locate the first trace of the protocol.",
     "Decode the transmission. Once you reach the location, observe the final approach and enter the number of stepping stones.",
     "5", "7", "cipher",
     "ILQG ZKHUH ILYH OHWWHUV UHVW DPRQJ WKH JUHHQ. WKH SURWRFOR OHIW LWV ILUVW WUDFH WKHUH.",
     {"cipher_hint": "RECOVERY KEY: 3 — The signal has shifted."}),
   ("B", "HIDDEN IN PLAIN SIGHT",
     "Where signals are taught but rarely seen, the names of those who teach them stand together. Rise to the third level of a building that remembers a jubilee. The next trace is hiding in plain sight.",
     "The board holds three numbers you need. Count those listed as Professor, Associate Professor, and Assistant Professor — in that order. But three numbers cannot open one node. Let the first multiply the strength of the second. Then strip away the weight of the third. Only one number survives. Enter it.",
     "85", "R", "answer", None, {}),
    ("C", "COORDINATION PROTOCOL",
     "A celebration measured in platinum guards the next signal. Seek the level where your climb has not yet begun. Find the halls built for hundreds of eyes and a single voice. Ignore the first. The second awaits your coordination.",
     "Four minds. Four controls. One objective. Report to the Protocol Volunteer. Once the sequence begins, your team has 120 seconds to construct the required formation. Direct contact with the objects is forbidden. Coordination is your only control.",
     "", "△", "volunteer_verify", None,
     {"retry_penalty": -20, "time_limit_seconds": 120}),
  ("D", "VISUAL TRACE",
     "Three fragments of a place have survived. Study the visual traces and identify where on campus they were captured.",
     "Locate the site shown in the visual traces. Search the area for the Protocol Node and scan its QR. Authentication will reveal your final verification.",
     "90", "3", "qr_answer", None,
     {
         "node_token": "LP-NODE-D-9F2A",
"images": [
    "/checkpoint-d/trace-1.png",
    "/checkpoint-d/trace-2.png",
    "/checkpoint-d/trace-3.png"
],
         "post_scan_clue": (
             "NODE AUTHENTICATED\n\n"
             "The trace does not end inside the lawn.\n"
             "Look beyond the entrance.\n\n"
             "A machine waits there, but it leaves only when its seats agree.\n"
             "Three travel. Thirty each.\n\n"
             "Recover the transmission value:\n"
             "What does one complete departure carry?"
         )
     }),
   ("E", "THE KEEPER",
     "Where a six is celebrated, a goal is chased, and a smash crosses the net, the Keeper waits. Among those carrying the familiar red identity, one carries a different colour. Find that person and ask: Did the protocol survive?",
   "If you have me, you may want to share me. But once you share me, you no longer have me. What am I?",
"", "K", "keeper", None,
     {
         "phrase": "Did the protocol survive?",
         "correct_answer": "SECRET",
         "retry_penalty": -20
     }),
    ("F", "THE OBSERVATORY",
     "Two paths open to the observatory. Choose within the countdown.",
     "SAFE (+100): easier clue. RISK (+180, -40 on failure): harder clue.",
     "", "♢", "risk_choice", None,
     {"safe": {"clue": "Name the hunter's constellation.", "answer_hash": bcrypt.hashpw(b"orion", bcrypt.gensalt()).decode(), "points": 100},
      "risk": {"clue": "Name the westernmost star of Orion's belt.", "answer_hash": bcrypt.hashpw(b"mintaka", bcrypt.gensalt()).decode(), "points": 180, "penalty": -40},
      "timer_seconds": 60}),
        ("G", "THE LAST SIGNAL",
     "Where platinum marks the passage of time, rise until the ground lies five levels beneath you. "
     "Seek the room whose number begins where you stand, while its final two digits complete a perfect week. "
     "The signal is waiting inside.",
     "Report to the Protocol Volunteer at Room 607. Your team will have 30 seconds inside the observation room. "
     "No phones, photographs, or writing. Once you leave, four questions will unlock. "
     "Recover at least 3 of the 4 signals to complete the node.",
     "", "9", "classroom_memory", None,
     {
         "observation_seconds": 30,
         "answer_seconds": 45,
         "questions_per_attempt": 4,
         "threshold": 3,
         "retry_penalty": -20
     }),
]


@api.post("/admin/seed")
async def seed_event(payload: SeedRequest):
    """Idempotent baseline seed. If the event already exists, only apply-mechanics runs."""
    operator = require_role(payload.access_token, {"admin", "super_admin"})
    existing = sb_get("events", {"name": "eq.THE LOST PROTOCOL", "select": "id", "limit": "1"})
    if not existing:
        event = sb_post_return("events", {"name": "THE LOST PROTOCOL", "state": "STANDBY"})
        event_id = event[0]["id"] if event else None
    else:
        event_id = existing[0]["id"]
    # Upsert checkpoints with mechanics
    checkpoints = []
    for code, name, clue, challenge, answer, fragment, mechanic, cipher_display, config in CHECKPOINT_MECHANICS:
        row = {"code": code, "name": name, "description": name, "clue": clue, "challenge": challenge,
               "answer_hash": bcrypt.hashpw((answer or code.lower()).encode(), bcrypt.gensalt()).decode() if answer else bcrypt.hashpw(b"__volunteer__", bcrypt.gensalt()).decode(),
               "fragment": fragment, "points": 120, "mechanic": mechanic, "config": config, "cipher_display": cipher_display}
        result = sb_upsert("checkpoints", row, on_conflict="code")
        checkpoints.append(result[0] if result else sb_get("checkpoints", {"code": f"eq.{code}", "select": "id,code", "limit": "1"})[0])
    # Routes (create only if missing)
    existing_routes = sb_get("routes", {"select": "id,name"})
    routes = [r["id"] for r in existing_routes]
    if len(routes) < 7:
        codes = [c[0] for c in CHECKPOINT_MECHANICS]
        for offset in range(7 - len(routes)):
            r = sb_post_return("routes", {"name": f"ROTATION {chr(65 + len(routes) + offset)}", "checkpoint_order": codes[offset:] + codes[:offset]})
            routes.append(r[0]["id"])
    # Teams + progress (only create if missing)
    for index in range(12):
        team_id = f"LP-{index + 1:02d}"
        existing_team = sb_get("teams", {"team_id": f"eq.{team_id}", "select": "id", "limit": "1"})
        if existing_team:
            continue
        team = sb_post_return("teams", {"team_id": team_id,
                                          "team_name": ["Night Shift", "Orbitals", "Red Thread", "North Star", "Signal Bloom", "The Variables"][index % 6],
                                          "pin_hash": bcrypt.hashpw(f"{index + 1:04d}".encode(), bcrypt.gensalt()).decode(),
                                          "status": "active"})
        team_row = team[0]
        route_id = routes[index % len(routes)]
        sb_post("team_routes", {"team_id": team_row["id"], "route_id": route_id})
        ordered = checkpoints[index % len(routes):] + checkpoints[:index % len(routes)]
        for pos, cp in enumerate(ordered):
            sb_post("team_progress", {"team_id": team_row["id"], "checkpoint_id": cp["id"], "route_position": pos, "status": "active" if pos == 0 else "locked"})
    # Fragments (dedupe by checkpoint)
    existing_frags = {f["checkpoint_id"]: f for f in sb_get("fragments", {"select": "id,checkpoint_id"})}
    for cp in checkpoints:
        entry = next((c for c in CHECKPOINT_MECHANICS if c[0] == cp["code"]), None)
        if entry and cp["id"] not in existing_frags:
            sb_post("fragments", {"checkpoint_id": cp["id"], "value": entry[5]})
    # Hints — one per checkpoint per level, upsert-like: create only if none exist
    for cp in checkpoints:
        hs = sb_get("hints", {"checkpoint_id": f"eq.{cp['id']}", "select": "id", "limit": "1"})
        if not hs:
            sb_post("hints", {"checkpoint_id": cp["id"], "name": "Hint 1", "content": "Look closer at the marked campus memory.", "penalty": -15})
            sb_post("hints", {"checkpoint_id": cp["id"], "name": "Hint 2", "content": "Sync your fragments and revisit the clue.", "penalty": -30})
    # Final answer
    existing_final = sb_get("event_settings", {"key": "eq.final_answer_hash", "select": "key", "limit": "1"})
    if not existing_final:
        sb_post("event_settings", {"key": "final_answer_hash", "value": {"hash": bcrypt.hashpw(b"protocol", bcrypt.gensalt()).decode()}})
    sb_post("audit_logs", {"action": "event_seeded", "actor_type": "operator", "actor_id": operator.get("id"), "metadata": {"teams": 12, "checkpoints": 7}})
    return {"event_id": event_id, "teams": 12, "checkpoints": 7, "message": "Seed applied (idempotent)."}


@api.post("/admin/apply-mechanics")
async def apply_mechanics(payload: SeedRequest):
    """Refresh mechanic/config on existing checkpoints without recreating teams/routes."""
    operator = require_role(payload.access_token, {"admin", "super_admin"})
    updated = []
    for code, name, clue, challenge, answer, fragment, mechanic, cipher_display, config in CHECKPOINT_MECHANICS:
        patch = {"mechanic": mechanic, "config": config, "cipher_display": cipher_display, "clue": clue, "challenge": challenge, "name": name, "fragment": fragment}
        if answer:
            patch["answer_hash"] = bcrypt.hashpw(answer.encode(), bcrypt.gensalt()).decode()
        rows = sb_patch_return("checkpoints", {"code": f"eq.{code}"}, patch)
        if rows:
            updated.append(code)
    sb_post("audit_logs", {"action": "mechanics_applied", "actor_type": "operator", "actor_id": operator.get("id"), "metadata": {"updated": updated}})
    return {"updated": updated}


@api.post("/admin/cleanup-test")
async def cleanup_test(payload: CleanupRequest):
    """Safely remove teams whose team_id starts with the given prefix (default TEST-). Never touches LP-*."""
    operator = require_role(payload.access_token, {"admin", "super_admin"})
    prefix = payload.prefix.upper()
    if not prefix or prefix in {"LP-", ""}:
        raise HTTPException(400, "Refusing to clean up with an unsafe prefix.")
    teams = sb_get("teams", {"team_id": f"like.{prefix}*", "select": "id,team_id"})
    removed = []
    for t in teams:
        tid = t["id"]
        # Delete dependent rows without cascade first
        for tbl in ("offline_tokens", "hint_usage", "final_attempts", "team_fragments", "team_progress", "team_routes", "team_members"):
            requests.delete(f"{SUPABASE_URL}/rest/v1/{tbl}", headers=_headers(), params={"team_id": f"eq.{tid}"}, timeout=12)
        requests.delete(f"{SUPABASE_URL}/rest/v1/audit_logs", headers=_headers(), params={"team_id": f"eq.{tid}"}, timeout=12)
        r = requests.delete(f"{SUPABASE_URL}/rest/v1/teams", headers=_headers(), params={"id": f"eq.{tid}"}, timeout=12)
        if r.status_code < 400:
            removed.append(t["team_id"])
    sb_post("audit_logs", {"action": "cleanup_test", "actor_type": "operator", "actor_id": operator.get("id"), "metadata": {"prefix": prefix, "removed": removed}})
    return {"removed": removed, "count": len(removed)}


@api.post("/dev/seed-operator")
async def dev_seed_operator(payload: DevOperatorSeed):
    if not hmac.compare_digest(payload.setup_key, SERVICE_KEY[:12]):
        raise HTTPException(403, "Setup key rejected")
    role = payload.role if payload.role in {"admin", "super_admin", "event_control", "volunteer"} else "volunteer"
    user_id = upsert_auth_user(payload.email, payload.password, role, payload.display_name)
    if role == "volunteer" and user_id:
        attach_volunteer(user_id, payload.display_name or payload.email.split("@")[0], payload.checkpoint_code)
    return {"id": user_id, "email": payload.email, "role": role}

@api.post("/admin/volunteer-assignment")
async def admin_volunteer_assignment(payload: dict):
    operator = require_role(
        payload.get("access_token"),
        {"admin", "super_admin", "event_control"},
    )

    volunteer_id = payload.get("volunteer_id")
    checkpoint_code = str(payload.get("checkpoint_code", "")).upper().strip()

    if not volunteer_id or not checkpoint_code:
        raise HTTPException(400, "volunteer_id and checkpoint_code are required")

    volunteers = sb_get(
        "volunteers",
        {
            "id": f"eq.{volunteer_id}",
            "select": "id,display_name",
            "limit": "1",
        },
    )

    if not volunteers:
        raise HTTPException(404, "Volunteer not found")

    checkpoints = sb_get(
        "checkpoints",
        {
            "code": f"eq.{checkpoint_code}",
            "select": "id,code,name",
            "limit": "1",
        },
    )

    if not checkpoints:
        raise HTTPException(404, "Checkpoint not found")

    checkpoint = checkpoints[0]

    # Remove previous assignment
    r = requests.delete(
        f"{SUPABASE_URL}/rest/v1/volunteer_assignments",
        headers=_headers(True),
        params={"volunteer_id": f"eq.{volunteer_id}"},
        timeout=10,
    )

    if r.status_code >= 400:
        raise HTTPException(503, f"DB unavailable: {r.text[:180]}")

    # Create new assignment
    sb_post(
        "volunteer_assignments",
        {
            "volunteer_id": volunteer_id,
            "checkpoint_id": checkpoint["id"],
        },
    )

    # Keep volunteers.checkpoint_id synchronized too
    sb_patch(
        "volunteers",
        {"id": f"eq.{volunteer_id}"},
        {"checkpoint_id": checkpoint["id"]},
    )

    sb_post(
        "audit_logs",
        {
            "action": "volunteer_assignment_changed",
            "actor_type": "operator",
            "actor_id": operator.get("id"),
            "metadata": {
                "volunteer_id": volunteer_id,
                "checkpoint_code": checkpoint_code,
            },
        },
    )

    return {
        "ok": True,
        "volunteer_id": volunteer_id,
        "checkpoint_code": checkpoint["code"],
        "checkpoint_name": checkpoint["name"],
    }
@api.post("/admin/operators")
async def admin_create_operator(payload: OperatorSeed):
    operator = require_role(payload.access_token, {"admin", "super_admin"})
    role = payload.role if payload.role in {"admin", "super_admin", "event_control", "volunteer"} else "volunteer"
    user_id = upsert_auth_user(payload.email, payload.password, role, payload.display_name)
    if role == "volunteer" and user_id:
        attach_volunteer(user_id, payload.display_name or payload.email.split("@")[0], payload.checkpoint_code)
    sb_post("audit_logs", {"action": "operator_created", "actor_type": "operator", "actor_id": operator.get("id"), "metadata": {"email": payload.email, "role": role}})
    return {"id": user_id, "email": payload.email, "role": role}


ADMIN_LIST_FIELDS = {
    "teams": "id,team_id,team_name,status,created_at",
    "checkpoints": "id,code,name,mechanic,clue,challenge,fragment,points,created_at",
    "hints": "id,checkpoint_id,name,content,penalty",
    "routes": "id,name,checkpoint_order",
    "volunteers": "id,display_name,role,checkpoint_id",
    "announcements": "id,message,active,created_at",
    "event_settings": "key,value",
    "audit_logs": "id,action,actor_type,metadata,created_at",
}
ADMIN_ALIAS = {"settings": "event_settings", "audit-log": "audit_logs"}
ADMIN_EDITABLE = {
    "teams": {"team_id", "team_name", "status", "pin"},
    "checkpoints": {"code", "name", "description", "clue", "challenge", "fragment", "points", "answer", "mechanic", "config", "cipher_display"},
    "hints": {"checkpoint_id", "name", "content", "penalty"},
    "routes": {"name", "checkpoint_order"},
    "announcements": {"message", "active"},
    "event_settings": {"key", "value"},
}


@api.get("/admin/{resource}")
async def admin_list(resource: str, authorization: str = Header(None)):
    access_token = (authorization or "").replace("Bearer ", "", 1).strip()

    if not access_token:
        raise HTTPException(401, "AUTH REQUIRED")

    require_role(access_token, {"admin", "super_admin", "event_control"})
    resource = ADMIN_ALIAS.get(resource, resource)
    if resource == "event_settings":
        order = "key.asc"
    elif "created_at" in ADMIN_LIST_FIELDS[resource]:
        order = "created_at.desc"
    elif resource == "volunteers":
        order = "display_name.asc"
    else:
        order = "name.asc"

    return sb_get(
        resource,
        {
            "select": ADMIN_LIST_FIELDS[resource],
            "order": order,
            "limit": "200",
        },
    )

def editable_payload(resource, payload):
    resource = ADMIN_ALIAS.get(resource, resource)
    if resource not in ADMIN_EDITABLE:
        raise HTTPException(404, "This workspace is read-only")
    clean = {key: value for key, value in payload.items() if key in ADMIN_EDITABLE[resource]}
    if resource == "teams" and clean.pop("pin", None):
        clean["pin_hash"] = bcrypt.hashpw(payload["pin"].encode(), bcrypt.gensalt()).decode()
    if resource == "checkpoints" and clean.pop("answer", None):
        clean["answer_hash"] = bcrypt.hashpw(payload["answer"].strip().lower().encode(), bcrypt.gensalt()).decode()
    if resource == "routes" and isinstance(clean.get("checkpoint_order"), str):
        clean["checkpoint_order"] = [x.strip().upper() for x in clean["checkpoint_order"].split(",") if x.strip()]
    if resource == "checkpoints" and isinstance(clean.get("config"), str):
        import json
        try: clean["config"] = json.loads(clean["config"])
        except Exception: raise HTTPException(400, "config must be valid JSON")
    return resource, clean


@api.post("/admin/{resource}")
async def admin_create(resource: str, request: ResourceRequest):
    require_role(request.access_token, {"admin", "super_admin"})
    resource, clean = editable_payload(resource, request.payload)
    if not clean:
        raise HTTPException(400, "No editable fields supplied")
    row = sb_post_return(resource, clean)
    sb_post("audit_logs", {"action": "admin_create", "actor_type": "operator", "metadata": {"resource": resource}})
    return row


@api.patch("/admin/{resource}/{row_id}")
async def admin_update(resource: str, row_id: str, request: ResourceRequest):
    require_role(request.access_token, {"admin", "super_admin"})
    resource, clean = editable_payload(resource, request.payload)
    if not clean:
        raise HTTPException(400, "No editable fields supplied")
    key_field = "key" if resource == "event_settings" else "id"
    row = sb_patch_return(resource, {key_field: f"eq.{row_id}"}, clean)
    sb_post("audit_logs", {"action": "admin_update", "actor_type": "operator", "metadata": {"resource": resource, "row_id": row_id}})
    return row


@api.delete("/admin/{resource}/{row_id}")
async def admin_delete(resource: str, row_id: str, access_token: str):
    require_role(access_token, {"admin", "super_admin"})
    resource = ADMIN_ALIAS.get(resource, resource)
    if resource not in ADMIN_EDITABLE:
        raise HTTPException(404, "This workspace is read-only")
    key_field = "key" if resource == "event_settings" else "id"
    sb_delete(resource, {key_field: f"eq.{row_id}"})
    sb_post("audit_logs", {"action": "admin_delete", "actor_type": "operator", "metadata": {"resource": resource, "row_id": row_id}})
    return {"deleted": row_id}


@api.get("/team/{team_id}/mission")
async def team_mission(team_id: str):
    team = get_team(team_id.upper())
    progress = sb_get("team_progress", {"team_id": f"eq.{team['id']}", "select": "checkpoint_id,status,score,completed_at", "order": "route_position.asc"})
    return {"team": team, "progress": progress}


app.include_router(api)
cors_origins = [
    origin.strip().rstrip("/")
    for origin in os.environ.get("CORS_ORIGINS", "*").split(",")
    if origin.strip()
]

app.add_middleware(
    CORSMiddleware,
    allow_credentials=False,
    allow_origins=cors_origins,
    allow_methods=["*"],
    allow_headers=["*"],
)