import { useEffect, useMemo, useState } from "react";

import { api } from "../lib/api";

type AuditEvent = {
  id: string;
  actor_user_id: string | null;
  action: string;
  entity_type: string;
  entity_id: string | null;
  event_metadata: Record<string, unknown>;
  occurred_at: string;
};

type TeamMember = {
  user_id: string;
  name: string;
  email: string;
};

export default function AuditViewer({ team }: { team: TeamMember[] }) {
  const [events, setEvents] = useState<AuditEvent[]>([]);
  const [action, setAction] = useState("");
  const [entityType, setEntityType] = useState("");
  const [actorId, setActorId] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const userMap = useMemo(
    () => new Map(team.map((member) => [member.user_id, member])),
    [team],
  );

  async function load() {
    setBusy(true);
    setError(null);
    try {
      const params = new URLSearchParams();
      if (action) params.set("action", action);
      if (entityType) params.set("entity_type", entityType);
      if (actorId) params.set("actor_user_id", actorId);
      params.set("limit", "200");
      const suffix = params.toString() ? "?" + params.toString() : "";
      setEvents(await api<AuditEvent[]>("/api/v1/audit-events" + suffix));
    } catch {
      setError("Não foi possível carregar a auditoria.");
    } finally {
      setBusy(false);
    }
  }

  useEffect(() => {
    void load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const actions = [...new Set(events.map((event) => event.action))].sort();
  const entityTypes = [...new Set(events.map((event) => event.entity_type))].sort();

  return (
    <section className="section-card">
      <div className="section-heading">
        <div>
          <span className="eyebrow">Governança</span>
          <h2>Auditoria</h2>
          <p className="section-copy">
            Histórico de alterações e ações relevantes realizadas no ERP.
          </p>
        </div>
        <button className="secondary-button" disabled={busy} onClick={() => void load()}>
          {busy ? "Atualizando..." : "Atualizar"}
        </button>
      </div>

      <div className="audit-filters">
        <label>
          Ação
          <select value={action} onChange={(event) => setAction(event.target.value)}>
            <option value="">Todas</option>
            {actions.map((item) => <option key={item} value={item}>{item}</option>)}
          </select>
        </label>
        <label>
          Entidade
          <select value={entityType} onChange={(event) => setEntityType(event.target.value)}>
            <option value="">Todas</option>
            {entityTypes.map((item) => <option key={item} value={item}>{item}</option>)}
          </select>
        </label>
        <label>
          Usuário
          <select value={actorId} onChange={(event) => setActorId(event.target.value)}>
            <option value="">Todos</option>
            {team.map((member) => (
              <option key={member.user_id} value={member.user_id}>
                {member.name}
              </option>
            ))}
          </select>
        </label>
        <button className="small-button" disabled={busy} onClick={() => void load()}>
          Aplicar filtros
        </button>
      </div>

      {error && <div className="form-error">{error}</div>}

      <div className="audit-list">
        {events.map((event) => (
          <div className="audit-row" key={event.id}>
            <div>
              <strong>{event.action}</strong>
              <span>
                {event.entity_type}
                {event.entity_id ? " · " + event.entity_id : ""}
              </span>
            </div>
            <div className="audit-meta">
              <span>
                {event.actor_user_id
                  ? userMap.get(event.actor_user_id)?.name ?? "Usuário"
                  : "Sistema"}
              </span>
              <time>
                {new Intl.DateTimeFormat("pt-BR", {
                  dateStyle: "short",
                  timeStyle: "short",
                }).format(new Date(event.occurred_at))}
              </time>
            </div>
          </div>
        ))}
        {events.length === 0 && !busy && (
          <div className="empty-state">Nenhum evento encontrado.</div>
        )}
      </div>
    </section>
  );
}
