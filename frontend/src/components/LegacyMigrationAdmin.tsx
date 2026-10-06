import { useEffect, useState } from "react";

import { api } from "../lib/api";
import type { AdminStation } from "./OperationalAdmin";

type TeamMember = {
  membership_id: string;
  name: string;
  role: string;
  is_active: boolean;
};

type Summary = {
  total: number;
  staged: number;
  imported: number;
  errors: number;
  unmapped: number;
  unmapped_station_labels: string[];
  unmapped_technician_labels: string[];
};

type StageResult = {
  source_file: string;
  sheet: string;
  staged: number;
  skipped_existing: number;
  errors: number;
};

export default function LegacyMigrationAdmin({
  stations,
  team,
}: {
  stations: AdminStation[];
  team: TeamMember[];
}) {
  const [summary, setSummary] = useState<Summary | null>(null);
  const [file, setFile] = useState<File | null>(null);
  const [preserveReview, setPreserveReview] = useState(false);
  const [busy, setBusy] = useState(false);
  const [feedback, setFeedback] = useState<string | null>(null);

  const fieldTeam = team.filter(
    (item) => item.is_active && ["TECNICO", "MANUTENCAO"].includes(item.role),
  );

  async function load() {
    try {
      setSummary(await api<Summary>("/api/v1/legacy-migration/summary"));
    } catch {
      setFeedback("Nao foi possivel carregar o estado da migracao.");
    }
  }

  useEffect(() => {
    void load();
  }, []);

  async function stage() {
    if (!file) {
      setFeedback("Selecione o arquivo XLSX.");
      return;
    }
    setBusy(true);
    try {
      const form = new FormData();
      form.append("file", file);
      form.append("sheet", "Página1");
      const result = await api<StageResult>("/api/v1/legacy-migration/stage", {
        method: "POST",
        body: form,
      });
      setFeedback(
        result.staged +
          " linha(s) adicionada(s) ao staging; " +
          result.skipped_existing +
          " ja existiam; " +
          result.errors +
          " com erro.",
      );
      await load();
    } catch {
      setFeedback("Nao foi possivel processar o arquivo.");
    } finally {
      setBusy(false);
    }
  }

  async function autoMap() {
    setBusy(true);
    try {
      const result = await api<{ stations_mapped: number; technicians_mapped: number }>(
        "/api/v1/legacy-migration/auto-map",
        { method: "POST" },
      );
      setFeedback(
        "Auto-mapeamento: " +
          result.stations_mapped +
          " estacao(oes), " +
          result.technicians_mapped +
          " tecnico(s).",
      );
      await load();
    } catch {
      setFeedback("Nao foi possivel executar o auto-mapeamento.");
    } finally {
      setBusy(false);
    }
  }

  async function mapStation(sourceLabel: string, stationId: string) {
    if (!stationId) return;
    await api("/api/v1/legacy-migration/map-station", {
      method: "POST",
      body: JSON.stringify({ source_label: sourceLabel, station_id: stationId }),
    });
    await load();
  }

  async function mapTechnician(sourceLabel: string, membershipId: string) {
    if (!membershipId) return;
    await api("/api/v1/legacy-migration/map-technician", {
      method: "POST",
      body: JSON.stringify({
        source_label: sourceLabel,
        membership_id: membershipId,
      }),
    });
    await load();
  }

  async function materialize() {
    setBusy(true);
    try {
      const result = await api<{
        imported: number;
        skipped_unmapped: number;
        errors: number;
      }>("/api/v1/legacy-migration/materialize", {
        method: "POST",
        body: JSON.stringify({
          limit: 1000,
          preserve_source_review_status: preserveReview,
        }),
      });
      setFeedback(
        result.imported +
          " visita(s) importada(s); " +
          result.skipped_unmapped +
          " sem mapeamento; " +
          result.errors +
          " erro(s).",
      );
      await load();
    } catch {
      setFeedback("Nao foi possivel materializar o lote.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className="section-card">
      <div className="section-heading">
        <div>
          <span className="eyebrow">Migracao</span>
          <h2>Historico da planilha</h2>
          <p className="section-copy">
            O staging preserva o registro bruto antes de qualquer normalizacao.
          </p>
        </div>
      </div>

      <section className="metric-grid migration-metrics">
        <div className="metric-card"><strong>{summary?.total ?? 0}</strong><span>No staging</span></div>
        <div className="metric-card"><strong>{summary?.imported ?? 0}</strong><span>Importados</span></div>
        <div className="metric-card"><strong>{summary?.unmapped ?? 0}</strong><span>Sem mapa</span></div>
        <div className="metric-card danger-metric"><strong>{summary?.errors ?? 0}</strong><span>Erros</span></div>
      </section>

      <div className="migration-actions">
        <label className="file-picker">
          Arquivo XLSX
          <input
            type="file"
            accept=".xlsx,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            onChange={(event) => setFile(event.target.files?.[0] ?? null)}
          />
        </label>
        <button className="small-button" disabled={busy || !file} onClick={() => void stage()}>
          Enviar para staging
        </button>
        <button className="secondary-button" disabled={busy} onClick={() => void autoMap()}>
          Auto-mapear nomes exatos
        </button>
      </div>

      <div className="migration-map-grid">
        <section>
          <h3>Estacoes ainda sem mapeamento</h3>
          <div className="mapping-list">
            {(summary?.unmapped_station_labels ?? []).slice(0, 30).map((label) => (
              <label className="mapping-row" key={label}>
                <span>{label}</span>
                <select defaultValue="" onChange={(event) => void mapStation(label, event.target.value)}>
                  <option value="">Mapear para...</option>
                  {stations.filter((item) => item.is_active).map((station) => (
                    <option key={station.id} value={station.id}>{station.name}</option>
                  ))}
                </select>
              </label>
            ))}
            {summary?.unmapped_station_labels.length === 0 && (
              <div className="empty-state">Todas as estacoes estao mapeadas.</div>
            )}
          </div>
        </section>

        <section>
          <h3>Tecnicos ainda sem mapeamento</h3>
          <div className="mapping-list">
            {(summary?.unmapped_technician_labels ?? []).slice(0, 30).map((label) => (
              <label className="mapping-row" key={label}>
                <span>{label}</span>
                <select defaultValue="" onChange={(event) => void mapTechnician(label, event.target.value)}>
                  <option value="">Mapear para...</option>
                  {fieldTeam.map((member) => (
                    <option key={member.membership_id} value={member.membership_id}>
                      {member.name}
                    </option>
                  ))}
                </select>
              </label>
            ))}
            {summary?.unmapped_technician_labels.length === 0 && (
              <div className="empty-state">Todos os tecnicos estao mapeados.</div>
            )}
          </div>
        </section>
      </div>

      <div className="migration-materialize">
        <label className="checkbox-field">
          <input
            type="checkbox"
            checked={preserveReview}
            onChange={(event) => setPreserveReview(event.target.checked)}
          />
          Preservar "Aguardando Revisao" como backlog operacional
        </label>
        <p>
          Recomendacao: deixe desmarcado na primeira migracao. O status original continua
          preservado no staging, mas registros historicos nao poluem a fila atual.
        </p>
        <button className="small-button" disabled={busy} onClick={() => void materialize()}>
          Importar proximo lote de 1.000
        </button>
      </div>

      {feedback && <div className="message">{feedback}</div>}
    </section>
  );
}
