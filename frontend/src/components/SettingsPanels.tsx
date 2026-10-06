import { useEffect, useState } from "react";

import { api } from "../lib/api";

type IntegrationKey = {
  id: string;
  name: string;
  key_prefix: string;
  created_at: string;
  last_used_at: string | null;
  revoked_at: string | null;
};

type IntegrationKeyCreated = IntegrationKey & {
  secret: string;
};

export function AccountSettings() {
  const [currentPassword, setCurrentPassword] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [busy, setBusy] = useState(false);
  const [feedback, setFeedback] = useState<string | null>(null);

  async function changePassword() {
    if (newPassword.length < 12) {
      setFeedback("A nova senha deve ter pelo menos 12 caracteres.");
      return;
    }
    if (newPassword !== confirmPassword) {
      setFeedback("A confirmacao da nova senha nao confere.");
      return;
    }
    setBusy(true);
    try {
      await api("/api/v1/auth/change-password", {
        method: "POST",
        body: JSON.stringify({
          current_password: currentPassword,
          new_password: newPassword,
        }),
      });
      setCurrentPassword("");
      setNewPassword("");
      setConfirmPassword("");
      setFeedback("Senha alterada. Outras sessoes foram revogadas.");
    } catch {
      setFeedback("Nao foi possivel alterar a senha. Confira a senha atual.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className="section-card">
      <span className="eyebrow">Conta</span>
      <h2>Seguranca da conta</h2>
      <div className="compact-form settings-form">
        <div className="compact-form-grid">
          <label>
            Senha atual
            <input
              type="password"
              autoComplete="current-password"
              value={currentPassword}
              onChange={(event) => setCurrentPassword(event.target.value)}
            />
          </label>
          <label>
            Nova senha
            <input
              type="password"
              autoComplete="new-password"
              value={newPassword}
              onChange={(event) => setNewPassword(event.target.value)}
            />
          </label>
          <label>
            Confirmar nova senha
            <input
              type="password"
              autoComplete="new-password"
              value={confirmPassword}
              onChange={(event) => setConfirmPassword(event.target.value)}
            />
          </label>
        </div>
        <button
          className="small-button"
          disabled={busy || !currentPassword || !newPassword || !confirmPassword}
          onClick={() => void changePassword()}
        >
          {busy ? "Alterando..." : "Alterar senha"}
        </button>
        {feedback && <span className="inline-feedback">{feedback}</span>}
      </div>
    </section>
  );
}

export function IntegrationSettings() {
  const [keys, setKeys] = useState<IntegrationKey[]>([]);
  const [name, setName] = useState("iAnalisys");
  const [newSecret, setNewSecret] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [feedback, setFeedback] = useState<string | null>(null);

  async function load() {
    try {
      setKeys(await api<IntegrationKey[]>("/api/v1/integration-keys"));
    } catch {
      setFeedback("Nao foi possivel carregar as chaves de integracao.");
    }
  }

  useEffect(() => {
    void load();
  }, []);

  async function createKey() {
    if (name.trim().length < 2) {
      setFeedback("Informe um nome para a integracao.");
      return;
    }
    setBusy(true);
    try {
      const created = await api<IntegrationKeyCreated>("/api/v1/integration-keys", {
        method: "POST",
        body: JSON.stringify({ name: name.trim() }),
      });
      setNewSecret(created.secret);
      setFeedback("Chave criada. Copie o segredo agora: ele nao sera exibido novamente.");
      await load();
    } catch {
      setFeedback("Nao foi possivel criar a chave. O nome pode ja estar em uso.");
    } finally {
      setBusy(false);
    }
  }

  async function revoke(key: IntegrationKey) {
    setBusy(true);
    try {
      await api("/api/v1/integration-keys/" + key.id + "/revoke", {
        method: "POST",
      });
      setFeedback("Chave revogada.");
      if (newSecret?.startsWith(key.key_prefix)) setNewSecret(null);
      await load();
    } catch {
      setFeedback("Nao foi possivel revogar a chave.");
    } finally {
      setBusy(false);
    }
  }

  async function copySecret() {
    if (!newSecret) return;
    try {
      await navigator.clipboard.writeText(newSecret);
      setFeedback("Segredo copiado para a area de transferencia.");
    } catch {
      setFeedback("Copie o segredo manualmente.");
    }
  }

  return (
    <section className="section-card">
      <div className="section-heading">
        <div>
          <span className="eyebrow">Integracao</span>
          <h2>iAnalisys</h2>
          <p className="section-copy">
            Credenciais read-only por tenant para sincronizacao segura com o iAnalisys.
          </p>
        </div>
      </div>

      {newSecret && (
        <div className="secret-once">
          <strong>Segredo exibido uma unica vez</strong>
          <code>{newSecret}</code>
          <button className="small-button" onClick={() => void copySecret()}>
            Copiar segredo
          </button>
        </div>
      )}

      <div className="integration-create">
        <label>
          Nome da integracao
          <input value={name} onChange={(event) => setName(event.target.value)} />
        </label>
        <button className="small-button" disabled={busy} onClick={() => void createKey()}>
          Criar chave
        </button>
      </div>

      <div className="audit-list">
        {keys.map((key) => (
          <div className="audit-row" key={key.id}>
            <div>
              <strong>{key.name}</strong>
              <span>
                Prefixo {key.key_prefix} · criada{" "}
                {new Intl.DateTimeFormat("pt-BR", { dateStyle: "short" }).format(
                  new Date(key.created_at),
                )}
              </span>
            </div>
            <div className="integration-key-actions">
              <span className={key.revoked_at ? "status" : "status status-revisada"}>
                {key.revoked_at ? "Revogada" : "Ativa"}
              </span>
              {!key.revoked_at && (
                <button className="text-button" disabled={busy} onClick={() => void revoke(key)}>
                  Revogar
                </button>
              )}
            </div>
          </div>
        ))}
        {keys.length === 0 && (
          <div className="empty-state">Nenhuma chave de integracao criada.</div>
        )}
      </div>

      {feedback && <span className="inline-feedback">{feedback}</span>}
    </section>
  );
}
