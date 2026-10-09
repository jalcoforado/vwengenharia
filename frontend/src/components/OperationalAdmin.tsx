import { useState } from "react";
import { Search } from "lucide-react";

import { api } from "../lib/api";
import { formatDocument, isValidCpfCnpj, normalizeDocument } from "../lib/document";
import { formatPhone, isCompletePhone } from "../lib/phone";

export type ClientRecord = {
  id: string;
  name: string;
  document: string | null;
  contact_name: string | null;
  contact_email: string | null;
  contact_phone: string | null;
  contact_role: string | null;
  contact_whatsapp: string | null;
  is_active: boolean;
};

export type ContactScope = "GERAL" | "TECNICO" | "FINANCEIRO" | "COMERCIAL" | "ADMINISTRATIVO";

export type ClientContactRecord = {
  id: string;
  client_id: string;
  development_id: string;
  scope: ContactScope;
  is_primary: boolean;
  portal_access: boolean;
  is_active: boolean;
};

const CONTACT_SCOPES: [ContactScope, string][] = [
  ["GERAL", "Geral"],
  ["TECNICO", "Tecnico"],
  ["FINANCEIRO", "Financeiro"],
  ["COMERCIAL", "Comercial"],
  ["ADMINISTRATIVO", "Administrativo"],
];

