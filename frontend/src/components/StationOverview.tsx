import { useEffect, useMemo, useState } from "react";

import { api } from "../lib/api";
import type { AdminStation, AssetRecord } from "./OperationalAdmin";
import type { MaterialRequest } from "./Materials";
import type { WorkOrderRecord, OccurrenceRecord } from "./WorkOrdersAdmin";

type VisitRecord = {
  id: string;
  station_id: string;
  scheduled_for: string;
  started_at: string | null;
  finished_at: string | null;
  status: string;
  notes: string | null;
};

type MaintenancePlanRecord = {
  id: string;
  asset_id: string;
  assigned_membership_id: string | null;
  maintenance_type: string;
  frequency_days: number;
  next_due_at: string;
  last_completed_at: string | null;
  instructions: string | null;
  is_active: boolean;
};

type StationOverviewData = {
  station: AdminStation;
  summary: {
    active_assets: number;
    unavailable_assets: number;
    open_occurrences: number;
    open_work_orders: number;
    overdue_work_orders: number;
    overdue_maintenance: number;
    open_material_requests: number;
  };
  assets: AssetRecord[];
  visits: VisitRecord[];
  occurrences: OccurrenceRecord[];
  work_orders: WorkOrderRecord[];
  maintenance_plans: MaintenancePlanRecord[];
  material_requests: MaterialRequest[];
};

