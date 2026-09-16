import { useCallback, useEffect, useRef, useState } from "react";
import { Radio, Eye, EyeOff, Play, CheckCircle2, XCircle } from "lucide-react";
import Shell, { StatusPill } from "@/components/Shell";
import { authorizedRequest } from "@/lib/api";
import { supabase } from "@/lib/supabase";

export default function VolunteerStation() {
  const [view, setView] = useState(null);
  const [notice, setNotice] = useState("");
  const [profile, setProfile] = useState(null);


 const loadingView = useRef(false);

const loadView = useCallback(async () => {
  if (loadingView.current) return;

  loadingView.current = true;
  setNotice("");

  try {
    const data = await authorizedRequest("/control/volunteer-view");
    setView(data);
  } catch (err) {
    setNotice(err.message);
  } finally {
    loadingView.current = false;
  }
}, []);

  useEffect(() => {
    supabase.auth.getUser().then(({ data }) => {
      const meta = { ...(data.user?.app_metadata || {}), ...(data.user?.user_metadata || {}) };
      setProfile({ email: data.user?.email, display_name: meta.display_name, role: meta.role });
    });
    loadView();
    const channel = supabase
      .channel("volunteer-station")
      .on("postgres_changes", { event: "*", schema: "public", table: "team_progress" }, loadView)
      .subscribe();
    const timer = setInterval(loadView, 5000);
    return () => {
      supabase.removeChannel(channel);
      clearInterval(timer);
    };
  }, [loadView]);

  const verify = async (teamId, result) => {
    setNotice("");
    try {
      const body = await authorizedRequest("/control/verify-team", "POST", {
        team_id: teamId, checkpoint_code: view.assigned_checkpoint.code, result,
      });
      setNotice(`${body.outcome.toUpperCase()} — ${teamId} @ ${body.checkpoint}`);
      loadView();
    } catch (err) {
      setNotice(err.message);
    }
  };

  const gridAction = async (teamId, action) => {
    setNotice("");
    try {
      await authorizedRequest("/control/grid", "POST", {
        team_id: teamId, checkpoint_code: view.assigned_checkpoint.code, action,
      });
      loadView();
    } catch (err) {
      setNotice(err.message);
    }
  };

  const issueToken = async (teamId) => {
    setNotice("");
    try {
      const body = await authorizedRequest("/control/offline-token", "POST", {
        team_id: teamId, checkpoint_code: view.assigned_checkpoint.code,
      });
      setNotice(`Offline token: ${body.token}`);
    } catch (err) {
      setNotice(err.message);
    }
  };

  const callControl = async () => {
    setNotice("");
    try {
      await authorizedRequest("/control/volunteer", "POST", {
        action: "CALL_CONTROL", team_id: "-", checkpoint_code: view?.assigned_checkpoint?.code || "-",
      });
      setNotice("Mission control has been notified.");
    } catch (err) {
      setNotice(err.message);
    }
  };

  if (!view) {
    return (
      <Shell role="VOLUNTEER STATION"><main className="page-wrap"><p className="muted">Loading assignment…</p>{notice && <div className="notice" data-testid="volunteer-notice">{notice}</div>}</main></Shell>
    );
  }

  if (!view.assigned_checkpoint) {
    return (
      <Shell role="VOLUNTEER STATION">
        <main className="control-page page-wrap">
          <div className="dash-heading">
            <div>
              <p className="eyebrow">CHECKPOINT OPERATIONS · {profile?.email || ""}</p>
              <h2>No checkpoint assigned</h2>
              <p className="muted">Ask an admin to assign you to a checkpoint before opening this station.</p>
            </div>
          </div>
        </main>
      </Shell>
    );
  }

  const cp = view.assigned_checkpoint;
  const isGrid = cp.mechanic === "grid_memory";
  const isVolMech = ["volunteer_verify", "keeper", "grid_memory"].includes(cp.mechanic);

  return (
    <Shell role="VOLUNTEER STATION">
      <main className="control-page page-wrap">
        <div className="dash-heading">
          <div>
            <p className="eyebrow">CHECKPOINT OPERATIONS · {profile?.email || ""}</p>
            <h2>Checkpoint {cp.code} — {cp.name}</h2>
            <p className="muted">Mechanic: {cp.mechanic.replace("_", " ").toUpperCase()}. Only teams currently at this node appear below.</p>
          </div>
          <StatusPill />
        </div>
        {notice && <div className="notice" data-testid="volunteer-notice">{notice}</div>}
        {view.teams.length === 0 ? (
          <section className="glass-card volunteer-card"><p className="muted" data-testid="no-teams-msg">No teams are currently at your checkpoint. Waiting for arrivals…</p></section>
        ) : (
          view.teams.map((t) => (
            <section className="glass-card volunteer-card" key={t.team_id} data-testid={`volunteer-team-card-${t.team_id}`}>
              <div className="section-head">
                <div>
                  <strong style={{ fontSize: 18 }}>{t.team_id}</strong>
                  <span className="muted"> · {t.team_name}</span>
                </div>
                <span className="workspace-status" data-testid={`team-state-${t.team_id}`}>{t.volunteer_state?.toUpperCase() || "IDLE"}</span>
              </div>
              {t.attempts > 0 && <div className="notice">Attempts: {t.attempts} · Penalty {t.penalty}</div>}
              {isVolMech && (
                <div className="volunteer-actions">
                  <button onClick={() => verify(t.team_id, "START")} data-testid={`volunteer-start-${t.team_id}`}><Play size={14} /> START</button>
                  <button className="pass" onClick={() => verify(t.team_id, "PASS")} data-testid={`volunteer-pass-${t.team_id}`}><CheckCircle2 size={14} /> PASS</button>
                  <button className="fail" onClick={() => verify(t.team_id, "FAIL")} data-testid={`volunteer-fail-${t.team_id}`}><XCircle size={14} /> FAIL</button>
                </div>
              )}
              {isGrid && (
                <div className="volunteer-actions" style={{ marginTop: 10 }}>
                  <button onClick={() => gridAction(t.team_id, "DISPLAY")} data-testid={`grid-display-${t.team_id}`}><Eye size={14} /> DISPLAY {t.grid_visible ? "(on)" : ""}</button>
                  <button onClick={() => gridAction(t.team_id, "HIDE")} data-testid={`grid-hide-${t.team_id}`}><EyeOff size={14} /> HIDE</button>
                </div>
              )}
              <button className="button ghost full" style={{ marginTop: 10 }} onClick={() => issueToken(t.team_id)} data-testid={`issue-token-${t.team_id}`}>
                Issue offline verification token
              </button>
            </section>
          ))
        )}
        <button className="button ghost full" style={{ marginTop: 18 }} onClick={callControl} data-testid="call-control-button">
          <Radio size={15} /> Call mission control
        </button>
      </main>
    </Shell>
  );
}
