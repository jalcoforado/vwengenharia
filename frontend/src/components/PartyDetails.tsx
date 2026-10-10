import { useEffect, useState } from "react";

import { api } from "../lib/api";
import type { ContractingPartyRecord } from "./ContractingPartyAdmin";
import { Field } from "./DevelopmentDetails";
import { formatDocument } from "../lib/document";
import { formatPhone } from "../lib/phone";

// Consultas somente leitura do contratante e do responsavel, com os empreendimentos de cada um.

type ListedDevelopment = {
  id: string;
  client_id: string;
  contracting_party_id: string | null;
  name: string;
  development_type: string | null;
  city: string | null;
  state: string | null;
  is_active: boolean;
};

type ListedClient = { id: string; name: string };

const SCOPE_LABELS: Record<string, string> = {
  GERAL: "Geral",
  TECNICO: "Técnico",
  FINANCEIRO: "Financeiro",
  COMERCIAL: "Comercial",
  ADMINISTRATIVO: "Administrativo",
};

function contractingPartyLabel(party: ContractingPartyRecord): string {
  return party.trade_name || party.name;
}

function place(development: ListedDevelopment): string {
  return [development.development_type, [development.city, development.state].filter(Boolean).join("/")]
    .filter(Boolean)
    .join(" · ");
}

export function ContractingPartyDetails({
  party,
  developments,
  clients,
}: {
  party: ContractingPartyRecord;
  developments: ListedDevelopment[];
  clients: ListedClient[];
}) {
  const clientMap = new Map(clients.map((item) => [item.id, item]));
  const contracted = developments
    .filter((item) => item.contracting_party_id === party.id)
    .sort((a, b) => a.name.localeCompare(b.name, "pt-BR"));

  return (
    <div className="client-contacts development-details">
      <section>
        <span className="eyebrow">Contratante</span>
        <dl className="detail-grid">
          <Field label="Tipo de pessoa" value={party.person_type === "PJ" ? "Pessoa jurídica" : "Pessoa física"} />
          <Field label={party.person_type === "PJ" ? "Razão social" : "Nome completo"} value={party.name} />
          <Field label={party.person_type === "PJ" ? "Nome fantasia" : "Nome de exibição"} value={party.trade_name} />
          <Field label={party.person_type === "PJ" ? "CNPJ" : "CPF"} value={formatDocument(party.document)} />
          <Field label="Telefone" value={formatPhone(party.contact_phone)} />
          <Field label="Email" value={party.contact_email} />
        </dl>
      </section>

      <section>
        <span className="eyebrow">Empreendimentos contratados</span>
        {contracted.length === 0 && (
          <p className="detail-note">
            Nenhum empreendimento ligado a este contratante. A ligação é feita no cadastro do empreendimento, no campo Contratante.
          </p>
        )}
        {contracted.map((development) => (
          <div className="client-contact-row" key={development.id}>
            <div>
              <strong>{development.name}</strong>
              <span>
                {[
                  place(development),
                  "Responsável principal: " + (clientMap.get(development.client_id)?.name ?? "não encontrado"),
                ].filter(Boolean).join(" · ")}
              </span>
            </div>
            <div className="admin-actions">
              <span className={development.is_active ? "status status-revisada" : "status"}>{development.is_active ? "Ativo" : "Inativo"}</span>
            </div>
          </div>
        ))}
      </section>
    </div>
  );
}

type ResponsibleClient = {
  id: string;
  name: string;
  document: string | null;
  contact_name: string | null;
  contact_role: string | null;
  contact_phone: string | null;
  contact_whatsapp: string | null;
  contact_email: string | null;
};

type ResponsibleContact = {
  id: string;
  development_id: string;
  scope: string;
  is_primary: boolean;
  portal_access: boolean;
  is_active: boolean;
};

