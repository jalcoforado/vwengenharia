import { useEffect, useState } from "react";
import { Boxes, Briefcase, Building2, EllipsisVertical, Layers, LocateFixed, Pencil, Search, Settings, User, UserPlus, Users, type LucideIcon } from "lucide-react";

import { api } from "../lib/api";
import { Avatar, RowMenu, TableHead, useFormPanel, useRowMenu, useSort, type RowMenuItem } from "./AdminTable";
import CollaboratorAdmin from "./CollaboratorAdmin";
import ContractingPartyAdmin, { contractingPartyLabel, type ContractingPartyRecord } from "./ContractingPartyAdmin";
import ProcessUnitAdmin, { type ProcessUnitRecord } from "./ProcessUnitAdmin";
import { formatDocument, isValidCpfCnpj, normalizeDocument } from "../lib/document";
import { optimizeEvidenceImage } from "../lib/media";
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
  ["TECNICO", "Técnico"],
  ["FINANCEIRO", "Financeiro"],
  ["COMERCIAL", "Comercial"],
  ["ADMINISTRATIVO", "Administrativo"],
];

// Funcoes aceitas para o responsavel. O backend guarda o texto (contact_role).
const CLIENT_ROLES = ["Síndico", "Subsíndico", "Administrador", "Outro"];

type ClientSortKey = "name" | "role" | "contact" | "status";

const CLIENT_COLUMNS: [ClientSortKey, string, string][] = [
  ["name", "Nome", "collab-col-name"],
  ["role", "Função", "collab-col-category"],
  ["contact", "Contato", "collab-col-contact"],
  ["status", "Status", "collab-col-status"],
];

export type DevelopmentRecord = {
  id: string;
  client_id: string;
  contracting_party_id: string | null;
  name: string;
  document: string | null;
  contact_phone: string | null;
  contact_email: string | null;
  address_line: string | null;
  city: string | null;
  state: string | null;
  postal_code: string | null;
  development_type: string | null;
  address_number: string | null;
  address_complement: string | null;
  address_district: string | null;
  latitude: number | null;
  longitude: number | null;
  units_count: number | null;
  access_hours: string | null;
  has_facade_photo: boolean;
  is_active: boolean;
};

type DevelopmentSortKey = "name" | "type" | "contact" | "status";

const DEVELOPMENT_COLUMNS: [DevelopmentSortKey, string, string][] = [
  ["name", "Nome", "collab-col-name"],
  ["type", "Tipo", "collab-col-category"],
  ["contact", "Contato", "collab-col-contact"],
  ["status", "Status", "collab-col-status"],
];

// Tipos aceitos para o empreendimento. O backend guarda o texto (development_type).
const DEVELOPMENT_TYPES = ["Condomínio residencial", "Condomínio comercial", "Indústria", "Comércio", "Hospedagem", "Outro"];

const FACADE_PHOTO_TYPES = ["image/jpeg", "image/png", "image/webp"];

// Aceita "-3,7319" ou "-3.7319"; devolve null se vazio e NaN se nao for numero.
function parseCoordinate(value: string): number | null {
  const text = value.trim().replace(",", ".");
  if (!text) return null;
  return /^-?\d+(\.\d+)?$/.test(text) ? Number(text) : Number.NaN;
}

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
  process_unit_id: string | null;
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
  canManageAccess: boolean;
  onChanged: () => Promise<void>;
  onOpenStation?: (stationId: string) => void;
};

export default function OperationalAdmin({
  clients,
  developments,
  stations,
  assetTypes,
  assets,
  canManageAccess,
  onChanged,
  onOpenStation,
}: Props) {
  const [tab, setTab] = useState<"COLABORADORES" | "CONTRATANTES" | "CLIENTES" | "EMPREENDIMENTOS" | "ESTACOES" | "UNIDADES" | "ATIVOS">("COLABORADORES");
  const [collaboratorCount, setCollaboratorCount] = useState<number | null>(null);
  const [parties, setParties] = useState<ContractingPartyRecord[]>([]);

  // Os contratantes sao usados pela aba propria e pelo cadastro do empreendimento.
  async function loadParties() {
    try {
      setParties(await api<ContractingPartyRecord[]>("/api/v1/contracting-parties?limit=500"));
    } catch {
      // Mantem a lista anterior; a aba mostra o que ja estava carregado.
    }
  }

  // As unidades de processo sao usadas pela aba propria e pelo cadastro de ativos.
  const [units, setUnits] = useState<ProcessUnitRecord[]>([]);

  async function loadUnits() {
    try {
      setUnits(await api<ProcessUnitRecord[]>("/api/v1/process-units?limit=500"));
    } catch {
      // Mantem a lista anterior.
    }
  }

  useEffect(() => {
    void loadParties();
    void loadUnits();
  }, []);

  // Os colaboradores sao carregados pela propria aba; aqui so buscamos o total para o resumo.
  useEffect(() => {
    api<{ is_active: boolean }[]>("/api/v1/collaborators")
      .then((items) => setCollaboratorCount(items.filter((item) => item.is_active).length))
      .catch(() => setCollaboratorCount(null));
  }, []);

  return (
    <section className="section-card admin-hub">
      <div className="section-heading admin-heading">
        <div>
          <span className="eyebrow">Administração operacional</span>
          <h2>Estrutura da operação</h2>
          <p className="section-copy">
            Colaboradores são a equipe da MW. Cadastre o contratante (quem assina com a MW) e o responsável, depois o empreendimento (o local atendido), suas estações, as unidades de cada estação e os ativos.
          </p>
        </div>
        <div className="admin-summary">
          {collaboratorCount !== null && <span><strong>{collaboratorCount}</strong> colaboradores</span>}
          <span><strong>{parties.filter((item) => item.is_active).length}</strong> contratantes</span>
          <span><strong>{clients.filter((item) => item.is_active).length}</strong> responsáveis</span>
          <span><strong>{developments.filter((item) => item.is_active).length}</strong> empreendimentos</span>
          <span><strong>{stations.filter((item) => item.is_active).length}</strong> estações</span>
          <span><strong>{assets.filter((item) => item.is_active).length}</strong> ativos</span>
        </div>
      </div>

      <div className="admin-tabs">
        {([
          ["COLABORADORES", "Colaboradores", Users],
          ["CONTRATANTES", "Contratantes", Briefcase],
          ["CLIENTES", "Responsáveis", User],
          ["EMPREENDIMENTOS", "Empreendimentos", Building2],
          ["ESTACOES", "Estações", Settings],
          ["UNIDADES", "Unidades", Boxes],
          ["ATIVOS", "Ativos", Layers],
        ] as [string, string, LucideIcon][]).map(([value, label, Icon]) => (
          <button
            key={value}
            className={tab === value ? "admin-tab active" : "admin-tab"}
            onClick={() => setTab(value as typeof tab)}
          >
            <Icon size={17} /> {label}
          </button>
        ))}
      </div>

      {tab === "COLABORADORES" && (
        <CollaboratorAdmin canManage={canManageAccess} onChanged={onChanged} onActiveCount={setCollaboratorCount} />
      )}
      {tab === "CONTRATANTES" && (
        <ContractingPartyAdmin
          parties={parties}
          developmentCount={(partyId) => developments.filter((item) => item.contracting_party_id === partyId).length}
          onChanged={loadParties}
        />
      )}
      {tab === "CLIENTES" && (
        <ClientAdmin
          clients={clients}
          developments={developments}
          canManageAccess={canManageAccess}
          onChanged={onChanged}
        />
      )}
      {tab === "EMPREENDIMENTOS" && (
        <DevelopmentAdmin clients={clients} parties={parties} developments={developments} onChanged={onChanged} />
      )}
      {tab === "ESTACOES" && (
        <StationAdmin
          developments={developments}
          stations={stations}
          onChanged={onChanged}
          onOpenStation={onOpenStation}
        />
      )}
      {tab === "UNIDADES" && (
        <ProcessUnitAdmin
          stations={stations}
          assets={assets}
          units={units}
          onUnitsChanged={loadUnits}
          onAssetsChanged={onChanged}
        />
      )}
      {tab === "ATIVOS" && (
        <AssetAdmin stations={stations} assetTypes={assetTypes} assets={assets} units={units} onChanged={onChanged} />
      )}
    </section>
  );
}