export type DevelopmentRecord = {
  id: string;
  client_id: string;
  name: string;
  document: string | null;
  contact_phone: string | null;
  contact_email: string | null;
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
            Cadastre o responsavel, depois o empreendimento (o cliente da MW), suas estacoes e ativos.
          </p>
        </div>
        <div className="admin-summary">
          <span><strong>{developments.filter((item) => item.is_active).length}</strong> empreendimentos</span>
          <span><strong>{clients.filter((item) => item.is_active).length}</strong> responsaveis</span>
          <span><strong>{stations.filter((item) => item.is_active).length}</strong> estacoes</span>
          <span><strong>{assets.filter((item) => item.is_active).length}</strong> ativos</span>
        </div>
      </div>

      <div className="admin-tabs">
        {[
          ["CLIENTES", "Responsaveis"],
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

      {tab === "CLIENTES" && (
        <ClientAdmin clients={clients} developments={developments} onChanged={onChanged} />
      )}
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

function ClientAdmin({
  clients,
  developments,
  onChanged,
}: {
  clients: ClientRecord[];
  developments: DevelopmentRecord[];
  onChanged: () => Promise<void>;
}) {
  const [editingId, setEditingId] = useState<string | null>(null);
  const [name, setName] = useState("");
  const [document, setDocument] = useState("");
  const [contactName, setContactName] = useState("");
  const [contactRole, setContactRole] = useState("");
  const [contactEmail, setContactEmail] = useState("");
  const [contactPhone, setContactPhone] = useState("");
  const [contactWhatsapp, setContactWhatsapp] = useState("");
  const [expandedId, setExpandedId] = useState<string | null>(null);
  const [contacts, setContacts] = useState<ClientContactRecord[]>([]);
  const [linkDevelopmentId, setLinkDevelopmentId] = useState("");
  const [linkScope, setLinkScope] = useState<ContactScope>("TECNICO");
  const [feedback, setFeedback] = useState<string | null>(null);
  const [linkFeedback, setLinkFeedback] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [search, setSearch] = useState("");
  const developmentMap = new Map(developments.map((item) => [item.id, item]));

  const term = search.trim().toLowerCase();
  const termDigits = term.replace(/\D/g, "");
  const visibleClients = clients.filter((client) => {
    if (!term) return true;
    const fields = [
      client.name,
      client.document,
      client.contact_role,
      client.contact_phone,
      client.contact_whatsapp,
      client.contact_email,
      client.contact_name,
    ].map((value) => value ?? "");
    if (fields.some((value) => value.toLowerCase().includes(term))) return true;
    // Permite achar CPF/CNPJ e telefones digitando so os numeros.
    return (
      termDigits.length >= 3 &&
      [client.document, client.contact_phone, client.contact_whatsapp].some((value) =>
        (value ?? "").replace(/\D/g, "").includes(termDigits),
      )
    );
  });

  function resetForm() {
    setEditingId(null);
    setName(""); setDocument(""); setContactName(""); setContactRole("");
    setContactEmail(""); setContactPhone(""); setContactWhatsapp("");
  }

  function startEdit(client: ClientRecord) {
    setEditingId(client.id);
    setName(client.name);
    setDocument(formatDocument(client.document));
    setContactName(client.contact_name ?? "");
    setContactRole(client.contact_role ?? "");
    setContactEmail(client.contact_email ?? "");
    setContactPhone(formatPhone(client.contact_phone));
    setContactWhatsapp(formatPhone(client.contact_whatsapp));
    setFeedback(null);
  }

  async function toggle(client: ClientRecord) {
    setBusy(true);
    try {
      await api("/api/v1/clients/" + client.id, {
        method: "PATCH",
        body: JSON.stringify({ is_active: !client.is_active }),
      });
      setFeedback(client.is_active ? "Responsavel inativado." : "Responsavel reativado.");
      await onChanged();
    } catch {
      setFeedback("Nao foi possivel alterar o responsavel.");
    } finally {
      setBusy(false);
    }
  }

  async function save() {
    if (name.trim().length < 2) return setFeedback("Informe o nome do responsavel.");
    if (!contactRole.trim()) return setFeedback("Informe a funcao do responsavel.");
    if (!document.trim()) return setFeedback("Informe o CPF/CNPJ do responsavel.");
    if (!isValidCpfCnpj(document)) {
      return setFeedback("CPF/CNPJ invalido. Confira os numeros digitados.");
    }
    if (!contactPhone.trim() && !contactWhatsapp.trim()) {
      return setFeedback("Informe o telefone ou o WhatsApp do responsavel.");
    }
    if (contactPhone.trim() && !isCompletePhone(contactPhone)) {
      return setFeedback("Telefone incompleto. Informe DDD e numero.");
    }
    if (contactWhatsapp.trim() && !isCompletePhone(contactWhatsapp)) {
      return setFeedback("WhatsApp incompleto. Informe DDD e numero.");
    }
    setBusy(true);
    try {
      await api(editingId ? "/api/v1/clients/" + editingId : "/api/v1/clients", {
        method: editingId ? "PATCH" : "POST",
        body: JSON.stringify({
          name: name.trim(),
          document: normalizeDocument(document),
          contact_name: contactName.trim() || null,
          contact_role: contactRole.trim() || null,
          contact_email: contactEmail.trim() || null,
          contact_phone: contactPhone.trim() || null,
          contact_whatsapp: contactWhatsapp.trim() || null,
        }),
      });
      setFeedback(editingId ? "Responsavel atualizado." : "Responsavel cadastrado.");
      resetForm();
      await onChanged();
    } catch (error) {
      const status =
        typeof error === "object" && error !== null && "status" in error ? error.status : null;
      if (status === 409) {
        setFeedback("Ja existe um responsavel com esse CPF/CNPJ. Use a busca para localiza-lo.");
      } else if (status === 422) {
        setFeedback("Confira os dados informados, em especial o email.");
      } else {
        setFeedback(editingId ? "Nao foi possivel atualizar o responsavel." : "Nao foi possivel cadastrar o responsavel.");
      }
    } finally {
      setBusy(false);
    }
  }

  async function loadContacts(clientId: string) {
    try {
      setContacts(
        await api<ClientContactRecord[]>("/api/v1/client-contacts?limit=500&client_id=" + clientId),
      );
    } catch {
      setContacts([]);
      setLinkFeedback("Nao foi possivel carregar os empreendimentos do responsavel.");
    }
  }

  async function toggleExpanded(client: ClientRecord) {
    setLinkFeedback(null);
    setLinkDevelopmentId("");
    if (expandedId === client.id) return setExpandedId(null);
    setContacts([]);
    setExpandedId(client.id);
    await loadContacts(client.id);
  }

  async function addLink(client: ClientRecord) {
    if (!linkDevelopmentId) return setLinkFeedback("Selecione o empreendimento.");
    setBusy(true);
    try {
      await api("/api/v1/client-contacts", {
        method: "POST",
        body: JSON.stringify({
          client_id: client.id,
          development_id: linkDevelopmentId,
          scope: linkScope,
        }),
      });
      setLinkDevelopmentId("");
      setLinkFeedback("Responsabilidade registrada.");
      await loadContacts(client.id);
    } catch (error) {
      const duplicated =
        typeof error === "object" && error !== null && "status" in error && error.status === 409;
      setLinkFeedback(
        duplicated
          ? "O responsavel ja responde por essa area nesse empreendimento."
          : "Nao foi possivel registrar a responsabilidade.",
      );
    } finally {
      setBusy(false);
    }
  }

  async function toggleLink(contact: ClientContactRecord) {
    setBusy(true);
    try {
      await api("/api/v1/client-contacts/" + contact.id, {
        method: "PATCH",
        body: JSON.stringify({ is_active: !contact.is_active }),
      });
      setLinkFeedback(contact.is_active ? "Responsabilidade inativada." : "Responsabilidade reativada.");
      await loadContacts(contact.client_id);
    } catch {
      setLinkFeedback("Nao foi possivel alterar a responsabilidade.");
    } finally {
      setBusy(false);
    }
  }

  async function togglePortal(contact: ClientContactRecord) {
    setBusy(true);
    try {
      await api("/api/v1/client-contacts/" + contact.id, {
        method: "PATCH",
        body: JSON.stringify({ portal_access: !contact.portal_access }),
      });
      setLinkFeedback(
        contact.portal_access
          ? "Portal bloqueado para este empreendimento."
          : "Portal liberado. O responsavel ve este empreendimento quando tiver login de portal.",
      );
      await loadContacts(contact.client_id);
    } catch (error) {
      const forbidden =
        typeof error === "object" && error !== null && "status" in error && error.status === 403;
      setLinkFeedback(
        forbidden
          ? "Somente administradores podem liberar o acesso ao portal."
          : "Nao foi possivel alterar o acesso ao portal.",
      );
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="admin-panel">
      <div className="client-list-column">
      <label className="search-field">
        <Search size={16} />
        <input
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          placeholder="Buscar nome, CPF/CNPJ, funcao, telefone ou email"
          aria-label="Buscar responsavel"
        />
      </label>
      <div className="admin-list">
        {visibleClients.map((client) => (
          <div className="client-entry" key={client.id}>
            <div className="admin-row">
              <div>
                <strong>{client.name}</strong>
                <span>
                  {[client.contact_role, formatPhone(client.contact_whatsapp || client.contact_phone), client.contact_email]
                    .filter(Boolean)
                    .join(" · ") || formatDocument(client.document) || "Sem contato informado"}
                </span>
              </div>
              <div className="admin-actions">
                <span className={client.is_active ? "status status-revisada" : "status"}>{client.is_active ? "Ativo" : "Inativo"}</span>
                <button className="text-button" disabled={busy} onClick={() => void toggleExpanded(client)}>
                  {expandedId === client.id ? "Fechar" : "Empreendimentos"}
                </button>
                <button className="text-button" disabled={busy} onClick={() => startEdit(client)}>Editar</button>
                <button className="text-button" disabled={busy} onClick={() => void toggle(client)}>
                  {client.is_active ? "Inativar" : "Reativar"}
                </button>
              </div>
            </div>
            {expandedId === client.id && (
              <div className="client-contacts">
                <span className="eyebrow">Empreendimentos pelos quais responde</span>
                {contacts.map((contact) => (
                  <div className="client-contact-row" key={contact.id}>
                    <div>
                      <strong>{developmentMap.get(contact.development_id)?.name ?? "Empreendimento"}</strong>
                      <span>
                        {[
                          contact.is_primary ? "Principal" : null,
                          CONTACT_SCOPES.find(([value]) => value === contact.scope)?.[1] ?? contact.scope,
                          contact.portal_access ? "Portal liberado" : "Portal bloqueado",
                        ].filter(Boolean).join(" · ")}
                      </span>
                    </div>
                    <div className="admin-actions">
                      <span className={contact.is_active ? "status status-revisada" : "status"}>{contact.is_active ? "Ativo" : "Inativo"}</span>
                      {contact.is_active && (
                        <button className="text-button" disabled={busy} onClick={() => void togglePortal(contact)}>
                          {contact.portal_access ? "Bloquear portal" : "Liberar portal"}
                        </button>
                      )}
                      {!contact.is_primary && (
                        <button className="text-button" disabled={busy} onClick={() => void toggleLink(contact)}>
                          {contact.is_active ? "Inativar" : "Reativar"}
                        </button>
                      )}
                    </div>
                  </div>
                ))}
                {contacts.length === 0 && (
                  <div className="empty-state">
                    Nenhum empreendimento vinculado. Selecione abaixo o empreendimento e a area pela qual este responsavel responde. O responsavel principal e definido no cadastro do empreendimento.
                  </div>
                )}
                <div className="client-contact-form">
                  <label>Empreendimento
                    <select value={linkDevelopmentId} onChange={(e) => setLinkDevelopmentId(e.target.value)}>
                      <option value="">Selecione</option>
                      {developments.filter((x) => x.is_active).map((x) => <option key={x.id} value={x.id}>{x.name}</option>)}
                    </select>
                  </label>
                  <label>Area de responsabilidade
                    <select value={linkScope} onChange={(e) => setLinkScope(e.target.value as ContactScope)}>
                      {CONTACT_SCOPES.map(([value, label]) => <option key={value} value={value}>{label}</option>)}
                    </select>
                  </label>
                  <button className="small-button" disabled={busy} onClick={() => void addLink(client)}>Vincular</button>
                </div>
                {linkFeedback && <span className="inline-feedback">{linkFeedback}</span>}
              </div>
            )}
          </div>
        ))}
        {clients.length === 0 && <div className="empty-state">Nenhum responsavel cadastrado.</div>}
        {clients.length > 0 && visibleClients.length === 0 && (
          <div className="empty-state">
            Nenhum responsavel encontrado para "{search.trim()}". Confira a grafia ou limpe a busca.
          </div>
        )}
      </div>
      </div>
      <div className="compact-form admin-create-form">
        <h3>{editingId ? "Editar responsavel" : "Novo responsavel"}</h3>
        <div className="compact-form-grid">
          <label><span>Nome <b className="required-mark">*</b></span><input required aria-required="true" value={name} onChange={(e) => setName(e.target.value)} /></label>
          <label><span>Funcao <b className="required-mark">*</b></span><input required aria-required="true" value={contactRole} onChange={(e) => setContactRole(e.target.value)} /></label>
          <label><span>CPF/CNPJ <b className="required-mark">*</b></span><input required aria-required="true" value={document} onChange={(e) => setDocument(e.target.value)} /></label>
          <label>Email<input type="email" value={contactEmail} onChange={(e) => setContactEmail(e.target.value)} /></label>
          <label><span>Telefone <b className="required-mark">**</b></span><input type="tel" inputMode="numeric" placeholder="(85) 3333-3333" value={contactPhone} onChange={(e) => setContactPhone(formatPhone(e.target.value))} /></label>
          <label><span>WhatsApp <b className="required-mark">**</b></span><input type="tel" inputMode="numeric" placeholder="(85) 99999-9999" value={contactWhatsapp} onChange={(e) => setContactWhatsapp(formatPhone(e.target.value))} /></label>
          <label>Contato alternativo<input value={contactName} onChange={(e) => setContactName(e.target.value)} /></label>
        </div>
        <p className="required-hint">
          <b className="required-mark">*</b> Obrigatorio. <b className="required-mark">**</b> Informe ao menos um: Telefone ou WhatsApp.
        </p>
        <div className="admin-actions">
          <button className="small-button" disabled={busy} onClick={() => void save()}>
            {busy ? "Salvando..." : editingId ? "Salvar alteracoes" : "Cadastrar responsavel"}
          </button>
          {editingId && <button className="text-button" disabled={busy} onClick={resetForm}>Cancelar</button>}
        </div>
        {feedback && <span className="inline-feedback">{feedback}</span>}
      </div>
    </div>
  );
}

function DevelopmentAdmin({ clients, developments, onChanged }: { clients: ClientRecord[]; developments: DevelopmentRecord[]; onChanged: () => Promise<void> }) {
  const [editingId, setEditingId] = useState<string | null>(null);
  const [clientId, setClientId] = useState("");
  const [name, setName] = useState("");
  const [document, setDocument] = useState("");
  const [contactPhone, setContactPhone] = useState("");
  const [contactEmail, setContactEmail] = useState("");
  const [addressLine, setAddressLine] = useState("");
  const [city, setCity] = useState("Fortaleza");
  const [state, setState] = useState("CE");
  const [postalCode, setPostalCode] = useState("");
  const [feedback, setFeedback] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const clientMap = new Map(clients.map((item) => [item.id, item]));

  function resetForm() {
    setEditingId(null);
    setClientId(""); setName(""); setDocument(""); setContactPhone(""); setContactEmail("");
    setAddressLine(""); setCity("Fortaleza"); setState("CE"); setPostalCode("");
  }

  function startEdit(item: DevelopmentRecord) {
    setEditingId(item.id);
    setClientId(item.client_id);
    setName(item.name);
    setDocument(formatDocument(item.document));
    setContactPhone(formatPhone(item.contact_phone));
    setContactEmail(item.contact_email ?? "");
    setAddressLine(item.address_line ?? "");
    setCity(item.city ?? "");
    setState(item.state ?? "");
    setPostalCode(item.postal_code ?? "");
    setFeedback(null);
  }

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

  async function save() {
    if (!clientId) return setFeedback("Selecione o responsavel principal.");
    if (name.trim().length < 2) return setFeedback("Informe o nome do empreendimento.");
    if (!document.trim()) return setFeedback("Informe o CNPJ do empreendimento.");
    if (normalizeDocument(document).length !== 14 || !isValidCpfCnpj(document)) {
      return setFeedback("CNPJ invalido. Confira os numeros digitados.");
    }
    if (contactPhone.trim() && !isCompletePhone(contactPhone)) {
      return setFeedback("Telefone incompleto. Informe DDD e numero.");
    }
    setBusy(true);
    try {
      await api(editingId ? "/api/v1/developments/" + editingId : "/api/v1/developments", {
        method: editingId ? "PATCH" : "POST",
        body: JSON.stringify({
          client_id: clientId,
          name: name.trim(),
          document: normalizeDocument(document),
          contact_phone: contactPhone.trim() || null,
          contact_email: contactEmail.trim() || null,
          address_line: addressLine.trim() || null,
          city: city.trim() || null,
          state: state.trim().toUpperCase() || null,
          postal_code: postalCode.trim() || null,
        }),
      });
      setFeedback(editingId ? "Empreendimento atualizado." : "Empreendimento cadastrado.");
      resetForm();
      await onChanged();
    } catch (error) {
      const status =
        typeof error === "object" && error !== null && "status" in error ? error.status : null;
      if (status === 409) {
        setFeedback("Ja existe um empreendimento com esse CNPJ.");
      } else if (status === 422) {
        setFeedback("Confira os dados informados, em especial o email e a UF.");
      } else {
        setFeedback(editingId ? "Nao foi possivel atualizar o empreendimento." : "Nao foi possivel cadastrar o empreendimento.");
      }
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="admin-panel">
      <div className="admin-list">
        {developments.map((item) => (
          <div className="admin-row" key={item.id}>
            <div>
              <strong>{item.name}</strong>
              <span>
                {[
                  formatDocument(item.document),
                  "Responsavel principal: " + (clientMap.get(item.client_id)?.name ?? "nao encontrado"),
                  [item.city, item.state].filter(Boolean).join("/"),
                ].filter(Boolean).join(" · ")}
              </span>
            </div>
            <div className="admin-actions">
              <span className={item.is_active ? "status status-revisada" : "status"}>{item.is_active ? "Ativo" : "Inativo"}</span>
              <button className="text-button" disabled={busy} onClick={() => startEdit(item)}>Editar</button>
              <button className="text-button" disabled={busy} onClick={() => void toggle(item)}>
                {item.is_active ? "Inativar" : "Reativar"}
              </button>
            </div>
          </div>
        ))}
        {developments.length === 0 && (
          <div className="empty-state">
            Nenhum empreendimento cadastrado. Cadastre primeiro o responsavel principal na aba Responsaveis.
          </div>
        )}
      </div>
      <div className="compact-form admin-create-form">
        <h3>{editingId ? "Editar empreendimento" : "Novo empreendimento"}</h3>
        <div className="compact-form-grid">
          <label><span>Nome <b className="required-mark">*</b></span><input required aria-required="true" value={name} onChange={(e) => setName(e.target.value)} /></label>
          <label><span>CNPJ <b className="required-mark">*</b></span><input required aria-required="true" value={document} onChange={(e) => setDocument(e.target.value)} /></label>
          <label><span>Responsavel principal <b className="required-mark">*</b></span><select required aria-required="true" value={clientId} onChange={(e) => setClientId(e.target.value)}><option value="">Selecione</option>{clients.filter((x) => x.is_active || x.id === clientId).map((x) => <option key={x.id} value={x.id}>{x.name}</option>)}</select></label>
          <label>Telefone<input type="tel" inputMode="numeric" placeholder="(85) 3333-3333" value={contactPhone} onChange={(e) => setContactPhone(formatPhone(e.target.value))} /></label>
          <label>Email<input type="email" value={contactEmail} onChange={(e) => setContactEmail(e.target.value)} /></label>
          <label>Endereco<input value={addressLine} onChange={(e) => setAddressLine(e.target.value)} /></label>
          <label>Cidade<input value={city} onChange={(e) => setCity(e.target.value)} /></label>
          <label>UF<input maxLength={2} value={state} onChange={(e) => setState(e.target.value)} /></label>
          <label>CEP<input value={postalCode} onChange={(e) => setPostalCode(e.target.value)} /></label>
        </div>
        <p className="required-hint"><b className="required-mark">*</b> Obrigatorio.</p>
        <div className="admin-actions">
          <button className="small-button" disabled={busy} onClick={() => void save()}>
            {busy ? "Salvando..." : editingId ? "Salvar alteracoes" : "Cadastrar empreendimento"}
          </button>
          {editingId && <button className="text-button" disabled={busy} onClick={resetForm}>Cancelar</button>}
        </div>
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
