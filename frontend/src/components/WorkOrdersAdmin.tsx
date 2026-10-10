import { Search } from "lucide-react";
import { useState } from "react";

import { api } from "../lib/api";
import type { AdminStation, AssetRecord } from "./OperationalAdmin";

export type WorkOrderRecord = {
  id: string;
  occurrence_id: string | null;
  station_id: string;
  asset_id: string | null;
  assigned_membership_id: string | null;
  priority: string;
  status: string;
  description: string;
  sla_due_at: string;
  started_at: string | null;
  completed_at: string | null;
  validated_at: string | null;
  created_at: string;
  updated_at: string;
};

export type OccurrenceRecord = {
  id: string;
  station_id: string;
  asset_id?: string | null;
  occurrence_type: string;
  severity: string;
  status: string;
  description: string;
  detected_at: string;
};

type TeamMember = {
  membership_id: string;
  name: string;
  role: string;
  is_active: boolean;
};

const TRANSITIONS: Record<string, Array<{ value: string; label: string }>> = {
  ABERTA: [
    { value: "TRIAGEM", label: "Enviar para triagem" },
    { value: "PLANEJADA", label: "Planejar" },
    { value: "CANCELADA", label: "Cancelar" },
  ],
  TRIAGEM: [
    { value: "PLANEJADA", label: "Planejar" },
    { value: "CANCELADA", label: "Cancelar" },
  ],
  PLANEJADA: [
    { value: "EM_EXECUCAO", label: "Iniciar execução" },
    { value: "AGUARDANDO_MATERIAL", label: "Aguardar material" },
    { value: "AGUARDANDO_TERCEIRO", label: "Aguardar terceiro" },
    { value: "CANCELADA", label: "Cancelar" },
  ],
  EM_EXECUCAO: [
    { value: "AGUARDANDO_MATERIAL", label: "Aguardar material" },
    { value: "AGUARDANDO_TERCEIRO", label: "Aguardar terceiro" },
    { value: "CONCLUIDA", label: "Concluir" },
    { value: "CANCELADA", label: "Cancelar" },
  ],
  AGUARDANDO_MATERIAL: [
    { value: "EM_EXECUCAO", label: "Retomar execução" },
    { value: "CONCLUIDA", label: "Concluir" },
    { value: "CANCELADA", label: "Cancelar" },
  ],
  AGUARDANDO_TERCEIRO: [
    { value: "EM_EXECUCAO", label: "Retomar execução" },
    { value: "CONCLUIDA", label: "Concluir" },
    { value: "CANCELADA", label: "Cancelar" },
  ],
  CONCLUIDA: [
    { value: "VALIDADA", label: "Validar" },
    { value: "EM_EXECUCAO", label: "Reabrir" },
  ],
  VALIDADA: [],
  CANCELADA: [],
};

