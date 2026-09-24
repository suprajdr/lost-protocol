import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { Activity, ChevronRight, Radio, KeyRound } from "lucide-react";
import Shell, { StatusPill } from "@/components/Shell";
import WinnerBoard from "@/components/WinnerBoard";
import { authorizedRequest, apiRequest } from "@/lib/api";
import { supabase } from "@/lib/supabase";

export default function EventControl() {
  const [event, setEvent] = useState({ state: "STANDBY" });
  const [teams, setTeams] = useState([]);
  const [announcement, setAnnouncement] = useState("");
  const [notice, setNotice] = useState("");
  const [finalTeamId, setFinalTeamId] = useState("");
  const [finalWord, setFinalWord] = useState("");
  const [verifyingFinal, setVerifyingFinal] = useState(false);

  const reload = async () => {
    try {
      const [ev, list] = await Promise.all([
        apiRequest("/event"),
        authorizedRequest("/admin/teams"),
      ]);
      setEvent(ev);
      setTeams(list || []);
    } catch (err) {
      setNotice(err.message);
    }
  };

  useEffect(() => {
    reload();
    const channel = supabase
      .channel("event-control")
      .on("postgres_changes", { event: "*", schema: "public", table: "events" }, reload)
      .on("postgres_changes", { event: "*", schema: "public", table: "team_progress" }, reload)
      .subscribe();
    const timer = setInterval(reload, 20000);
    return () => {
      supabase.removeChannel(channel);
      clearInterval(timer);
    };
  }, []);

  const control = async (state) => {
    setNotice("");
    try {
      const body = await authorizedRequest("/control/event", "POST", { state });
      setEvent((e) => ({ ...e, state: body.state }));
      setNotice(`Event state → ${body.state}`);
    } catch (err) {
      setNotice(err.message);
    }
  };

  const broadcast = async (e) => {
    e.preventDefault();
    if (!announcement.trim()) return;
    setNotice("");
    try {
      await authorizedRequest("/control/announce", "POST", { message: announcement });
      setNotice("Broadcast delivered.");
      setAnnouncement("");
    } catch (err) {
      setNotice(err.message);
    }
  };
  const verifyAudi2Finish = async (e) => {
  e.preventDefault();

  const teamId = finalTeamId.trim().toUpperCase();
  const answer = finalWord.trim().toUpperCase();

  if (!teamId) {
    setNotice("Enter the team ID.");
    return;
  }

  if (!answer) {
    setNotice("Enter the final extraction word.");
    return;
  }

  setVerifyingFinal(true);
  setNotice("");

  try {
    const body = await authorizedRequest(
      "/control/audi2-finish",
      "POST",
      {
        team_id: teamId,
        answer,
      }
    );

    if (!body.valid) {
      setNotice(body.message || "Final extraction rejected.");
      return;
    }

    setNotice(
      `${body.team_id} — FINAL EXTRACTION VERIFIED. PROTOCOL RESTORED.`
    );

    setFinalTeamId("");
    setFinalWord("");

    await reload();
  } catch (err) {
    setNotice(err.message);
  } finally {
    setVerifyingFinal(false);
  }
};
  const activeCount = teams.filter((t) => t.status === "active").length;
  const finishedCount = teams.filter((t) => t.status === "finished").length;

  return (
    <Shell role="EVENT CONTROL">
      <main className="control-page page-wrap">
        <div className="dash-heading">
          <div>
            <p className="eyebrow">MISSION CONTROL // SECURE</p>
            <h2>Command center</h2>
            <p className="muted">Event state, live signals, broadcasts and the winner board.</p>
          </div>
          <StatusPill />
        </div>
        <div className="control-actions">
          <button className="button primary" onClick={() => control("LIVE")} data-testid="start-event-button"><Radio size={16} /> Start</button>
          <button className="button ghost" onClick={() => control("PAUSED")} data-testid="pause-event-button">Pause</button>
          <button className="button ghost" onClick={() => control("LIVE")} data-testid="resume-event-button">Resume</button>
          <button className="button ghost" onClick={() => control("ENDED")} data-testid="end-event-button">End</button>
          <span className="live-state" data-testid="control-event-state"><span className="pulse-dot" /> {event.state}</span>
        </div>
        {notice && <div className="notice" data-testid="control-notice">{notice}</div>}
        <section className="bento">
          <div className="glass-card big-stat">
            <span className="metric-label">TEAMS ACTIVE</span>
            <strong data-testid="active-teams-stat">{String(activeCount).padStart(2, "0")}</strong>
            <span className="trend">{teams.length} registered</span>
          </div>
          <div className="glass-card big-stat">
            <span className="metric-label">TEAMS FINISHED</span>
            <strong data-testid="finished-teams-stat">{String(finishedCount).padStart(2, "0")}<span>/{teams.length}</span></strong>
            <div className="mini-bars"><i /><i /><i /><i /><i /><i /><i /></div>
          </div>
          <form className="glass-card status-list" onSubmit={broadcast} data-testid="broadcast-form">
            <div className="section-head">
              <span className="metric-label">BROADCAST MESSAGE</span>
              <Activity size={17} />
            </div>
            <label className="answer-label" style={{ marginTop: 12 }}>ANNOUNCEMENT
              <input value={announcement} onChange={(e) => setAnnouncement(e.target.value)} placeholder="Ten minutes remaining." data-testid="broadcast-input" />
            </label>
            <button className="button primary full" type="submit" data-testid="broadcast-button">Send to all teams</button>
          </form>
          <form
            className="glass-card status-list"
            onSubmit={verifyAudi2Finish}
            data-testid="audi2-final-form"
          >
            <div className="section-head">
              <span className="metric-label">
                AUDI 2 // FINAL EXTRACTION
              </span>
              <KeyRound size={17} />
            </div>

            <p className="muted" style={{ marginTop: 10 }}>
              Verify a team only after they physically return to Audi 2
              and solve the final extraction.
            </p>

            <label className="answer-label" style={{ marginTop: 12 }}>
              TEAM ID
              <input
                value={finalTeamId}
                onChange={(e) => setFinalTeamId(e.target.value.toUpperCase())}
                placeholder="LP-07"
                autoComplete="off"
              />
            </label>

            <label className="answer-label">
              FINAL WORD
              <input
                value={finalWord}
                onChange={(e) => setFinalWord(e.target.value.toUpperCase())}
                placeholder="Enter extracted word"
                autoComplete="off"
              />
            </label>

            <button
              className="button primary full"
              type="submit"
              disabled={verifyingFinal}
            >
              <KeyRound size={15} />
              {verifyingFinal ? "VERIFYING..." : "VERIFY FINAL EXTRACTION"}
            </button>
          </form>
          <div className="glass-card table-card">
            <div className="section-head">
              <span className="metric-label">TEAM FLEET</span>
              <Link to="/admin/teams" className="text-button" data-testid="view-teams-link">View all <ChevronRight size={14} /></Link>
            </div>
            {teams.slice(0, 6).map((t, i) => (
              <div className="team-row" key={t.id} data-testid={`team-row-${i}`}>
                <span className="team-avatar">{t.team_id.slice(-2)}</span>
                <strong>{t.team_id} · {t.team_name}</strong>
                <span className="team-progress">{t.status}</span>
                <span className={`status-dot ${t.status === "finished" ? "pink" : ""}`} />
              </div>
            ))}
            {!teams.length && <div className="empty-workspace"><p>Sign in as admin to see the fleet.</p></div>}
          </div>
        </section>
        <WinnerBoard />
      </main>
    </Shell>
  );
}
