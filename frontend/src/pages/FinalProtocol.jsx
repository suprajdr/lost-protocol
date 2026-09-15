import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { ArrowRight, Sparkles } from "lucide-react";
import Shell from "@/components/Shell";
import { apiRequest, getTeamSession } from "@/lib/api";

export default function FinalProtocol() {
  const nav = useNavigate();
  const session = getTeamSession();
  const [answer, setAnswer] = useState("");
  const [notice, setNotice] = useState("");
  const [complete, setComplete] = useState(false);

  const submit = async () => {
    if (!navigator.onLine) return setNotice("Final submission requires a live link.");
    if (!session) return nav("/team/login");
    setNotice("");
    try {
      const data = await apiRequest("/team/final", {
        method: "POST",
        body: JSON.stringify({ session_token: session.session_token, answer }),
      });
      setNotice(data.message);
      if (data.valid) {
        setComplete(true);
        setTimeout(() => nav("/team/finished"), 2000);
      }
    } catch (err) {
      setNotice(err.message);
    }
  };

  return (
    <Shell role="TEAM // FINAL PROTOCOL">
      <main className="final-page page-wrap">
        <div className="final-orbit">
          <div className="orbit-core">
            <Sparkles size={28} />
            <strong>{complete ? "✔" : "7/7"}</strong>
            <span>{complete ? "PROTOCOL ACTIVATED" : "NODES RECOVERED"}</span>
          </div>
        </div>
        <p className="eyebrow center">{complete ? "FINAL PROTOCOL ACTIVATED" : "RECOVERY COMPLETE"}</p>
        <h2 className="center">FINAL <em>PROTOCOL</em></h2>
        <p className="muted center">Your fragments are assembled. The last lock is server-verified.</p>
        <div className="glass-card final-card">
          <span className="metric-label">MASTER KEY TRANSMISSION</span>
          <input data-testid="master-key-input" value={answer} onChange={(e) => setAnswer(e.target.value)} placeholder="Enter the reconstructed key" />
          <button className="button primary full" onClick={submit} data-testid="submit-master-key-button">Submit master key <ArrowRight size={16} /></button>
          {notice && <p className="notice" data-testid="final-submission-notice">{notice}</p>}
          <p className="muted center small">Winner = earliest valid completion; score is the tie-breaker.</p>
        </div>
      </main>
    </Shell>
  );
}
