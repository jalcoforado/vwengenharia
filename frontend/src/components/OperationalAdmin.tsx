import { useState } from "react";

import { api } from "../lib/api";

export type ClientRecord = {
  id: string;
  name: string;
  document: string | null;
  contact_name: string | null;
  contact_email: string | null;
  contact_phone: string | null;
  is_active: boolean;
};

export type DevelopmentRecord = {
  id: string;
  client_id: string;
  name: string;
  address_line: string | null;
  city: string | null;
  state: string | null;
  postal_code: string | null;
  is_active: boolean;
};

export type AdminStation = {
  id: string;
  development_id: string;
  name: string;
  code: string | null;
  station_type: string | null;
  visit_frequency_days: number | null;
  is_active: boolean;
};

export type AssetTypeRecord = {
  id: string;
  name: string;
  code: string | null;
  is_active: boolean;
};

export type AssetRecord = {
  id: string;
  station_id: string;
  asset_type_id: string;
  name: string;
  manufacturer: string | null;
  model: string | null;
  serial_number: string | null;
  status: string;
  is_active: boolean;
};

type Props = {
  clients: ClientRecord[];
  developments: DevelopmentRecord[];
  stations: AdminStation[];
  assetTypes: AssetTypeRecord[];
  assets: AssetRecord[];
  onChanged: () => Promise<void>;
  onOpenStation?: (stationId: string) => void;
};

export default function OperationalAdmin({
  clients,
  developments,
  stations,
  assetTypes,
  assets,
  onChanged,
  onOpenStation,
}: Props) {
  const [tab, setTab] = useState<"CLIENTES" | "EMPREENDIMENTOS" | "ESTACOES" | "ATIVOS">("CLIENTES");

  return (
    <section className="section-card admin-hub">
      <div className="section-heading admin-heading">
        <div>
          <span className="eyebrow">Administracao operacional</span>
          <h2>Estrutura da operacao</h2>
          <p className="section-copy">
            Cadastre a hierarquia Cliente → Empreendimento → Estacao → Ativo.
          </p>
        </div>
        <div className="admin-summary">
          <span><strong>{clients.filter((item) => item.is_active).length}</strong> clientes</span>
          <span><strong>{stations.filter((item) => item.is_active).length}</strong> estacoes</span>
          <span><strong>{assets.filter((item) => item.is_active).length}</strong> ativos</span>
        </div>
      </div>

      <div className="admin-tabs">
        {[
          ["CLIENTES", "Clientes"],
          ["EMPREENDIMENTOS", "Empreendimentos"],
          ["ESTACOES", "Estacoes"],
          ["ATIVOS", "Ativos"],
        ].map(([value, label]) => (
          <button
            key={value}
            className={tab === value ? "admin-tab active" : "admin-tab"}
            onClick={() => setTab(value as typeof tab)}
          >
            {label}
          </button>
        ))}
      </div>

      {tab === "CLIENTES" && <ClientAdmin clients={clients} onChanged={onChanged} />}
      {tab === "EMPREENDIMENTOS" && (
        <DevelopmentAdmin clients={clients} developments={developments} onChanged={onChanged} />
      )}
      {tab === "ESTACOES" && (
        <StationAdmin
          developments={developments}
          stations={stations}
          onChanged={onChanged}
          onOpenStation={onOpenStation}
        />
      )}
      {tab === "ATIVOS" && (
        <AssetAdmin stations={stations} assetTypes={assetTypes} assets={assets} onChanged={onChanged} />
      )}
    </section>
  );
}

