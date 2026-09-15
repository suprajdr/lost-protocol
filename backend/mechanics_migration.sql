-- THE LOST PROTOCOL — Mechanics + RLS hardening migration
-- Idempotent. Re-runnable.

-- Event state additions
do $$ begin
  begin
    execute 'alter type public.event_state add value if not exists ''DRAFT''';
  exception when others then null; end;
  begin
    execute 'alter type public.event_state add value if not exists ''READY''';
  exception when others then null; end;
end $$;

-- Checkpoint mechanic + config
alter table public.checkpoints add column if not exists mechanic text not null default 'answer';
alter table public.checkpoints add column if not exists config jsonb not null default '{}'::jsonb;
alter table public.checkpoints add column if not exists cipher_display text;
alter table public.checkpoints add column if not exists asset_urls jsonb not null default '[]'::jsonb;

-- Per-team per-checkpoint state (attempts, retry penalty, mechanic-specific metadata, volunteer state)
alter table public.team_progress add column if not exists attempts integer not null default 0;
alter table public.team_progress add column if not exists penalty integer not null default 0;
alter table public.team_progress add column if not exists metadata jsonb not null default '{}'::jsonb;
alter table public.team_progress add column if not exists volunteer_state text not null default 'idle';

-- Ensure each hint is only charged once per team
create unique index if not exists hint_usage_team_hint_unique on public.hint_usage(team_id, hint_id);

-- === RLS: enable + policies for previously unrestricted tables ===
alter table public.teams enable row level security;
alter table public.team_members enable row level security;
alter table public.team_routes enable row level security;
alter table public.fragments enable row level security;
alter table public.team_fragments enable row level security;
alter table public.hints enable row level security;
alter table public.hint_usage enable row level security;
alter table public.volunteers enable row level security;
alter table public.team_sessions enable row level security;
alter table public.volunteer_assignments enable row level security;
alter table public.offline_tokens enable row level security;
alter table public.final_attempts enable row level security;
alter table public.announcements enable row level security;
alter table public.routes enable row level security;

do $$ begin
  drop policy if exists "admins manage teams" on public.teams;
  drop policy if exists teams_operator_read on public.teams;
  drop policy if exists teams_admin_write on public.teams;
  drop policy if exists team_members_read on public.team_members;
  drop policy if exists routes_operator_read on public.routes;
  drop policy if exists routes_admin_write on public.routes;
  drop policy if exists team_routes_operator_read on public.team_routes;
  drop policy if exists fragments_operator_read on public.fragments;
  drop policy if exists fragments_admin_write on public.fragments;
  drop policy if exists team_fragments_operator_read on public.team_fragments;
  drop policy if exists hints_operator_read on public.hints;
  drop policy if exists hints_admin_write on public.hints;
  drop policy if exists hint_usage_operator_read on public.hint_usage;
  drop policy if exists volunteers_read on public.volunteers;
  drop policy if exists volunteers_admin_write on public.volunteers;
  drop policy if exists team_sessions_read on public.team_sessions;
  drop policy if exists volunteer_assignments_read on public.volunteer_assignments;
  drop policy if exists offline_tokens_operator_read on public.offline_tokens;
  drop policy if exists final_attempts_operator_read on public.final_attempts;
  drop policy if exists announcements_public_read on public.announcements;
  drop policy if exists announcements_admin_write on public.announcements;
  drop policy if exists "volunteers read announcements" on public.announcements;
exception when undefined_object then null; end $$;

-- Teams: operator role only, admin can write. Anon/team users cannot read; the FastAPI backend uses service-role (bypasses RLS) for team login.
create policy teams_operator_read on public.teams for select using (public.is_event_control() or public.operator_role() = 'volunteer');
create policy teams_admin_write on public.teams for all using (public.is_admin()) with check (public.is_admin());

create policy team_members_read on public.team_members for select using (public.is_event_control());

create policy routes_operator_read on public.routes for select using (public.is_event_control() or public.operator_role() = 'volunteer');
create policy routes_admin_write on public.routes for all using (public.is_admin()) with check (public.is_admin());

create policy team_routes_operator_read on public.team_routes for select using (public.is_event_control());

create policy fragments_operator_read on public.fragments for select using (public.is_event_control() or public.operator_role() = 'volunteer');
create policy fragments_admin_write on public.fragments for all using (public.is_admin()) with check (public.is_admin());

create policy team_fragments_operator_read on public.team_fragments for select using (public.is_event_control());

create policy hints_operator_read on public.hints for select using (public.is_event_control() or public.operator_role() = 'volunteer');
create policy hints_admin_write on public.hints for all using (public.is_admin()) with check (public.is_admin());

create policy hint_usage_operator_read on public.hint_usage for select using (public.is_event_control());

create policy volunteers_read on public.volunteers for select using (public.is_admin() or id = auth.uid());
create policy volunteers_admin_write on public.volunteers for all using (public.is_admin()) with check (public.is_admin());

create policy team_sessions_read on public.team_sessions for select using (public.is_admin() or auth_user_id = auth.uid());

create policy volunteer_assignments_read on public.volunteer_assignments for select using (public.is_admin() or volunteer_id = auth.uid());

create policy offline_tokens_operator_read on public.offline_tokens for select using (public.is_event_control() or public.is_assigned_volunteer(checkpoint_id));

create policy final_attempts_operator_read on public.final_attempts for select using (public.is_event_control());

create policy announcements_public_read on public.announcements for select using (active = true);
create policy announcements_admin_write on public.announcements for all using (public.is_admin()) with check (public.is_admin());
