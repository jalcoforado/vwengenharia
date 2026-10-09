import { useEffect, useState } from "react";
import { EllipsisVertical, KeyRound, Lock, LockOpen, Pencil, Search, UserPlus } from "lucide-react";

import { api } from "../lib/api";
import { Avatar, RowMenu, TableHead, useRowMenu, useSort, type RowMenuItem } from "./AdminTable";
import { formatDocument, isValidCpfCnpj, normalizeDocument } from "../lib/document";
import { formatPhone, isCompletePhone } from "../lib/phone";

type CollaboratorCategory = "DIRETORIA" | "BACKOFFICE" | "TECNICO";

type CollaboratorRecord = {
  id: string;
  name: string;
  document: string | null;
  category: CollaboratorCategory;
  contact_phone: string | null;
  contact_whatsapp: string | null;
  contact_email: string | null;
  is_active: boolean;
  membership_id: string | null;
  credential_email: string | null;
  credential_role: string | null;
  credential_active: boolean | null;
};

const CATEGORIES: [CollaboratorCategory, string][] = [
  ["DIRETORIA", "Diretoria"],
  ["BACKOFFICE", "Backoffice"],
  ["TECNICO", "Técnico"],
];

const ACCESS_ROLES: [string, string][] = [
  ["TECNICO", "Técnico"],
  ["MANUTENCAO", "Manutenção"],
  ["SUPERVISOR", "Supervisor"],
  ["GESTOR", "Gestor"],
  ["ADMIN", "Administrador"],
];

const ERROR_MESSAGES: Record<string, string> = {
  collaborator_document_already_exists: "Já existe um colaborador com esse CPF.",
  email_already_registered: "Esse email já é usado por outro acesso.",
  cannot_change_own_membership: "Você não pode inativar o seu próprio cadastro.",
  cannot_manage_superadmin: "Somente um superadministrador altera esse cadastro.",
  cannot_assign_role: "Você não pode conceder esse perfil.",
  collaborator_inactive: "Reative o colaborador antes de liberar o acesso.",
  collaborator_already_has_credential: "Esse colaborador já tem acesso ao app.",
};

function errorMessage(error: unknown, fallback: string): string {
  if (typeof error === "object" && error !== null && "detail" in error) {
    const detail = error.detail;
    if (typeof detail === "string" && ERROR_MESSAGES[detail]) return ERROR_MESSAGES[detail];
  }
  if (typeof error === "object" && error !== null && "status" in error && error.status === 422) {
    return "Confira os dados informados, em especial o email.";
  }
  return fallback;
}

function label(options: [string, string][], value: string | null): string {
  return options.find(([key]) => key === value)?.[1] ?? value ?? "";
}

type SortKey = "name" | "category" | "contact" | "status";

const SORT_COLUMNS: [SortKey, string, string][] = [
  ["name", "Nome", "collab-col-name"],
  ["category", "Grupo", "collab-col-category"],
  ["contact", "Contato", "collab-col-contact"],
  ["status", "Status", "collab-col-status"],
];