export function ResponsibleDetails({
  client,
  developments,
  parties,
  showPortalLogin,
}: {
  client: ResponsibleClient;
  developments: ListedDevelopment[];
  parties: ContractingPartyRecord[];
  showPortalLogin: boolean;
}) {
  const [contacts, setContacts] = useState<ResponsibleContact[] | null>(null);
  const [failed, setFailed] = useState(false);
  const [portalLogin, setPortalLogin] = useState<string | null | undefined>(undefined);

  useEffect(() => {
    let current = true;
    setContacts(null);
    setFailed(false);
    setPortalLogin(undefined);
    api<ResponsibleContact[]>("/api/v1/client-contacts?limit=500&client_id=" + client.id)
      .then((items) => { if (current) setContacts(items); })
      .catch(() => { if (current) setFailed(true); });
    if (showPortalLogin) {
      api<{ client_id: string; user_email: string | null }[]>("/api/v1/client-access")
        .then((items) => {
          if (current) setPortalLogin(items.find((item) => item.client_id === client.id)?.user_email ?? null);
        })
        .catch(() => { if (current) setPortalLogin(null); });
    }
    return () => { current = false; };
  }, [client.id, showPortalLogin]);

  const developmentMap = new Map(developments.map((item) => [item.id, item]));
  const partyMap = new Map(parties.map((item) => [item.id, item]));
  const rows = contacts ?? [];

  // Empreendimentos em que e principal entram mesmo sem linha de responsabilidade gravada.
  const developmentIds = [
    ...new Set([
      ...developments.filter((item) => item.client_id === client.id).map((item) => item.id),
      ...rows.map((row) => row.development_id),
    ]),
  ];
  const responsibilities = developmentIds
    .map((developmentId) => {
      const development = developmentMap.get(developmentId);
      const own = rows.filter((row) => row.development_id === developmentId);
      const active = own.filter((row) => row.is_active);
      const isPrimary = development?.client_id === client.id;
      const areas = (active.length ? active : own)
        .filter((row) => !row.is_primary)
        .map((row) => SCOPE_LABELS[row.scope] ?? row.scope);
      const party = development?.contracting_party_id ? partyMap.get(development.contracting_party_id) : undefined;
      return {
        id: developmentId,
        name: development?.name ?? "Empreendimento não encontrado",
        place: development ? place(development) : "",
        role: [isPrimary ? "Responsável principal" : null, areas.length ? "Área: " + areas.join(", ") : null]
          .filter(Boolean)
          .join(" · "),
        contract: party
          ? "Contratante: " + contractingPartyLabel(party)
          : isPrimary
            ? "Responde pelo contrato (sem contratante)"
            : "Sem contratante",
        active: isPrimary || active.length > 0,
        portal: active.some((row) => row.portal_access),
      };
    })
    .sort((a, b) => a.name.localeCompare(b.name, "pt-BR"));

  return (
    <div className="client-contacts development-details">
      <section>
        <span className="eyebrow">Responsável</span>
        <dl className="detail-grid">
          <Field label="Nome" value={client.name} />
          <Field label="Função" value={client.contact_role} />
          <Field label="CPF/CNPJ" value={formatDocument(client.document)} />
          <Field label="WhatsApp" value={formatPhone(client.contact_whatsapp)} />
          <Field label="Telefone" value={formatPhone(client.contact_phone)} />
          <Field label="Email" value={client.contact_email} />
          <Field label="Contato alternativo" value={client.contact_name} />
          {showPortalLogin && (
            <Field
              label="Login no portal"
              value={portalLogin === undefined ? "Carregando..." : portalLogin ?? "Sem login de portal"}
            />
          )}
        </dl>
      </section>

      <section>
        <span className="eyebrow">Empreendimentos pelos quais responde</span>
        {failed && <p className="detail-note">Não foi possível carregar os empreendimentos. Feche e abra a consulta de novo.</p>}
        {!failed && contacts === null && <p className="detail-note">Carregando...</p>}
        {!failed && contacts !== null && responsibilities.length === 0 && (
          <p className="detail-note">
            Este responsável ainda não responde por nenhum empreendimento. Use o botão Empreendimentos, ao lado, para vincular.
          </p>
        )}
        {!failed && contacts !== null && responsibilities.map((item) => (
          <div className="client-contact-row" key={item.id}>
            <div>
              <strong>{item.name}</strong>
              <span>{[item.role, item.place, item.contract].filter(Boolean).join(" · ")}</span>
            </div>
            <div className="admin-actions">
              <span className="status">{item.portal ? "Portal liberado" : "Portal bloqueado"}</span>
              <span className={item.active ? "status status-revisada" : "status"}>{item.active ? "Ativo" : "Inativo"}</span>
            </div>
          </div>
        ))}
      </section>
    </div>
  );
}
