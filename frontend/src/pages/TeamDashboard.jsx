import { useCallback, useEffect, useState, useMemo, useRef } from "react";
import { Link, useNavigate } from "react-router-dom";
import { Bell, ChevronRight, CircleHelp, WifiOff } from "lucide-react";
import Shell from "@/components/Shell";
import Nodes from "@/components/Nodes";
import { AnswerCard, CipherCard, VolunteerWaitCard, KeeperCard, QRScanCard, RiskChoiceCard, GridMemoryCard } from "@/components/CheckpointCards";
import { apiRequest, formatDetail, getTeamSession, clearTeamSession } from "@/lib/api";
import { cacheMission, readCachedMission } from "@/lib/offline";
import { supabase } from "@/lib/supabase";

export default function TeamDashboard() {
  const nav = useNavigate();
  const session = useMemo(() => getTeamSession(), []);
  const [state, setState] = useState(null);
  const [notice, setNotice] = useState("");
  const [announcements, setAnnouncements] = useState([]);
  const [pendingHint, setPendingHint] = useState(null);
  const loadingState = useRef(false);

 const loadState = useCallback(async () => {
  if (!session) return nav("/team/login");

  // Prevent overlapping /team/state requests
  if (loadingState.current) return;
  loadingState.current = true;

  try {
    const data = await apiRequest(
      `/team/state?session_token=${encodeURIComponent(session.session_token)}`
    );

    setState(data);
    setNotice("");
    cacheMission(session.team_id, data);
  } catch (err) {
    const cached = readCachedMission(session.team_id);

    if (cached) {
      setState(cached.state);
      setNotice("Using cached mission — reconnect for live updates.");
    } else {
      setNotice(err.message);
    }
  } finally {
    loadingState.current = false;
  }
}, [session, nav]);

 useEffect(() => {
  // Initial load
  loadState();

  apiRequest("/event/announcements")
    .then(setAnnouncements)
    .catch(() => {});

  // Refresh immediately when internet reconnects
  const on = () => loadState();
  window.addEventListener("online", on);

  // Poll mission state every 10 seconds
  const timer = setInterval(() => {
    loadState();
  }, 30000);

  return () => {
    window.removeEventListener("online", on);
    clearInterval(timer);
  };
}, [loadState]);
  if (!state) {
    return (
      <Shell role="TEAM // LOADING">
        <main className="page-wrap"><p className="muted">Locking on to your mission…</p></main>
      </Shell>
    );
  }

  const current = state.current;
  const isLive = state.event_state === "LIVE";

  const submitAnswer = async (answer) => {
    setNotice("");
    if (!navigator.onLine) return setNotice("Offline completion is blocked. Use a verified volunteer token when the link returns.");
    if (!current) return;
    try {
      const data = await apiRequest("/team/answer", {
        method: "POST",
        body: JSON.stringify({ session_token: session.session_token, checkpoint_code: current.code, answer }),
      });
      setNotice(data.message);
      loadState();
    } catch (err) {
      setNotice(formatDetail(err.message));
    }
  };

  const scanNode = async (nodeToken) => {
    setNotice("");
    if (!current) return;
    try {
      const data = await apiRequest("/team/scan-node", {
        method: "POST",
        body: JSON.stringify({ session_token: session.session_token, checkpoint_code: current.code, node_token: nodeToken }),
      });
      setNotice(data.message);
      loadState();
    } catch (err) {
      setNotice(err.message);
    }
  };

  const chooseRisk = async (choice) => {
    setNotice("");
    if (!current) return;
    try {
      await apiRequest("/team/choice", {
        method: "POST",
        body: JSON.stringify({ session_token: session.session_token, checkpoint_code: current.code, choice }),
      });
      loadState();
    } catch (err) {
      setNotice(err.message);
    }
  };

  const requestHint = async (index) => {
    setNotice("");
    if (!navigator.onLine) return setNotice("Hints require a live link.");
    if (!current) return;
    // Confirm penalty
    const label = index === 0 ? "Hint 1 (-15)" : "Hint 2 (-30)";
    if (!window.confirm(`Reveal ${label}? Penalty is applied once per team.`)) return;
    try {
      const data = await apiRequest("/team/hint", {
        method: "POST",
        body: JSON.stringify({ session_token: session.session_token, checkpoint_code: current.code, hint_index: index }),
      });
      setPendingHint(data);
      loadState();
    } catch (err) {
      setNotice(err.message);
    }
  };

  const exitTeam = () => {
    clearTeamSession();
    nav("/");
  };

  if (state.ready_for_final) {
    return (
      <Shell role={`TEAM // ${session.team_id}`}>
        <main className="dashboard page-wrap">
          <div className="dash-heading">
            <div>
              <p className="eyebrow">FIELD OPERATIVE // {session.team_id}</p>
              <h2>All nodes recovered, <em>{session.team_name}</em></h2>
            </div>
            <button className="icon-button" onClick={exitTeam} data-testid="team-exit-button" aria-label="Exit">×</button>
          </div>
          <p className="muted">Route complete. Assemble your fragments and reconstruct the final protocol.</p>
          <Link className="button primary" to="/team/final" data-testid="final-protocol-link">Enter final protocol <ChevronRight size={16} /></Link>
        </main>
      </Shell>
    );
  }

  const renderMechanic = () => {
    if (!current) return <p className="muted">Awaiting activation…</p>;
    const m = current.mechanic || "answer";
    if (m === "cipher") return <CipherCard session={session} current={current} onSubmit={submitAnswer} />;
    if (m === "qr_answer") return <QRScanCard session={session} current={current} onScan={scanNode} onSubmit={submitAnswer} />;
    if (m === "risk_choice") return <RiskChoiceCard current={current} onChoose={chooseRisk} onSubmit={submitAnswer} />;
    if (m === "volunteer_verify") return <VolunteerWaitCard current={current} />;
    if (m === "keeper") return <KeeperCard current={current} />;
    if (m === "grid_memory") return <GridMemoryCard current={current} />;
    return <AnswerCard current={current} onSubmit={submitAnswer} />;
  };

  return (
    <Shell role={`TEAM // ${session.team_id}`}>
      <main className="dashboard page-wrap">
        <div className="dash-heading">
          <div>
            <p className="eyebrow">FIELD OPERATIVE // {session.team_id} · STATE {state.event_state}</p>
            <h2>Good hunting, <em>{session.team_name}</em></h2>
          </div>
          <button className="icon-button" onClick={exitTeam} data-testid="team-exit-button" aria-label="Exit">×</button>
        </div>
        {announcements[0] && (
          <div className="announcement" data-testid="announcement-banner">
            <Bell size={18} />
            <div>
              <strong>MISSION BRIEFING</strong>
              <p>{announcements[0].message}</p>
            </div>
          </div>
        )}
        <section className="progress-section">
          <div className="section-head">
            <span className="eyebrow">PROTOCOL RECOVERY</span>
            <strong data-testid="progress-count">{String(state.completed).padStart(2, "0")} / {String(state.total).padStart(2, "0")}</strong>
          </div>
          <Nodes route={state.route} currentCode={current?.code} />
        </section>
        <div className="mission-grid">
          <section className="glass-card clue-card">
            <div className="card-top">
              <span className="node-badge">{current?.code || "—"}</span>
              <div>
                <span className="eyebrow">CURRENT CHECKPOINT · {current?.mechanic?.replace("_", " ").toUpperCase() || "STANDBY"}</span>
                <h3>{current?.name || "Awaiting activation"}</h3>
              </div>
            </div>
            {isLive && current ? renderMechanic() : (
              <div className="notice"><WifiOff size={13} /> Event state: {state.event_state}. Await mission control.</div>
            )}
            {notice && <div className="notice" data-testid="submission-notice">{notice}</div>}
            {pendingHint && (
              <div className="notice" data-testid="hint-reveal">
                <strong>{pendingHint.name}:</strong> {pendingHint.content}
                <span className="muted"> — {pendingHint.charged ? `${pendingHint.penalty} pts applied` : "already charged, no new penalty"}</span>
              </div>
            )}
            <div className="clue-actions">
              <button className="text-button" onClick={() => requestHint(0)} data-testid="request-hint-1-button"><CircleHelp size={15} /> Hint 1 (-15)</button>
              <button className="text-button" onClick={() => requestHint(1)} data-testid="request-hint-2-button"><CircleHelp size={15} /> Hint 2 (-30)</button>
              <Link className="text-button" to="/team/redeem" data-testid="open-offline-redeem">Redeem token <ChevronRight size={15} /></Link>
            </div>
          </section>
          <aside className="side-stack">
            <div className="glass-card stat-card">
              <span className="metric-label">SCORE</span>
              <strong data-testid="team-score">{state.score}</strong>
              <span className="muted">Live from mission control</span>
            </div>
            <div className="glass-card fragments-card">
              <div className="section-head">
                <span className="metric-label">FRAGMENTS</span>
                <span className="fragment-count" data-testid="fragment-count">{String(state.fragments.length).padStart(2, "0")}</span>
              </div>
              <div className="fragments">
                {["A","B","C","D","E","F","G"].map((code) => {
                  const collected = state.fragments.find((f) => f.code === code);
                  return <span key={code} className={collected ? "" : "empty"} data-testid={`fragment-${code}`}>{collected?.value || "?"}</span>;
                })}
              </div>
            </div>
          </aside>
        </div>
      </main>
    </Shell>
  );
}
