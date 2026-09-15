import { useState, useEffect } from "react";
import { ArrowRight, CircleHelp, ScanLine, Shield, Zap, Clock } from "lucide-react";
import { apiRequest, formatDetail } from "@/lib/api";

function useSecondsElapsed(startedAt) {
  const [secs, setSecs] = useState(0);
  useEffect(() => {
    if (!startedAt) return;
    const t = new Date(startedAt).getTime();
    const tick = () => setSecs(Math.max(0, Math.floor((Date.now() - t) / 1000)));
    tick();
    const id = setInterval(tick, 1000);
    return () => clearInterval(id);
  }, [startedAt]);
  return secs;
}

export function CipherCard({ session, current, onSubmit, onHint }) {
  const [answer, setAnswer] = useState("");
  return (
    <>
      <div className="clue-copy">
        <span className="metric-label">CIPHER TRANSMISSION</span>
        <p data-testid="cipher-display" style={{ fontFamily: "'JetBrains Mono', monospace", fontSize: 18, letterSpacing: 2, color: "#ff9dca" }}>
          {current.cipher_display || current.clue}
        </p>
        <span className="metric-label">CLUE</span>
        <p className="muted">{current.clue}</p>
        {current.cipher_hint && (
          <>
            <span className="metric-label">DECODING HINT</span>
            <p className="muted">{current.cipher_hint}</p>
          </>
        )}
        <span className="metric-label">CHALLENGE</span>
        <p className="muted">{current.challenge}</p>
      </div>
      <label className="answer-label">VERIFICATION CODE
        <input data-testid="answer-input" value={answer} onChange={(e) => setAnswer(e.target.value)} placeholder="e.g. Enter verification code" />
      </label>
      <button className="button primary full" onClick={() => onSubmit(answer)} data-testid="submit-answer-button">
        <Zap size={16} /> Transmit code
      </button>
    </>
  );
}

export function AnswerCard({ current, onSubmit }) {
  const [answer, setAnswer] = useState("");
  return (
    <>
      <div className="clue-copy">
        <span className="metric-label">TRANSMISSION // CLUE</span>
        <p data-testid="current-clue">{current.clue}</p>
        <span className="metric-label">CHALLENGE</span>
        <p className="muted">{current.challenge}</p>
      </div>
      <label className="answer-label">YOUR RESPONSE
        <input data-testid="answer-input" value={answer} onChange={(e) => setAnswer(e.target.value)} placeholder="Enter decoded phrase" />
      </label>
      <button className="button primary full" onClick={() => onSubmit(answer)} data-testid="submit-answer-button">
        <Zap size={16} /> Transmit answer
      </button>
    </>
  );
}

export function VolunteerWaitCard({ current, label = "AWAITING VOLUNTEER VERIFICATION" }) {
  const elapsed = useSecondsElapsed(current.metadata?.started_at);
  return (
    <div className="volunteer-wait" data-testid="volunteer-wait-card">
      <div className="clue-copy">
        <span className="metric-label">MISSION BRIEFING</span>
        <p data-testid="current-clue">{current.clue}</p>
        <span className="metric-label">CHALLENGE</span>
        <p className="muted">{current.challenge}</p>
      </div>
      <div className="notice"><Clock size={13} /> {label} {current.volunteer_state === "in_progress" ? `· in progress ${elapsed}s` : "· find the volunteer for this node"}</div>
      {current.attempts > 0 && <div className="notice" data-testid="attempts-notice">Attempts: {current.attempts} · penalty {current.penalty} pts</div>}
    </div>
  );
}

export function KeeperCard({ current }) {
  return (
    <>
      <div className="clue-copy">
        <span className="metric-label">FIND THE KEEPER</span>
        <p style={{ fontSize: 32, letterSpacing: 4, color: "#ff9dca" }} data-testid="keeper-symbol">{current.symbol || "♜"}</p>
        <span className="metric-label">PHRASE</span>
        <p data-testid="current-clue" style={{ fontStyle: "italic" }}>“{current.phrase || "Did the protocol survive?"}”</p>
        <span className="metric-label">CHALLENGE</span>
        <p className="muted">{current.challenge}</p>
      </div>
      <div className="notice"><Shield size={13} /> One keeper. One truth. The keeper will PASS or FAIL your team on their device.</div>
      {current.attempts > 0 && <div className="notice">Attempts: {current.attempts} · penalty {current.penalty} pts</div>}
    </>
  );
}

