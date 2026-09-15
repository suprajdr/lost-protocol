import { useState } from "react";
import { Link } from "react-router-dom";
import { ArrowRight, WifiOff } from "lucide-react";
import Shell from "@/components/Shell";
import { apiRequest, getTeamSession } from "@/lib/api";

export default function OfflineRedeem() {
  const [token, setToken] = useState("");
  const [notice, setNotice] = useState("");

  const redeem = async (event) => {
    event.preventDefault();
    setNotice("");
    if (!navigator.onLine) return setNotice("You are offline. Reconnect to redeem a verification token.");
    const session = getTeamSession();
    if (!session) return setNotice("Session expired. Log in again.");
    const code = token.split("-")[0] || "";
    try {
      const data = await apiRequest("/team/redeem-token", {
        method: "POST",
        body: JSON.stringify({ session_token: session.session_token, token: token.toUpperCase(), checkpoint_code: code.toUpperCase() }),
      });
      setNotice(data.message);
    } catch (err) {
      setNotice(err.message);
    }
  };

  return (
    <Shell role="TEAM // OFFLINE VERIFY">
      <main className="auth-page page-wrap">
        <Link to="/team/dashboard" className="back-link" data-testid="redeem-back-link">← Return to mission</Link>
        <section className="auth-card reveal">
          <div className="auth-symbol"><WifiOff /></div>
          <p className="eyebrow">VOLUNTEER VERIFICATION</p>
          <h2>Redeem an offline token</h2>
          <p className="muted">Completion remains server-validated. Enter the one-time token issued at your checkpoint.</p>
          <form onSubmit={redeem} data-testid="offline-redeem-form">
            <label>VERIFICATION TOKEN
              <input value={token} onChange={(e) => setToken(e.target.value.toUpperCase())} placeholder="C-AB12CD" data-testid="offline-token-input" required />
            </label>
            <button className="button primary full" type="submit" data-testid="offline-redeem-submit">Redeem token <ArrowRight size={16} /></button>
            {notice && <div className="notice" data-testid="offline-redeem-notice">{notice}</div>}
          </form>
        </section>
      </main>
    </Shell>
  );
}
