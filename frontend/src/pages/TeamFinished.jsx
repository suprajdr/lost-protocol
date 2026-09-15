import { Link } from "react-router-dom";
import { Trophy } from "lucide-react";
import Shell from "@/components/Shell";
import { getTeamSession } from "@/lib/api";

export default function TeamFinished() {
  const session = getTeamSession();
  return (
    <Shell role="TEAM // COMPLETE">
      <main className="final-page page-wrap">
        <div className="final-orbit">
          <div className="orbit-core">
            <Trophy size={28} />
            <strong>OK</strong>
            <span>PROTOCOL ACTIVATED</span>
          </div>
        </div>
        <h2 className="center">Mission complete, <em>{session?.team_name || "operative"}</em></h2>
        <p className="muted center">Your final protocol timestamp is recorded on the server. Watch the leaderboard for the winner announcement.</p>
        <div className="glass-card final-card">
          <p className="muted small center">You may return to base. Mission Control will contact your team if you are the earliest valid completion.</p>
          <Link to="/" className="button ghost full" data-testid="return-home-link">Return to home</Link>
        </div>
      </main>
    </Shell>
  );
}
