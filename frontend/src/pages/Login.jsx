import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { ArrowRight, KeyRound, LockKeyhole } from "lucide-react";
import Shell from "@/components/Shell";
import { API, apiRequest, saveTeamSession } from "@/lib/api";
import { supabase } from "@/lib/supabase";

export default function Login({ type = "team" }) {
  const [teamId, setTeamId] = useState("");
  const [pin, setPin] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const nav = useNavigate();
  const isTeam = type === "team";

  const submit = async (event) => {
    event.preventDefault();
    setError("");
    try {
      if (isTeam) {
        const data = await apiRequest("/team/login", {
          method: "POST",
          body: JSON.stringify({ team_id: teamId.trim().toUpperCase(), pin }),
        });
        saveTeamSession(data);
        nav("/team/dashboard");
      } else {
        const { error: authError } = await supabase.auth.signInWithPassword({ email, password });
        if (authError) throw authError;
        nav(type === "volunteer" ? "/volunteer/dashboard" : "/admin/dashboard");
      }
    } catch (err) {
      setError(err.message || "Access denied");
    }
  };

  return (
    <Shell role={isTeam ? "TEAM GATEWAY" : "CONTROL GATEWAY"}>
      <main className="auth-page page-wrap">
        <Link to="/" className="back-link" data-testid="login-back-link">← Return to signal</Link>
        <section className="auth-card reveal">
          <div className="auth-symbol">{isTeam ? <KeyRound /> : <LockKeyhole />}</div>
          <p className="eyebrow">{isTeam ? "PARTICIPANT CHANNEL" : "AUTHORIZED PERSONNEL"}</p>
          <h2>{isTeam ? "Enter your team code" : "Identify yourself"}</h2>
          <p className="muted">{isTeam ? "Your route is waiting beyond the gate." : "Supabase-secured access to mission control."}</p>
          <form onSubmit={submit} data-testid={`${type}-login-form`}>
            {isTeam ? (
              <>
                <label>TEAM ID<input data-testid="team-id-input" value={teamId} onChange={(e) => setTeamId(e.target.value)} placeholder="LP-01" required /></label>
                <label>MISSION PIN<input data-testid="team-pin-input" value={pin} onChange={(e) => setPin(e.target.value)} placeholder="••••" type="password" required /></label>
              </>
            ) : (
              <>
                <label>EMAIL<input data-testid="auth-email-input" type="email" value={email} onChange={(e) => setEmail(e.target.value)} placeholder="operator@college.edu" required /></label>
                <label>PASSWORD<input data-testid="auth-password-input" type="password" value={password} onChange={(e) => setPassword(e.target.value)} placeholder="••••••••" required /></label>
              </>
            )}
            {error && <div className="error-message" data-testid="login-error">{error}</div>}
            <button className="button primary full" type="submit" data-testid="login-submit-button">Open channel <ArrowRight size={17} /></button>
          </form>
          <p className="muted small" style={{ marginTop: 22 }}>
            Backend: <code>{API}</code>
          </p>
        </section>
      </main>
    </Shell>
  );
}
