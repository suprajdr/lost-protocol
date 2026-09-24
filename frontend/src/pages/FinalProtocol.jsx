import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { ArrowRight, Sparkles, Undo2, Trash2 } from "lucide-react";
import Shell from "@/components/Shell";
import { apiRequest, getTeamSession } from "@/lib/api";

export default function FinalProtocol() {
  const nav = useNavigate();
  const session = getTeamSession();

  const [fragments, setFragments] = useState([]);
  const [answer, setAnswer] = useState([]);
  const [notice, setNotice] = useState("");
  const [complete, setComplete] = useState(false);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const loadFragments = async () => {
      if (!session) {
        nav("/team/login");
        return;
      }

      try {
        const data = await apiRequest(
          `/team/state?session_token=${encodeURIComponent(
            session.session_token
          )}`
        );

        const recovered = (data.fragments || []).map(
          (fragment) => fragment.value
        );

        setFragments(recovered);

        if (recovered.length !== 7) {
          setNotice(
            `Only ${recovered.length}/7 fragments recovered. Complete all nodes first.`
          );
        }
      } catch (err) {
        setNotice(err.message);
      } finally {
        setLoading(false);
      }
    };

    loadFragments();
  }, []);

  const addFragment = (fragment, index) => {
    if (complete) return;

    if (answer.some((item) => item.index === index)) return;

    setAnswer((current) => [
      ...current,
      {
        value: fragment,
        index,
      },
    ]);

    setNotice("");
  };

  const undo = () => {
    if (complete) return;
    setAnswer((current) => current.slice(0, -1));
    setNotice("");
  };

  const clear = () => {
    if (complete) return;
    setAnswer([]);
    setNotice("");
  };

  const submit = async () => {
    if (!navigator.onLine) {
      return setNotice("Final submission requires a live link.");
    }

    if (!session) {
      return nav("/team/login");
    }

    if (answer.length !== fragments.length || fragments.length !== 7) {
      return setNotice(
        "Use all 7 recovered fragments to reconstruct the master key."
      );
    }

    setNotice("");

    try {
      const requiredOrder = ["K", "R", "9", "7", "3", "\u25C7", "\u25B3"]; 
      const selectedOrder = answer.map((item) => item.value);

      const correctOrder = requiredOrder.every(
        (fragment, index) => selectedOrder[index] === fragment
      );

      /*
       * Convert the two shape fragments before sending:
       * △ = 3 sides
       * ♢ = 4 sides
       */
      const reconstructedKey = answer
  .map((item) => item.value)
  .join("");

      const data = await apiRequest("/team/final", {
        method: "POST",
        body: JSON.stringify({
          session_token: session.session_token,
          answer: reconstructedKey,
        }),
      });

      setNotice(data.message);

      if (data.valid) {
        setComplete(true);
        setNotice("");
      }
    } catch (err) {
      setNotice(err.message);
    }
  };
  if (complete) {
    return (
      <Shell role="TEAM // FINAL PROTOCOL">
        <main className="final-page page-wrap">

          <div className="final-orbit">
            <div className="orbit-core">
              <Sparkles size={28} />
              <strong>✓</strong>
              <span>PROTOCOL RECONSTRUCTED</span>
            </div>
          </div>

          <p className="eyebrow center">
            MASTER KEY ACCEPTED
          </p>

          <h2 className="center">
            RETURN TO <em>ORIGIN</em>
          </h2>

          <div
            className="glass-card final-card"
            style={{ textAlign: "center" }}
          >
            <span className="metric-label">
              FINAL TRANSMISSION
            </span>

            <h2 style={{ marginTop: "20px" }}>
              AUDI 2
            </h2>

            <p className="muted" style={{ marginTop: "14px" }}>
              The transmission began before you knew
              you were searching for it.
            </p>

            <p style={{ marginTop: "22px" }}>
              Seven fragments.
              <br />
              Seven channels.
              <br />
              The final signal is waiting at the origin.
            </p>

            <div
              style={{
                marginTop: "28px",
                padding: "18px",
                border: "1px solid rgba(255,255,255,0.12)",
                borderRadius: "12px",
              }}
            >
              <span className="metric-label">
                DEPTH KEY
              </span>

              <h3
                style={{
                  marginTop: "12px",
                  letterSpacing: "6px",
                }}
              >
                II · V · I · VII · IV · III · VI
              </h3>

              <p className="muted" style={{ marginTop: "12px" }}>
                Seven fragments. Seven channels.
                <br />
                Left to right.
                <br />
                Depth reveals what order conceals.
              </p>
            </div>

            <p
              className="muted"
              style={{ marginTop: "28px" }}
            >
              Return to Audi 2 and complete the final extraction.
              <br />
              Your protocol has not been fully restored yet.
            </p>

          </div>
        </main>
      </Shell>
    );
  }
  return (
    <Shell role="TEAM // FINAL PROTOCOL">
      <main className="final-page page-wrap">
        <div className="final-orbit">
          <div className="orbit-core">
            <Sparkles size={28} />

            <strong>{complete ? "✔" : "7/7"}</strong>

            <span>
              {complete ? "PROTOCOL RECONSTRUCTED" : "NODES RECOVERED"}
            </span>
          </div>
        </div>

        <p className="eyebrow center">
          {complete ? "MASTER KEY ACCEPTED" : "RECOVERY COMPLETE"}
        </p>

        <h2 className="center">
          FINAL <em>PROTOCOL</em>
        </h2>

        <p className="muted center">
          Seven fragments have survived the protocol.
          Their recovery order is not their true order.
        </p>

        <div className="glass-card final-card">
          <span className="metric-label">RECOVERED FRAGMENTS</span>

          <div
            style={{
              display: "flex",
              flexWrap: "wrap",
              gap: "12px",
              justifyContent: "center",
              margin: "20px 0 28px",
            }}
          >
            {loading ? (
              <span className="muted">Recovering fragments...</span>
            ) : (
              fragments.map((fragment, index) => {
                const used = answer.some(
                  (item) => item.index === index
                );

                return (
                  <button
                    key={`${fragment}-${index}`}
                    type="button"
                    onClick={() => addFragment(fragment, index)}
                    disabled={used || complete}
                    style={{
                      width: "58px",
                      height: "58px",
                      fontSize: "22px",
                      fontWeight: 700,
                      borderRadius: "10px",
                      cursor: used ? "default" : "pointer",
                      opacity: used ? 0.35 : 1,
                    }}
                  >
                    {fragment}
                  </button>
                );
              })
            )}
          </div>

          <div
            style={{
              margin: "0 0 28px",
              padding: "18px",
              border: "1px solid rgba(255,255,255,0.12)",
              borderRadius: "12px",
            }}
          >
            <span className="metric-label">FINAL TRANSMISSION</span>

            <p className="center" style={{ marginTop: "14px" }}>
              <strong>
                THE ROUTE WAS YOURS. THE PROTOCOL IS ONE.
              </strong>
            </p>

            <p className="muted center">
              Seven fragments. Seven memories.
              Restore them by retracing the protocol.
            </p>

            <p className="muted">
              Begin where the Keeper judged your secret.
              <br /><br />

              Then return to where the number was discovered from the ECE staff board.
              <br /><br />

              Follow the signal to where thirty seconds of memory decided your fate.
              <br /><br />

              Seek the place where five letters rested among the green.
              <br /><br />

              Continue where images led you to the hidden signal.
              <br /><br />

              Look again beneath the stars, where you chose between SAFE and RISK.
              <br /><br />

              End where your team moved as one to control the cups.
            </p>

            <p className="center" style={{ marginBottom: 0 }}>
              <strong>
            
              </strong>
            </p>
          </div>

          <span className="metric-label">MASTER KEY</span>

          <div
            style={{
              minHeight: "64px",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              gap: "10px",
              flexWrap: "wrap",
              margin: "12px 0",
              padding: "12px",
              border: "1px solid rgba(255,255,255,0.15)",
              borderRadius: "10px",
            }}
          >
            {answer.length === 0 ? (
              <span className="muted">
                Tap the fragments above to construct the key
              </span>
            ) : (
              answer.map((item, index) => (
                <strong
                  key={`${item.value}-${item.index}-${index}`}
                  style={{ fontSize: "24px" }}
                >
                  {item.value}
                </strong>
              ))
            )}
          </div>

          <div
            style={{
              display: "flex",
              gap: "10px",
              marginBottom: "16px",
            }}
          >
            <button
              type="button"
              className="button full"
              onClick={undo}
              disabled={answer.length === 0 || complete}
            >
              <Undo2 size={16} />
              Undo
            </button>

            <button
              type="button"
              className="button full"
              onClick={clear}
              disabled={answer.length === 0 || complete}
            >
              <Trash2 size={16} />
              Clear
            </button>
          </div>

          <button
            className="button primary full"
            onClick={submit}
            disabled={
              loading ||
              fragments.length !== 7 ||
              answer.length !== 7 ||
              complete
            }
            data-testid="submit-master-key-button"
          >
            Submit master key
            <ArrowRight size={16} />
          </button>

          {notice && (
            <p
              className="notice"
              data-testid="final-submission-notice"
            >
              {notice}
            </p>
          )}

          
        </div>
      </main>
    </Shell>
  );
}