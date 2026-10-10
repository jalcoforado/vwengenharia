import { useState } from "react";

import { api } from "../lib/api";
import mwLogo from "../assets/mw-logo.png";

// Tela obrigatoria para quem entrou com senha provisoria: o app so abre depois da troca.
export default function ForcePasswordChange({
  email,
  onDone,
  onCancel,
}: {
  email: string;
  onDone: () => void;
  onCancel: () => void;
}) {
  const [currentPassword, setCurrentPassword] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  async function submit(event: React.FormEvent) {
    event.preventDefault();
    if (newPassword.length < 12) return setError("A nova senha deve ter pelo menos 12 caracteres.");
    if (newPassword === currentPassword) return setError("A nova senha deve ser diferente da provisória.");
    if (newPassword !== confirmPassword) return setError("A confirmação não confere com a nova senha.");
    setBusy(true);
    setError("");
    try {
      await api("/api/v1/auth/change-password", {
        method: "POST",
        body: JSON.stringify({ current_password: currentPassword, new_password: newPassword }),
      });
      onDone();
    } catch (failure) {
      const status =
        typeof failure === "object" && failure !== null && "status" in failure ? Number(failure.status) : 0;
      setError(
        status === 0
          ? "Sem conexão com o servidor. Tente de novo quando houver sinal."
          : "Não foi possível trocar a senha. Confira a senha provisória.",
      );
    } finally {
      setBusy(false);
    }
  }

  return (
    <main className="login-page">
      <section className="login-card">
        <img className="login-logo" src={mwLogo} alt="MW Engenharia" />
        <h1>Crie a sua senha</h1>
        <p>
          Você entrou com uma senha provisória. Para usar o app, escolha uma senha só sua. Depois da troca, entre de novo com ela.
        </p>
        <form onSubmit={submit}>
          <label>
            Login
            <input type="email" value={email} readOnly autoComplete="username" />
          </label>
          <label>
            Senha provisória
            <input
              type="password"
              autoComplete="current-password"
              required
              value={currentPassword}
              onChange={(event) => setCurrentPassword(event.target.value)}
            />
          </label>
          <label>
            Nova senha (mínimo de 12 caracteres)
            <input
              type="password"
              autoComplete="new-password"
              required
              value={newPassword}
              onChange={(event) => setNewPassword(event.target.value)}
            />
          </label>
          <label>
            Repita a nova senha
            <input
              type="password"
              autoComplete="new-password"
              required
              value={confirmPassword}
              onChange={(event) => setConfirmPassword(event.target.value)}
            />
          </label>
          {error && <span className="form-error" role="alert">{error}</span>}
          <button className="primary-button" disabled={busy} type="submit">
            {busy ? "Salvando..." : "Salvar nova senha"}
          </button>
          <button className="text-button" type="button" disabled={busy} onClick={onCancel}>
            Sair
          </button>
        </form>
      </section>
    </main>
  );
}