function ClientAdmin({
  clients,
  developments,
  canManageAccess,
  onChanged,
}: {
  clients: ClientRecord[];
  developments: DevelopmentRecord[];
  canManageAccess: boolean;
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
  const [portalLogin, setPortalLogin] = useState<string | null>(null);
  const [portalEmail, setPortalEmail] = useState("");
  const [portalPassword, setPortalPassword] = useState("");
  const [busy, setBusy] = useState(false);
  const [search, setSearch] = useState("");
  const [listFeedback, setListFeedback] = useState<string | null>(null);
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

  const { sortKey, sortAsc, toggleSort, sortBy } = useSort<ClientSortKey>("name");
  const { menu, openMenu, closeMenu } = useRowMenu();
  const panel = useFormPanel();
  const sortedClients = sortBy(visibleClients, (client, key) => {
    if (key === "role") return client.contact_role ?? "";
    if (key === "contact") return (client.contact_whatsapp || client.contact_phone || "").replace(/\D/g, "");
    if (key === "status") return client.is_active ? "0" : "1";
    return client.name;
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
    panel.show();
  }

  function openNew() {
    resetForm();
    setFeedback(null);
    panel.show();
  }

  function closeForm() {
    resetForm();
    setFeedback(null);
    panel.hide();
  }

  async function toggle(client: ClientRecord) {
    setBusy(true);
    try {
      await api("/api/v1/clients/" + client.id, {
        method: "PATCH",
        body: JSON.stringify({ is_active: !client.is_active }),
      });
      setListFeedback(client.is_active ? "Responsável inativado." : "Responsável reativado.");
      await onChanged();
    } catch {
      setListFeedback("Não foi possível alterar o responsável.");
    } finally {
      setBusy(false);
    }
  }

  async function save() {
    if (name.trim().length < 2) return setFeedback("Informe o nome do responsável.");
    if (!contactRole.trim()) return setFeedback("Selecione a função do responsável.");
    if (!document.trim()) return setFeedback("Informe o CPF/CNPJ do responsável.");
    if (!isValidCpfCnpj(document)) {
      return setFeedback("CPF/CNPJ inválido. Confira os números digitados.");
    }
    if (!contactPhone.trim() && !contactWhatsapp.trim()) {
      return setFeedback("Informe o WhatsApp ou o telefone do responsável.");
    }
    if (contactWhatsapp.trim() && !isCompletePhone(contactWhatsapp)) {
      return setFeedback("WhatsApp incompleto. Informe DDD e número.");
    }
    if (contactPhone.trim() && !isCompletePhone(contactPhone)) {
      return setFeedback("Telefone incompleto. Informe DDD e número.");
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
      if (editingId) {
        setListFeedback("Responsável atualizado.");
        closeForm();
      } else {
        resetForm();
        setFeedback("Responsável cadastrado. O formulário segue aberto para o próximo.");
      }
      await onChanged();
    } catch (error) {
      const status =
        typeof error === "object" && error !== null && "status" in error ? error.status : null;
      if (status === 409) {
        setFeedback("Já existe um responsável com esse CPF/CNPJ. Use a busca para localiza-lo.");
      } else if (status === 422) {
        setFeedback("Confira os dados informados, em especial o email.");
      } else {
        setFeedback(editingId ? "Não foi possível atualizar o responsável." : "Não foi possível cadastrar o responsável.");
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
      setLinkFeedback("Não foi possível carregar os empreendimentos do responsável.");
    }
  }

  async function loadPortalLogin(clientId: string) {
    if (!canManageAccess) return;
    try {
      const accesses = await api<{ client_id: string; user_email: string | null }[]>(
        "/api/v1/client-access",
      );
      setPortalLogin(accesses.find((item) => item.client_id === clientId)?.user_email ?? null);
    } catch {
      setPortalLogin(null);
    }
  }

  async function createPortalLogin(client: ClientRecord) {
    if (!portalEmail.trim() || portalPassword.length < 12) {
      return setLinkFeedback("Informe o email e uma senha inicial com pelo menos 12 caracteres.");
    }
    setBusy(true);
    try {
      const created = await api<{ user_email: string | null }>(
        "/api/v1/clients/" + client.id + "/portal-credential",
        {
          method: "POST",
          body: JSON.stringify({ email: portalEmail.trim(), password: portalPassword }),
        },
      );
      setPortalLogin(created.user_email);
      setPortalPassword("");
      setLinkFeedback(
        "Login de portal criado. Ele só vê os empreendimentos com o portal liberado abaixo.",
      );
    } catch (error) {
      const detail =
        typeof error === "object" && error !== null && "detail" in error ? error.detail : null;
      setLinkFeedback(
        detail === "email_already_registered"
          ? "Esse email já é usado por outro acesso."
          : detail === "client_already_has_portal_credential"
            ? "Esse responsável já tem login de portal."
            : "Não foi possível criar o login de portal. Confira o email.",
      );
    } finally {
      setBusy(false);
    }
  }

  async function toggleExpanded(client: ClientRecord) {
    setLinkFeedback(null);
    setLinkDevelopmentId("");
    if (expandedId === client.id) return setExpandedId(null);
    setContacts([]);
    setPortalLogin(null);
    setPortalEmail(client.contact_email ?? "");
    setPortalPassword("");
    setExpandedId(client.id);
    await Promise.all([loadContacts(client.id), loadPortalLogin(client.id)]);
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
          ? "O responsável já responde por essa área nesse empreendimento."
          : "Não foi possível registrar a responsabilidade.",
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
      setLinkFeedback("Não foi possível alterar a responsabilidade.");
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
          : "Portal liberado. O responsável vê este empreendimento quando tiver login de portal.",
      );
      await loadContacts(contact.client_id);
    } catch (error) {
      const forbidden =
        typeof error === "object" && error !== null && "status" in error && error.status === 403;
      setLinkFeedback(
        forbidden
          ? "Somente administradores podem liberar o acesso ao portal."
          : "Não foi possível alterar o acesso ao portal.",
      );
    } finally {
      setBusy(false);
    }
  }

  const menuClient = menu ? clients.find((client) => client.id === menu.id) : undefined;
  const menuItems: RowMenuItem[] = menuClient
    ? [
        { text: expandedId === menuClient.id ? "Fechar empreendimentos" : "Empreendimentos", run: () => void toggleExpanded(menuClient) },
        { text: "Editar", run: () => startEdit(menuClient) },
        { text: menuClient.is_active ? "Inativar" : "Reativar", run: () => void toggle(menuClient), danger: menuClient.is_active },
      ]
    : [];

  return (
    <div className="admin-stack">
      {panel.open && (
      <div className="compact-form admin-create-form" ref={panel.ref}>
        <h3 className="form-title">{editingId ? <Pencil size={17} /> : <UserPlus size={17} />}{editingId ? "Editar responsável" : "Novo responsável"}</h3>
        <div className="compact-form-grid">
          <label><span>Nome <b className="required-mark">*</b></span><input required aria-required="true" placeholder="Nome completo" value={name} onChange={(e) => setName(e.target.value)} /></label>
          <label><span>Função <b className="required-mark">*</b></span>
            <select required aria-required="true" value={contactRole} onChange={(e) => setContactRole(e.target.value)}>
              <option value="">Selecione</option>
              {CLIENT_ROLES.map((role) => <option key={role} value={role}>{role}</option>)}
              {contactRole && !CLIENT_ROLES.includes(contactRole) && <option value={contactRole}>{contactRole} (cadastro antigo)</option>}
            </select>
          </label>
          <label><span>CPF/CNPJ <b className="required-mark">*</b></span><input required aria-required="true" inputMode="numeric" placeholder="CPF ou CNPJ" value={document} onChange={(e) => setDocument(e.target.value)} /></label>
          <label>Email<input type="email" placeholder="email@exemplo.com" value={contactEmail} onChange={(e) => setContactEmail(e.target.value)} /></label>
          <label><span>WhatsApp <b className="required-mark">**</b></span><input type="tel" inputMode="numeric" placeholder="(85) 99999-9999" value={contactWhatsapp} onChange={(e) => setContactWhatsapp(formatPhone(e.target.value))} /></label>
          <label><span>Telefone <b className="required-mark">**</b></span><input type="tel" inputMode="numeric" placeholder="(85) 3333-3333" value={contactPhone} onChange={(e) => setContactPhone(formatPhone(e.target.value))} /></label>
          <label>Contato alternativo<input value={contactName} onChange={(e) => setContactName(e.target.value)} /></label>
        </div>
        <p className="required-hint">
          <b className="required-mark">*</b> Obrigatório. <b className="required-mark">**</b> Informe ao menos um: WhatsApp ou Telefone.
        </p>
        <div className="admin-actions form-submit">
          <button className="primary-button" disabled={busy} onClick={() => void save()}>
            {!editingId && <UserPlus size={17} />}
            {busy ? "Salvando..." : editingId ? "Salvar alterações" : "Cadastrar responsável"}
          </button>
          <button className="text-button" disabled={busy} onClick={closeForm}>{editingId ? "Cancelar" : "Fechar"}</button>
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
          placeholder="Buscar nome, CPF/CNPJ, função, telefone ou email"
          aria-label="Buscar responsável"
        />
      </label>
{!panel.open && (
<button className="primary-button" disabled={busy} onClick={openNew}><UserPlus size={17} /> Novo responsável</button>
)}
</div>
{listFeedback && <span className="inline-feedback" role="status">{listFeedback}</span>}
      <div className="admin-list collab-table" role="table" aria-label="Responsáveis">
        <TableHead columns={CLIENT_COLUMNS} sortKey={sortKey} sortAsc={sortAsc} onSort={toggleSort} />
        {sortedClients.map((client) => {
          const detail = client.contact_email || formatDocument(client.document) || "Sem email informado";
          const expandText = expandedId === client.id ? "Fechar empreendimentos" : "Empreendimentos";
          return (
          <div className="client-entry" key={client.id}>
            <div className={client.is_active ? "collab-row" : "collab-row collab-row-inactive"} role="row">
              <div className="collab-person" role="cell">
                <Avatar name={client.name} />
                <div>
                  <strong>{client.name}</strong>
                  <span title={detail}>{detail}</span>
                </div>
              </div>
              <div className="collab-col-category" role="cell">
                {client.contact_role ? <span className="collab-chip" title={client.contact_role}>{client.contact_role}</span> : "—"}
              </div>
              <div className="collab-col-contact" role="cell">
                {formatPhone(client.contact_whatsapp || client.contact_phone) || "—"}
              </div>
              <div className="collab-col-status" role="cell">
                <span className={client.is_active ? "collab-status active" : "collab-status"}>{client.is_active ? "Ativo" : "Inativo"}</span>
              </div>
              <div className="collab-actions" role="cell">
                <button
                  className={expandedId === client.id ? "icon-action icon-action-on" : "icon-action"}
                  disabled={busy}
                  title={expandText}
                  aria-label={expandText + ": " + client.name}
                  aria-expanded={expandedId === client.id}
                  onClick={() => void toggleExpanded(client)}
                >
                  <Building2 size={16} />
                </button>
                <button className="icon-action icon-action-edit" disabled={busy} title="Editar" aria-label={"Editar: " + client.name} onClick={() => startEdit(client)}>
                  <Pencil size={16} />
                </button>
                <button
                  className="icon-action row-menu-trigger"
                  disabled={busy}
                  title="Mais ações"
                  aria-label={"Mais ações: " + client.name}
                  aria-haspopup="menu"
                  aria-expanded={menu?.id === client.id}
                  onClick={(event) => openMenu(client.id, event.currentTarget)}
                >
                  <EllipsisVertical size={16} />
                </button>
              </div>
            </div>
            {expandedId === client.id && (
              <div className="client-contacts">
                {canManageAccess && (
                  <div className="portal-login">
                    <span className="eyebrow">Login no portal do cliente</span>
                    {portalLogin ? (
                      <span className="required-hint">
                        Login: {portalLogin}. Ele vê apenas os empreendimentos com o portal liberado.
                      </span>
                    ) : (
                      <div className="client-contact-form">
                        <label>Email de login
                          <input type="email" value={portalEmail} onChange={(e) => setPortalEmail(e.target.value)} />
                        </label>
                        <label>Senha inicial
                          <input type="password" autoComplete="new-password" value={portalPassword} onChange={(e) => setPortalPassword(e.target.value)} />
                        </label>
                        <button className="small-button" disabled={busy} onClick={() => void createPortalLogin(client)}>Criar login</button>
                      </div>
                    )}
                  </div>
                )}
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
                    Nenhum empreendimento vinculado. Selecione abaixo o empreendimento e a área pela qual este responsável responde. O responsável principal é definido no cadastro do empreendimento.
                  </div>
                )}
                <div className="client-contact-form">
                  <label>Empreendimento
                    <select value={linkDevelopmentId} onChange={(e) => setLinkDevelopmentId(e.target.value)}>
                      <option value="">Selecione</option>
                      {developments.filter((x) => x.is_active).map((x) => <option key={x.id} value={x.id}>{x.name}</option>)}
                    </select>
                  </label>
                  <label>Área de responsabilidade
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
          );
        })}
        {clients.length === 0 && <div className="empty-state">Nenhum responsável cadastrado.</div>}
        {clients.length > 0 && visibleClients.length === 0 && (
          <div className="empty-state">
            Nenhum responsável encontrado para "{search.trim()}". Confira a grafia ou limpe a busca.
          </div>
        )}
      </div>
      {menu && menuClient && <RowMenu menu={menu} items={menuItems} busy={busy} onClose={closeMenu} />}
      </div>
    </div>
  );
}

function DevelopmentAdmin({
  clients,
  parties,
  developments,
  onChanged,
}: {
  clients: ClientRecord[];
  parties: ContractingPartyRecord[];
  developments: DevelopmentRecord[];
  onChanged: () => Promise<void>;
}) {
  const [editingId, setEditingId] = useState<string | null>(null);
  const [clientId, setClientId] = useState("");
  const [name, setName] = useState("");
  const [partyId, setPartyId] = useState("");
  const [contactPhone, setContactPhone] = useState("");
  const [contactEmail, setContactEmail] = useState("");
  const [addressLine, setAddressLine] = useState("");
  const [city, setCity] = useState("Fortaleza");
  const [state, setState] = useState("CE");
  const [postalCode, setPostalCode] = useState("");
  const [developmentType, setDevelopmentType] = useState("");
  const [addressNumber, setAddressNumber] = useState("");
  const [addressComplement, setAddressComplement] = useState("");
  const [addressDistrict, setAddressDistrict] = useState("");
  const [latitude, setLatitude] = useState("");
  const [longitude, setLongitude] = useState("");
  const [unitsCount, setUnitsCount] = useState("");
  const [accessHours, setAccessHours] = useState("");
  const [photoFile, setPhotoFile] = useState<File | null>(null);
  const [photoUrl, setPhotoUrl] = useState<string | null>(null);
  const [photoInputKey, setPhotoInputKey] = useState(0);
  const [feedback, setFeedback] = useState<string | null>(null);
  const [rowFeedback, setRowFeedback] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [search, setSearch] = useState("");
  const { sortKey, sortAsc, toggleSort, sortBy } = useSort<DevelopmentSortKey>("name");
  const { menu, openMenu, closeMenu } = useRowMenu();
  const panel = useFormPanel();
  const clientMap = new Map(clients.map((item) => [item.id, item]));
  const partyMap = new Map(parties.map((item) => [item.id, item]));

  function partyName(item: DevelopmentRecord): string {
    const party = item.contracting_party_id ? partyMap.get(item.contracting_party_id) : undefined;
    return party ? contractingPartyLabel(party) : "";
  }

  function summary(item: DevelopmentRecord): string {
    return [
      partyName(item) ? "Contratante: " + partyName(item) : "Sem contratante",
      "Responsável principal: " + (clientMap.get(item.client_id)?.name ?? "não encontrado"),
      [item.city, item.state].filter(Boolean).join("/"),
    ].filter(Boolean).join(" · ");
  }

  const term = search.trim().toLowerCase();
  const termDigits = term.replace(/\D/g, "");
  const visible = developments.filter((item) => {
    if (!term) return true;
    const fields = [
      item.name,
      partyName(item),
      item.development_type,
      clientMap.get(item.client_id)?.name,
      item.city,
      item.address_district,
      item.contact_phone,
      item.contact_email,
    ].map((value) => (value ?? "").toLowerCase());
    if (fields.some((value) => value.includes(term))) return true;
    // Permite achar o CNPJ do contratante e o telefone digitando so os numeros.
    const partyDocument = item.contracting_party_id ? partyMap.get(item.contracting_party_id)?.document : null;
    return (
      termDigits.length >= 3 &&
      [partyDocument, item.contact_phone].some((value) => (value ?? "").replace(/\D/g, "").includes(termDigits))
    );
  });

  const sorted = sortBy(visible, (item, key) => {
    if (key === "type") return item.development_type ?? "";
    if (key === "contact") return (item.contact_phone ?? "").replace(/\D/g, "");
    if (key === "status") return item.is_active ? "0" : "1";
    return item.name;
  });

  function resetForm() {
    setEditingId(null);
    setClientId(""); setName(""); setPartyId(""); setContactPhone(""); setContactEmail("");
    setAddressLine(""); setCity("Fortaleza"); setState("CE"); setPostalCode("");
    setDevelopmentType(""); setAddressNumber(""); setAddressComplement(""); setAddressDistrict("");
    setLatitude(""); setLongitude(""); setUnitsCount(""); setAccessHours("");
    setPhotoFile(null); setPhotoUrl(null); setPhotoInputKey((key) => key + 1);
  }

  async function loadPhoto(developmentId: string) {
    try {
      const photo = await api<{ url: string }>("/api/v1/developments/" + developmentId + "/facade-photo");
      setPhotoUrl(photo.url);
    } catch {
      setPhotoUrl(null);
    }
  }

  async function uploadPhoto(developmentId: string, file: File) {
    const optimized = (await optimizeEvidenceImage(file)).file;
    const presign = await api<{ upload_url: string; object_key: string; required_headers: Record<string, string> }>(
      "/api/v1/developments/" + developmentId + "/facade-photo/presign",
      {
        method: "POST",
        body: JSON.stringify({ filename: optimized.name, content_type: optimized.type, size_bytes: optimized.size }),
      },
    );
    const uploaded = await fetch(presign.upload_url, { method: "PUT", headers: presign.required_headers, body: optimized });
    if (!uploaded.ok) throw new Error("facade_photo_upload_failed");
    await api("/api/v1/developments/" + developmentId + "/facade-photo/complete", {
      method: "POST",
      body: JSON.stringify({ object_key: presign.object_key }),
    });
  }

  async function removePhoto() {
    if (!editingId) return;
    setBusy(true);
    try {
      await api("/api/v1/developments/" + editingId + "/facade-photo", { method: "DELETE" });
      setPhotoUrl(null);
      setFeedback("Foto da fachada removida.");
      await onChanged();
    } catch {
      setFeedback("Não foi possível remover a foto.");
    } finally {
      setBusy(false);
    }
  }

  function useMyLocation() {
    if (!navigator.geolocation) return setFeedback("Este aparelho não informa a localização.");
    navigator.geolocation.getCurrentPosition(
      (position) => {
        setLatitude(position.coords.latitude.toFixed(6));
        setLongitude(position.coords.longitude.toFixed(6));
        setFeedback("Localização preenchida. Confira se você está no empreendimento.");
      },
      () => setFeedback("Não foi possível obter a localização. Libere o acesso no navegador ou digite as coordenadas."),
      { enableHighAccuracy: true, timeout: 15000 },
    );
  }

  function startEdit(item: DevelopmentRecord) {
    setEditingId(item.id);
    setClientId(item.client_id);
    setName(item.name);
    setPartyId(item.contracting_party_id ?? "");
    setContactPhone(formatPhone(item.contact_phone));
    setContactEmail(item.contact_email ?? "");
    setAddressLine(item.address_line ?? "");
    setCity(item.city ?? "");
    setState(item.state ?? "");
    setPostalCode(item.postal_code ?? "");
    setDevelopmentType(item.development_type ?? "");
    setAddressNumber(item.address_number ?? "");
    setAddressComplement(item.address_complement ?? "");
    setAddressDistrict(item.address_district ?? "");
    setLatitude(item.latitude === null ? "" : String(item.latitude));
    setLongitude(item.longitude === null ? "" : String(item.longitude));
    setUnitsCount(item.units_count === null ? "" : String(item.units_count));
    setAccessHours(item.access_hours ?? "");
    setPhotoFile(null); setPhotoUrl(null); setPhotoInputKey((key) => key + 1);
    if (item.has_facade_photo) void loadPhoto(item.id);
    setFeedback(null);
    panel.show();
  }

  function openNew() {
    resetForm();
    setFeedback(null);
    panel.show();
  }

  function closeForm() {
    resetForm();
    setFeedback(null);
    panel.hide();
  }

  async function toggle(item: DevelopmentRecord) {
    setBusy(true);
    try {
      await api("/api/v1/developments/" + item.id, {
        method: "PATCH",
        body: JSON.stringify({ is_active: !item.is_active }),
      });
      setRowFeedback(item.is_active ? "Empreendimento inativado." : "Empreendimento reativado.");
      await onChanged();
    } catch {
      setRowFeedback("Não foi possível alterar o empreendimento.");
    } finally {
      setBusy(false);
    }
  }

  async function save() {
    if (name.trim().length < 2) return setFeedback("Informe o nome do empreendimento.");
    if (!partyId) return setFeedback("Selecione o contratante.");
    if (!clientId) return setFeedback("Selecione o responsável principal.");
    if (contactPhone.trim() && !isCompletePhone(contactPhone)) {
      return setFeedback("Telefone incompleto. Informe DDD e número.");
    }
    if (!developmentType) return setFeedback("Selecione o tipo do empreendimento.");
    if (!addressLine.trim()) return setFeedback("Informe o logradouro do empreendimento.");
    if (!city.trim()) return setFeedback("Informe o município do empreendimento.");
    if (state.trim().length !== 2) return setFeedback("Informe a UF com duas letras.");
    const lat = parseCoordinate(latitude);
    const lng = parseCoordinate(longitude);
    if (Number.isNaN(lat) || (lat !== null && Math.abs(lat) > 90)) {
      return setFeedback("Latitude inválida. Use graus decimais entre -90 e 90, por exemplo -3,7319.");
    }
    if (Number.isNaN(lng) || (lng !== null && Math.abs(lng) > 180)) {
      return setFeedback("Longitude inválida. Use graus decimais entre -180 e 180, por exemplo -38,5267.");
    }
    if ((lat === null) !== (lng === null)) return setFeedback("Informe latitude e longitude juntas, ou deixe as duas em branco.");
    if (unitsCount.trim() && !/^\d+$/.test(unitsCount.trim())) {
      return setFeedback("Número de economias inválido. Use apenas números inteiros.");
    }
    if (photoFile && !FACADE_PHOTO_TYPES.includes(photoFile.type)) {
      return setFeedback("A foto da fachada deve ser uma imagem JPG, PNG ou WebP.");
    }
    setBusy(true);
    try {
      const saved = await api<{ id: string }>(editingId ? "/api/v1/developments/" + editingId : "/api/v1/developments", {
        method: editingId ? "PATCH" : "POST",
        body: JSON.stringify({
          client_id: clientId,
          name: name.trim(),
          contracting_party_id: partyId,
          contact_phone: contactPhone.trim() || null,
          contact_email: contactEmail.trim() || null,
          development_type: developmentType,
          address_line: addressLine.trim() || null,
          address_number: addressNumber.trim() || null,
          address_complement: addressComplement.trim() || null,
          address_district: addressDistrict.trim() || null,
          city: city.trim() || null,
          state: state.trim().toUpperCase() || null,
          postal_code: postalCode.trim() || null,
          latitude: lat,
          longitude: lng,
          units_count: unitsCount.trim() ? Number(unitsCount.trim()) : null,
          access_hours: accessHours.trim() || null,
        }),
      });
      let photoFailed = false;
      if (photoFile) {
        try {
          await uploadPhoto(saved.id, photoFile);
        } catch {
          photoFailed = true;
        }
      }
      const photoNote = photoFailed ? " A foto da fachada não foi enviada; edite o cadastro e tente de novo." : "";
      if (editingId) {
        setRowFeedback("Empreendimento atualizado." + photoNote);
        closeForm();
      } else {
        resetForm();
        setFeedback("Empreendimento cadastrado." + photoNote + " O formulário segue aberto para o próximo.");
      }
      await onChanged();
    } catch (error) {
      const status =
        typeof error === "object" && error !== null && "status" in error ? error.status : null;
      if (status === 409) {
        setFeedback("Já existe um empreendimento com esse CNPJ. Edite o cadastro existente.");
      } else if (status === 422) {
        setFeedback("Confira os dados informados, em especial o email e a UF.");
      } else {
        setFeedback(editingId ? "Não foi possível atualizar o empreendimento." : "Não foi possível cadastrar o empreendimento.");
      }
    } finally {
      setBusy(false);
    }
  }

  const menuItem = menu ? developments.find((item) => item.id === menu.id) : undefined;
  const menuItems: RowMenuItem[] = menuItem
    ? [
        { text: "Editar", run: () => startEdit(menuItem) },
        { text: menuItem.is_active ? "Inativar" : "Reativar", run: () => void toggle(menuItem), danger: menuItem.is_active },
      ]
    : [];

  return (
    <div className="admin-stack">
      {panel.open && (
      <div className="compact-form admin-create-form" ref={panel.ref}>
        <h3 className="form-title">{editingId ? <Pencil size={17} /> : <Building2 size={17} />}{editingId ? "Editar empreendimento" : "Novo empreendimento"}</h3>
        <div className="compact-form-grid">
          <label className="form-span-2"><span>Nome <b className="required-mark">*</b></span><input required aria-required="true" placeholder="Nome do empreendimento" value={name} onChange={(e) => setName(e.target.value)} /></label>
          <label><span>Tipo <b className="required-mark">*</b></span>
            <select required aria-required="true" value={developmentType} onChange={(e) => setDevelopmentType(e.target.value)}>
              <option value="">Selecione</option>
              {DEVELOPMENT_TYPES.map((type) => <option key={type} value={type}>{type}</option>)}
              {developmentType && !DEVELOPMENT_TYPES.includes(developmentType) && <option value={developmentType}>{developmentType} (cadastro antigo)</option>}
            </select>
          </label>
          <label><span>Contratante <b className="required-mark">*</b></span>
            <select required aria-required="true" value={partyId} onChange={(e) => setPartyId(e.target.value)}>
              <option value="">Selecione</option>
              {parties.filter((x) => x.is_active || x.id === partyId).map((x) => (
                <option key={x.id} value={x.id}>{contractingPartyLabel(x)}{x.document ? " · " + formatDocument(x.document) : ""}</option>
              ))}
            </select>
          </label>
          <label className="form-span-2"><span>Responsável principal <b className="required-mark">*</b></span><select required aria-required="true" value={clientId} onChange={(e) => setClientId(e.target.value)}><option value="">Selecione</option>{clients.filter((x) => x.is_active || x.id === clientId).map((x) => <option key={x.id} value={x.id}>{x.name}</option>)}</select></label>
          <label>Telefone<input type="tel" inputMode="numeric" placeholder="(85) 3333-3333" value={contactPhone} onChange={(e) => setContactPhone(formatPhone(e.target.value))} /></label>
          <label>Email<input type="email" placeholder="email@exemplo.com" value={contactEmail} onChange={(e) => setContactEmail(e.target.value)} /></label>
        </div>
        <span className="eyebrow">Endereço</span>
        <div className="compact-form-grid">
          <label className="form-span-2"><span>Logradouro <b className="required-mark">*</b></span><input required aria-required="true" placeholder="Rua, avenida..." value={addressLine} onChange={(e) => setAddressLine(e.target.value)} /></label>
          <label>Número<input placeholder="Ex.: 1200 ou S/N" value={addressNumber} onChange={(e) => setAddressNumber(e.target.value)} /></label>
          <label>Complemento<input placeholder="Bloco, torre..." value={addressComplement} onChange={(e) => setAddressComplement(e.target.value)} /></label>
          <label>Bairro<input value={addressDistrict} onChange={(e) => setAddressDistrict(e.target.value)} /></label>
          <label>CEP<input inputMode="numeric" placeholder="00000-000" value={postalCode} onChange={(e) => setPostalCode(e.target.value)} /></label>
          <label><span>Município <b className="required-mark">*</b></span><input required aria-required="true" value={city} onChange={(e) => setCity(e.target.value)} /></label>
          <label><span>UF <b className="required-mark">*</b></span><input required aria-required="true" maxLength={2} value={state} onChange={(e) => setState(e.target.value.toUpperCase())} /></label>
          <label>Latitude<input inputMode="decimal" placeholder="-3,731900" value={latitude} onChange={(e) => setLatitude(e.target.value)} /></label>
          <label>Longitude<input inputMode="decimal" placeholder="-38,526700" value={longitude} onChange={(e) => setLongitude(e.target.value)} /></label>
        </div>
        <button type="button" className="small-button form-inline-button" disabled={busy} onClick={useMyLocation}>
          <LocateFixed size={16} /> Usar minha localização
        </button>
        <span className="eyebrow">Operação</span>
        <div className="compact-form-grid">
          <label>Número de economias<input inputMode="numeric" placeholder="Ex.: 120" value={unitsCount} onChange={(e) => setUnitsCount(e.target.value)} /></label>
          <label>Horário de acesso<input placeholder="Ex.: seg a sex, 8h às 17h" value={accessHours} onChange={(e) => setAccessHours(e.target.value)} /></label>
          <label className="form-span-2">Foto da fachada
            <input key={photoInputKey} type="file" accept="image/jpeg,image/png,image/webp" onChange={(e) => setPhotoFile(e.target.files?.[0] ?? null)} />
          </label>
        </div>
        {photoUrl && !photoFile && (
          <div className="facade-photo">
            <a href={photoUrl} target="_blank" rel="noreferrer"><img src={photoUrl} alt={"Fachada de " + name} /></a>
            <button type="button" className="text-button" disabled={busy} onClick={() => void removePhoto()}>Remover foto</button>
          </div>
        )}
        {photoFile && <span className="required-hint">Nova foto selecionada: {photoFile.name}. Ela é enviada ao salvar{photoUrl ? " e substitui a atual" : ""}.</span>}
        <p className="required-hint"><b className="required-mark">*</b> Obrigatório.</p>
        <div className="admin-actions form-submit">
          <button className="primary-button" disabled={busy} onClick={() => void save()}>
            {!editingId && <Building2 size={17} />}
            {busy ? "Salvando..." : editingId ? "Salvar alterações" : "Cadastrar empreendimento"}
          </button>
          <button className="text-button" disabled={busy} onClick={closeForm}>{editingId ? "Cancelar" : "Fechar"}</button>
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
            placeholder="Buscar nome, contratante, tipo, responsável ou município"
            aria-label="Buscar empreendimento"
          />
        </label>
{!panel.open && (
<button className="primary-button" disabled={busy} onClick={openNew}><Building2 size={17} /> Novo empreendimento</button>
)}
</div>
{rowFeedback && <span className="inline-feedback" role="status">{rowFeedback}</span>}
        <div className="admin-list collab-table collab-table-wide" role="table" aria-label="Empreendimentos">
          <TableHead columns={DEVELOPMENT_COLUMNS} sortKey={sortKey} sortAsc={sortAsc} onSort={toggleSort} />
          {sorted.map((item) => (
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
                  {item.development_type
                    ? <span className="collab-chip" title={item.development_type}>{item.development_type}</span>
                    : "—"}
                </div>
                <div className="collab-col-contact" role="cell">
                  {formatPhone(item.contact_phone) || "—"}
                </div>
                <div className="collab-col-status" role="cell">
                  <span className={item.is_active ? "collab-status active" : "collab-status"}>{item.is_active ? "Ativo" : "Inativo"}</span>
                </div>
                <div className="collab-actions" role="cell">
                  <button className="icon-action icon-action-edit" disabled={busy} title="Editar" aria-label={"Editar: " + item.name} onClick={() => startEdit(item)}>
                    <Pencil size={16} />
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
            </div>
          ))}
          {developments.length === 0 && (
            <div className="empty-state">
              Nenhum empreendimento cadastrado. Cadastre primeiro o contratante e o responsável principal, nas abas ao lado.
            </div>
          )}
          {developments.length > 0 && visible.length === 0 && (
            <div className="empty-state">
              Nenhum empreendimento encontrado para "{search.trim()}". Confira a grafia ou limpe a busca.
            </div>
          )}
        </div>
        {menu && menuItem && <RowMenu menu={menu} items={menuItems} busy={busy} onClose={closeMenu} />}
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
      setFeedback(station.is_active ? "Estação inativada." : "Estação reativada.");
      await onChanged();
    } catch {
      setFeedback("Não foi possível alterar a estação.");
    } finally {
      setBusy(false);
    }
  }

  async function create() {
    if (!developmentId || name.trim().length < 2) return setFeedback("Selecione o empreendimento e informe a estação.");
    setBusy(true);
    try {
      await api("/api/v1/stations", { method: "POST", body: JSON.stringify({
        development_id: developmentId, name: name.trim(), code: code.trim() || null,
        station_type: stationType, visit_frequency_days: Number(frequencyDays) || null,
      }) });
      setName(""); setCode(""); setFeedback("Estação cadastrada."); await onChanged();
    } catch { setFeedback("Não foi possível cadastrar a estação."); }
    finally { setBusy(false); }
  }

  return (
    <div className="admin-panel">
      <div className="admin-list">
        {stations.map((station) => (
          <div className="admin-row" key={station.id}>
            <div><strong>{station.name}</strong><span>{developmentMap.get(station.development_id)?.name ?? "Empreendimento"} · {station.code || station.station_type || "Estação"}</span></div>
            <div className="admin-actions">
              <span className={station.is_active ? "status status-revisada" : "status"}>
                {station.is_active ? (station.visit_frequency_days ? station.visit_frequency_days + "d" : "Ativa") : "Inativa"}
              </span>
              {onOpenStation && (
                <button className="text-button" onClick={() => onOpenStation(station.id)}>
                  Ver estação
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
        <h3>Nova estação</h3>
        <div className="compact-form-grid">
          <label>Empreendimento<select value={developmentId} onChange={(e) => setDevelopmentId(e.target.value)}><option value="">Selecione</option>{developments.filter((x) => x.is_active).map((x) => <option key={x.id} value={x.id}>{x.name}</option>)}</select></label>
          <label>Nome<input value={name} onChange={(e) => setName(e.target.value)} /></label>
          <label>Código<input value={code} onChange={(e) => setCode(e.target.value)} /></label>
          <label>Tipo<select value={stationType} onChange={(e) => setStationType(e.target.value)}><option value="ETE">ETE</option><option value="ETA">ETA</option><option value="EEE">EEE</option><option value="ELEVATORIA">Elevatória</option><option value="OUTRA">Outra</option></select></label>
          <label>Frequência<select value={frequencyDays} onChange={(e) => setFrequencyDays(e.target.value)}><option value="1">Diária</option><option value="7">Semanal</option><option value="14">Quinzenal</option><option value="30">Mensal</option></select></label>
        </div>
        <button className="small-button" disabled={busy} onClick={() => void create()}>{busy ? "Salvando..." : "Cadastrar estação"}</button>
        {feedback && <span className="inline-feedback">{feedback}</span>}
      </div>
    </div>
  );
}

function AssetAdmin({
  stations,
  assetTypes,
  assets,
  units,
  onChanged,
}: {
  stations: AdminStation[];
  assetTypes: AssetTypeRecord[];
  assets: AssetRecord[];
  units: ProcessUnitRecord[];
  onChanged: () => Promise<void>;
}) {
  const [stationId, setStationId] = useState("");
  const [assetTypeId, setAssetTypeId] = useState("");
  const [unitId, setUnitId] = useState("");
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
  const unitMap = new Map(units.map((item) => [item.id, item]));
  const stationUnits = units.filter((item) => item.station_id === stationId && item.is_active);

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
      setFeedback("Não foi possível atualizar o ativo.");
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
      setFeedback("Não foi possível atualizar o tipo.");
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
    } catch { setFeedback("Não foi possível cadastrar o tipo de ativo."); }
    finally { setBusy(false); }
  }

  async function createAsset() {
    if (!stationId || !assetTypeId || name.trim().length < 2) return setFeedback("Selecione estação/tipo e informe o ativo.");
    setBusy(true);
    try {
      await api("/api/v1/assets", { method: "POST", body: JSON.stringify({
        station_id: stationId, asset_type_id: assetTypeId, process_unit_id: unitId || null, name: name.trim(),
        manufacturer: manufacturer.trim() || null, model: model.trim() || null,
        serial_number: serialNumber.trim() || null, status: statusValue,
      }) });
      setName(""); setManufacturer(""); setModel(""); setSerialNumber(""); setFeedback("Ativo cadastrado."); await onChanged();
    } catch { setFeedback("Não foi possível cadastrar o ativo."); }
    finally { setBusy(false); }
  }

  return (
    <div className="admin-panel">
      <div className="admin-list">
        {assets.map((asset) => (
          <div className="admin-row" key={asset.id}>
            <div><strong>{asset.name}</strong><span>{stationMap.get(asset.station_id)?.name ?? "Estação"} · {(asset.process_unit_id && unitMap.get(asset.process_unit_id)?.name) || "Sem unidade"} · {typeMap.get(asset.asset_type_id)?.name ?? "Tipo"} · {asset.manufacturer || asset.model || "Sem fabricante"}</span></div>
            <div className="admin-actions asset-actions">
              <select
                value={asset.status}
                disabled={busy}
                onChange={(event) => void updateAsset(asset, { status: event.target.value })}
              >
                <option value="OPERANDO">Operando</option>
                <option value="DESLIGADO">Desligado</option>
                <option value="EM_MANUTENCAO">Em manutenção</option>
                <option value="AGUARDANDO_MANUTENCAO">Aguardando manutenção</option>
                <option value="AGUARDANDO_INSTALACAO">Aguardando instalação</option>
                <option value="NECESSITA_VERIFICACAO">Necessita verificação</option>
                <option value="NAO_POSSUI">Não possui</option>
                <option value="NAO_APLICAVEL">Não aplicável</option>
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
            <label>Código<input value={assetTypeCode} onChange={(e) => setAssetTypeCode(e.target.value)} /></label>
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
            <label>Estação<select value={stationId} onChange={(e) => { setStationId(e.target.value); setUnitId(""); }}><option value="">Selecione</option>{stations.filter((x) => x.is_active).map((x) => <option key={x.id} value={x.id}>{x.name}</option>)}</select></label>
            <label>Tipo<select value={assetTypeId} onChange={(e) => setAssetTypeId(e.target.value)}><option value="">Selecione</option>{assetTypes.filter((x) => x.is_active).map((x) => <option key={x.id} value={x.id}>{x.name}</option>)}</select></label>
            <label>Unidade<select value={unitId} onChange={(e) => setUnitId(e.target.value)}><option value="">Sem unidade (área geral)</option>{stationUnits.map((x) => <option key={x.id} value={x.id}>{x.name}</option>)}</select></label>
            <label>Nome<input value={name} onChange={(e) => setName(e.target.value)} /></label>
            <label>Fabricante<input value={manufacturer} onChange={(e) => setManufacturer(e.target.value)} /></label>
            <label>Modelo<input value={model} onChange={(e) => setModel(e.target.value)} /></label>
            <label>Número de série<input value={serialNumber} onChange={(e) => setSerialNumber(e.target.value)} /></label>
            <label>Status<select value={statusValue} onChange={(e) => setStatusValue(e.target.value)}><option value="OPERANDO">Operando</option><option value="DESLIGADO">Desligado</option><option value="EM_MANUTENCAO">Em manutenção</option><option value="AGUARDANDO_MANUTENCAO">Aguardando manutenção</option><option value="AGUARDANDO_INSTALACAO">Aguardando instalação</option><option value="NECESSITA_VERIFICACAO">Necessita verificação</option><option value="NAO_POSSUI">Não possui</option><option value="NAO_APLICAVEL">Não aplicável</option></select></label>
          </div>
          <button className="small-button" disabled={busy} onClick={() => void createAsset()}>{busy ? "Salvando..." : "Cadastrar ativo"}</button>
        </div>
      </div>
      {feedback && <span className="inline-feedback">{feedback}</span>}
    </div>
  );
}
