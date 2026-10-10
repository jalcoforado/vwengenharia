import { useEffect, useState } from "react";

import { api } from "../lib/api";
import { contractingPartyLabel, type ContractingPartyRecord } from "./ContractingPartyAdmin";
import { formatDocument } from "../lib/document";
import { formatPhone } from "../lib/phone";

// Consulta do empreendimento: dados do local, contrato, responsaveis e estacoes numa so visao.

type DetailDevelopment = {
  id: string;
  client_id: string;
  name: string;
  contact_phone: string | null;
  contact_email: string | null;
  address_line: string | null;
  address_number: string | null;
  address_complement: string | null;
  address_district: string | null;
  city: string | null;
  state: string | null;
  postal_code: string | null;
  development_type: string | null;
  latitude: number | null;
  longitude: number | null;
  units_count: number | null;
  access_hours: string | null;
  has_facade_photo: boolean;
};

type DetailClient = {
  id: string;
  name: string;
  contact_role: string | null;
  contact_phone: string | null;
  contact_whatsapp: string | null;
  contact_email: string | null;
  is_active: boolean;
};

type DetailContact = {
  id: string;
  client_id: string;
  scope: string;
  is_primary: boolean;
  portal_access: boolean;
  is_active: boolean;
};

const SCOPE_LABELS: Record<string, string> = {
  GERAL: "Geral",
  TECNICO: "Técnico",
  FINANCEIRO: "Financeiro",
  COMERCIAL: "Comercial",
  ADMINISTRATIVO: "Administrativo",
};

function Field({ label, value }: { label: string; value: string | null | undefined }) {
  return (
    <div className="detail-field">
      <dt>{label}</dt>
      <dd>{value || "—"}</dd>
    </div>
  );
}

function personContact(client: DetailClient): string {
  return [
    client.contact_whatsapp ? "WhatsApp " + formatPhone(client.contact_whatsapp) : null,
    client.contact_phone ? "Tel. " + formatPhone(client.contact_phone) : null,
    client.contact_email,
  ].filter(Boolean).join(" · ");
}

