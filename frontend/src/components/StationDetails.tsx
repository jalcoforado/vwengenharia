import { LayoutDashboard } from "lucide-react";

import { DetailsHead, Field } from "./DevelopmentDetails";
import type { AdminStation, AssetRecord } from "./OperationalAdmin";
import type { ProcessUnitRecord } from "./ProcessUnitAdmin";

// Consulta somente leitura da estacao: dados do cadastro, unidades e equipamentos.

function coordinates(station: AdminStation): string {
  if (station.latitude == null || station.longitude == null) return "";
  return station.latitude + ", " + station.longitude;
}

export default function StationDetails({
  station,
  developmentName,
  typeLabel,
  frequencyLabel,
  units,
  assets,
  assetStatusLabel,
  onEdit,
  onOpenOverview,
}: {
  station: AdminStation;
  developmentName: string;
  typeLabel: string;
  frequencyLabel: string;
  units: ProcessUnitRecord[];
  assets: AssetRecord[];
  assetStatusLabel: (asset: AssetRecord) => string;
  onEdit?: () => void;
  onOpenOverview?: () => void;
}) {
  const unitMap = new Map(units.map((unit) => [unit.id, unit.name]));
  const sortedUnits = [...units].sort((a, b) => a.name.localeCompare(b.name, "pt-BR"));
  const sortedAssets = [...assets].sort((a, b) => a.name.localeCompare(b.name, "pt-BR"));

  return (
    <div className="client-contacts development-details">
      <section>
        <DetailsHead title="Estação" editLabel="Editar estação" onEdit={onEdit} />
        <dl className="detail-grid">
          <Field label="Código" value={station.code} />
          <Field label="Tipo" value={typeLabel} />
          <Field label="Frequência de visita" value={frequencyLabel} />
          <Field label="Empreendimento" value={developmentName} />
          <Field label="Coordenadas" value={coordinates(station)} />
        </dl>
      </section>

      <section>
        <span className="eyebrow">Unidades de processo</span>
        {sortedUnits.length === 0 ? (
          <p className="detail-note">Nenhuma unidade cadastrada. As unidades são cadastradas na aba Unidades.</p>
        ) : (
          <p className="detail-note">{sortedUnits.map((unit) => unit.name).join(" · ")}</p>
        )}
      </section>

      <section>
        <span className="eyebrow">Equipamentos</span>
        {sortedAssets.length === 0 && (
          <p className="detail-note">Nenhum equipamento cadastrado. Os equipamentos são cadastrados na aba Ativos.</p>
        )}
        {sortedAssets.map((asset) => (
          <div className="client-contact-row" key={asset.id}>
            <div>
              <strong>{asset.name}</strong>
              <span>
                {[asset.process_unit_id ? unitMap.get(asset.process_unit_id) : null, asset.manufacturer, asset.model]
                  .filter(Boolean)
                  .join(" · ") || "Sem unidade de processo"}
              </span>
            </div>
            <div className="admin-actions">
              <span className="status">{assetStatusLabel(asset)}</span>
              <span className={asset.is_active ? "status status-revisada" : "status"}>{asset.is_active ? "Ativo" : "Inativo"}</span>
            </div>
          </div>
        ))}
      </section>

      {onOpenOverview && (
        <div className="admin-actions">
          <button className="secondary-button details-edit" type="button" onClick={onOpenOverview}>
            <LayoutDashboard size={15} />Abrir Visão 360 da estação
          </button>
        </div>
      )}
    </div>
  );
}
