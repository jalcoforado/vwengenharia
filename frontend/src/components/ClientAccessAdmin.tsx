import { useEffect, useMemo, useState } from "react";
import { Link2 } from "lucide-react";

import { api } from "../lib/api";
import type { ClientRecord } from "./OperationalAdmin";

type TeamMember = {
  membership_id: string;
  name: string;
  email: string;
  role: string;
  is_active: boolean;
};

type ClientAccess = {
  id: string;
  membership_id: string;
  client_id: string;
};

export default function ClientAccessAdmin({
  clients,
  team,
}: {
  clients: ClientRecord[];
  team: TeamMember[];
}) {
  const [accesses, setAccesses] = useState<ClientAccess[]>([]);
  const [membershipId, setMembershipId] = useState("");
  const [clientId, setClientId] = useState("");
  const [feedback, setFeedback] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const clientUsers = useMemo(
    () => team.filter((item) => item.is_active && item.role === "CLIENTE"),
    [team],
  );
  const clientMap = new Map(clients.map((item) => [item.id, item]));
  const memberMap = new Map(team.map((item) => [item.membership_id, item]));

  async function load() {
    try {
      setAccesses(await api<ClientAccess[]>("/api/v1/client-access"));
    } catch {
      setFeedback("Nao foi possivel carregar os acessos de clientes.");
    }
  }

  useEffect(() => {
    void load();
  }, []);

  async function grant() {
    if (!membershipId || !clientId) {
      setFeedback("Selecione o usuario cliente e o cliente.");
      return;
    }
    setBusy(true);
    try {
      await api("/api/v1/client-access", {
        method: "POST",
        body: JSON.stringify({
          membership_id: membershipId,
          client_id: clientId,
        }),
      });
      setFeedback("Acesso do portal vinculado.");
      setMembershipId("");
      setClientId("");
      await load();
    } catch {
      setFeedback("Nao foi possivel vincular o acesso.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className="section-card">
      <div className="section-heading">
        <div>
          <span className="eyebrow">Portal do cliente</span>
          <h2>Acessos externos</h2>
          <p className="section-copy">
            Vincule cada usuario CLIENTE apenas aos contratos que ele pode visualizar.
          </p>
        </div>
      </div>

      <div className="client-access-form">
        <label>
          Usuario cliente
          <select value={membershipId} onChange={(event) => setMembershipId(event.target.value)}>
            <option value="">Selecione</option>
            {clientUsers.map((member) => (
              <option key={member.membership_id} value={member.membership_id}>
                {member.name} · {member.email}
              </option>
            ))}
          </select>
        </label>
        <label>
          Cliente
          <select value={clientId} onChange={(event) => setClientId(event.target.value)}>
            <option value="">Selecione</option>
            {clients.filter((item) => item.is_active).map((client) => (
              <option key={client.id} value={client.id}>{client.name}</option>
            ))}
          </select>
        </label>
        <button className="primary-button" disabled={busy} onClick={() => void grant()}>
          <Link2 size={16} />
          {busy ? "Vinculando..." : "Vincular acesso"}
        </button>
      </div>

      {clientUsers.length === 0 && (
        <div className="empty-state">
          <strong>Nenhum usuario CLIENTE cadastrado</strong>
          <span>Crie um membro com perfil Cliente antes de conceder acesso ao portal.</span>
        </div>
      )}

      {accesses.length > 0 && (
        <div className="admin-list client-access-list">
          {accesses.map((item) => (
            <div className="admin-row" key={item.id}>
              <div>
                <strong>{memberMap.get(item.membership_id)?.name ?? "Usuario cliente"}</strong>
                <span>{memberMap.get(item.membership_id)?.email ?? item.membership_id}</span>
              </div>
              <span className="status status-revisada">
                {clientMap.get(item.client_id)?.name ?? "Cliente"}
              </span>
            </div>
          ))}
        </div>
      )}

      {feedback && <span className="inline-feedback">{feedback}</span>}
    </section>
  );
}