export default function DevelopmentDetails({
  development,
  party,
  clients,
  stationNames,
}: {
  development: DetailDevelopment;
  party: ContractingPartyRecord | undefined;
  clients: DetailClient[];
  stationNames: string[];
}) {
  const [contacts, setContacts] = useState<DetailContact[] | null>(null);
  const [failed, setFailed] = useState(false);
  const [photoUrl, setPhotoUrl] = useState<string | null>(null);

  useEffect(() => {
    let current = true;
    setContacts(null);
    setFailed(false);
    setPhotoUrl(null);
    api<DetailContact[]>("/api/v1/client-contacts?limit=500&development_id=" + development.id)
      .then((items) => { if (current) setContacts(items); })
      .catch(() => { if (current) setFailed(true); });
    if (development.has_facade_photo) {
      api<{ url: string }>("/api/v1/developments/" + development.id + "/facade-photo")
        .then((photo) => { if (current) setPhotoUrl(photo.url); })
        .catch(() => undefined);
    }
    return () => { current = false; };
  }, [development.id, development.has_facade_photo]);

  const clientMap = new Map(clients.map((item) => [item.id, item]));
  const primary = clientMap.get(development.client_id);
  const rows = contacts ?? [];
  const primaryPortal = rows.some((row) => row.client_id === development.client_id && row.is_active && row.portal_access);

  // Uma pessoa pode responder por mais de uma area: junta as areas numa linha so.
  const others = [...new Set(rows.filter((row) => row.client_id !== development.client_id).map((row) => row.client_id))]
    .map((clientId) => {
      const own = rows.filter((row) => row.client_id === clientId);
      const active = own.filter((row) => row.is_active);
      return {
        client: clientMap.get(clientId),
        areas: (active.length ? active : own).map((row) => SCOPE_LABELS[row.scope] ?? row.scope).join(", "),
        active: active.length > 0,
        portal: active.some((row) => row.portal_access),
      };
    })
    .sort((a, b) => (a.client?.name ?? "").localeCompare(b.client?.name ?? "", "pt-BR"));

  // Areas adicionais do proprio principal, alem da linha "Geral".
  const primaryAreas = rows
    .filter((row) => row.client_id === development.client_id && row.is_active && !row.is_primary)
    .map((row) => SCOPE_LABELS[row.scope] ?? row.scope);

  const address = [
    [development.address_line, development.address_number].filter(Boolean).join(", "),
    development.address_complement,
    development.address_district,
  ].filter(Boolean).join(" · ");
  const cityLine = [[development.city, development.state].filter(Boolean).join("/"), development.postal_code]
    .filter(Boolean)
    .join(" · ");
  const hasLocation = development.latitude !== null && development.longitude !== null;

  return (
    <div className="client-contacts development-details">
      <section>
        <span className="eyebrow">Local atendido</span>
        <dl className="detail-grid">
          <Field label="Tipo" value={development.development_type} />
          <Field label="Endereço" value={address} />
          <Field label="Município" value={cityLine} />
          <Field label="Telefone" value={formatPhone(development.contact_phone)} />
          <Field label="Email" value={development.contact_email} />
          <Field label="Número de economias" value={development.units_count === null ? null : String(development.units_count)} />
          <Field label="Horário de acesso" value={development.access_hours} />
          <div className="detail-field">
            <dt>Localização</dt>
            <dd>
              {hasLocation ? (
                <a href={"https://www.google.com/maps?q=" + development.latitude + "," + development.longitude} target="_blank" rel="noreferrer">
                  {development.latitude}, {development.longitude}
                </a>
              ) : "—"}
            </dd>
          </div>
        </dl>
        {photoUrl && (
          <a className="detail-photo" href={photoUrl} target="_blank" rel="noreferrer">
            <img src={photoUrl} alt={"Fachada de " + development.name} />
          </a>
        )}
      </section>

      <section>
        <span className="eyebrow">Contrato</span>
        {party ? (
          <dl className="detail-grid">
            <Field label="Contratante" value={contractingPartyLabel(party)} />
            <Field label={party.person_type === "PJ" ? "Razão social" : "Nome completo"} value={party.name} />
            <Field label={party.person_type === "PJ" ? "CNPJ" : "CPF"} value={formatDocument(party.document)} />
            <Field label="Telefone" value={formatPhone(party.contact_phone)} />
            <Field label="Email" value={party.contact_email} />
          </dl>
        ) : (
          <p className="detail-note">
            Sem contratante cadastrado. {primary ? primary.name + ", o responsável principal, responde pelo contrato." : "O responsável principal responde pelo contrato."}
          </p>
        )}
      </section>

      <section>
        <span className="eyebrow">Responsável principal</span>
        {primary ? (
          <dl className="detail-grid">
            <Field label="Nome" value={primary.name + (primary.is_active ? "" : " (inativo)")} />
            <Field label="Função" value={primary.contact_role} />
            <Field label="Contato" value={personContact(primary)} />
            <Field label="Outras áreas" value={primaryAreas.join(", ")} />
            <Field label="Portal do cliente" value={contacts === null ? "Carregando..." : primaryPortal ? "Liberado" : "Bloqueado"} />
          </dl>
        ) : (
          <p className="detail-note">Responsável principal não encontrado no cadastro de responsáveis.</p>
        )}
      </section>

      <section>
        <span className="eyebrow">Outros responsáveis</span>
        {failed && <p className="detail-note">Não foi possível carregar os responsáveis. Feche e abra a consulta de novo.</p>}
        {!failed && contacts === null && <p className="detail-note">Carregando...</p>}
        {!failed && contacts !== null && others.length === 0 && (
          <p className="detail-note">Nenhum outro responsável. Para incluir, abra a aba Responsáveis e vincule a pessoa a este empreendimento.</p>
        )}
        {others.map((item) => (
          <div className="client-contact-row" key={item.client?.id ?? item.areas}>
            <div>
              <strong>{item.client?.name ?? "Responsável não encontrado"}</strong>
              <span>
                {[
                  item.client?.contact_role,
                  "Área: " + item.areas,
                  item.client ? personContact(item.client) : null,
                ].filter(Boolean).join(" · ")}
              </span>
            </div>
            <div className="admin-actions">
              <span className="status">{item.portal ? "Portal liberado" : "Portal bloqueado"}</span>
              <span className={item.active ? "status status-revisada" : "status"}>{item.active ? "Ativo" : "Inativo"}</span>
            </div>
          </div>
        ))}
      </section>

      <section>
        <span className="eyebrow">Estações</span>
        <p className="detail-note">
          {stationNames.length ? stationNames.join(" · ") : "Nenhuma estação cadastrada neste empreendimento."}
        </p>
      </section>
    </div>
  );
}
