import { useState } from "react";
import { ArrowRight, X } from "lucide-react";
import { authorizedRequest } from "@/lib/api";

export const EDIT_FIELDS = {
  teams: [
    { name: "team_id", label: "Team ID", placeholder: "LP-01" },
    { name: "team_name", label: "Team name", placeholder: "Night Shift" },
    { name: "pin", label: "PIN (create/rotate)", placeholder: "1234", optional: true },
    { name: "status", label: "Status", options: ["active", "finished", "disabled"] },
  ],
  checkpoints: [
    { name: "code", label: "Code", placeholder: "A" },
    { name: "name", label: "Name", placeholder: "The Archive" },
    { name: "clue", label: "Clue", type: "textarea" },
    { name: "challenge", label: "Challenge", type: "textarea" },
    { name: "answer", label: "Answer (bcrypt on save)", optional: true },
    { name: "fragment", label: "Fragment symbol", placeholder: "△" },
    { name: "points", label: "Points", type: "number", placeholder: "120" },
  ],
  hints: [
    { name: "checkpoint_id", label: "Checkpoint ID (UUID)" },
    { name: "name", label: "Name", placeholder: "Hint 1" },
    { name: "content", label: "Content", type: "textarea" },
    { name: "penalty", label: "Penalty", type: "number", placeholder: "-15" },
  ],
  routes: [
    { name: "name", label: "Route name", placeholder: "ROTATION A" },
    { name: "checkpoint_order", label: "Checkpoint order (comma-separated codes)", placeholder: "A,B,C,D,E,F,G" },
  ],
  announcements: [
    { name: "message", label: "Message", type: "textarea" },
    { name: "active", label: "Active", options: ["true", "false"] },
  ],
  event_settings: [
    { name: "key", label: "Setting key" },
    { name: "value", label: "Value (JSON)", type: "textarea", placeholder: '{"hash":"..."}' },
  ],
};

function normalize(resource, form) {
  const clean = { ...form };
  if (resource === "announcements" && "active" in clean) clean.active = clean.active === "true" || clean.active === true;
  if (resource === "checkpoints" && clean.points) clean.points = Number(clean.points);
  if (resource === "hints" && clean.penalty !== undefined && clean.penalty !== "") clean.penalty = Number(clean.penalty);
  if (resource === "event_settings" && typeof clean.value === "string") {
    try { clean.value = JSON.parse(clean.value); } catch {}
  }
  return clean;
}

export default function AdminEditor({ resource, row, onClose, onSaved }) {
  const fields = EDIT_FIELDS[resource] || [];
  const [form, setForm] = useState(() => {
    const initial = {};
    fields.forEach((f) => {
      const val = row?.[f.name];
      if (val === undefined || val === null) return;
      initial[f.name] = Array.isArray(val) ? val.join(",") : typeof val === "object" ? JSON.stringify(val) : String(val);
    });
    return initial;
  });
  const [notice, setNotice] = useState("");
  const [saving, setSaving] = useState(false);
  const isEdit = Boolean(row && (row.id || row.key));

  const save = async (event) => {
    event.preventDefault();
    setNotice("");
    setSaving(true);
    try {
      const payload = normalize(resource, form);
      const targetId = row?.id || row?.key;
      if (isEdit && targetId) {
        await authorizedRequest(`/admin/${resource}/${targetId}`, "PATCH", { payload });
      } else {
        await authorizedRequest(`/admin/${resource}`, "POST", { payload });
      }
      onSaved();
    } catch (err) {
      setNotice(err.message);
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="modal-veil" onClick={onClose}>
      <section className="modal-card glass-card reveal" onClick={(e) => e.stopPropagation()} data-testid={`${resource}-editor-modal`}>
        <div className="modal-head">
          <div>
            <p className="eyebrow">OPERATOR EDITOR</p>
            <h3>{isEdit ? "Update" : "Create"} {resource.replace("_", " ")}</h3>
          </div>
          <button className="icon-button" onClick={onClose} aria-label="Close" data-testid="editor-close-button"><X size={18} /></button>
        </div>
        <form onSubmit={save} data-testid={`${resource}-editor-form`}>
          {fields.map((f) => (
            <label key={f.name}>
              {f.label.toUpperCase()}
              {f.options ? (
                <select
                  data-testid={`editor-${f.name}-input`}
                  value={form[f.name] || ""}
                  onChange={(e) => setForm({ ...form, [f.name]: e.target.value })}
                >
                  <option value="">—</option>
                  {f.options.map((opt) => <option value={opt} key={opt}>{opt}</option>)}
                </select>
              ) : f.type === "textarea" ? (
                <textarea
                  data-testid={`editor-${f.name}-input`}
                  value={form[f.name] || ""}
                  onChange={(e) => setForm({ ...form, [f.name]: e.target.value })}
                  placeholder={f.placeholder || ""}
                  rows={3}
                />
              ) : (
                <input
                  data-testid={`editor-${f.name}-input`}
                  type={f.type || "text"}
                  value={form[f.name] || ""}
                  onChange={(e) => setForm({ ...form, [f.name]: e.target.value })}
                  placeholder={f.placeholder || ""}
                />
              )}
            </label>
          ))}
          <button className="button primary full" type="submit" disabled={saving} data-testid={`${resource}-editor-save`}>
            {saving ? "Saving…" : isEdit ? "Update record" : "Create record"} <ArrowRight size={16} />
          </button>
          {notice && <div className="notice" data-testid="editor-notice">{notice}</div>}
        </form>
      </section>
    </div>
  );
}
