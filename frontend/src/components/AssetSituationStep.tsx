import { useEffect, useState } from "react";

export type AssetSituationRecord = {
  id: string;
  visit_id: string;
  asset_id: string;
  situation: string;
  comment: string | null;
};

type StepAsset = { id: string; name: string; process_unit_id?: string | null };
type StepUnit = { id: string; name: string };

// Lista fechada do formulario de campo. A ordem segue a que a equipe ja usa.
export const ASSET_SITUATIONS: [string, string][] = [
  ["FUNCIONANDO", "Funcionando adequadamente"],
  ["DESLIGADO", "Desligado (equipamento ok)"],
  ["NECESSARIO_VERIFICAR", "Necessário verificar"],
  ["AGUARDANDO_RETIRADA", "Aguardando ser retirado"],
  ["RETIRADO_AGUARDANDO_MANUTENCAO", "Retirado e aguardando manutenção"],
  ["EM_MANUTENCAO", "Em manutenção"],
  ["AGUARDANDO_INSTALACAO", "Aguardando ser instalado"],
  ["NAO_POSSUI", "Não possui"],
  ["OUTRO", "Outro"],
];

function AssetSituationRow({
  asset,
  record,
  onSave,
}: {
  asset: StepAsset;
  record: AssetSituationRecord | undefined;
  onSave: (assetId: string, situation: string, comment: string | null) => Promise<void>;
}) {
  const [situation, setSituation] = useState(record?.situation ?? "");
  const [comment, setComment] = useState(record?.comment ?? "");

  // Acompanha o que veio do servidor ou do aparelho quando a visita e recarregada.
  useEffect(() => {
    setSituation(record?.situation ?? "");
    setComment(record?.comment ?? "");
  }, [record?.situation, record?.comment]);

  const needsComment = situation === "OUTRO" && !comment.trim();
  const inputId = "asset-situation-" + asset.id;

  function chooseSituation(value: string) {
    setSituation(value);
    if (!value) return;
    // "Outro" so e gravado junto com a descricao.
    if (value === "OUTRO" && !comment.trim()) return;
    void onSave(asset.id, value, comment.trim() || null);
  }

  function saveComment() {
    if (!situation || needsComment) return;
    const next = comment.trim() || null;
    if (next === (record?.comment ?? null) && situation === record?.situation) return;
    void onSave(asset.id, situation, next);
  }

  return (
    <div className={record ? "asset-situation-row done" : "asset-situation-row"}>
      <label htmlFor={inputId}>{asset.name}</label>
      <select id={inputId} value={situation} onChange={(event) => chooseSituation(event.target.value)}>
        <option value="">Selecione a situação</option>
        {ASSET_SITUATIONS.map(([value, text]) => <option key={value} value={value}>{text}</option>)}
      </select>
      {situation && (
        <input
          aria-label={"Observação sobre " + asset.name}
          placeholder={situation === "OUTRO" ? "Descreva a situação (obrigatório)" : "Observação (opcional)"}
          value={comment}
          maxLength={500}
          onChange={(event) => setComment(event.target.value)}
          onBlur={saveComment}
        />
      )}
      {needsComment && <span className="required-hint">Descreva a situação para salvar.</span>}
    </div>
  );
}

export default function AssetSituationStep({
  assets,
  units,
  situations,
  onSave,
}: {
  assets: StepAsset[];
  units: StepUnit[];
  situations: AssetSituationRecord[];
  onSave: (assetId: string, situation: string, comment: string | null) => Promise<void>;
}) {
  const recordMap = new Map(situations.map((item) => [item.asset_id, item]));
  const unitIds = new Set(units.map((unit) => unit.id));
  const groups = [
    ...units.map((unit) => ({
      key: unit.id,
      title: unit.name,
      items: assets.filter((asset) => asset.process_unit_id === unit.id),
    })),
    {
      key: "area-geral",
      title: units.length ? "Área geral" : "",
      items: assets.filter((asset) => !asset.process_unit_id || !unitIds.has(asset.process_unit_id)),
    },
  ].filter((group) => group.items.length > 0);
  const recorded = assets.filter((asset) => recordMap.has(asset.id)).length;

  if (assets.length === 0) {
    return <div className="empty-state">Esta estação ainda não tem equipamentos cadastrados.</div>;
  }

  return (
    <div className="asset-situations">
      <span className={recorded === assets.length ? "progress-ready" : "progress-pending"} role="status">
        {recorded} de {assets.length} equipamentos registrados
      </span>
      {groups.map((group) => (
        <div className="asset-situation-group" key={group.key}>
          {group.title && <h3>{group.title}</h3>}
          {group.items.map((asset) => (
            <AssetSituationRow key={asset.id} asset={asset} record={recordMap.get(asset.id)} onSave={onSave} />
          ))}
        </div>
      ))}
    </div>
  );
}