export default function WorkOrdersAdmin({
  orders,
  occurrences,
  stations,
  assets,
  team,
  onChanged,
}: {
  orders: WorkOrderRecord[];
  occurrences: OccurrenceRecord[];
  stations: AdminStation[];
  assets: AssetRecord[];
  team: TeamMember[];
  onChanged: () => Promise<void>;
}) {
  const [occurrenceId, setOccurrenceId] = useState("");
  const [stationId, setStationId] = useState("");
  const [assetId, setAssetId] = useState("");
  const [assignedId, setAssignedId] = useState("");
  const [priority, setPriority] = useState("MEDIA");
  const [description, setDescription] = useState("");
  const [feedback, setFeedback] = useState<string | null>(null);
  const [busyId, setBusyId] = useState<string | null>(null);
  const [search, setSearch] = useState("");
  const [statusFilter, setStatusFilter] = useState("ALL");
  const [priorityFilter, setPriorityFilter] = useState("ALL");

  const stationMap = new Map(stations.map((item) => [item.id, item]));
  const assetMap = new Map(assets.map((item) => [item.id, item]));
  const memberMap = new Map(team.map((item) => [item.membership_id, item]));
  const assignableTeam = team.filter(
    (item) =>
      item.is_active &&
      ["TECNICO", "MANUTENCAO", "SUPERVISOR"].includes(item.role),
  );
  const openOccurrences = occurrences.filter(
    (item) => !["RESOLVIDA", "CANCELADA"].includes(item.status),
  );

  function selectOccurrence(value: string) {
    setOccurrenceId(value);
    const occurrence = occurrences.find((item) => item.id === value);
    if (occurrence) {
      setStationId(occurrence.station_id);
      setAssetId(occurrence.asset_id ?? "");
      setDescription(occurrence.description);
      setPriority(
        occurrence.severity === "CRITICA"
          ? "CRITICA"
          : occurrence.severity === "ALTA"
            ? "ALTA"
            : occurrence.severity === "BAIXA"
              ? "BAIXA"
              : "MEDIA",
      );
    }
  }

  async function createOrder() {
    if (!stationId || description.trim().length < 3) {
      setFeedback("Selecione a estação e descreva o serviço.");
      return;
    }
    setBusyId("new");
    try {
      await api("/api/v1/work-orders", {
        method: "POST",
        body: JSON.stringify({
          occurrence_id: occurrenceId || null,
          station_id: stationId,
          asset_id: assetId || null,
          assigned_membership_id: assignedId || null,
          priority,
          description: description.trim(),
        }),
      });
      setOccurrenceId("");
      setStationId("");
      setAssetId("");
      setAssignedId("");
      setPriority("MEDIA");
      setDescription("");
      setFeedback("Ordem de serviço criada.");
      await onChanged();
    } catch {
      setFeedback("Não foi possível criar a ordem de serviço.");
    } finally {
      setBusyId(null);
    }
  }

  async function assign(order: WorkOrderRecord, membershipId: string) {
    setBusyId(order.id);
    try {
      await api("/api/v1/work-orders/" + order.id + "/assign", {
        method: "POST",
        body: JSON.stringify({
          assigned_membership_id: membershipId || null,
        }),
      });
      setFeedback("Responsável atualizado.");
      await onChanged();
    } catch {
      setFeedback("Não foi possível atribuir a OS.");
    } finally {
      setBusyId(null);
    }
  }

  async function transition(order: WorkOrderRecord, target: string) {
    if (!target) return;
    setBusyId(order.id);
    try {
      await api("/api/v1/work-orders/" + order.id + "/transition", {
        method: "POST",
        body: JSON.stringify({
          status: target,
          note: "Atualização pelo cockpit operacional.",
        }),
      });
      setFeedback("Status da OS atualizado.");
      await onChanged();
    } catch {
      setFeedback("Não foi possível alterar o status da OS.");
    } finally {
      setBusyId(null);
    }
  }

  const sortedOrders = [...orders].sort(
    (a, b) => new Date(a.sla_due_at).getTime() - new Date(b.sla_due_at).getTime(),
  );
  const filteredOrders = sortedOrders.filter((order) => {
    const haystack = [
      stationMap.get(order.station_id)?.name,
      assetMap.get(order.asset_id ?? "")?.name,
      memberMap.get(order.assigned_membership_id ?? "")?.name,
      order.description,
      order.status,
      order.priority,
    ]
      .filter(Boolean)
      .join(" ")
      .toLowerCase();
    const matchesSearch = !search.trim() || haystack.includes(search.trim().toLowerCase());
    const matchesStatus = statusFilter === "ALL" || order.status === statusFilter;
    const matchesPriority = priorityFilter === "ALL" || order.priority === priorityFilter;
    return matchesSearch && matchesStatus && matchesPriority;
  });

  return (
    <section className="section-card">
      <div className="section-heading">
        <div>
          <span className="eyebrow">Execução</span>
          <h2>Ordens de serviço</h2>
          <p className="section-copy">
            Abra, atribua, execute e valide a OS sem sair do cockpit.
          </p>
        </div>
        <div className="admin-summary">
          <span>
            <strong>
              {orders.filter((item) => !["VALIDADA", "CANCELADA"].includes(item.status)).length}
            </strong>{" "}
            abertas
          </span>
          <span>
            <strong>{orders.filter((item) => item.status === "CONCLUIDA").length}</strong>{" "}
            para validar
          </span>
        </div>
      </div>

      <div className="list-toolbar work-order-toolbar">
        <label className="search-field">
          <Search size={16} />
          <input
            value={search}
            onChange={(event) => setSearch(event.target.value)}
            placeholder="Buscar estação, ativo, responsável ou descrição"
          />
        </label>
        <select value={statusFilter} onChange={(event) => setStatusFilter(event.target.value)}>
          <option value="ALL">Todos os status</option>
          <option value="ABERTA">Aberta</option>
          <option value="TRIAGEM">Triagem</option>
          <option value="PLANEJADA">Planejada</option>
          <option value="EM_EXECUCAO">Em execução</option>
          <option value="AGUARDANDO_MATERIAL">Aguardando material</option>
          <option value="AGUARDANDO_TERCEIRO">Aguardando terceiro</option>
          <option value="CONCLUIDA">Concluída</option>
          <option value="VALIDADA">Validada</option>
        </select>
        <select value={priorityFilter} onChange={(event) => setPriorityFilter(event.target.value)}>
          <option value="ALL">Todas as prioridades</option>
          <option value="CRITICA">Crítica</option>
          <option value="ALTA">Alta</option>
          <option value="MEDIA">Média</option>
          <option value="BAIXA">Baixa</option>
        </select>
      </div>

      <div className="work-order-layout">
        <div className="ops-list">
          {filteredOrders.slice(0, 30).map((order) => (
            <div className="work-order-card" key={order.id}>
              <div className="work-order-main">
                <div>
                  <strong>{stationMap.get(order.station_id)?.name ?? "Estação"}</strong>
                  <span>{order.description}</span>
                  <span>
                    {(order.asset_id ? assetMap.get(order.asset_id)?.name + " · " : "") +
                      (memberMap.get(order.assigned_membership_id ?? "")?.name ?? "Sem responsável")}
                  </span>
                </div>
                <div className="ops-meta">
                  <span className={"priority priority-" + order.priority.toLowerCase()}>
                    {order.priority}
                  </span>
                  <span className="status">{order.status.replaceAll("_", " ")}</span>
                </div>
              </div>

              <div className="work-order-controls">
                <label>
                  Responsável
                  <select
                    value={order.assigned_membership_id ?? ""}
                    disabled={busyId === order.id}
                    onChange={(event) => void assign(order, event.target.value)}
                  >
                    <option value="">Sem responsável</option>
                    {assignableTeam.map((member) => (
                      <option key={member.membership_id} value={member.membership_id}>
                        {member.name + " · " + member.role}
                      </option>
                    ))}
                  </select>
                </label>
                <label>
                  Próxima etapa
                  <select
                    value=""
                    disabled={busyId === order.id || !(TRANSITIONS[order.status]?.length)}
                    onChange={(event) => void transition(order, event.target.value)}
                  >
                    <option value="">
                      {TRANSITIONS[order.status]?.length ? "Selecione" : "Fluxo encerrado"}
                    </option>
                    {(TRANSITIONS[order.status] ?? []).map((item) => (
                      <option key={item.value} value={item.value}>{item.label}</option>
                    ))}
                  </select>
                </label>
              </div>
            </div>
          ))}
          {orders.length === 0 && (
            <div className="empty-state empty-state-positive">
              <strong>Nenhuma ordem de serviço</strong>
              <span>A operação não possui OS registrada neste momento.</span>
            </div>
          )}
          {orders.length > 0 && filteredOrders.length === 0 && (
            <div className="empty-state">
              <Search size={22} />
              <strong>Nenhuma OS encontrada</strong>
              <span>Altere a busca ou os filtros para ampliar os resultados.</span>
              <button
                className="small-button"
                onClick={() => {
                  setSearch("");
                  setStatusFilter("ALL");
                  setPriorityFilter("ALL");
                }}
              >
                Limpar filtros
              </button>
            </div>
          )}
        </div>

        <div className="compact-form admin-create-form">
          <h3>Nova ordem de serviço</h3>
          <label>
            Ocorrência
            <select value={occurrenceId} onChange={(event) => selectOccurrence(event.target.value)}>
              <option value="">OS avulsa</option>
              {openOccurrences.map((item) => (
                <option key={item.id} value={item.id}>
                  {(stationMap.get(item.station_id)?.name ?? "Estação") + " · " + item.description}
                </option>
              ))}
            </select>
          </label>
          <div className="compact-form-grid">
            <label>
              Estação
              <select
                value={stationId}
                disabled={Boolean(occurrenceId)}
                onChange={(event) => {
                  setStationId(event.target.value);
                  setAssetId("");
                }}
              >
                <option value="">Selecione</option>
                {stations.filter((item) => item.is_active).map((item) => (
                  <option key={item.id} value={item.id}>{item.name}</option>
                ))}
              </select>
            </label>
            <label>
              Ativo
              <select value={assetId} onChange={(event) => setAssetId(event.target.value)}>
                <option value="">Sem ativo específico</option>
                {assets
                  .filter((item) => item.is_active && item.station_id === stationId)
                  .map((item) => (
                    <option key={item.id} value={item.id}>{item.name}</option>
                  ))}
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
              Responsável
              <select value={assignedId} onChange={(event) => setAssignedId(event.target.value)}>
                <option value="">Definir depois</option>
                {assignableTeam.map((member) => (
                  <option key={member.membership_id} value={member.membership_id}>
                    {member.name + " · " + member.role}
                  </option>
                ))}
              </select>
            </label>
          </div>
          <label className="full-field">
            Descrição
            <textarea rows={4} value={description} onChange={(event) => setDescription(event.target.value)} />
          </label>
          <button className="small-button" disabled={busyId === "new"} onClick={() => void createOrder()}>
            {busyId === "new" ? "Criando..." : "Criar OS"}
          </button>
          {feedback && <span className="inline-feedback">{feedback}</span>}
        </div>
      </div>
    </section>
  );
}
