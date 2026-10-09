import { useEffect, useState } from "react";
import { Boxes, EllipsisVertical, Pencil, Plus, Search, Wrench } from "lucide-react";

import { api } from "../lib/api";
import { Avatar, RowMenu, TableHead, useFormPanel, useRowMenu, useSort, type RowMenuItem } from "./AdminTable";

export type ProcessUnitRecord = {
  id: string;
  station_id: string;
  unit_type_id: string;
  name: string;
  is_active: boolean;
};

type ProcessUnitTypeRecord = {
  id: string;
  name: string;
  code: string | null;
  stage: string | null;
  is_active: boolean;
};

type StationOption = { id: string; name: string; is_active: boolean };
type AssetOption = { id: string; station_id: string; process_unit_id: string | null; name: string; is_active: boolean };

// Etapas do tratamento, para agrupar os tipos de unidade.
const STAGES = [
  "Preliminar", "Equalização", "Elevatória", "Primário", "Secundário anaeróbio", "Secundário aeróbio",
  "Clarificação/decantação", "Terciário/polimento", "Desinfecção", "Tratamento de lodo", "Medição",
  "Disposição final", "Utilidades", "Captação (ETA)", "Coagulação/floculação (ETA)", "Filtração (ETA)",
  "Membranas (ETA)", "Reservação",
];

type SortKey = "name" | "type" | "stage" | "status";

const SORT_COLUMNS: [SortKey, string, string][] = [
  ["name", "Nome", "collab-col-name"],
  ["type", "Tipo", "collab-col-category"],
  ["stage", "Etapa", "collab-col-contact"],
  ["status", "Status", "collab-col-status"],
];

function errorDetail(error: unknown): string | null {
  if (typeof error === "object" && error !== null && "detail" in error && typeof error.detail === "string") {
    return error.detail;
  }
  return null;
}

