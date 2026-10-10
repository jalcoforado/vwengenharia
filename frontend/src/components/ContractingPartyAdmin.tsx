import { useState } from "react";
import { Briefcase, EllipsisVertical, Eye, Pencil, Search } from "lucide-react";

import { api } from "../lib/api";
import { Avatar, RowMenu, TableHead, useFormPanel, useRowMenu, useSort, type RowMenuItem } from "./AdminTable";
import { ContractingPartyDetails } from "./PartyDetails";
import { formatDocument, isValidCpfCnpj, normalizeDocument } from "../lib/document";
import { formatPhone, isCompletePhone } from "../lib/phone";

export type PersonType = "PJ" | "PF";

export type ContractingPartyRecord = {
  id: string;
  person_type: PersonType;
  name: string;
  trade_name: string | null;
  document: string | null;
  contact_email: string | null;
  contact_phone: string | null;
  contact_whatsapp: string | null;
  is_active: boolean;
};

// O que a consulta precisa saber de cada empreendimento contratado.
type PartyDevelopment = {
  id: string;
  client_id: string;
  contracting_party_id: string | null;
  name: string;
  development_type: string | null;
  city: string | null;
  state: string | null;
  is_active: boolean;
};

const PERSON_TYPES: [PersonType, string][] = [
  ["PJ", "Pessoa jurídica"],
  ["PF", "Pessoa física"],
];

type SortKey = "name" | "type" | "contact" | "status";

const SORT_COLUMNS: [SortKey, string, string][] = [
  ["name", "Nome", "collab-col-name"],
  ["type", "Tipo", "collab-col-category"],
  ["contact", "Contato", "collab-col-contact"],
  ["status", "Status", "collab-col-status"],
];

// Nome usado nas listas e selecoes: o fantasia, quando existe, e o que a equipe reconhece.
export function contractingPartyLabel(party: ContractingPartyRecord): string {
  return party.trade_name || party.name;
}

