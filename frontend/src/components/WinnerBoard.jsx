import { useEffect, useState } from "react";
import { Sparkles, Trophy } from "lucide-react";
import { authorizedRequest } from "@/lib/api";
import { supabase } from "@/lib/supabase";

export default function WinnerBoard({ compact = false }) {
  const [board, setBoard] = useState(null);
  const [error, setError] = useState("");

  useEffect(() => {
    let cancelled = false;
    async function load() {
      try {
        const body = await authorizedRequest("/control/winner");
        if (!cancelled) setBoard(body);
      } catch (err) {
        if (!cancelled) setError(err.message);
      }
    }
    load();
    const channel = supabase
      .channel("winner-board")
      .on("postgres_changes", { event: "INSERT", schema: "public", table: "final_attempts" }, load)
      .subscribe();
    const interval = setInterval(load, 15000);
    return () => {
      cancelled = true;
      supabase.removeChannel(channel);
      clearInterval(interval);
    };
  }, []);

  const list = board?.finish_order || [];
  return (
    <section className={`winner-board glass-card ${compact ? "compact" : ""}`} data-testid="winner-board">
      <div className="section-head">
        <span className="metric-label"><Trophy size={13} /> FINAL PROTOCOL // FINISH ORDER</span>
        <span className="workspace-status">SERVER TIME</span>
      </div>
      {error && <div className="notice" data-testid="winner-error">{error}</div>}
      {list.length ? (
        list.slice(0, compact ? 3 : 10).map((entry, index) => (
          <div className={`winner-row ${index === 0 ? "champion" : ""}`} key={entry.id} data-testid={`winner-row-${index}`}>
            <span className="winner-rank">{String(index + 1).padStart(2, "0")}</span>
            <strong>{entry.team?.team_id || "TEAM"}</strong>
            <span className="muted">{entry.team?.team_name || ""}</span>
            <span className="team-progress">{entry.score} pts · {new Date(entry.attempted_at).toLocaleTimeString()}</span>
          </div>
        ))
      ) : (
        !error && (
          <div className="winner-empty">
            <Sparkles size={17} />
            <span>Awaiting a valid final completion. Winner = earliest server-recorded final submission; score is the tie-breaker.</span>
          </div>
        )
      )}
    </section>
  );
}
