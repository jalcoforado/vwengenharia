import { useEffect, useState } from "react";
import { Search } from "lucide-react";

import { api } from "../lib/api";
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
  ["TECNICO", "Tecnico"],
];

const ACCESS_ROLES: [string, string][] = [
  ["TECNICO", "Tecnico"],
  ["MANUTENCAO", "Manutencao"],
  ["SUPERVISOR", "Supervisor"],
  ["GESTOR", "Gestor"],
  ["ADMIN", "Administrador"],
];

const ERROR_MESSAGES: Record<string, string> = {
  collaborator_document_already_exists: "Ja existe um colaborador com esse CPF.",
  email_already_registered: "Esse email ja e usado por outro acesso.",
  cannot_change_own_membership: "Voce nao pode inativar o seu proprio cadastro.",
  cannot_manage_superadmin: "Somente um superadministrador altera esse cadastro.",
  cannot_assign_role: "Voce nao pode conceder esse perfil.",
  collaborator_inactive: "Reative o colaborador antes de liberar o acesso.",
  collaborator_already_has_credential: "Esse colaborador ja tem acesso ao app.",
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

export default function CollaboratorAdmin({
  canManage,
  onChanged,
}: {
  canManage: boolean;
  onChanged: () => Promise<void>;
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

  async function load() {
    try {
      setCollaborators(await api<CollaboratorRecord[]>("/api/v1/collaborators"));
    } catch {
      setRowFeedback("Nao foi possivel carregar os colaboradores.");
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
      return setFeedback("CPF invalido. Confira os numeros digitados.");
    }
    if (contactPhone.trim() && !isCompletePhone(contactPhone)) {
      return setFeedback("Telefone incompleto. Informe DDD e numero.");
    }
    if (contactWhatsapp.trim() && !isCompletePhone(contactWhatsapp)) {
      return setFeedback("WhatsApp incompleto. Informe DDD e numero.");
    }
    setBusy(true);
    try {
      await api(editingId ? "/api/v1/collaborators/" + editingId : "/api/v1/collaborators", {
        method: editingId ? "PATCH" : "POST",
        body: JSON.stringify({
          name: name.trim(),
          document: normalizeDocument(document),
          category,
          contact_phone: contactPhone.trim() || null,
          contact_whatsapp: contactWhatsapp.trim() || null,
          contact_email: contactEmail.trim() || null,
        }),
      });
      setFeedback(editingId ? "Colaborador atualizado." : "Colaborador cadastrado. Ele ainda nao tem acesso ao app.");
      resetForm();
      await load();
    } catch (error) {
      setFeedback(errorMessage(error, "Nao foi possivel salvar o colaborador."));
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
          : "Colaborador reativado. O acesso ao app continua bloqueado ate ser reativado.",
      );
      await load();
      await onChanged();
    } catch (error) {
      setRowFeedback(errorMessage(error, "Nao foi possivel alterar o colaborador."));
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
      setRowFeedback(errorMessage(error, "Nao foi possivel alterar o acesso."));
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
      setRowFeedback(errorMessage(error, "Nao foi possivel criar o acesso."));
    } finally {
      setBusy(false);
    }
  }

  function accessSummary(item: CollaboratorRecord): string {
    if (!item.membership_id) return "Sem acesso ao app";
    const role = label(ACCESS_ROLES, item.credential_role);
    return item.credential_active
      ? "Acesso: " + role + " (" + item.credential_email + ")"
      : "Acesso bloqueado (" + item.credential_email + ")";
  }

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
        <div className="admin-list">
          {visible.map((item) => (
            <div className="client-entry" key={item.id}>
              <div className="admin-row">
                <div>
                  <strong>{item.name}</strong>
                  <span>
                    {[
                      label(CATEGORIES, item.category),
                      formatPhone(item.contact_whatsapp || item.contact_phone),
                      accessSummary(item),
                    ].filter(Boolean).join(" · ")}
                  </span>
                </div>
                <div className="admin-actions">
                  <span className={item.is_active ? "status status-revisada" : "status"}>{item.is_active ? "Ativo" : "Inativo"}</span>
                  {canManage && item.is_active && !item.membership_id && (
                    <button className="text-button" disabled={busy} onClick={() => openAccess(item)}>
                      {accessId === item.id ? "Fechar" : "Criar acesso"}
                    </button>
                  )}
                  {canManage && item.is_active && item.membership_id && (
                    <button className="text-button" disabled={busy} onClick={() => void toggleAccess(item)}>
                      {item.credential_active ? "Bloquear acesso" : "Reativar acesso"}
                    </button>
                  )}
                  {canManage && (
                    <button className="text-button" disabled={busy} onClick={() => startEdit(item)}>Editar</button>
                  )}
                  {canManage && (
                    <button className="text-button" disabled={busy} onClick={() => void toggleActive(item)}>
                      {item.is_active ? "Inativar" : "Reativar"}
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
          ))}
          {collaborators.length === 0 && (
            <div className="empty-state">Nenhum colaborador cadastrado.</div>
          )}
          {collaborators.length > 0 && visible.length === 0 && (
            <div className="empty-state">
              Nenhum colaborador encontrado para "{search.trim()}". Confira a grafia ou limpe a busca.
            </div>
          )}
        </div>
        {rowFeedback && <span className="inline-feedback">{rowFeedback}</span>}
        {!canManage && (
          <span className="required-hint">Somente administradores cadastram colaboradores e liberam acessos.</span>
        )}
      </div>
      {canManage && (
        <div className="compact-form admin-create-form">
          <h3>{editingId ? "Editar colaborador" : "Novo colaborador"}</h3>
          <div className="compact-form-grid">
            <label><span>Nome <b className="required-mark">*</b></span><input required aria-required="true" value={name} onChange={(e) => setName(e.target.value)} /></label>
            <label><span>CPF <b className="required-mark">*</b></span><input required aria-required="true" value={document} onChange={(e) => setDocument(e.target.value)} /></label>
            <label><span>Grupo <b className="required-mark">*</b></span>
              <select required aria-required="true" value={category} onChange={(e) => setCategory(e.target.value as CollaboratorCategory)}>
                {CATEGORIES.map(([value, text]) => <option key={value} value={value}>{text}</option>)}
              </select>
            </label>
            <label>Email<input type="email" value={contactEmail} onChange={(e) => setContactEmail(e.target.value)} /></label>
            <label>Telefone<input type="tel" inputMode="numeric" placeholder="(85) 3333-3333" value={contactPhone} onChange={(e) => setContactPhone(formatPhone(e.target.value))} /></label>
            <label>WhatsApp<input type="tel" inputMode="numeric" placeholder="(85) 99999-9999" value={contactWhatsapp} onChange={(e) => setContactWhatsapp(formatPhone(e.target.value))} /></label>
          </div>
          <p className="required-hint">
            <b className="required-mark">*</b> Obrigatorio. O acesso ao app e opcional e criado depois, na lista.
          </p>
          <div className="admin-actions">
            <button className="small-button" disabled={busy} onClick={() => void save()}>
              {busy ? "Salvando..." : editingId ? "Salvar alteracoes" : "Cadastrar colaborador"}
            </button>
            {editingId && <button className="text-button" disabled={busy} onClick={resetForm}>Cancelar</button>}
          </div>
          {feedback && <span className="inline-feedback">{feedback}</span>}
        </div>
      )}
    </div>
  );
}