export default function StationOverview({
  stationId,
  onClose,
}: {
  stationId: string;
  onClose: () => void;
}) {
  const [data, setData] = useState<StationOverviewData | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function load() {
    setBusy(true);
    setError(null);
    try {
      setData(await api<StationOverviewData>("/api/v1/stations/" + stationId + "/overview"));
    } catch {
      setError("Não foi possível carregar a visão da estação.");
    } finally {
      setBusy(false);
    }
  }

  useEffect(() => {
    void load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [stationId]);

  const lastVisit = useMemo(
    () => data?.visits[0] ?? null,
    [data],
  );

  return (
    <section className="section-card station-overview">
      <div className="section-heading station-overview-heading">
        <div>
          <span className="eyebrow">Visão 360 · somente consulta</span>
          <h2>{data?.station.name ?? "Estação"}</h2>
          <p className="section-copy">
            {[data?.station.code, data?.station.station_type].filter(Boolean).join(" · ")}
          </p>
        </div>
        <div className="station-overview-actions">
          <button
            className="secondary-button"
            disabled={busy}
            title="Busca de novo as informações desta estação no servidor"
            onClick={() => void load()}
          >
            Recarregar dados
          </button>
          <button className="text-button" onClick={onClose}>
            Fechar
          </button>
        </div>
      </div>

      {error && <div className="form-error">{error}</div>}

      {data && (
        <>
          <section className="metric-grid management-metrics">
            <div className="metric-card">
              <strong>{data.summary.active_assets}</strong>
              <span>Ativos</span>
            </div>
            <div className="metric-card">
              <strong>{data.summary.unavailable_assets}</strong>
              <span>Indisponíveis</span>
            </div>
            <div className="metric-card">
              <strong>{data.summary.open_occurrences}</strong>
              <span>Ocorrências abertas</span>
            </div>
            <div className="metric-card">
              <strong>{data.summary.open_work_orders}</strong>
              <span>OS abertas</span>
            </div>
            <div className="metric-card danger-metric">
              <strong>{data.summary.overdue_work_orders}</strong>
              <span>OS fora do SLA</span>
            </div>
            <div className="metric-card">
              <strong>{data.summary.overdue_maintenance}</strong>
              <span>Preventivas vencidas</span>
            </div>
          </section>

          <div className="station-health-strip">
            <span>
              Última visita:{" "}
              <strong>
                {lastVisit
                  ? new Intl.DateTimeFormat("pt-BR", {
                      dateStyle: "short",
                      timeStyle: "short",
                    }).format(new Date(lastVisit.finished_at ?? lastVisit.scheduled_for))
                  : "sem histórico"}
              </strong>
            </span>
            <span>
              Solicitações abertas: <strong>{data.summary.open_material_requests}</strong>
            </span>
          </div>

          <div className="station-overview-grid">
            <OverviewBlock title="Ativos">
              {data.assets.map((asset) => (
                <div className="admin-row" key={asset.id}>
                  <div>
                    <strong>{asset.name}</strong>
                    <span>{asset.manufacturer || asset.model || "Sem identificação complementar"}</span>
                  </div>
                  <span className={asset.status === "OPERANDO" ? "status status-revisada" : "status"}>
                    {asset.status.replaceAll("_", " ")}
                  </span>
                </div>
              ))}
            </OverviewBlock>

            <OverviewBlock title="Últimas visitas">
              {data.visits.slice(0, 8).map((visit) => (
                <div className="admin-row" key={visit.id}>
                  <div>
                    <strong>
                      {new Intl.DateTimeFormat("pt-BR", { dateStyle: "short" }).format(
                        new Date(visit.scheduled_for),
                      )}
                    </strong>
                    <span>{visit.notes || "Sem observação"}</span>
                  </div>
                  <span className="status">{visit.status.replaceAll("_", " ")}</span>
                </div>
              ))}
            </OverviewBlock>

            <OverviewBlock title="Ocorrências">
              {data.occurrences.slice(0, 8).map((item) => (
                <div className="admin-row" key={item.id}>
                  <div>
                    <strong>{item.occurrence_type}</strong>
                    <span>{item.description}</span>
                  </div>
                  <span className={"priority priority-" + item.severity.toLowerCase()}>
                    {item.severity}
                  </span>
                </div>
              ))}
            </OverviewBlock>

            <OverviewBlock title="Ordens de serviço">
              {data.work_orders.slice(0, 8).map((item) => (
                <div className="admin-row" key={item.id}>
                  <div>
                    <strong>{item.description}</strong>
                    <span>
                      SLA{" "}
                      {new Intl.DateTimeFormat("pt-BR", {
                        dateStyle: "short",
                        timeStyle: "short",
                      }).format(new Date(item.sla_due_at))}
                    </span>
                  </div>
                  <span className="status">{item.status.replaceAll("_", " ")}</span>
                </div>
              ))}
            </OverviewBlock>

            <OverviewBlock title="Manutenção preventiva">
              {data.maintenance_plans.slice(0, 8).map((item) => (
                <div className="admin-row" key={item.id}>
                  <div>
                    <strong>
                      {data.assets.find((asset) => asset.id === item.asset_id)?.name ?? "Ativo"}
                    </strong>
                    <span>
                      A cada {item.frequency_days} dias · próxima{" "}
                      {new Intl.DateTimeFormat("pt-BR", { dateStyle: "short" }).format(
                        new Date(item.next_due_at),
                      )}
                    </span>
                  </div>
                  <span className="status">{item.maintenance_type}</span>
                </div>
              ))}
            </OverviewBlock>

            <OverviewBlock title="Materiais e serviços">
              {data.material_requests.slice(0, 8).map((item) => (
                <div className="admin-row" key={item.id}>
                  <div>
                    <strong>{item.item_name}</strong>
                    <span>
                      {item.category}
                      {item.quantity ? " · " + item.quantity + " " + (item.unit ?? "") : ""}
                    </span>
                  </div>
                  <span className="status">{item.status.replaceAll("_", " ")}</span>
                </div>
              ))}
            </OverviewBlock>
          </div>
        </>
      )}
    </section>
  );
}

function OverviewBlock({
  title,
  children,
}: {
  title: string;
  children: React.ReactNode;
}) {
  return (
    <section className="station-overview-block">
      <h3>{title}</h3>
      <div className="admin-list">{children}</div>
    </section>
  );
}