export default function ContractingPartyAdmin({
  parties,
  developments,
  clients,
  onChanged,
}: {
  parties: ContractingPartyRecord[];
  developments: PartyDevelopment[];
  clients: { id: string; name: string }[];
  onChanged: () => Promise<void>;
}) {
  const [search, setSearch] = useState("");
  const [editingId, setEditingId] = useState<string | null>(null);
  const [personType, setPersonType] = useState<PersonType>("PJ");
  const [name, setName] = useState("");
  const [tradeName, setTradeName] = useState("");
  const [document, setDocument] = useState("");
  const [contactEmail, setContactEmail] = useState("");
  const [contactPhone, setContactPhone] = useState("");
  const [contactWhatsapp, setContactWhatsapp] = useState("");
  const [feedback, setFeedback] = useState<string | null>(null);
  const [rowFeedback, setRowFeedback] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [expandedId, setExpandedId] = useState<string | null>(null);
  const { sortKey, sortAsc, toggleSort, sortBy } = useSort<SortKey>("name");
  const { menu, openMenu, closeMenu } = useRowMenu();
  const panel = useFormPanel();

  const term = search.trim().toLowerCase();
  const termDigits = term.replace(/\D/g, "");
  const visible = parties.filter((item) => {
    if (!term) return true;
    const fields = [item.name, item.trade_name, item.document, item.contact_email, item.contact_phone, item.contact_whatsapp]
      .map((value) => (value ?? "").toLowerCase());
    if (fields.some((value) => value.includes(term))) return true;
    // Permite achar CPF/CNPJ e telefone digitando so os numeros.
    return (
      termDigits.length >= 3 &&
      [item.document, item.contact_phone, item.contact_whatsapp].some((value) => (value ?? "").replace(/\D/g, "").includes(termDigits))
    );
  });

  const sorted = sortBy(visible, (item, key) => {
    if (key === "type") return item.person_type;
    if (key === "contact") return (item.contact_whatsapp || item.contact_phone || "").replace(/\D/g, "");
    if (key === "status") return item.is_active ? "0" : "1";
    return contractingPartyLabel(item);
  });

  function resetForm() {
    setEditingId(null);
    setPersonType("PJ"); setName(""); setTradeName(""); setDocument("");
    setContactEmail(""); setContactPhone(""); setContactWhatsapp("");
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

  function startEdit(item: ContractingPartyRecord) {
    setEditingId(item.id);
    setPersonType(item.person_type);
    setName(item.name);
    setTradeName(item.trade_name ?? "");
    setDocument(formatDocument(item.document));
    setContactEmail(item.contact_email ?? "");
    setContactPhone(formatPhone(item.contact_phone));
    setContactWhatsapp(formatPhone(item.contact_whatsapp));
    setFeedback(null);
    panel.show();
  }

  async function save() {
    const documentLabel = personType === "PJ" ? "CNPJ" : "CPF";
    if (name.trim().length < 2) {
      return setFeedback(personType === "PJ" ? "Informe a razão social do contratante." : "Informe o nome do contratante.");
    }
    if (!document.trim()) return setFeedback("Informe o " + documentLabel + " do contratante.");
    if (normalizeDocument(document).length !== (personType === "PJ" ? 14 : 11) || !isValidCpfCnpj(document)) {
      return setFeedback(documentLabel + " inválido. Confira os números digitados.");
    }
    if (!contactWhatsapp.trim() && !contactPhone.trim()) {
      return setFeedback("Informe o WhatsApp ou o telefone do contratante.");
    }
    if (contactWhatsapp.trim() && !isCompletePhone(contactWhatsapp)) {
      return setFeedback("WhatsApp incompleto. Informe DDD e número.");
    }
    if (contactPhone.trim() && !isCompletePhone(contactPhone)) {
      return setFeedback("Telefone incompleto. Informe DDD e número.");
    }
    setBusy(true);
    try {
      await api(editingId ? "/api/v1/contracting-parties/" + editingId : "/api/v1/contracting-parties", {
        method: editingId ? "PATCH" : "POST",
        body: JSON.stringify({
          person_type: personType,
          name: name.trim(),
          trade_name: tradeName.trim() || null,
          document: normalizeDocument(document),
          contact_email: contactEmail.trim() || null,
          contact_phone: contactPhone.trim() || null,
          contact_whatsapp: contactWhatsapp.trim() || null,
        }),
      });
      if (editingId) {
        setRowFeedback("Contratante atualizado.");
        closeForm();
      } else {
        resetForm();
        setFeedback("Contratante cadastrado. O formulário segue aberto para o próximo.");
      }
      await onChanged();
    } catch (error) {
      const status =
        typeof error === "object" && error !== null && "status" in error ? error.status : null;
      if (status === 409) {
        setFeedback("Já existe um contratante com esse " + documentLabel + ". Use a busca para localizá-lo.");
      } else if (status === 422) {
        setFeedback("Confira os dados informados, em especial o email.");
      } else {
        setFeedback("Não foi possível salvar o contratante.");
      }
    } finally {
      setBusy(false);
    }
  }

  async function toggle(item: ContractingPartyRecord) {
    setBusy(true);
    try {
      await api("/api/v1/contracting-parties/" + item.id, {
        method: "PATCH",
        body: JSON.stringify({ is_active: !item.is_active }),
      });
      setRowFeedback(item.is_active ? "Contratante inativado." : "Contratante reativado.");
      await onChanged();
    } catch {
      setRowFeedback("Não foi possível alterar o contratante.");
    } finally {
      setBusy(false);
    }
  }

  function summary(item: ContractingPartyRecord): string {
    const count = developments.filter((development) => development.contracting_party_id === item.id).length;
    return [
      formatDocument(item.document) || "Sem CPF/CNPJ informado",
      item.trade_name ? item.name : null,
      count === 1 ? "1 empreendimento" : count + " empreendimentos",
    ].filter(Boolean).join(" · ");
  }

  const menuItem = menu ? parties.find((item) => item.id === menu.id) : undefined;
  const menuItems: RowMenuItem[] = menuItem
    ? [
        { text: expandedId === menuItem.id ? "Fechar consulta" : "Consultar", run: () => setExpandedId(expandedId === menuItem.id ? null : menuItem.id) },
        { text: "Editar", run: () => startEdit(menuItem) },
        { text: menuItem.is_active ? "Inativar" : "Reativar", run: () => void toggle(menuItem), danger: menuItem.is_active },
      ]
    : [];

  return (
    <div className="admin-stack">
      {panel.open && (
        <div className="compact-form admin-create-form" ref={panel.ref}>
          <h3 className="form-title">{editingId ? <Pencil size={17} /> : <Briefcase size={17} />}{editingId ? "Editar contratante" : "Novo contratante"}</h3>
          <div className="compact-form-grid">
            <label><span>Tipo de pessoa <b className="required-mark">*</b></span>
              <select required aria-required="true" value={personType} onChange={(e) => setPersonType(e.target.value as PersonType)}>
                {PERSON_TYPES.map(([value, text]) => <option key={value} value={value}>{text}</option>)}
              </select>
            </label>
            <label className="form-span-2"><span>{personType === "PJ" ? "Razão social" : "Nome completo"} <b className="required-mark">*</b></span><input required aria-required="true" value={name} onChange={(e) => setName(e.target.value)} /></label>
            <label><span>{personType === "PJ" ? "CNPJ" : "CPF"} <b className="required-mark">*</b></span><input required aria-required="true" inputMode="numeric" placeholder={personType === "PJ" ? "00.000.000/0000-00" : "000.000.000-00"} value={document} onChange={(e) => setDocument(e.target.value)} /></label>
            <label className="form-span-2">{personType === "PJ" ? "Nome fantasia" : "Nome de exibição"}<input placeholder="Como a equipe identifica este contratante" value={tradeName} onChange={(e) => setTradeName(e.target.value)} /></label>
            <label>Email<input type="email" placeholder="email@exemplo.com" value={contactEmail} onChange={(e) => setContactEmail(e.target.value)} /></label>
            <label><span>WhatsApp <b className="required-mark">**</b></span><input type="tel" inputMode="numeric" placeholder="(85) 99999-9999" value={contactWhatsapp} onChange={(e) => setContactWhatsapp(formatPhone(e.target.value))} /></label>
            <label><span>Telefone <b className="required-mark">**</b></span><input type="tel" inputMode="numeric" placeholder="(85) 3333-3333" value={contactPhone} onChange={(e) => setContactPhone(formatPhone(e.target.value))} /></label>
          </div>
          <p className="required-hint">
            <b className="required-mark">*</b> Obrigatório. <b className="required-mark">**</b> Informe ao menos um: WhatsApp ou Telefone. O contratante é quem assina com a MW; os locais atendidos são cadastrados em Empreendimentos.
          </p>
          <div className="admin-actions form-submit">
            <button className="primary-button" disabled={busy} onClick={() => void save()}>
              {!editingId && <Briefcase size={17} />}
              {busy ? "Salvando..." : editingId ? "Salvar alterações" : "Cadastrar contratante"}
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
              placeholder="Buscar razão social, nome fantasia, CPF/CNPJ ou email"
              aria-label="Buscar contratante"
            />
          </label>
          {!panel.open && (
            <button className="primary-button" disabled={busy} onClick={openNew}><Briefcase size={17} /> Novo contratante</button>
          )}
        </div>
        {rowFeedback && <span className="inline-feedback" role="status">{rowFeedback}</span>}
        <div className="admin-list collab-table" role="table" aria-label="Contratantes">
          <TableHead columns={SORT_COLUMNS} sortKey={sortKey} sortAsc={sortAsc} onSort={toggleSort} />
          {sorted.map((item) => (
            <div className="client-entry" key={item.id}>
              <div className={item.is_active ? "collab-row" : "collab-row collab-row-inactive"} role="row">
                <div className="collab-person" role="cell">
                  <Avatar name={contractingPartyLabel(item)} />
                  <div>
                    <strong>{contractingPartyLabel(item)}</strong>
                    <span title={summary(item)}>{summary(item)}</span>
                  </div>
                </div>
                <div className="collab-col-category" role="cell">
                  <span className="collab-chip">{item.person_type === "PJ" ? "Pessoa jurídica" : "Pessoa física"}</span>
                </div>
                <div className="collab-col-contact" role="cell">
                  {formatPhone(item.contact_whatsapp || item.contact_phone) || "—"}
                </div>
                <div className="collab-col-status" role="cell">
                  <span className={item.is_active ? "collab-status active" : "collab-status"}>{item.is_active ? "Ativo" : "Inativo"}</span>
                </div>
                <div className="collab-actions" role="cell">
                  <button
                    className={expandedId === item.id ? "icon-action icon-action-on" : "icon-action"}
                    title={expandedId === item.id ? "Fechar consulta" : "Consultar"}
                    aria-label={(expandedId === item.id ? "Fechar consulta: " : "Consultar: ") + contractingPartyLabel(item)}
                    aria-expanded={expandedId === item.id}
                    onClick={() => setExpandedId(expandedId === item.id ? null : item.id)}
                  >
                    <Eye size={16} />
                  </button>
                  <button className="icon-action icon-action-edit" disabled={busy} title="Editar" aria-label={"Editar: " + contractingPartyLabel(item)} onClick={() => startEdit(item)}>
                    <Pencil size={16} />
                  </button>
                  <button
                    className="icon-action row-menu-trigger"
                    disabled={busy}
                    title="Mais ações"
                    aria-label={"Mais ações: " + contractingPartyLabel(item)}
                    aria-haspopup="menu"
                    aria-expanded={menu?.id === item.id}
                    onClick={(event) => openMenu(item.id, event.currentTarget)}
                  >
                    <EllipsisVertical size={16} />
                  </button>
                </div>
              </div>
              {expandedId === item.id && (
                <ContractingPartyDetails party={item} developments={developments} clients={clients} />
              )}
            </div>
          ))}
          {parties.length === 0 && (
            <div className="empty-state">
              Nenhum contratante cadastrado. Ele é opcional: sem contratante, o responsável principal do empreendimento responde pelo contrato.
            </div>
          )}
          {parties.length > 0 && visible.length === 0 && (
            <div className="empty-state">
              Nenhum contratante encontrado para "{search.trim()}". Confira a grafia ou limpe a busca.
            </div>
          )}
        </div>
        {menu && menuItem && <RowMenu menu={menu} items={menuItems} busy={busy} onClose={closeMenu} />}
      </div>
    </div>
  );
}