export function QRScanCard({ session, current, onScan, onSubmit }) {
  const [nodeToken, setNodeToken] = useState("");
  const [answer, setAnswer] = useState("");
  const scanned = !!current.node_scanned;
  return (
    <>
      <div className="clue-copy">
        <span className="metric-label">VISUAL TRACE</span>
        <p data-testid="current-clue">{current.clue}</p>
        <span className="metric-label">CHALLENGE</span>
        <p className="muted">{current.challenge}</p>
        {(current.asset_urls || []).length > 0 && (
          <div className="asset-grid" data-testid="asset-grid">
            {current.asset_urls.map((u, i) => <img key={i} src={u} alt="" />)}
          </div>
        )}
      </div>
      {!scanned ? (
        <>
          <label className="answer-label">NODE QR CODE
            <input data-testid="qr-input" value={nodeToken} onChange={(e) => setNodeToken(e.target.value)} placeholder="Scan or paste the LP-NODE-* token" />
          </label>
          <button className="button primary full" onClick={() => onScan(nodeToken)} data-testid="scan-node-button">
            <ScanLine size={16} /> Verify node
          </button>
        </>
      ) : (
        <>
          <div className="notice" data-testid="node-recognized-notice">✔ Node recognized. Enter the verification.</div>
          <label className="answer-label">VERIFICATION
            <input data-testid="answer-input" value={answer} onChange={(e) => setAnswer(e.target.value)} placeholder="Enter the reading" />
          </label>
          <button className="button primary full" onClick={() => onSubmit(answer)} data-testid="submit-answer-button">
            <Zap size={16} /> Transmit answer
          </button>
        </>
      )}
    </>
  );
}

export function RiskChoiceCard({ current, onChoose, onSubmit }) {
  const [answer, setAnswer] = useState("");
  const choice = current.choice;
  return (
    <>
      <div className="clue-copy">
        <span className="metric-label">RISK PROTOCOL</span>
        <p data-testid="current-clue">{current.clue}</p>
        <span className="metric-label">CHALLENGE</span>
        <p className="muted">{current.challenge}</p>
      </div>
      {!choice ? (
        <div className="risk-choice" data-testid="risk-choice-panel">
          <button className="risk-safe" onClick={() => onChoose("safe")} data-testid="choose-safe-button">
            <strong>SAFE</strong>
            <span className="muted">+{current.safe_points} pts · easier clue</span>
          </button>
          <button className="risk-danger" onClick={() => onChoose("risk")} data-testid="choose-risk-button">
            <strong>RISK</strong>
            <span className="muted">+{current.risk_points} pts · penalty {current.risk_penalty} on failure</span>
          </button>
        </div>
      ) : (
        <>
          <div className="notice" data-testid="risk-choice-locked">
            🔒 Choice locked: <strong style={{ color: "#ff9dca" }}>{choice.toUpperCase()}</strong>
          </div>
          <div className="clue-copy" style={{ marginTop: 12 }}>
            <span className="metric-label">{choice.toUpperCase()} PATH CLUE</span>
            <p data-testid="path-clue">{current.path_clue}</p>
          </div>
          <label className="answer-label">YOUR RESPONSE
            <input data-testid="answer-input" value={answer} onChange={(e) => setAnswer(e.target.value)} placeholder="Enter your answer" />
          </label>
          <button className="button primary full" onClick={() => onSubmit(answer)} data-testid="submit-answer-button">
            <Zap size={16} /> Transmit answer
          </button>
          {current.attempts > 0 && <div className="notice" data-testid="attempts-notice">Attempts: {current.attempts} · penalty {current.penalty} pts</div>}
        </>
      )}
    </>
  );
}

export function GridMemoryCard({ current }) {
  const grid = current.grid_visible ? (current.grid || []) : null;
  return (
    <>
      <div className="clue-copy">
        <span className="metric-label">COMMUNICATION BLACKOUT</span>
        <p data-testid="current-clue">{current.clue}</p>
        <span className="metric-label">CHALLENGE</span>
        <p className="muted">{current.challenge}</p>
      </div>
      {grid ? (
        <div className="memory-grid" data-testid="memory-grid">
          {grid.map((row, ri) => (
            <div className="memory-row" key={ri}>
              {row.map((cell, ci) => <span key={ci}>{cell}</span>)}
            </div>
          ))}
        </div>
      ) : (
        <div className="notice" data-testid="grid-hidden">Grid hidden. Await the volunteer's DISPLAY signal — you have ~{Math.floor((current.display_ms || 20000)/1000)}s to memorize it.</div>
      )}
      <div className="notice">The volunteer will run the recall quiz on their device. PASS: node completes. FAIL: retry with a small penalty.</div>
      {current.attempts > 0 && <div className="notice">Attempts: {current.attempts} · penalty {current.penalty} pts</div>}
    </>
  );
}
