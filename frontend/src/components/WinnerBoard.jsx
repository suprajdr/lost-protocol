import { useEffect, useState } from "react";
import { Sparkles, Trophy, Radio } from "lucide-react";
import { authorizedRequest } from "@/lib/api";
import { supabase } from "@/lib/supabase";

function formatTime(value) {
  if (!value) return "--";

  return new Date(value).toLocaleTimeString([], {
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
  });
}

function formatDuration(seconds) {
  if (seconds === null || seconds === undefined) {
    return "--";
  }

  const minutes = Math.floor(seconds / 60);
  const remainingSeconds = seconds % 60;

  return `${minutes}m ${String(remainingSeconds).padStart(2, "0")}s`;
}

export default function WinnerBoard({ compact = false }) {
  const [board, setBoard] = useState(null);
  const [error, setError] = useState("");

  useEffect(() => {
    let cancelled = false;

    async function load() {
      try {
        const body = await authorizedRequest("/control/winner");

        if (!cancelled) {
          setBoard(body);
          setError("");
        }
      } catch (err) {
        if (!cancelled) {
          setError(err.message);
        }
      }
    }

    load();

    const channel = supabase
      .channel("winner-board")
      .on(
        "postgres_changes",
        {
          event: "*",
          schema: "public",
          table: "final_attempts",
        },
        load
      )
      .subscribe();

    const interval = setInterval(load, 15000);

    return () => {
      cancelled = true;
      supabase.removeChannel(channel);
      clearInterval(interval);
    };
  }, []);

  const finishOrder = board?.finish_order || [];
  const pending = board?.audi2_pending || [];

  return (
    <section
      className={`winner-board glass-card ${
        compact ? "compact" : ""
      }`}
      data-testid="winner-board"
    >
      <div className="section-head">
        <span className="metric-label">
          <Trophy size={13} />
          FINAL EXTRACTION // FINISH ORDER
        </span>

        <span className="workspace-status">
          AUDI 2 VERIFIED
        </span>
      </div>

      {error && (
        <div
          className="notice"
          data-testid="winner-error"
        >
          {error}
        </div>
      )}

      {!compact && pending.length > 0 && (
        <div style={{ marginTop: 18 }}>
          <div className="section-head">
            <span className="metric-label">
              <Radio size={13} />
              RETURNING TO AUDI 2
            </span>

            <span className="workspace-status">
              {pending.length} PENDING
            </span>
          </div>

          {pending.map((entry) => (
            <div
              className="winner-row"
              key={`pending-${entry.id}`}
            >
              <span className="winner-rank">--</span>

              <strong>
                {entry.team?.team_id || "TEAM"}
              </strong>

              <span className="muted">
                {entry.team?.team_name || ""}
              </span>

              <span className="team-progress">
                PROTOCOL SOLVED ·{" "}
                {formatTime(entry.protocol_solved_at)}
              </span>
            </div>
          ))}
        </div>
      )}

      <div style={{ marginTop: 18 }}>
        <div className="section-head">
          <span className="metric-label">
            OFFICIAL FINISH ORDER
          </span>
        </div>

        {finishOrder.length ? (
          finishOrder
            .slice(0, compact ? 3 : 10)
            .map((entry, index) => (
              <div
                className={`winner-row ${
                  index === 0 ? "champion" : ""
                }`}
                key={entry.id}
                data-testid={`winner-row-${index}`}
              >
                <span className="winner-rank">
                  {String(index + 1).padStart(2, "0")}
                </span>

                <strong>
                  {entry.team?.team_id || "TEAM"}
                </strong>

                <span className="muted">
                  {entry.team?.team_name || ""}
                </span>

                <span className="team-progress">
                  FINISHED {formatTime(entry.finished_at)}
                  {" · "}
                  EXTRACTION{" "}
                  {formatDuration(entry.extraction_seconds)}
                </span>
              </div>
            ))
        ) : (
          !error && (
            <div className="winner-empty">
              <Sparkles size={17} />

              <span>
                No team has completed the Audi 2 final
                extraction yet.
              </span>
            </div>
          )
        )}
      </div>
    </section>
  );
}