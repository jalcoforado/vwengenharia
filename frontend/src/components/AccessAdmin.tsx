import { useEffect, useState } from "react";
import { EllipsisVertical, KeyRound, Search, ShieldCheck, UserCog } from "lucide-react";

import { api } from "../lib/api";
import { Avatar, RowMenu, TableHead, useFormPanel, useRowMenu, useSort, type RowMenuItem } from "./AdminTable";

// Controle de acesso: todos os logins do app, com perfil, senha provisoria e bloqueio.

type AccessRecord = {
  membership_id: string;
  name: string;
  email: string;
  role: string;
  is_active: boolean;
  must_change_password: boolean;
  kind: "COLLABORATOR" | "RESPONSIBLE" | "UNLINKED";
  linked_id: string | null;
  linked_name: string | null;
  linked_active: boolean | null;
};

type CollaboratorOption = {
  id: string;
  name: string;
  category: string;
  contact_email: string | null;
  is_active: boolean;
  membership_id: string | null;
};

type ResponsibleOption = { id: string; name: string; contact_email: string | null; is_active: boolean };

const ROLE_LABELS: Record<string, string> = {
  SUPERADMIN: "Superadministrador",
  ADMIN: "Administrador",
  GESTOR: "Gestor",
  SUPERVISOR: "Supervisor",
  TECNICO: "Técnico",
  MANUTENCAO: "Manutenção",
  CLIENTE: "Cliente (portal)",
};

// Perfis que um administrador pode conceder a um colaborador.
const INTERNAL_ROLES = ["TECNICO", "MANUTENCAO", "SUPERVISOR", "GESTOR", "ADMIN"];

const ROLE_SUMMARY: [string, string][] = [
  ["Administrador", "Tudo o que o gestor faz, mais colaboradores, acessos, chaves de integração e migração histórica."],
  ["Gestor", "Cadastros, planejamento e revisão de visitas, ordens de serviço, materiais, painéis e auditoria."],
  ["Supervisor", "Acompanha a operação, revisa visitas, agenda e ordens de serviço. Não vê auditoria nem acessos."],
  ["Técnico", "Sua própria agenda: executa visitas, checklist, medições, evidências e ocorrências, inclusive offline."],
  ["Manutenção", "As ordens de serviço atribuídas a ele e os registros de manutenção."],
  ["Cliente (portal)", "Só o portal do cliente, e só os empreendimentos liberados para o responsável."],
];

const ERROR_MESSAGES: Record<string, string> = {
  email_already_registered: "Esse email já é usado por outro acesso.",
  cannot_change_own_membership: "Você não altera o seu próprio acesso por aqui. Para a sua senha, use Segurança da conta.",
  cannot_manage_superadmin: "Somente um superadministrador altera esse acesso.",
  cannot_assign_role: "Você não pode conceder esse perfil.",
  collaborator_inactive: "O colaborador está inativo. Reative o cadastro dele antes de liberar o acesso.",
  collaborator_already_has_credential: "Esse colaborador já tem acesso ao app.",
  client_already_has_portal_credential: "Esse responsável já tem login de portal.",
  client_role_is_fixed: "O perfil de portal não é trocado por um perfil da equipe, nem o contrário.",
};

function errorMessage(error: unknown, fallback: string): string {
  if (typeof error === "object" && error !== null && "detail" in error) {
    const detail = error.detail;
    if (typeof detail === "string" && ERROR_MESSAGES[detail]) return ERROR_MESSAGES[detail];
  }
  if (typeof error === "object" && error !== null && "status" in error && error.status === 422) {
    return "Confira os dados informados: o email precisa ser válido e a senha ter pelo menos 12 caracteres.";
  }
  return fallback;
}

// Senha provisoria facil de ditar: sem caracteres que se confundem (0/O, 1/l/I).
function generatePassword(): string {
  const alphabet = "abcdefghijkmnpqrstuvwxyzABCDEFGHJKLMNPQRSTUVWXYZ23456789";
  const values = new Uint32Array(14);
  window.crypto.getRandomValues(values);
  return Array.from(values, (value) => alphabet[value % alphabet.length]).join("");
}

type SortKey = "name" | "role" | "kind" | "status";
type FormMode = "NEW" | "ROLE" | "PASSWORD";

const SORT_COLUMNS: [SortKey, string, string][] = [
  ["name", "Nome", "collab-col-name"],
  ["role", "Perfil", "collab-col-category"],
  ["kind", "Tipo", "collab-col-contact"],
  ["status", "Situação", "collab-col-status"],
];

function kindLabel(access: AccessRecord): string {
  if (access.kind === "RESPONSIBLE") return "Portal do cliente";
  return "Equipe MW";
}

