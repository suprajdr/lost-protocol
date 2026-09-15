# THE LOST PROTOCOL — Product Record

## Original problem statement
Mobile-first, real live-event treasure hunt management platform for a college event called THE LOST PROTOCOL. Teams use Team ID + PIN; volunteers and administrators use Supabase Auth. Manages seven routed checkpoints, hints, fragments, scores, final protocol submissions, event controls, announcements, offline status and one-time offline verification tokens. Visual direction: deep purple/plum, magenta, soft pink glow glassmorphism per uploaded reference.

## Architecture
- React 19 + react-router-dom 7 + Supabase JS on the frontend (kept, TanStack Router migration deferred).
- FastAPI backend proxying Supabase REST + Auth Admin API with HMAC-signed team session tokens.
- Supabase Postgres source of truth. Realtime channels drive live pulses.
- Service worker caches app shell + `/api/team/state` responses so operatives keep their clue when offline. Completion always requires a live server round-trip (or a one-time volunteer offline token).

## Personas
- Team participant: mobile cockpit, walk-and-play ergonomics.
- Volunteer: assigned checkpoint, START/PASS/FAIL, issues offline tokens.
- Event Control: live state, broadcasts, winner board.
- Super Admin: full CRUD workspaces + audit trail.

## Implemented — 2026-02 (session 2)
- Modularized frontend into `pages/*` and `components/*` (App.js is now 15 lines of routing).
- Backend endpoints added: `GET /api/team/state`, `POST /api/admin/operators`, `POST /api/dev/seed-operator`, `POST /api/control/announce`, `DELETE /api/admin/{resource}/{id}`, plus richer admin list (hints, routes).
- Winner board queries `final_attempts` (server timestamp) + score tie-breaker; frontend `WinnerBoard.jsx` re-subscribes on `final_attempts` insert.
- Admin editor modal (`AdminEditor.jsx`) with create + update + delete for teams, checkpoints, hints, routes, announcements, event_settings. Sensitive fields (PIN, answer) are bcrypt-hashed server-side.
- Service worker (`public/service-worker.js`) caches shell + mission-read APIs; offline banner in Shell.
- Seed operator accounts (`admin@lostprotocol.dev`, `volunteer1@lostprotocol.dev`) via `/api/dev/seed-operator` — written to `/app/memory/test_credentials.md`.
- RLS hardening SQL applied to the pooler (events, checkpoints, progress, audit_logs, settings, plus operator-role helpers).

## Test results (iteration 5)
27/29 backend tests pass. Minor issues fixed post-report: winner tie-breaker sort now score-DESC after timestamp; FK errors on DELETE now surface as 409 with a readable message. Full flow verified: team login → answer → advance → hint → final → winner board.

## Backlog
- P1: Split `server.py` into routers (auth/team/admin/control).
- P1: Batch winner-board team lookups with `in.(...)` filter.
- P2: Session-token expiry / revocation.
- P2: Optional migration to TanStack Router (skipped by user preference).
- P2: CORS tightening (allow_credentials + wildcard).