function ClientAdmin({ clients, onChanged }: { clients: ClientRecord[]; onChanged: () => Promise<void> }) {
  const [name, setName] = useState("");
  const [document, setDocument] = useState("");
  const [contactName, setContactName] = useState("");
  const [contactEmail, setContactEmail] = useState("");
  const [contactPhone, setContactPhone] = useState("");
  const [feedback, setFeedback] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function toggle(client: ClientRecord) {
    setBusy(true);
    try {
      await api("/api/v1/clients/" + client.id, {
        method: "PATCH",
        body: JSON.stringify({ is_active: !client.is_active }),
      });
      setFeedback(client.is_active ? "Cliente inativado." : "Cliente reativado.");
      await onChanged();
    } catch {
      setFeedback("Nao foi possivel alterar o cliente.");
    } finally {
      setBusy(false);
    }
  }

  async function create() {
    if (name.trim().length < 2) return setFeedback("Informe o nome do cliente.");
    setBusy(true);
    try {
      await api("/api/v1/clients", {
        method: "POST",
        body: JSON.stringify({
          name: name.trim(),
          document: document.trim() || null,
          contact_name: contactName.trim() || null,
          contact_email: contactEmail.trim() || null,
          contact_phone: contactPhone.trim() || null,
        }),
      });
      setName(""); setDocument(""); setContactName(""); setContactEmail(""); setContactPhone("");
      setFeedback("Cliente cadastrado.");
      await onChanged();
    } catch {
      setFeedback("Nao foi possivel cadastrar o cliente.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="admin-panel">
      <div className="admin-list">
        {clients.map((client) => (
          <div className="admin-row" key={client.id}>
            <div><strong>{client.name}</strong><span>{client.document || client.contact_name || "Sem documento informado"}</span></div>
            <div className="admin-actions">
              <span className={client.is_active ? "status status-revisada" : "status"}>{client.is_active ? "Ativo" : "Inativo"}</span>
              <button className="text-button" disabled={busy} onClick={() => void toggle(client)}>
                {client.is_active ? "Inativar" : "Reativar"}
              </button>
            </div>
          </div>
        ))}
        {clients.length === 0 && <div className="empty-state">Nenhum cliente cadastrado.</div>}
      </div>
      <div className="compact-form admin-create-form">
        <h3>Novo cliente</h3>
        <div className="compact-form-grid">
          <label>Nome<input value={name} onChange={(e) => setName(e.target.value)} /></label>
          <label>CNPJ/Documento<input value={document} onChange={(e) => setDocument(e.target.value)} /></label>
          <label>Contato<input value={contactName} onChange={(e) => setContactName(e.target.value)} /></label>
          <label>Email<input type="email" value={contactEmail} onChange={(e) => setContactEmail(e.target.value)} /></label>
          <label>Telefone<input value={contactPhone} onChange={(e) => setContactPhone(e.target.value)} /></label>
        </div>
        <button className="small-button" disabled={busy} onClick={() => void create()}>{busy ? "Salvando..." : "Cadastrar cliente"}</button>
        {feedback && <span className="inline-feedback">{feedback}</span>}
      </div>
    </div>
  );
}

function DevelopmentAdmin({ clients, developments, onChanged }: { clients: ClientRecord[]; developments: DevelopmentRecord[]; onChanged: () => Promise<void> }) {
  const [clientId, setClientId] = useState("");
  const [name, setName] = useState("");
  const [addressLine, setAddressLine] = useState("");
  const [city, setCity] = useState("Fortaleza");
  const [state, setState] = useState("CE");
  const [postalCode, setPostalCode] = useState("");
  const [feedback, setFeedback] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const clientMap = new Map(clients.map((item) => [item.id, item]));

  async function toggle(item: DevelopmentRecord) {
    setBusy(true);
    try {
      await api("/api/v1/developments/" + item.id, {
        method: "PATCH",
        body: JSON.stringify({ is_active: !item.is_active }),
      });
      setFeedback(item.is_active ? "Empreendimento inativado." : "Empreendimento reativado.");
      await onChanged();
    } catch {
      setFeedback("Nao foi possivel alterar o empreendimento.");
    } finally {
      setBusy(false);
    }
  }

  async function create() {
    if (!clientId || name.trim().length < 2) return setFeedback("Selecione o cliente e informe o empreendimento.");
    setBusy(true);
    try {
      await api("/api/v1/developments", { method: "POST", body: JSON.stringify({
        client_id: clientId, name: name.trim(), address_line: addressLine.trim() || null,
        city: city.trim() || null, state: state.trim().toUpperCase() || null, postal_code: postalCode.trim() || null,
      }) });
      setName(""); setAddressLine(""); setPostalCode(""); setFeedback("Empreendimento cadastrado.");
      await onChanged();
    } catch { setFeedback("Nao foi possivel cadastrar o empreendimento."); }
    finally { setBusy(false); }
  }

  return (
    <div className="admin-panel">
      <div className="admin-list">
        {developments.map((item) => (
          <div className="admin-row" key={item.id}>
            <div><strong>{item.name}</strong><span>{clientMap.get(item.client_id)?.name ?? "Cliente"} · {[item.city, item.state].filter(Boolean).join("/")}</span></div>
            <div className="admin-actions">
              <span className={item.is_active ? "status status-revisada" : "status"}>{item.is_active ? "Ativo" : "Inativo"}</span>
              <button className="text-button" disabled={busy} onClick={() => void toggle(item)}>
                {item.is_active ? "Inativar" : "Reativar"}
              </button>
            </div>
          </div>
        ))}
      </div>
      <div className="compact-form admin-create-form">
        <h3>Novo empreendimento</h3>
        <div className="compact-form-grid">
          <label>Cliente<select value={clientId} onChange={(e) => setClientId(e.target.value)}><option value="">Selecione</option>{clients.filter((x) => x.is_active).map((x) => <option key={x.id} value={x.id}>{x.name}</option>)}</select></label>
          <label>Nome<input value={name} onChange={(e) => setName(e.target.value)} /></label>
          <label>Endereco<input value={addressLine} onChange={(e) => setAddressLine(e.target.value)} /></label>
          <label>Cidade<input value={city} onChange={(e) => setCity(e.target.value)} /></label>
          <label>UF<input maxLength={2} value={state} onChange={(e) => setState(e.target.value)} /></label>
          <label>CEP<input value={postalCode} onChange={(e) => setPostalCode(e.target.value)} /></label>
        </div>
        <button className="small-button" disabled={busy} onClick={() => void create()}>{busy ? "Salvando..." : "Cadastrar empreendimento"}</button>
        {feedback && <span className="inline-feedback">{feedback}</span>}
      </div>
    </div>
  );
}

function StationAdmin({
  developments,
  stations,
  onChanged,
  onOpenStation,
}: {
  developments: DevelopmentRecord[];
  stations: AdminStation[];
  onChanged: () => Promise<void>;
  onOpenStation?: (stationId: string) => void;
}) {
  const [developmentId, setDevelopmentId] = useState("");
  const [name, setName] = useState("");
  const [code, setCode] = useState("");
  const [stationType, setStationType] = useState("ETE");
  const [frequencyDays, setFrequencyDays] = useState("7");
  const [feedback, setFeedback] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const developmentMap = new Map(developments.map((item) => [item.id, item]));

  async function toggle(station: AdminStation) {
    setBusy(true);
    try {
      await api("/api/v1/stations/" + station.id, {
        method: "PATCH",
        body: JSON.stringify({ is_active: !station.is_active }),
      });
      setFeedback(station.is_active ? "Estacao inativada." : "Estacao reativada.");
      await onChanged();
    } catch {
      setFeedback("Nao foi possivel alterar a estacao.");
    } finally {
      setBusy(false);
    }
  }

  async function create() {
    if (!developmentId || name.trim().length < 2) return setFeedback("Selecione o empreendimento e informe a estacao.");
    setBusy(true);
    try {
      await api("/api/v1/stations", { method: "POST", body: JSON.stringify({
        development_id: developmentId, name: name.trim(), code: code.trim() || null,
        station_type: stationType, visit_frequency_days: Number(frequencyDays) || null,
      }) });
      setName(""); setCode(""); setFeedback("Estacao cadastrada."); await onChanged();
    } catch { setFeedback("Nao foi possivel cadastrar a estacao."); }
    finally { setBusy(false); }
  }

  return (
    <div className="admin-panel">
      <div className="admin-list">
        {stations.map((station) => (
          <div className="admin-row" key={station.id}>
            <div><strong>{station.name}</strong><span>{developmentMap.get(station.development_id)?.name ?? "Empreendimento"} · {station.code || station.station_type || "Estacao"}</span></div>
            <div className="admin-actions">
              <span className={station.is_active ? "status status-revisada" : "status"}>
                {station.is_active ? (station.visit_frequency_days ? station.visit_frequency_days + "d" : "Ativa") : "Inativa"}
              </span>
              {onOpenStation && (
                <button className="text-button" onClick={() => onOpenStation(station.id)}>
                  Ver estacao
                </button>
              )}
              <button className="text-button" disabled={busy} onClick={() => void toggle(station)}>
                {station.is_active ? "Inativar" : "Reativar"}
              </button>
            </div>
          </div>
        ))}
      </div>
      <div className="compact-form admin-create-form">
        <h3>Nova estacao</h3>
        <div className="compact-form-grid">
          <label>Empreendimento<select value={developmentId} onChange={(e) => setDevelopmentId(e.target.value)}><option value="">Selecione</option>{developments.filter((x) => x.is_active).map((x) => <option key={x.id} value={x.id}>{x.name}</option>)}</select></label>
          <label>Nome<input value={name} onChange={(e) => setName(e.target.value)} /></label>
          <label>Codigo<input value={code} onChange={(e) => setCode(e.target.value)} /></label>
          <label>Tipo<select value={stationType} onChange={(e) => setStationType(e.target.value)}><option value="ETE">ETE</option><option value="ETA">ETA</option><option value="EEE">EEE</option><option value="ELEVATORIA">Elevatoria</option><option value="OUTRA">Outra</option></select></label>
          <label>Frequencia<select value={frequencyDays} onChange={(e) => setFrequencyDays(e.target.value)}><option value="1">Diaria</option><option value="7">Semanal</option><option value="14">Quinzenal</option><option value="30">Mensal</option></select></label>
        </div>
        <button className="small-button" disabled={busy} onClick={() => void create()}>{busy ? "Salvando..." : "Cadastrar estacao"}</button>
        {feedback && <span className="inline-feedback">{feedback}</span>}
      </div>
    </div>
  );
}

function AssetAdmin({ stations, assetTypes, assets, onChanged }: { stations: AdminStation[]; assetTypes: AssetTypeRecord[]; assets: AssetRecord[]; onChanged: () => Promise<void> }) {
  const [stationId, setStationId] = useState("");
  const [assetTypeId, setAssetTypeId] = useState("");
  const [assetTypeName, setAssetTypeName] = useState("");
  const [assetTypeCode, setAssetTypeCode] = useState("");
  const [name, setName] = useState("");
  const [manufacturer, setManufacturer] = useState("");
  const [model, setModel] = useState("");
  const [serialNumber, setSerialNumber] = useState("");
  const [statusValue, setStatusValue] = useState("OPERANDO");
  const [feedback, setFeedback] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const stationMap = new Map(stations.map((item) => [item.id, item]));
  const typeMap = new Map(assetTypes.map((item) => [item.id, item]));

  async function updateAsset(asset: AssetRecord, patch: Record<string, unknown>) {
    setBusy(true);
    try {
      await api("/api/v1/assets/" + asset.id, {
        method: "PATCH",
        body: JSON.stringify(patch),
      });
      setFeedback("Ativo atualizado.");
      await onChanged();
    } catch {
      setFeedback("Nao foi possivel atualizar o ativo.");
    } finally {
      setBusy(false);
    }
  }

  async function toggleAssetType(item: AssetTypeRecord) {
    setBusy(true);
    try {
      await api("/api/v1/asset-types/" + item.id, {
        method: "PATCH",
        body: JSON.stringify({ is_active: !item.is_active }),
      });
      setFeedback("Tipo de ativo atualizado.");
      await onChanged();
    } catch {
      setFeedback("Nao foi possivel atualizar o tipo.");
    } finally {
      setBusy(false);
    }
  }

  async function createAssetType() {
    if (assetTypeName.trim().length < 2) return setFeedback("Informe o nome do tipo de ativo.");
    setBusy(true);
    try {
      await api("/api/v1/asset-types", { method: "POST", body: JSON.stringify({ name: assetTypeName.trim(), code: assetTypeCode.trim() || null }) });
      setAssetTypeName(""); setAssetTypeCode(""); setFeedback("Tipo de ativo cadastrado."); await onChanged();
    } catch { setFeedback("Nao foi possivel cadastrar o tipo de ativo."); }
    finally { setBusy(false); }
  }

  async function createAsset() {
    if (!stationId || !assetTypeId || name.trim().length < 2) return setFeedback("Selecione estacao/tipo e informe o ativo.");
    setBusy(true);
    try {
      await api("/api/v1/assets", { method: "POST", body: JSON.stringify({
        station_id: stationId, asset_type_id: assetTypeId, name: name.trim(),
        manufacturer: manufacturer.trim() || null, model: model.trim() || null,
        serial_number: serialNumber.trim() || null, status: statusValue,
      }) });
      setName(""); setManufacturer(""); setModel(""); setSerialNumber(""); setFeedback("Ativo cadastrado."); await onChanged();
    } catch { setFeedback("Nao foi possivel cadastrar o ativo."); }
    finally { setBusy(false); }
  }

  return (
    <div className="admin-panel">
      <div className="admin-list">
        {assets.map((asset) => (
          <div className="admin-row" key={asset.id}>
            <div><strong>{asset.name}</strong><span>{stationMap.get(asset.station_id)?.name ?? "Estacao"} · {typeMap.get(asset.asset_type_id)?.name ?? "Tipo"} · {asset.manufacturer || asset.model || "Sem fabricante"}</span></div>
            <div className="admin-actions asset-actions">
              <select
                value={asset.status}
                disabled={busy}
                onChange={(event) => void updateAsset(asset, { status: event.target.value })}
              >
                <option value="OPERANDO">Operando</option>
                <option value="DESLIGADO">Desligado</option>
                <option value="EM_MANUTENCAO">Em manutencao</option>
                <option value="AGUARDANDO_MANUTENCAO">Aguardando manutencao</option>
                <option value="AGUARDANDO_INSTALACAO">Aguardando instalacao</option>
                <option value="NECESSITA_VERIFICACAO">Necessita verificacao</option>
                <option value="NAO_POSSUI">Nao possui</option>
                <option value="NAO_APLICAVEL">Nao aplicavel</option>
              </select>
              <button className="text-button" disabled={busy} onClick={() => void updateAsset(asset, { is_active: !asset.is_active })}>
                {asset.is_active ? "Inativar" : "Reativar"}
              </button>
            </div>
          </div>
        ))}
      </div>
      <div className="admin-double-form">
        <div className="compact-form admin-create-form">
          <h3>Novo tipo de ativo</h3>
          <div className="compact-form-grid">
            <label>Nome<input value={assetTypeName} onChange={(e) => setAssetTypeName(e.target.value)} /></label>
            <label>Codigo<input value={assetTypeCode} onChange={(e) => setAssetTypeCode(e.target.value)} /></label>
          </div>
          <div className="type-list">
            {assetTypes.map((item) => (
              <div className="type-chip" key={item.id}>
                <span>{item.name}</span>
                <button className="text-button" disabled={busy} onClick={() => void toggleAssetType(item)}>
                  {item.is_active ? "Inativar" : "Reativar"}
                </button>
              </div>
            ))}
          </div>
          <button className="small-button" disabled={busy} onClick={() => void createAssetType()}>{busy ? "Salvando..." : "Cadastrar tipo"}</button>
        </div>
        <div className="compact-form admin-create-form">
          <h3>Novo ativo</h3>
          <div className="compact-form-grid">
            <label>Estacao<select value={stationId} onChange={(e) => setStationId(e.target.value)}><option value="">Selecione</option>{stations.filter((x) => x.is_active).map((x) => <option key={x.id} value={x.id}>{x.name}</option>)}</select></label>
            <label>Tipo<select value={assetTypeId} onChange={(e) => setAssetTypeId(e.target.value)}><option value="">Selecione</option>{assetTypes.filter((x) => x.is_active).map((x) => <option key={x.id} value={x.id}>{x.name}</option>)}</select></label>
            <label>Nome<input value={name} onChange={(e) => setName(e.target.value)} /></label>
            <label>Fabricante<input value={manufacturer} onChange={(e) => setManufacturer(e.target.value)} /></label>
            <label>Modelo<input value={model} onChange={(e) => setModel(e.target.value)} /></label>
            <label>Numero de serie<input value={serialNumber} onChange={(e) => setSerialNumber(e.target.value)} /></label>
            <label>Status<select value={statusValue} onChange={(e) => setStatusValue(e.target.value)}><option value="OPERANDO">Operando</option><option value="DESLIGADO">Desligado</option><option value="EM_MANUTENCAO">Em manutencao</option><option value="AGUARDANDO_MANUTENCAO">Aguardando manutencao</option><option value="AGUARDANDO_INSTALACAO">Aguardando instalacao</option><option value="NECESSITA_VERIFICACAO">Necessita verificacao</option><option value="NAO_POSSUI">Nao possui</option><option value="NAO_APLICAVEL">Nao aplicavel</option></select></label>
          </div>
          <button className="small-button" disabled={busy} onClick={() => void createAsset()}>{busy ? "Salvando..." : "Cadastrar ativo"}</button>
        </div>
      </div>
      {feedback && <span className="inline-feedback">{feedback}</span>}
    </div>
  );
}