export default function AccessAdmin({
  currentMembershipId,
  responsibles,
  onChanged,
}: {
  currentMembershipId: string;
  responsibles: ResponsibleOption[];
  onChanged: () => Promise<void>;
}) {
  const [accesses, setAccesses] = useState<AccessRecord[]>([]);
  const [collaborators, setCollaborators] = useState<CollaboratorOption[]>([]);
  const [search, setSearch] = useState("");
  const [roleFilter, setRoleFilter] = useState("");
  const [statusFilter, setStatusFilter] = useState("");
  const [mode, setMode] = useState<FormMode>("NEW");
  const [targetId, setTargetId] = useState<string | null>(null);
  const [newKind, setNewKind] = useState<"COLLABORATOR" | "RESPONSIBLE">("COLLABORATOR");
  const [personId, setPersonId] = useState("");
  const [email, setEmail] = useState("");
  const [role, setRole] = useState("TECNICO");
  const [password, setPassword] = useState("");
  const [feedback, setFeedback] = useState<string | null>(null);
  const [rowFeedback, setRowFeedback] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const { sortKey, sortAsc, toggleSort, sortBy } = useSort<SortKey>("name");
  const { menu, openMenu, closeMenu } = useRowMenu();
  const panel = useFormPanel();

  async function load() {
    try {
      const [accessList, collaboratorList] = await Promise.all([
        api<AccessRecord[]>("/api/v1/accesses"),
        api<CollaboratorOption[]>("/api/v1/collaborators"),
      ]);
      setAccesses(accessList);
      setCollaborators(collaboratorList);
    } catch {
      setRowFeedback("Não foi possível carregar os acessos.");
    }
  }

  useEffect(() => {
    void load();
  }, []);

  const target = accesses.find((item) => item.membership_id === targetId) ?? null;
  const responsiblesWithLogin = new Set(
    accesses.filter((item) => item.kind === "RESPONSIBLE" && item.linked_id).map((item) => item.linked_id),
  );
  const availableCollaborators = collaborators.filter((item) => item.is_active && !item.membership_id);
  const availableResponsibles = responsibles.filter((item) => item.is_active && !responsiblesWithLogin.has(item.id));

  const term = search.trim().toLowerCase();
  const visible = accesses.filter((item) => {
    if (roleFilter && item.role !== roleFilter) return false;
    if (statusFilter === "ACTIVE" && !item.is_active) return false;
    if (statusFilter === "BLOCKED" && item.is_active) return false;
    if (!term) return true;
    return [item.name, item.email, item.linked_name, ROLE_LABELS[item.role], kindLabel(item)]
      .some((value) => (value ?? "").toLowerCase().includes(term));
  });

  const sorted = sortBy(visible, (item, key) => {
    if (key === "role") return ROLE_LABELS[item.role] ?? item.role;
    if (key === "kind") return kindLabel(item);
    if (key === "status") return item.is_active ? "0" : "1";
    return item.name;
  });

  function closeForm() {
    setTargetId(null);
    setPersonId(""); setEmail(""); setPassword(""); setRole("TECNICO");
    setFeedback(null);
    panel.hide();
  }

  function openNew() {
    setMode("NEW");
    setTargetId(null);
    setNewKind("COLLABORATOR");
    setPersonId(""); setEmail(""); setRole("TECNICO");
    setPassword(generatePassword());
    setFeedback(null);
    panel.show();
  }

  function openFor(access: AccessRecord, nextMode: "ROLE" | "PASSWORD") {
    setMode(nextMode);
    setTargetId(access.membership_id);
    setRole(access.role);
    setPassword(nextMode === "PASSWORD" ? generatePassword() : "");
    setFeedback(null);
    panel.show();
  }

  function choosePerson(id: string) {
    setPersonId(id);
    if (newKind === "COLLABORATOR") {
      const person = collaborators.find((item) => item.id === id);
      setEmail(person?.contact_email ?? "");
      setRole(person?.category === "TECNICO" ? "TECNICO" : "GESTOR");
    } else {
      setEmail(responsibles.find((item) => item.id === id)?.contact_email ?? "");
    }
  }

  async function createAccess() {
    if (!personId) return setFeedback(newKind === "COLLABORATOR" ? "Selecione o colaborador." : "Selecione o responsável.");
    if (!email.trim()) return setFeedback("Informe o email de login.");
    if (password.length < 12) return setFeedback("A senha provisória deve ter pelo menos 12 caracteres.");
    setBusy(true);
    try {
      if (newKind === "COLLABORATOR") {
        await api("/api/v1/collaborators/" + personId + "/credential", {
          method: "POST",
          body: JSON.stringify({ email: email.trim(), password, role }),
        });
      } else {
        await api("/api/v1/clients/" + personId + "/portal-credential", {
          method: "POST",
          body: JSON.stringify({ email: email.trim(), password }),
        });
      }
      setRowFeedback("Acesso criado para " + email.trim() + ". Senha provisória: " + password + ". Informe à pessoa; ela troca no primeiro acesso.");
      closeForm();
      await load();
      await onChanged();
    } catch (error) {
      setFeedback(errorMessage(error, "Não foi possível criar o acesso."));
    } finally {
      setBusy(false);
    }
  }

  async function saveRole() {
    if (!target) return;
    setBusy(true);
    try {
      await api("/api/v1/team/" + target.membership_id, { method: "PATCH", body: JSON.stringify({ role }) });
      setRowFeedback("Perfil de " + target.name + " alterado para " + (ROLE_LABELS[role] ?? role) + ". Vale a partir do próximo login.");
      closeForm();
      await load();
      await onChanged();
    } catch (error) {
      setFeedback(errorMessage(error, "Não foi possível alterar o perfil."));
    } finally {
      setBusy(false);
    }
  }

  async function resetPassword() {
    if (!target) return;
    if (password.length < 12) return setFeedback("A senha provisória deve ter pelo menos 12 caracteres.");
    setBusy(true);
    try {
      await api("/api/v1/team/" + target.membership_id + "/reset-password", {
        method: "POST",
        body: JSON.stringify({ new_password: password }),
      });
      setRowFeedback("Senha de " + target.name + " redefinida. Senha provisória: " + password + ". Informe à pessoa; ela troca no próximo acesso.");
      closeForm();
      await load();
    } catch (error) {
      setFeedback(errorMessage(error, "Não foi possível redefinir a senha."));
    } finally {
      setBusy(false);
    }
  }

  async function toggleActive(access: AccessRecord) {
    setBusy(true);
    try {
      await api("/api/v1/team/" + access.membership_id, {
        method: "PATCH",
        body: JSON.stringify({ is_active: !access.is_active }),
      });
      setRowFeedback(access.is_active ? "Acesso de " + access.name + " bloqueado." : "Acesso de " + access.name + " reativado.");
      await load();
      await onChanged();
    } catch (error) {
      setRowFeedback(errorMessage(error, "Não foi possível alterar o acesso."));
    } finally {
      setBusy(false);
    }
  }

  function summary(access: AccessRecord): string {
    return [
      access.email,
      access.kind === "COLLABORATOR" ? "Colaborador: " + access.linked_name
        : access.kind === "RESPONSIBLE" ? "Responsável: " + access.linked_name
          : "Sem cadastro ligado",
      access.must_change_password ? "Senha provisória" : null,
    ].filter(Boolean).join(" · ");
  }

  const menuAccess = menu ? accesses.find((item) => item.membership_id === menu.id) : undefined;
  const menuIsSelf = menuAccess?.membership_id === currentMembershipId;
  const menuItems: RowMenuItem[] = menuAccess && !menuIsSelf
    ? [
        { text: "Redefinir senha", run: () => openFor(menuAccess, "PASSWORD") },
        ...(menuAccess.role === "CLIENTE" ? [] : [{ text: "Alterar perfil", run: () => openFor(menuAccess, "ROLE") }]),
        { text: menuAccess.is_active ? "Bloquear acesso" : "Reativar acesso", run: () => void toggleActive(menuAccess), danger: menuAccess.is_active },
      ]
    : [];

  return (
    <section className="section-card admin-hub">
      <div className="section-heading admin-heading">
        <div>
          <span className="eyebrow">Controle de acesso</span>
          <h2>Acessos ao app</h2>
          <p className="section-copy">
            Quem entra no app, com qual login e qual perfil. Só tem acesso quem está cadastrado como colaborador ou como responsável.
          </p>
        </div>
        <div className="admin-summary">
          <span><strong>{accesses.filter((item) => item.is_active).length}</strong> ativos</span>
          <span><strong>{accesses.filter((item) => !item.is_active).length}</strong> bloqueados</span>
          <span><strong>{accesses.filter((item) => item.must_change_password).length}</strong> com senha provisória</span>
        </div>
      </div>

      <div className="admin-stack">
        {panel.open && mode === "NEW" && (
          <div className="compact-form admin-create-form" ref={panel.ref}>
            <h3 className="form-title"><ShieldCheck size={17} />Novo acesso</h3>
            <div className="compact-form-grid">
              <label><span>Para quem <b className="required-mark">*</b></span>
                <select value={newKind} onChange={(e) => { setNewKind(e.target.value as typeof newKind); setPersonId(""); setEmail(""); }}>
                  <option value="COLLABORATOR">Colaborador da MW</option>
                  <option value="RESPONSIBLE">Responsável (portal do cliente)</option>
                </select>
              </label>
              <label><span>{newKind === "COLLABORATOR" ? "Colaborador" : "Responsável"} <b className="required-mark">*</b></span>
                <select required aria-required="true" value={personId} onChange={(e) => choosePerson(e.target.value)}>
                  <option value="">{(newKind === "COLLABORATOR" ? availableCollaborators : availableResponsibles).length ? "Selecione" : "Ninguém sem acesso"}</option>
                  {(newKind === "COLLABORATOR" ? availableCollaborators : availableResponsibles).map((item) => (
                    <option key={item.id} value={item.id}>{item.name}</option>
                  ))}
                </select>
              </label>
              <label><span>Login (email) <b className="required-mark">*</b></span><input required aria-required="true" type="email" placeholder="email@exemplo.com" value={email} onChange={(e) => setEmail(e.target.value)} /></label>
              {newKind === "COLLABORATOR" ? (
                <label><span>Perfil <b className="required-mark">*</b></span>
                  <select value={role} onChange={(e) => setRole(e.target.value)}>
                    {INTERNAL_ROLES.map((value) => <option key={value} value={value}>{ROLE_LABELS[value]}</option>)}
                  </select>
                </label>
              ) : (
                <label>Perfil<input value="Cliente (portal)" readOnly /></label>
              )}
              <label className="form-span-2"><span>Senha provisória <b className="required-mark">*</b></span><input required aria-required="true" autoComplete="off" spellCheck={false} value={password} onChange={(e) => setPassword(e.target.value)} /></label>
            </div>
            <p className="required-hint">
              <b className="required-mark">*</b> Obrigatório. A lista só traz quem já está cadastrado e ainda não tem acesso. A pessoa é obrigada a trocar a senha provisória no primeiro login.
            </p>
            <div className="admin-actions form-submit">
              <button className="primary-button" disabled={busy} onClick={() => void createAccess()}><ShieldCheck size={17} />{busy ? "Criando..." : "Criar acesso"}</button>
              <button className="secondary-button" type="button" disabled={busy} onClick={() => setPassword(generatePassword())}>Gerar outra senha</button>
              <button className="text-button" disabled={busy} onClick={closeForm}>Fechar</button>
            </div>
            {feedback && <span className="inline-feedback">{feedback}</span>}
          </div>
        )}
        {panel.open && mode === "ROLE" && target && (
          <div className="compact-form admin-create-form" ref={panel.ref}>
            <h3 className="form-title"><UserCog size={17} />Alterar perfil de {target.name}</h3>
            <div className="compact-form-grid">
              <label>Login<input value={target.email} readOnly /></label>
              <label><span>Perfil <b className="required-mark">*</b></span>
                <select value={role} onChange={(e) => setRole(e.target.value)}>
                  {INTERNAL_ROLES.map((value) => <option key={value} value={value}>{ROLE_LABELS[value]}</option>)}
                  {!INTERNAL_ROLES.includes(role) && <option value={role}>{ROLE_LABELS[role] ?? role}</option>}
                </select>
              </label>
            </div>
            <p className="required-hint">O novo perfil vale a partir do próximo login da pessoa. Veja abaixo o que cada perfil pode fazer.</p>
            <div className="admin-actions form-submit">
              <button className="primary-button" disabled={busy || role === target.role} onClick={() => void saveRole()}>{busy ? "Salvando..." : "Salvar perfil"}</button>
              <button className="text-button" disabled={busy} onClick={closeForm}>Cancelar</button>
            </div>
            {feedback && <span className="inline-feedback">{feedback}</span>}
          </div>
        )}
        {panel.open && mode === "PASSWORD" && target && (
          <div className="compact-form admin-create-form" ref={panel.ref}>
            <h3 className="form-title"><KeyRound size={17} />Redefinir senha de {target.name}</h3>
            <div className="compact-form-grid">
              <label>Login<input value={target.email} readOnly /></label>
              <label className="form-span-2"><span>Senha provisória <b className="required-mark">*</b></span><input required aria-required="true" autoComplete="off" spellCheck={false} value={password} onChange={(e) => setPassword(e.target.value)} /></label>
            </div>
            <p className="required-hint">
              A senha atual deixa de valer na hora e as sessões abertas são encerradas. Informe a senha provisória à pessoa: ela será obrigada a trocá-la ao entrar.
            </p>
            <div className="admin-actions form-submit">
              <button className="primary-button" disabled={busy} onClick={() => void resetPassword()}><KeyRound size={17} />{busy ? "Redefinindo..." : "Redefinir senha"}</button>
              <button className="secondary-button" type="button" disabled={busy} onClick={() => setPassword(generatePassword())}>Gerar outra senha</button>
              <button className="text-button" disabled={busy} onClick={closeForm}>Cancelar</button>
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
                placeholder="Buscar nome, login ou perfil"
                aria-label="Buscar acesso"
              />
            </label>
            <select className="admin-toolbar-select" aria-label="Filtrar por perfil" value={roleFilter} onChange={(e) => setRoleFilter(e.target.value)}>
              <option value="">Todos os perfis</option>
              {Object.entries(ROLE_LABELS).filter(([value]) => accesses.some((item) => item.role === value)).map(([value, text]) => (
                <option key={value} value={value}>{text}</option>
              ))}
            </select>
            <select className="admin-toolbar-select" aria-label="Filtrar por situação" value={statusFilter} onChange={(e) => setStatusFilter(e.target.value)}>
              <option value="">Todas as situações</option>
              <option value="ACTIVE">Ativos</option>
              <option value="BLOCKED">Bloqueados</option>
            </select>
            {!panel.open && (
              <button className="primary-button" disabled={busy} onClick={openNew}><ShieldCheck size={17} /> Novo acesso</button>
            )}
          </div>
          {rowFeedback && <span className="inline-feedback" role="status">{rowFeedback}</span>}
          <div className="admin-list collab-table collab-table-wide" role="table" aria-label="Acessos ao app">
            <TableHead columns={SORT_COLUMNS} sortKey={sortKey} sortAsc={sortAsc} onSort={toggleSort} />
            {sorted.map((access) => {
              const isSelf = access.membership_id === currentMembershipId;
              return (
                <div className="client-entry" key={access.membership_id}>
                  <div className={access.is_active ? "collab-row" : "collab-row collab-row-inactive"} role="row">
                    <div className="collab-person" role="cell">
                      <Avatar name={access.name} />
                      <div>
                        <strong>{access.name}{isSelf ? " (você)" : ""}</strong>
                        <span title={summary(access)}>{summary(access)}</span>
                      </div>
                    </div>
                    <div className="collab-col-category" role="cell">
                      <span className="collab-chip">{ROLE_LABELS[access.role] ?? access.role}</span>
                    </div>
                    <div className="collab-col-contact" role="cell">{kindLabel(access)}</div>
                    <div className="collab-col-status" role="cell">
                      <span className={access.is_active ? "collab-status active" : "collab-status"}>{access.is_active ? "Ativo" : "Bloqueado"}</span>
                    </div>
                    <div className="collab-actions" role="cell">
                      {!isSelf && (
                        <>
                          <button className="icon-action" disabled={busy} title="Redefinir senha" aria-label={"Redefinir senha: " + access.name} onClick={() => openFor(access, "PASSWORD")}>
                            <KeyRound size={16} />
                          </button>
                          {access.role !== "CLIENTE" && (
                            <button className="icon-action icon-action-edit" disabled={busy} title="Alterar perfil" aria-label={"Alterar perfil: " + access.name} onClick={() => openFor(access, "ROLE")}>
                              <UserCog size={16} />
                            </button>
                          )}
                          <button
                            className="icon-action row-menu-trigger"
                            disabled={busy}
                            title="Mais ações"
                            aria-label={"Mais ações: " + access.name}
                            aria-haspopup="menu"
                            aria-expanded={menu?.id === access.membership_id}
                            onClick={(event) => openMenu(access.membership_id, event.currentTarget)}
                          >
                            <EllipsisVertical size={16} />
                          </button>
                        </>
                      )}
                    </div>
                  </div>
                </div>
              );
            })}
            {accesses.length > 0 && visible.length === 0 && (
              <div className="empty-state">Nenhum acesso encontrado com esse filtro. Limpe a busca ou escolha outro perfil.</div>
            )}
          </div>
          {menu && menuAccess && menuItems.length > 0 && <RowMenu menu={menu} items={menuItems} busy={busy} onClose={closeMenu} />}
        </div>

        <details className="role-reference">
          <summary>O que cada perfil pode fazer</summary>
          <dl>
            {ROLE_SUMMARY.map(([name, text]) => (
              <div key={name}>
                <dt>{name}</dt>
                <dd>{text}</dd>
              </div>
            ))}
          </dl>
        </details>
      </div>
    </section>
  );
}
