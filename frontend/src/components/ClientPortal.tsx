import { useEffect, useMemo, useState } from "react";
import { AlertTriangle, Building2, CheckCircle2, ClipboardCheck, RefreshCw, Wrench } from "lucide-react";

import { api, openApiDocument } from "../lib/api";

type PortalClient = { id: string; name: string };
type PortalStation = {
  id: string;
  development_id: string;
  development_name: string;
  name: string;
  code: string | null;
  station_type: string | null;
};
type PortalVisit = {
  id: string;
  station_id: string;
  scheduled_for: string;
  finished_at: string | null;
  status: string;
};
type PortalOccurrence = {
  id: string;
  station_id: string;
  occurrence_type: string;
  severity: string;
  status: string;
  description: string;
  detected_at: string;
};
type PortalWorkOrder = {
  id: string;
  station_id: string;
  asset_id: string | null;
  priority: string;
  status: string;
  description: string;
  sla_due_at: string;
  completed_at: string | null;
};
type PortalData = {
  clients: PortalClient[];
  stations: PortalStation[];
  visits: PortalVisit[];
  occurrences: PortalOccurrence[];
  work_orders: PortalWorkOrder[];
};

function humanStatus(value: string) {
  return value.replaceAll("_", " ").toLowerCase().replace(/^./, (letter) => letter.toUpperCase());
}

export default function ClientPortal({ userName }: { userName: string }) {
  const [data, setData] = useState<PortalData | null>(null);
  const [busy, setBusy] = useState(true);
  const [error, setError] = useState("");

  async function load() {
    setBusy(true);
    setError("");
    try {
      setData(await api<PortalData>("/api/v1/client-portal"));
    } catch {
      setError("Nao foi possivel carregar o portal neste momento.");
    } finally {
      setBusy(false);
    }
  }

  useEffect(() => {
    void load();
  }, []);

  const stationMap = useMemo(
    () => new Map((data?.stations ?? []).map((item) => [item.id, item])),
    [data],
  );
  const completedVisits = data?.visits.filter((item) => item.status === "REVISADA") ?? [];
  const openOccurrences =
    data?.occurrences.filter((item) => !["RESOLVIDA", "CANCELADA"].includes(item.status)) ?? [];
  const openOrders =
    data?.work_orders.filter((item) => !["VALIDADA", "CANCELADA"].includes(item.status)) ?? [];

  return (
    <main className="content client-portal">
      <section className="welcome client-welcome">
        <div>
          <span className="eyebrow">Portal do cliente</span>
          <h1>Ola, {userName.split(" ")[0]}</h1>
          <p>
            {data?.clients.length
              ? data.clients.map((item) => item.name).join(" · ")
              : "Acompanhe a operacao dos seus empreendimentos."}
          </p>
        </div>
        <button className="secondary-button" disabled={busy} onClick={() => void load()}>
          <RefreshCw size={17} className={busy ? "spin" : ""} />
          Atualizar
        </button>
      </section>

      {error && <div className="form-error">{error}</div>}

      {!busy && data?.clients.length === 0 && (
        <section className="section-card empty-state">
          <Building2 size={26} />
          <strong>Acesso ainda nao configurado</strong>
          <span>Solicite a VW Engenharia para vincular seu usuario ao contrato correto.</span>
        </section>
      )}

      {data && data.clients.length > 0 && (
        <>
          <section className="metric-grid client-metrics">
            <div className="metric-card">
              <Building2 />
              <strong>{data.stations.length}</strong>
              <span>Estacoes acompanhadas</span>
            </div>
            <div className="metric-card">
              <CheckCircle2 />
              <strong>{completedVisits.length}</strong>
              <span>Visitas validadas</span>
            </div>
            <div className="metric-card">
              <AlertTriangle />
              <strong>{openOccurrences.length}</strong>
              <span>Ocorrencias abertas</span>
            </div>
            <div className="metric-card">
              <Wrench />
              <strong>{openOrders.length}</strong>
              <span>OS em andamento</span>
            </div>
          </section>

          <div className="client-portal-grid">
            <section className="section-card">
              <span className="eyebrow">Atendimento</span>
              <h2>Visitas recentes</h2>
              <div className="ops-list">
                {data.visits.slice(0, 12).map((visit) => (
                  <div className="ops-row client-row" key={visit.id}>
                    <div>
                      <strong>{stationMap.get(visit.station_id)?.name ?? "Estacao"}</strong>
                      <span>
                        {new Intl.DateTimeFormat("pt-BR", {
                          dateStyle: "short",
                          timeStyle: "short",
                        }).format(new Date(visit.scheduled_for))}
                      </span>
                    </div>
                    <div className="client-row-actions">
                      <span className={"status status-" + visit.status.toLowerCase()}>
                        {humanStatus(visit.status)}
                      </span>
                      {visit.status === "REVISADA" && (
                        <button
                          className="text-button"
                          onClick={() => void openApiDocument(`/api/v1/reports/visits/${visit.id}.html`)}
                        >
                          Relatorio
                        </button>
                      )}
                    </div>
                  </div>
                ))}
                {data.visits.length === 0 && (
                  <div className="empty-state">Nenhuma visita registrada para seus empreendimentos.</div>
                )}
              </div>
            </section>

            <section className="section-card">
              <span className="eyebrow">Acompanhamento</span>
              <h2>Ordens de servico</h2>
              <div className="ops-list">
                {data.work_orders.slice(0, 12).map((order) => (
                  <div className="ops-row" key={order.id}>
                    <div>
                      <strong>{stationMap.get(order.station_id)?.name ?? "Estacao"}</strong>
                      <span>{order.description}</span>
                    </div>
                    <div className="ops-meta">
                      <span className={"priority priority-" + order.priority.toLowerCase()}>
                        {order.priority}
                      </span>
                      <span className="status">{humanStatus(order.status)}</span>
                    </div>
                  </div>
                ))}
                {data.work_orders.length === 0 && (
                  <div className="empty-state empty-state-positive">
                    <ClipboardCheck size={22} />
                    <strong>Nenhuma OS registrada</strong>
                    <span>Nao ha ordens de servico para os seus empreendimentos.</span>
                  </div>
                )}
              </div>
            </section>
          </div>

          <section className="section-card">
            <span className="eyebrow">Transparencia</span>
            <h2>Ocorrencias recentes</h2>
            <div className="ops-list">
              {data.occurrences.slice(0, 12).map((item) => (
                <div className="ops-row" key={item.id}>
                  <div>
                    <strong>{stationMap.get(item.station_id)?.name ?? "Estacao"}</strong>
                    <span>{item.description}</span>
                  </div>
                  <div className="ops-meta">
                    <span className={"priority priority-" + item.severity.toLowerCase()}>
                      {item.severity}
                    </span>
                    <span className="status">{humanStatus(item.status)}</span>
                  </div>
                </div>
              ))}
              {data.occurrences.length === 0 && (
                <div className="empty-state empty-state-positive">
                  <CheckCircle2 size={22} />
                  <strong>Sem ocorrencias registradas</strong>
                  <span>Nenhuma ocorrencia foi registrada para os seus empreendimentos.</span>
                </div>
              )}
            </div>
          </section>
        </>
      )}
    </main>
  );
}