export default function CollaboratorAdmin({
  canManage,
  onChanged,
  onActiveCount,
}: {
  canManage: boolean;
  onChanged: () => Promise<void>;
  onActiveCount?: (count: number) => void;
}) {
  const [collaborators, setCollaborators] = useState<CollaboratorRecord[]>([]);
  const [search, setSearch] = useState("");
  const [editingId, setEditingId] = useState<string | null>(null);
  const [name, setName] = useState("");
  const [document, setDocument] = useState("");
  const [category, setCategory] = useState<CollaboratorCategory>("TECNICO");
  const [contactPhone, setContactPhone] = useState("");
  const [contactWhatsapp, setContactWhatsapp] = useState("");
  const [contactEmail, setContactEmail] = useState("");
  const [accessId, setAccessId] = useState<string | null>(null);
  const [accessEmail, setAccessEmail] = useState("");
  const [accessRole, setAccessRole] = useState("TECNICO");
  const [accessPassword, setAccessPassword] = useState("");
  const [feedback, setFeedback] = useState<string | null>(null);
  const [rowFeedback, setRowFeedback] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const { sortKey, sortAsc, toggleSort, sortBy } = useSort<SortKey>("name");
  const { menu, openMenu, closeMenu } = useRowMenu();

  async function load() {
    try {
      const loaded = await api<CollaboratorRecord[]>("/api/v1/collaborators");
      setCollaborators(loaded);
      onActiveCount?.(loaded.filter((item) => item.is_active).length);
    } catch {
      setRowFeedback("Não foi possível carregar os colaboradores.");
    }
  }

  useEffect(() => {
    void load();
  }, []);

  const term = search.trim().toLowerCase();
  const termDigits = term.replace(/\D/g, "");
  const visible = collaborators.filter((item) => {
    if (!term) return true;
    const fields = [
      item.name,
      item.document,
      label(CATEGORIES, item.category),
      item.contact_phone,
      item.contact_whatsapp,
      item.contact_email,
      item.credential_email,
    ].map((value) => (value ?? "").toLowerCase());
    if (fields.some((value) => value.includes(term))) return true;
    return (
      termDigits.length >= 3 &&
      [item.document, item.contact_phone, item.contact_whatsapp].some((value) =>
        (value ?? "").replace(/\D/g, "").includes(termDigits),
      )
    );
  });

  const sorted = sortBy(visible, (item, key) => {
    if (key === "category") return label(CATEGORIES, item.category);
    if (key === "contact") return (item.contact_whatsapp || item.contact_phone || "").replace(/\D/g, "");
    if (key === "status") return item.is_active ? "0" : "1";
    return item.name;
  });

  function resetForm() {
    setEditingId(null);
    setName(""); setDocument(""); setCategory("TECNICO");
    setContactPhone(""); setContactWhatsapp(""); setContactEmail("");
  }

  function startEdit(item: CollaboratorRecord) {
    setEditingId(item.id);
    setName(item.name);
    setDocument(formatDocument(item.document));
    setCategory(item.category);
    setContactPhone(formatPhone(item.contact_phone));
    setContactWhatsapp(formatPhone(item.contact_whatsapp));
    setContactEmail(item.contact_email ?? "");
    setFeedback(null);
  }

  async function save() {
    if (name.trim().length < 2) return setFeedback("Informe o nome do colaborador.");
    if (!document.trim()) return setFeedback("Informe o CPF do colaborador.");
    if (normalizeDocument(document).length !== 11 || !isValidCpfCnpj(document)) {
      return setFeedback("CPF inválido. Confira os números digitados.");
    }
    if (!contactWhatsapp.trim()) return setFeedback("Informe o WhatsApp do colaborador.");
    if (!isCompletePhone(contactWhatsapp)) {
      return setFeedback("WhatsApp incompleto. Informe DDD e número.");
    }
    if (contactPhone.trim() && !isCompletePhone(contactPhone)) {
      return setFeedback("Telefone incompleto. Informe DDD e número.");
    }
    setBusy(true);
    try {
      await api(editingId ? "/api/v1/collaborators/" + editingId : "/api/v1/collaborators", {
        method: editingId ? "PATCH" : "POST",
        body: JSON.stringify({
          name: name.trim(),
          document: normalizeDocument(document),
          category,
          contact_whatsapp: contactWhatsapp.trim(),
          contact_phone: contactPhone.trim() || null,
          contact_email: contactEmail.trim() || null,
        }),
      });
      setFeedback(editingId ? "Colaborador atualizado." : "Colaborador cadastrado. Ele ainda não tem acesso ao app.");
      resetForm();
      await load();
    } catch (error) {
      setFeedback(errorMessage(error, "Não foi possível salvar o colaborador."));
    } finally {
      setBusy(false);
    }
  }

  async function toggleActive(item: CollaboratorRecord) {
    setBusy(true);
    try {
      await api("/api/v1/collaborators/" + item.id, {
        method: "PATCH",
        body: JSON.stringify({ is_active: !item.is_active }),
      });
      setRowFeedback(
        item.is_active
          ? "Colaborador inativado. O acesso dele ao app foi bloqueado."
          : "Colaborador reativado. O acesso ao app continua bloqueado até ser reativado.",
      );
      await load();
      await onChanged();
    } catch (error) {
      setRowFeedback(errorMessage(error, "Não foi possível alterar o colaborador."));
    } finally {
      setBusy(false);
    }
  }

  async function toggleAccess(item: CollaboratorRecord) {
    if (!item.membership_id) return;
    setBusy(true);
    try {
      await api("/api/v1/team/" + item.membership_id, {
        method: "PATCH",
        body: JSON.stringify({ is_active: !item.credential_active }),
      });
      setRowFeedback(item.credential_active ? "Acesso ao app bloqueado." : "Acesso ao app reativado.");
      await load();
      await onChanged();
    } catch (error) {
      setRowFeedback(errorMessage(error, "Não foi possível alterar o acesso."));
    } finally {
      setBusy(false);
    }
  }

  function openAccess(item: CollaboratorRecord) {
    setRowFeedback(null);
    if (accessId === item.id) return setAccessId(null);
    setAccessId(item.id);
    setAccessEmail(item.contact_email ?? "");
    setAccessRole(item.category === "TECNICO" ? "TECNICO" : "GESTOR");
    setAccessPassword("");
  }

  async function createAccess(item: CollaboratorRecord) {
    if (!accessEmail.trim() || accessPassword.length < 12) {
      return setRowFeedback("Informe o email e uma senha inicial com pelo menos 12 caracteres.");
    }
    setBusy(true);
    try {
      await api("/api/v1/collaborators/" + item.id + "/credential", {
        method: "POST",
        body: JSON.stringify({ email: accessEmail.trim(), password: accessPassword, role: accessRole }),
      });
      setAccessId(null);
      setAccessPassword("");
      setRowFeedback("Acesso criado. Informe a senha inicial ao colaborador.");
      await load();
      await onChanged();
    } catch (error) {
      setRowFeedback(errorMessage(error, "Não foi possível criar o acesso."));
    } finally {
      setBusy(false);
    }
  }

  function accessSummary(item: CollaboratorRecord): string {
    if (!item.membership_id) return [item.contact_email, "Sem acesso ao app"].filter(Boolean).join(" · ");
    return item.credential_active
      ? item.credential_email + " · " + label(ACCESS_ROLES, item.credential_role)
      : item.credential_email + " · Acesso bloqueado";
  }

  function accessAction(item: CollaboratorRecord): { text: string; run: () => void } | null {
    if (!item.is_active) return null;
    if (!item.membership_id) {
      return { text: accessId === item.id ? "Fechar criação de acesso" : "Criar acesso", run: () => openAccess(item) };
    }
    return {
      text: item.credential_active ? "Bloquear acesso" : "Reativar acesso",
      run: () => void toggleAccess(item),
    };
  }

  const menuItem = menu ? collaborators.find((item) => item.id === menu.id) : undefined;
  const menuAccess = menuItem ? accessAction(menuItem) : null;
  const menuItems: RowMenuItem[] = menuItem
    ? [
        ...(menuAccess ? [menuAccess] : []),
        { text: "Editar", run: () => startEdit(menuItem) },
        { text: menuItem.is_active ? "Inativar" : "Reativar", run: () => void toggleActive(menuItem), danger: menuItem.is_active },
      ]
    : [];

  return (
    <div className={canManage ? "admin-panel" : "admin-panel admin-panel-single"}>
      <div className="client-list-column">
        <label className="search-field">
          <Search size={16} />
          <input
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Buscar nome, CPF, grupo, telefone ou email"
            aria-label="Buscar colaborador"
          />
        </label>
        <div className="admin-list collab-table" role="table" aria-label="Colaboradores">
          <TableHead columns={SORT_COLUMNS} sortKey={sortKey} sortAsc={sortAsc} onSort={toggleSort} />
          {sorted.map((item) => {
            const access = accessAction(item);
            return (
            <div className="client-entry" key={item.id}>
              <div className={item.is_active ? "collab-row" : "collab-row collab-row-inactive"} role="row">
                <div className="collab-person" role="cell">
                  <Avatar name={item.name} />
                  <div>
                    <strong>{item.name}</strong>
                    <span title={accessSummary(item)}>{accessSummary(item)}</span>
                  </div>
                </div>
                <div className="collab-col-category" role="cell">
                  <span className="collab-chip">{label(CATEGORIES, item.category)}</span>
                </div>
                <div className="collab-col-contact" role="cell">
                  {formatPhone(item.contact_whatsapp || item.contact_phone) || "—"}
                </div>
                <div className="collab-col-status" role="cell">
                  <span className={item.is_active ? "collab-status active" : "collab-status"}>{item.is_active ? "Ativo" : "Inativo"}</span>
                </div>
                <div className="collab-actions" role="cell">
                  {canManage && access && (
                    <button className="icon-action" disabled={busy} title={access.text} aria-label={access.text + ": " + item.name} onClick={access.run}>
                      {!item.membership_id ? <KeyRound size={16} /> : item.credential_active ? <Lock size={16} /> : <LockOpen size={16} />}
                    </button>
                  )}
                  {canManage && (
                    <button className="icon-action icon-action-edit" disabled={busy} title="Editar" aria-label={"Editar: " + item.name} onClick={() => startEdit(item)}>
                      <Pencil size={16} />
                    </button>
                  )}
                  {canManage && (
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
                  )}
                </div>
              </div>
              {accessId === item.id && (
                <div className="client-contacts">
                  <span className="eyebrow">Acesso ao app</span>
                  <div className="client-contact-form">
                    <label>Email de login
                      <input type="email" value={accessEmail} onChange={(e) => setAccessEmail(e.target.value)} />
                    </label>
                    <label>Perfil de acesso
                      <select value={accessRole} onChange={(e) => setAccessRole(e.target.value)}>
                        {ACCESS_ROLES.map(([value, text]) => <option key={value} value={value}>{text}</option>)}
                      </select>
                    </label>
                    <label>Senha inicial
                      <input type="password" autoComplete="new-password" value={accessPassword} onChange={(e) => setAccessPassword(e.target.value)} />
                    </label>
                    <button className="small-button" disabled={busy} onClick={() => void createAccess(item)}>Criar acesso</button>
                  </div>
                </div>
              )}
            </div>
            );
          })}
          {collaborators.length === 0 && (
            <div className="empty-state">Nenhum colaborador cadastrado.</div>
          )}
          {collaborators.length > 0 && visible.length === 0 && (
            <div className="empty-state">
              Nenhum colaborador encontrado para "{search.trim()}". Confira a grafia ou limpe a busca.
            </div>
          )}
        </div>
        {menu && menuItem && <RowMenu menu={menu} items={menuItems} busy={busy} onClose={closeMenu} />}
        {rowFeedback && <span className="inline-feedback">{rowFeedback}</span>}
        {!canManage && (
          <span className="required-hint">Somente administradores cadastram colaboradores e liberam acessos.</span>
        )}
      </div>
      {canManage && (
        <div className="compact-form admin-create-form">
          <h3 className="form-title">{editingId ? <Pencil size={17} /> : <UserPlus size={17} />}{editingId ? "Editar colaborador" : "Novo colaborador"}</h3>
          <div className="compact-form-grid">
            <label><span>Nome <b className="required-mark">*</b></span><input required aria-required="true" placeholder="Nome completo" value={name} onChange={(e) => setName(e.target.value)} /></label>
            <label><span>CPF <b className="required-mark">*</b></span><input required aria-required="true" inputMode="numeric" placeholder="000.000.000-00" value={document} onChange={(e) => setDocument(e.target.value)} /></label>
            <label><span>Grupo <b className="required-mark">*</b></span>
              <select required aria-required="true" value={category} onChange={(e) => setCategory(e.target.value as CollaboratorCategory)}>
                {CATEGORIES.map(([value, text]) => <option key={value} value={value}>{text}</option>)}
              </select>
            </label>
            <label>Email<input type="email" placeholder="email@exemplo.com" value={contactEmail} onChange={(e) => setContactEmail(e.target.value)} /></label>
            <label><span>WhatsApp <b className="required-mark">*</b></span><input required aria-required="true" type="tel" inputMode="numeric" placeholder="(85) 99999-9999" value={contactWhatsapp} onChange={(e) => setContactWhatsapp(formatPhone(e.target.value))} /></label>
            <label>Telefone<input type="tel" inputMode="numeric" placeholder="(85) 3333-3333" value={contactPhone} onChange={(e) => setContactPhone(formatPhone(e.target.value))} /></label>
          </div>
          <p className="required-hint">
            <b className="required-mark">*</b> Obrigatório. O acesso ao app é opcional e criado depois, na lista.
          </p>
          <div className="admin-actions form-submit">
            <button className="primary-button" disabled={busy} onClick={() => void save()}>
              {!editingId && <UserPlus size={17} />}
              {busy ? "Salvando..." : editingId ? "Salvar alterações" : "Cadastrar colaborador"}
            </button>
            {editingId && <button className="text-button" disabled={busy} onClick={resetForm}>Cancelar</button>}
          </div>
          {feedback && <span className="inline-feedback">{feedback}</span>}
        </div>
      )}
    </div>
  );
}
