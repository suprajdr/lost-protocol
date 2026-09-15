import { useCallback, useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { Sparkles } from "lucide-react";
import Shell from "@/components/Shell";
import { LivePulse } from "@/components/Shell";
import AdminEditor, { EDIT_FIELDS } from "@/pages/AdminEditor";
import { authorizedRequest } from "@/lib/api";

const NAV_ITEMS = ["teams", "checkpoints", "hints", "routes", "volunteers", "announcements", "settings", "audit-log"];

export default function AdminWorkspace() {
  const { resource = "teams" } = useParams();
  const [rows, setRows] = useState([]);
  const [message, setMessage] = useState("");
  const [editing, setEditing] = useState(null);

  const load = useCallback(async () => {
    setMessage("");
    try {
      const body = await authorizedRequest(`/admin/${resource}`);
      setRows(body);
    } catch (err) {
      setMessage(err.message);
    }
  }, [resource]);

  useEffect(() => {
    load();
  }, [load]);

  const seed = async () => {
    try {
      const body = await authorizedRequest("/admin/seed", "POST", {});
      setMessage(`Seed complete: ${body.teams} teams / ${body.checkpoints} checkpoints`);
      load();
    } catch (err) {
      setMessage(err.message);
    }
  };

  const removeRow = async (id) => {
    if (!window.confirm("Delete this record permanently?")) return;
    try {
      await authorizedRequest(`/admin/${resource}/${id}`, "DELETE");
      load();
    } catch (err) {
      setMessage(err.message);
    }
  };

  const title = resource === "audit-log" ? "Audit log" : resource === "settings" ? "Event settings" : resource[0].toUpperCase() + resource.slice(1);
  const canEdit = Object.keys(EDIT_FIELDS).includes(resource) || resource === "settings";
  const primaryLabel = resource === "teams" && !rows.length ? "Seed event data" : canEdit ? "Add record" : "Refresh";
  const primaryAction = resource === "teams" && !rows.length ? seed : canEdit ? () => setEditing({}) : load;

  const renderRow = (row, index) => {
    const key = row.id || row.key || `${index}`;
    const primary = row.team_id || row.code || row.display_name || row.name || row.key || row.action || row.message || "Record";
    const secondary = row.team_name || row.content || row.actor_type || (row.checkpoint_order && row.checkpoint_order.join("→")) || (row.value && JSON.stringify(row.value).slice(0, 40)) || "";
    const status = row.status || (row.active === false ? "INACTIVE" : "LIVE");
    return (
      <div className="workspace-row" key={key} data-testid={`row-${resource}-${index}`}>
        <span className="row-index">{String(index + 1).padStart(2, "0")}</span>
        <strong>{primary}</strong>
        <span className="muted">{secondary}</span>
        <span className="workspace-status">{status}</span>
        {canEdit && (
          <span className="row-actions">
            <button className="text-button" onClick={() => setEditing(row)} data-testid={`edit-${resource}-${index}`}>Edit</button>
            {row.id && <button className="text-button danger" onClick={() => removeRow(row.id)} data-testid={`delete-${resource}-${index}`}>Delete</button>}
          </span>
        )}
      </div>
    );
  };

  return (
    <Shell role="SUPER ADMIN">
      <main className="workspace page-wrap">
        <div className="workspace-heading">
          <div>
            <p className="eyebrow">ADMIN WORKSPACE // DATABASE CONTROL</p>
            <h2>{title}</h2>
            <p className="muted">Live Supabase records, guarded by operator access and audit trails.</p>
          </div>
          <button className="button primary" onClick={primaryAction} data-testid={`${resource}-primary-action`}>{primaryLabel}</button>
        </div>
        <nav className="workspace-nav" data-testid="admin-workspace-nav">
          {NAV_ITEMS.map((item) => (
            <Link className={resource === item ? "active" : ""} key={item} to={`/admin/${item}`} data-testid={`admin-nav-${item}`}>
              {item.replace("-", " ")}
            </Link>
          ))}
        </nav>
        {message && <div className="notice" data-testid="workspace-message">{message}</div>}
        <section className="workspace-table glass-card" data-testid={`${resource}-workspace`}>
          <div className="section-head">
            <span className="metric-label">{rows.length ? `${rows.length} RECORDS` : "NO RECORDS LOADED"}</span>
            <LivePulse />
          </div>
          {rows.length ? rows.map(renderRow) : (
            <div className="empty-workspace">
              <Sparkles size={20} />
              <p>{canEdit ? "No records yet. Use the button above to add one." : "Connect an operator session to load this workspace."}</p>
              <span className="muted">Every change is stored with an audit trail.</span>
            </div>
          )}
        </section>
        {editing !== null && canEdit && (
          <AdminEditor
            resource={resource === "settings" ? "event_settings" : resource}
            row={editing}
            onClose={() => setEditing(null)}
            onSaved={() => {
              setEditing(null);
              load();
            }}
          />
        )}
      </main>
    </Shell>
  );
}