export default function ProcessUnitAdmin({
  stations,
  assets,
  units,
  onUnitsChanged,
  onAssetsChanged,
}: {
  stations: StationOption[];
  assets: AssetOption[];
  units: ProcessUnitRecord[];
  onUnitsChanged: () => Promise<void>;
  onAssetsChanged: () => Promise<void>;
}) {
  const [types, setTypes] = useState<ProcessUnitTypeRecord[]>([]);
  const [search, setSearch] = useState("");
  const [stationFilter, setStationFilter] = useState("");
  const [formMode, setFormMode] = useState<"UNIT" | "TYPE">("UNIT");
  const [editingId, setEditingId] = useState<string | null>(null);
  const [stationId, setStationId] = useState("");
  const [unitTypeId, setUnitTypeId] = useState("");
  const [name, setName] = useState("");
  const [typeName, setTypeName] = useState("");
  const [typeCode, setTypeCode] = useState("");
  const [typeStage, setTypeStage] = useState("");
  const [expandedId, setExpandedId] = useState<string | null>(null);
  const [assetToAdd, setAssetToAdd] = useState("");
  const [feedback, setFeedback] = useState<string | null>(null);
  const [rowFeedback, setRowFeedback] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const { sortKey, sortAsc, toggleSort, sortBy } = useSort<SortKey>("name");
  const { menu, openMenu, closeMenu } = useRowMenu();
  const panel = useFormPanel();
  const stationMap = new Map(stations.map((item) => [item.id, item]));
  const typeMap = new Map(types.map((item) => [item.id, item]));

  async function loadTypes() {
    try {
      setTypes(await api<ProcessUnitTypeRecord[]>("/api/v1/process-unit-types?limit=500"));
    } catch {
      setRowFeedback("Não foi possível carregar os tipos de unidade.");
    }
  }

  useEffect(() => {
    void loadTypes();
  }, []);

  const term = search.trim().toLowerCase();
  const visible = units.filter((item) => {
    if (stationFilter && item.station_id !== stationFilter) return false;
    if (!term) return true;
    const type = typeMap.get(item.unit_type_id);
    return [item.name, stationMap.get(item.station_id)?.name, type?.name, type?.stage]
      .some((value) => (value ?? "").toLowerCase().includes(term));
  });

  const sorted = sortBy(visible, (item, key) => {
    if (key === "type") return typeMap.get(item.unit_type_id)?.name ?? "";
    if (key === "stage") return typeMap.get(item.unit_type_id)?.stage ?? "";
    if (key === "status") return item.is_active ? "0" : "1";
    return (stationMap.get(item.station_id)?.name ?? "") + " " + item.name;
  });

  function resetForm() {
    setEditingId(null);
    setStationId(stationFilter); setUnitTypeId(""); setName("");
    setTypeName(""); setTypeCode(""); setTypeStage("");
  }

  function openNew(mode: "UNIT" | "TYPE") {
    resetForm();
    setFormMode(mode);
    setFeedback(null);
    panel.show();
  }

  function closeForm() {
    resetForm();
    setFeedback(null);
    panel.hide();
  }

  function startEdit(item: ProcessUnitRecord) {
    setFormMode("UNIT");
    setEditingId(item.id);
    setStationId(item.station_id);
    setUnitTypeId(item.unit_type_id);
    setName(item.name);
    setFeedback(null);
    panel.show();
  }

  async function saveUnit() {
    if (!stationId) return setFeedback("Selecione a estação.");
    if (!unitTypeId) return setFeedback("Selecione o tipo da unidade.");
    if (name.trim().length < 2) return setFeedback("Informe o nome da unidade.");
    setBusy(true);
    try {
      if (editingId) {
        await api("/api/v1/process-units/" + editingId, {
          method: "PATCH",
          body: JSON.stringify({ unit_type_id: unitTypeId, name: name.trim() }),
        });
        setRowFeedback("Unidade atualizada.");
        closeForm();
      } else {
        await api("/api/v1/process-units", {
          method: "POST",
          body: JSON.stringify({ station_id: stationId, unit_type_id: unitTypeId, name: name.trim() }),
        });
        // Mantem a estacao para cadastrar as proximas unidades da mesma estacao.
        setUnitTypeId(""); setName("");
        setFeedback("Unidade cadastrada. O formulário segue aberto para a próxima da mesma estação.");
      }
      await onUnitsChanged();
    } catch (error) {
      setFeedback(
        errorDetail(error) === "process_unit_name_already_exists"
          ? "Essa estação já tem uma unidade com esse nome. Use um nome diferente, como \"UASB 2\"."
          : "Não foi possível salvar a unidade.",
      );
    } finally {
      setBusy(false);
    }
  }

  async function saveType() {
    if (typeName.trim().length < 2) return setFeedback("Informe o nome do tipo de unidade.");
    setBusy(true);
    try {
      await api("/api/v1/process-unit-types", {
        method: "POST",
        body: JSON.stringify({ name: typeName.trim(), code: typeCode.trim() || null, stage: typeStage || null }),
      });
      setTypeName(""); setTypeCode("");
      setFeedback("Tipo de unidade cadastrado. O formulário segue aberto para o próximo.");
      await loadTypes();
    } catch (error) {
      const detail = errorDetail(error);
      setFeedback(
        detail === "process_unit_type_name_already_exists"
          ? "Já existe um tipo de unidade com esse nome."
          : detail === "process_unit_type_code_already_exists"
            ? "Já existe um tipo de unidade com esse código."
            : "Não foi possível salvar o tipo de unidade.",
      );
    } finally {
      setBusy(false);
    }
  }

  async function toggle(item: ProcessUnitRecord) {
    setBusy(true);
    try {
      await api("/api/v1/process-units/" + item.id, {
        method: "PATCH",
        body: JSON.stringify({ is_active: !item.is_active }),
      });
      setRowFeedback(item.is_active ? "Unidade inativada." : "Unidade reativada.");
      await onUnitsChanged();
    } catch {
      setRowFeedback("Não foi possível alterar a unidade.");
    } finally {
      setBusy(false);
    }
  }

  async function moveAsset(assetId: string, unitId: string | null) {
    setBusy(true);
    try {
      await api("/api/v1/assets/" + assetId, {
        method: "PATCH",
        body: JSON.stringify({ process_unit_id: unitId }),
      });
      setAssetToAdd("");
      setRowFeedback(unitId ? "Equipamento incluído na unidade." : "Equipamento retirado da unidade.");
      await onAssetsChanged();
    } catch {
      setRowFeedback("Não foi possível mover o equipamento.");
    } finally {
      setBusy(false);
    }
  }

  function toggleExpanded(item: ProcessUnitRecord) {
    setAssetToAdd("");
    setExpandedId(expandedId === item.id ? null : item.id);
  }

  function summary(item: ProcessUnitRecord): string {
    const count = assets.filter((asset) => asset.process_unit_id === item.id).length;
    return [
      stationMap.get(item.station_id)?.name ?? "Estação",
      count === 1 ? "1 equipamento" : count + " equipamentos",
    ].join(" · ");
  }

  const menuItem = menu ? units.find((item) => item.id === menu.id) : undefined;
  const menuItems: RowMenuItem[] = menuItem
    ? [
        { text: expandedId === menuItem.id ? "Fechar equipamentos" : "Equipamentos", run: () => toggleExpanded(menuItem) },
        { text: "Editar", run: () => startEdit(menuItem) },
        { text: menuItem.is_active ? "Inativar" : "Reativar", run: () => void toggle(menuItem), danger: menuItem.is_active },
      ]
    : [];

  return (
    <div className="admin-stack">
      {panel.open && formMode === "UNIT" && (
        <div className="compact-form admin-create-form" ref={panel.ref}>
          <h3 className="form-title">{editingId ? <Pencil size={17} /> : <Boxes size={17} />}{editingId ? "Editar unidade" : "Nova unidade"}</h3>
          <div className="compact-form-grid">
            <label><span>Estação <b className="required-mark">*</b></span>
              <select required aria-required="true" disabled={Boolean(editingId)} value={stationId} onChange={(e) => setStationId(e.target.value)}>
                <option value="">Selecione</option>
                {stations.filter((x) => x.is_active || x.id === stationId).map((x) => <option key={x.id} value={x.id}>{x.name}</option>)}
              </select>
            </label>
            <label><span>Tipo <b className="required-mark">*</b></span>
              <select required aria-required="true" value={unitTypeId} onChange={(e) => setUnitTypeId(e.target.value)}>
                <option value="">Selecione</option>
                {types.filter((x) => x.is_active || x.id === unitTypeId).map((x) => <option key={x.id} value={x.id}>{x.name}</option>)}
              </select>
            </label>
            <label className="form-span-2"><span>Nome <b className="required-mark">*</b></span><input required aria-required="true" placeholder="Como a equipe chama esta unidade, ex.: UASB 1" value={name} onChange={(e) => setName(e.target.value)} /></label>
          </div>
          <p className="required-hint">
            <b className="required-mark">*</b> Obrigatório. {types.length === 0 ? "Ainda não há tipos de unidade: feche e use \"Novo tipo\" primeiro." : "Os equipamentos são incluídos depois, na lista."}
          </p>
          <div className="admin-actions form-submit">
            <button className="primary-button" disabled={busy} onClick={() => void saveUnit()}>
              {!editingId && <Boxes size={17} />}
              {busy ? "Salvando..." : editingId ? "Salvar alterações" : "Cadastrar unidade"}
            </button>
            <button className="text-button" disabled={busy} onClick={closeForm}>{editingId ? "Cancelar" : "Fechar"}</button>
          </div>
          {feedback && <span className="inline-feedback">{feedback}</span>}
        </div>
      )}
      {panel.open && formMode === "TYPE" && (
        <div className="compact-form admin-create-form" ref={panel.ref}>
          <h3 className="form-title"><Plus size={17} />Novo tipo de unidade</h3>
          <div className="compact-form-grid">
            <label className="form-span-2"><span>Nome <b className="required-mark">*</b></span><input required aria-required="true" placeholder="Ex.: Reator UASB, Tanque de contato" value={typeName} onChange={(e) => setTypeName(e.target.value)} /></label>
            <label>Etapa do tratamento
              <select value={typeStage} onChange={(e) => setTypeStage(e.target.value)}>
                <option value="">Não informar</option>
                {STAGES.map((stage) => <option key={stage} value={stage}>{stage}</option>)}
              </select>
            </label>
            <label>Código<input placeholder="Opcional, ex.: U11" value={typeCode} onChange={(e) => setTypeCode(e.target.value)} /></label>
          </div>
          {types.length > 0 && (
            <div className="type-list">
              {types.map((item) => <div className="type-chip" key={item.id}><span>{item.name}</span></div>)}
            </div>
          )}
          <p className="required-hint"><b className="required-mark">*</b> Obrigatório. O tipo é um catálogo: cadastre uma vez e use em todas as estações.</p>
          <div className="admin-actions form-submit">
            <button className="primary-button" disabled={busy} onClick={() => void saveType()}>
              <Plus size={17} />{busy ? "Salvando..." : "Cadastrar tipo"}
            </button>
            <button className="text-button" disabled={busy} onClick={closeForm}>Fechar</button>
          </div>
          {feedback && <span className="inline-feedback">{feedback}</span>}
        </div>
      )}
      <div className="client-list-column">
        <div className="admin-toolbar">
          <label className="search-field">
            <Search size={16} />
            <input
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="Buscar unidade, estação, tipo ou etapa"
              aria-label="Buscar unidade"
            />
          </label>
          <select className="admin-toolbar-select" aria-label="Filtrar por estação" value={stationFilter} onChange={(e) => setStationFilter(e.target.value)}>
            <option value="">Todas as estações</option>
            {stations.map((x) => <option key={x.id} value={x.id}>{x.name}</option>)}
          </select>
          {!panel.open && (
            <>
              <button className="secondary-button" disabled={busy} onClick={() => openNew("TYPE")}><Plus size={17} /> Novo tipo</button>
              <button className="primary-button" disabled={busy} onClick={() => openNew("UNIT")}><Boxes size={17} /> Nova unidade</button>
            </>
          )}
        </div>
        {rowFeedback && <span className="inline-feedback" role="status">{rowFeedback}</span>}
        <div className="admin-list collab-table collab-table-wide" role="table" aria-label="Unidades de processo">
          <TableHead columns={SORT_COLUMNS} sortKey={sortKey} sortAsc={sortAsc} onSort={toggleSort} />
          {sorted.map((item) => {
            const type = typeMap.get(item.unit_type_id);
            const inUnit = assets.filter((asset) => asset.process_unit_id === item.id);
            const available = assets.filter(
              (asset) => asset.station_id === item.station_id && asset.process_unit_id === null && asset.is_active,
            );
            const expandText = expandedId === item.id ? "Fechar equipamentos" : "Equipamentos";
            return (
              <div className="client-entry" key={item.id}>
                <div className={item.is_active ? "collab-row" : "collab-row collab-row-inactive"} role="row">
                  <div className="collab-person" role="cell">
                    <Avatar name={item.name} />
                    <div>
                      <strong>{item.name}</strong>
                      <span title={summary(item)}>{summary(item)}</span>
                    </div>
                  </div>
                  <div className="collab-col-category" role="cell">
                    <span className="collab-chip" title={type?.name}>{type?.name ?? "—"}</span>
                  </div>
                  <div className="collab-col-contact" role="cell">{type?.stage ?? "—"}</div>
                  <div className="collab-col-status" role="cell">
                    <span className={item.is_active ? "collab-status active" : "collab-status"}>{item.is_active ? "Ativa" : "Inativa"}</span>
                  </div>
                  <div className="collab-actions" role="cell">
                    <button
                      className={expandedId === item.id ? "icon-action icon-action-on" : "icon-action"}
                      disabled={busy}
                      title={expandText}
                      aria-label={expandText + ": " + item.name}
                      aria-expanded={expandedId === item.id}
                      onClick={() => toggleExpanded(item)}
                    >
                      <Wrench size={16} />
                    </button>
                    <button
                      className="icon-action row-menu-trigger"
                      disabled={busy}
                      title="Mais ações"
                      aria-label={"Mais ações: " + item.name}
                      aria-haspopup="menu"
                      aria-expanded={menu?.id === item.id}
                      onClick={(event) => openMenu(item.id, event.currentTarget)}
                    >
                      <EllipsisVertical size={16} />
                    </button>
                  </div>
                </div>
                {expandedId === item.id && (
                  <div className="client-contacts">
                    <span className="eyebrow">Equipamentos nesta unidade</span>
                    {inUnit.map((asset) => (
                      <div className="client-contact-row" key={asset.id}>
                        <div><strong>{asset.name}</strong></div>
                        <div className="admin-actions">
                          <button className="text-button" disabled={busy} onClick={() => void moveAsset(asset.id, null)}>Retirar da unidade</button>
                        </div>
                      </div>
                    ))}
                    {inUnit.length === 0 && (
                      <div className="empty-state">
                        Nenhum equipamento nesta unidade. Escolha abaixo um equipamento da estação que ainda não está em nenhuma unidade.
                      </div>
                    )}
                    <div className="client-contact-form">
                      <label>Equipamento da estação sem unidade
                        <select value={assetToAdd} onChange={(e) => setAssetToAdd(e.target.value)}>
                          <option value="">{available.length === 0 ? "Nenhum disponível" : "Selecione"}</option>
                          {available.map((asset) => <option key={asset.id} value={asset.id}>{asset.name}</option>)}
                        </select>
                      </label>
                      <button className="small-button" disabled={busy || !assetToAdd} onClick={() => void moveAsset(assetToAdd, item.id)}>Incluir na unidade</button>
                    </div>
                  </div>
                )}
              </div>
            );
          })}
          {units.length === 0 && (
            <div className="empty-state">
              Nenhuma unidade cadastrada. Cadastre os tipos em "Novo tipo" e depois as unidades de cada estação.
            </div>
          )}
          {units.length > 0 && visible.length === 0 && (
            <div className="empty-state">
              Nenhuma unidade encontrada com esse filtro. Limpe a busca ou escolha outra estação.
            </div>
          )}
        </div>
        {menu && menuItem && <RowMenu menu={menu} items={menuItems} busy={busy} onClose={closeMenu} />}
      </div>
    </div>
  );
}
