import { useState } from "react";

import { api } from "../lib/api";
import { runOrQueue } from "../lib/sync";
import type { AdminStation } from "./OperationalAdmin";

export type MaterialRequest = {
  id: string;
  station_id: string;
  visit_id: string | null;
  work_order_id: string | null;
  asset_id: string | null;
  requested_by_user_id: string;
  category: string;
  item_name: string;
  quantity: string | number | null;
  unit: string | null;
  priority: string;
  status: string;
  needed_by: string | null;
  notes: string | null;
  created_at: string;
  updated_at: string;
};

type VisitRef = {
  id: string;
  station_id: string;
};

export function VisitMaterialRequestForm({ visit }: { visit: VisitRef }) {
  const [category, setCategory] = useState("MATERIAL");
  const [itemName, setItemName] = useState("");
  const [quantity, setQuantity] = useState("");
  const [unit, setUnit] = useState("un");
  const [priority, setPriority] = useState("MEDIA");
  const [notes, setNotes] = useState("");
  const [feedback, setFeedback] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function submit() {
    if (itemName.trim().length < 2) {
      setFeedback("Informe o material ou serviço necessário.");
      return;
    }

    const operationId = crypto.randomUUID();
    const body = {
      station_id: visit.station_id,
      visit_id: visit.id,
      category,
      item_name: itemName.trim(),
      quantity: quantity ? Number(quantity.replace(",", ".")) : null,
      unit: quantity ? unit.trim() || null : null,
      priority,
      notes: notes.trim() || null,
    };

    setBusy(true);
    try {
      const result = await runOrQueue<MaterialRequest>(
        {
          id: operationId,
          method: "POST",
          path: "/api/v1/material-requests",
          body,
          createdAt: new Date().toISOString(),
        },
        () =>
          api<MaterialRequest>("/api/v1/material-requests", {
            method: "POST",
            body: JSON.stringify(body),
          }),
      );
      setItemName("");
      setQuantity("");
      setNotes("");
      setFeedback(
        result.queued
          ? "Solicitação salva no aparelho e pendente de sincronização."
          : "Solicitação enviada para a gestão.",
      );
    } catch {
      setFeedback("Não foi possível registrar a solicitação.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="material-request-form">
      <div className="compact-form-grid">
        <label>
          Tipo
          <select value={category} onChange={(event) => setCategory(event.target.value)}>
            <option value="MATERIAL">Material</option>
            <option value="SERVICO">Serviço</option>
            <option value="TERCEIRO">Terceiro</option>
          </select>
        </label>
        <label>
          Prioridade
          <select value={priority} onChange={(event) => setPriority(event.target.value)}>
            <option value="BAIXA">Baixa</option>
            <option value="MEDIA">Média</option>
            <option value="ALTA">Alta</option>
            <option value="CRITICA">Crítica</option>
          </select>
        </label>
        <label>
          Item / serviço
          <input value={itemName} onChange={(event) => setItemName(event.target.value)} />
        </label>
        <label>
          Quantidade
          <div className="quantity-row">
            <input
              inputMode="decimal"
              value={quantity}
              onChange={(event) => setQuantity(event.target.value)}
              placeholder="Opcional"
            />
            <input value={unit} onChange={(event) => setUnit(event.target.value)} aria-label="Unidade" />
          </div>
        </label>
      </div>
      <label className="full-field">
        Observação
        <textarea rows={2} value={notes} onChange={(event) => setNotes(event.target.value)} />
      </label>
      <button className="small-button" disabled={busy} onClick={() => void submit()}>
        {busy ? "Enviando..." : "Solicitar"}
      </button>
      {feedback && <span className="inline-feedback">{feedback}</span>}
    </div>
  );
}

export function MaterialRequestsAdmin({
  requests,
  stations,
  onChanged,
}: {
  requests: MaterialRequest[];
  stations: AdminStation[];
  onChanged: () => Promise<void>;
}) {
  const [busyId, setBusyId] = useState<string | null>(null);
  const [feedback, setFeedback] = useState<string | null>(null);
  const stationMap = new Map(stations.map((item) => [item.id, item]));
  const open = requests.filter((item) => !["ATENDIDA", "CANCELADA"].includes(item.status));

  async function changeStatus(request: MaterialRequest, status: string) {
    setBusyId(request.id);
    try {
      await api("/api/v1/material-requests/" + request.id, {
        method: "PATCH",
        body: JSON.stringify({ status }),
      });
      setFeedback("Solicitação atualizada.");
      await onChanged();
    } catch {
      setFeedback("Não foi possível atualizar a solicitação.");
    } finally {
      setBusyId(null);
    }
  }

  return (
    <section className="section-card">
      <div className="section-heading">
        <div>
          <span className="eyebrow">Suprimentos e serviços</span>
          <h2>Solicitações operacionais</h2>
          <p className="section-copy">
            Pedidos originados em campo, manutenções e necessidades de terceiros.
          </p>
        </div>
        <div className="admin-summary">
          <span><strong>{open.length}</strong> abertas</span>
          <span><strong>{open.filter((item) => item.priority === "CRITICA").length}</strong> críticas</span>
        </div>
      </div>

      <div className="ops-list">
        {open.slice(0, 20).map((request) => (
          <div className="ops-row material-request-row" key={request.id}>
            <div>
              <strong>{request.item_name}</strong>
              <span>
                {(stationMap.get(request.station_id)?.name ?? "Estação") +
                  " · " + request.category +
                  (request.quantity ? " · " + request.quantity + " " + (request.unit ?? "") : "")}
              </span>
              {request.notes && <span>{request.notes}</span>}
            </div>
            <div className="ops-meta request-actions">
              <span className={"priority priority-" + request.priority.toLowerCase()}>
                {request.priority}
              </span>
              <select
                value={request.status}
                disabled={busyId === request.id}
                onChange={(event) => void changeStatus(request, event.target.value)}
              >
                <option value="SOLICITADA">Solicitada</option>
                <option value="APROVADA">Aprovada</option>
                <option value="EM_COMPRA">Em compra</option>
                <option value="AGUARDANDO_TERCEIRO">Aguardando terceiro</option>
                <option value="ATENDIDA">Atendida</option>
                <option value="CANCELADA">Cancelada</option>
              </select>
            </div>
          </div>
        ))}
        {open.length === 0 && <div className="empty-state">Nenhuma solicitação pendente.</div>}
      </div>
      {feedback && <span className="inline-feedback">{feedback}</span>}
    </section>
  );
}
