import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { ArrowRight, ShieldCheck, Sparkles } from "lucide-react";
import Shell from "@/components/Shell";
import { apiRequest } from "@/lib/api";

export default function Landing() {
  const [event, setEvent] = useState({ state: "STANDBY", name: "THE LOST PROTOCOL" });
  useEffect(() => {
    apiRequest("/event").then(setEvent).catch(() => {});
  }, []);
  const locked = event.state !== "LIVE";
  return (
    <Shell>
      <main className="landing page-wrap">
        <section className="landing-copy reveal">
          <p className="eyebrow"><span className="pulse-dot" /> COLLEGE CAMPUS // LIVE PROTOCOL</p>
          <h1>THE LOST<br /><em>PROTOCOL</em></h1>
          <p className="lede">
            {locked
              ? "A campus-wide mystery is loading. Mission Control will unlock the gate when the countdown ends."
              : "The gate is open. Enter your team channel and continue the recovery of the seven nodes."}
          </p>
          <div className="landing-actions">
            <Link className="button primary" to="/team/login" data-testid="team-access-button">Team access <ArrowRight size={17} /></Link>
            <Link className="button ghost" to="/admin/login" data-testid="control-access-button">Control room <ShieldCheck size={16} /></Link>
            <Link className="button ghost" to="/volunteer/login" data-testid="volunteer-access-button">Volunteer</Link>
          </div>
        </section>
        <section className="portal-panel reveal delay-2">
          <div className="portal-ring">
            <div className="portal-core"><Sparkles size={30} /><span>LP</span></div>
          </div>
          <p className="panel-kicker">SIGNAL DETECTED</p>
          <p className="panel-value">7 nodes / 1 protocol</p>
          <div className="signal-line"><span /><span /><span /><span /><span /></div>
          <p className="panel-note">The campus is the map.<br />Your team is the variable.</p>
        </section>
        <section className="entry-grid reveal delay-3">
          <div><span className="metric-label">PROTOCOL STATE</span><strong data-testid="event-state">{event.state}</strong></div>
          <div><span className="metric-label">CHECKPOINTS</span><strong data-testid="checkpoint-count">07</strong></div>
          <div><span className="metric-label">ACCESS</span><strong>SECURED</strong></div>
        </section>
      </main>
    </Shell>
  );
}
