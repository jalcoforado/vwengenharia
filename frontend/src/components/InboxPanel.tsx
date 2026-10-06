import { useEffect, useState } from "react";

import { api } from "../lib/api";

type InboxItem = {
  kind: string;
  priority: string;
  title: string;
  message: string;
  entity_type: string;
  entity_id: string;
  due_at: string | null;
  status: string;
};

export default function InboxPanel({ compact = false }: { compact?: boolean }) {
  const [items, setItems] = useState<InboxItem[]>([]);
  const [busy, setBusy] = useState(false);

  async function load() {
    setBusy(true);
    try {
      setItems(await api<InboxItem[]>("/api/v1/inbox"));
    } finally {
      setBusy(false);
    }
  }

  useEffect(() => {
    void load();
  }, []);

  return (
    <section className="section-card inbox-panel">
      <div className="section-heading">
        <div>
          <span className="eyebrow">Minha fila</span>
          <h2>Pendencias que exigem sua acao</h2>
        </div>
        <button className="text-button" disabled={busy} onClick={() => void load()}>
          {busy ? "Atualizando..." : "Atualizar"}
        </button>
      </div>

      <div className="ops-list">
        {items.slice(0, compact ? 6 : 12).map((item) => (
          <div className="ops-row inbox-row" key={item.kind + "-" + item.entity_id}>
            <div>
              <strong>{item.title}</strong>
              <span>{item.message}</span>
            </div>
            <div className="ops-meta">
              <span className={"priority priority-" + item.priority.toLowerCase()}>
                {item.priority}
              </span>
              <span className="status">{item.status.replaceAll("_", " ")}</span>
              {item.due_at && (
                <span className="sla">
                  {new Intl.DateTimeFormat("pt-BR", {
                    dateStyle: "short",
                    timeStyle: "short",
                  }).format(new Date(item.due_at))}
                </span>
              )}
            </div>
          </div>
        ))}
        {!busy && items.length === 0 && (
          <div className="empty-state">Nenhuma pendencia para voce agora.</div>
        )}
      </div>
    </section>
  );
}
