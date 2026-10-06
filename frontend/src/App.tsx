import { useEffect, useMemo, useState } from "react";
import {
  ArrowLeft,
  CheckCircle2,
  Cloud,
  CloudOff,
  LogOut,
  RefreshCw,
  Route,
  Save,
  Wrench,
} from "lucide-react";

import { api, clearSession, hasSession, login } from "./lib/api";
import { cacheValue, outboxCount, readCache } from "./offline/db";
import { runOrQueue, syncOutbox } from "./lib/sync";

type Visit = {
  id: string;
  station_id: string;
  technician_membership_id: string;
  checklist_template_id: string | null;
  scheduled_for: string;
  started_at: string | null;
  finished_at: string | null;
  status: string;
  notes: string | null;
};

type Station = {
  id: string;
  name: string;
  code: string | null;
  station_type: string | null;
};

type ChecklistItem = {
  id: string;
  template_id: string;
  code: string;
  label: string;
  answer_type: string;
  required: boolean;
  position: number;
  options_json: string[] | null;
};

type VisitAnswer = {
  id: string;
  visit_id: string;
  item_id: string;
  value_json: unknown;
};

type Measurement = {
  id: string;
  visit_id: string;
  measurement_type: string;
  status: string;
  value: string | number | null;
  unit: string | null;
  reason: string | null;
};

type Bootstrap = {
  generated_at: string;
  visits: Visit[];
  stations: Station[];
  assets: Array<{
    id: string;
    station_id: string;
    asset_type_id: string;
    name: string;
    status: string;
  }>;
  templates: Array<{
    id: string;
    name: string;
    version: number;
  }>;
  items: ChecklistItem[];
  answers: VisitAnswer[];
  measurements: Measurement[];
  attachments: unknown[];
};

type Me = {
  user: { id: string; email: string; name: string };
  tenant: { id: string; name: string; slug: string };
  membership_id: string;
  role: string;
};

const CACHE_KEY = "field-bootstrap";

function statusLabel(status: string) {
  return (
    {
      PROGRAMADA: "Programada",
      EM_EXECUCAO: "Em execucao",
      AGUARDANDO_REVISAO: "Aguardando revisao",
      REVISADA: "Revisada",
      DEVOLVIDA: "Devolvida",
    }[status] ?? status
  );
}

function uuid() {
  return crypto.randomUUID();
}

export default function App() {
  const [authenticated, setAuthenticated] = useState(hasSession());
  const [me, setMe] = useState<Me | null>(null);
  const [bootstrap, setBootstrap] = useState<Bootstrap | null>(null);
  const [selectedVisitId, setSelectedVisitId] = useState<string | null>(null);
  const [online, setOnline] = useState(navigator.onLine);
  const [pending, setPending] = useState(0);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState<string | null>(null);

  async function refreshPending() {
    setPending(await outboxCount());
  }

  async function loadFieldData() {
    setBusy(true);
    setMessage(null);
    try {
      if (navigator.onLine && authenticated) {
        const [who, data] = await Promise.all([
          api<Me>("/api/v1/auth/me"),
          api<Bootstrap>("/api/v1/field/bootstrap"),
        ]);
        setMe(who);
        setBootstrap(data);
        await cacheValue(CACHE_KEY, data);
      } else {
        const cached = await readCache<Bootstrap>(CACHE_KEY);
        if (cached) setBootstrap(cached);
      }
    } catch {
      const cached = await readCache<Bootstrap>(CACHE_KEY);
      if (cached) {
        setBootstrap(cached);
        setMessage("Sem conexao com o servidor. Exibindo dados salvos no aparelho.");
      }
    } finally {
      setBusy(false);
      await refreshPending();
    }
  }

  useEffect(() => {
    void loadFieldData();

    const goOnline = async () => {
      setOnline(true);
      const count = await syncOutbox();
      if (count > 0) setMessage(`${count} operacao(oes) sincronizada(s).`);
      await loadFieldData();
    };
    const goOffline = () => {
      setOnline(false);
      setMessage("Modo offline ativo. Seu trabalho sera salvo neste aparelho.");
    };

    window.addEventListener("online", goOnline);
    window.addEventListener("offline", goOffline);
    return () => {
      window.removeEventListener("online", goOnline);
      window.removeEventListener("offline", goOffline);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [authenticated]);

  function updateCachedVisit(visitId: string, patch: Partial<Visit>) {
    setBootstrap((current) => {
      if (!current) return current;
      const next = {
        ...current,
        visits: current.visits.map((visit) =>
          visit.id === visitId ? { ...visit, ...patch } : visit,
        ),
      };
      void cacheValue(CACHE_KEY, next);
      return next;
    });
  }

  function upsertCachedAnswer(visitId: string, itemId: string, value: unknown) {
    setBootstrap((current) => {
      if (!current) return current;
      const existing = current.answers.find(
        (answer) => answer.visit_id === visitId && answer.item_id === itemId,
      );
      const nextAnswer: VisitAnswer = existing
        ? { ...existing, value_json: value }
        : { id: `local-${uuid()}`, visit_id: visitId, item_id: itemId, value_json: value };
      const next = {
        ...current,
        answers: existing
          ? current.answers.map((answer) =>
              answer.id === existing.id ? nextAnswer : answer,
            )
          : [...current.answers, nextAnswer],
      };
      void cacheValue(CACHE_KEY, next);
      return next;
    });
  }

  async function commandVisit(visit: Visit, action: "start" | "finish") {
    const operationId = uuid();
    if (action === "finish" && bootstrap) {
      const required = bootstrap.items.filter(
        (item) => item.template_id === visit.checklist_template_id && item.required,
      );
      const answered = new Set(
        bootstrap.answers
          .filter((answer) => answer.visit_id === visit.id)
          .map((answer) => answer.item_id),
      );
      const missing = required.filter((item) => !answered.has(item.id));
      if (missing.length) {
        setMessage(`Preencha os campos obrigatorios: ${missing.map((x) => x.label).join(", ")}.`);
        return;
      }
    }

    setBusy(true);
    try {
      const result = await runOrQueue<Visit>(
        {
          id: operationId,
          method: "POST",
          path: `/api/v1/visits/${visit.id}/${action}`,
          body: { client_operation_id: operationId },
          createdAt: new Date().toISOString(),
        },
        () =>
          api<Visit>(`/api/v1/visits/${visit.id}/${action}`, {
            method: "POST",
            body: JSON.stringify({ client_operation_id: operationId }),
          }),
      );

      if (result.result) {
        updateCachedVisit(visit.id, result.result);
      } else {
        updateCachedVisit(
          visit.id,
          action === "start"
            ? { status: "EM_EXECUCAO", started_at: new Date().toISOString() }
            : { status: "AGUARDANDO_REVISAO", finished_at: new Date().toISOString() },
        );
        setMessage("Operacao salva no aparelho e pendente de sincronizacao.");
      }
      await refreshPending();
    } catch {
      setMessage("Nao foi possivel concluir a operacao.");
    } finally {
      setBusy(false);
    }
  }

  async function saveAnswer(visitId: string, itemId: string, value: unknown) {
    const operationId = uuid();
    const body = {
      item_id: itemId,
      value,
      client_operation_id: operationId,
    };
    upsertCachedAnswer(visitId, itemId, value);

    try {
      const result = await runOrQueue<VisitAnswer>(
        {
          id: operationId,
          method: "PUT",
          path: `/api/v1/visits/${visitId}/answers`,
          body,
          createdAt: new Date().toISOString(),
        },
        () =>
          api<VisitAnswer>(`/api/v1/visits/${visitId}/answers`, {
            method: "PUT",
            body: JSON.stringify(body),
          }),
      );
      if (result.queued) setMessage("Resposta salva offline.");
      await refreshPending();
    } catch {
      setMessage("Nao foi possivel salvar a resposta.");
    }
  }

  async function saveMeasurement(
    visitId: string,
    type: string,
    value: string,
    unit: string,
  ) {
    if (!value.trim()) return;
    const operationId = uuid();
    const body = {
      measurement_type: type,
      status: "MEASURED",
      value,
      unit,
      measured_at: new Date().toISOString(),
      client_operation_id: operationId,
    };
    try {
      const result = await runOrQueue<Measurement>(
        {
          id: operationId,
          method: "POST",
          path: `/api/v1/visits/${visitId}/measurements`,
          body,
          createdAt: new Date().toISOString(),
        },
        () =>
          api<Measurement>(`/api/v1/visits/${visitId}/measurements`, {
            method: "POST",
            body: JSON.stringify(body),
          }),
      );
      if (result.result) {
        setBootstrap((current) =>
          current
            ? { ...current, measurements: [...current.measurements, result.result!] }
            : current,
        );
      }
      if (result.queued) setMessage("Medicao salva offline.");
      await refreshPending();
    } catch {
      setMessage("Nao foi possivel salvar a medicao.");
    }
  }

  function logout() {
    clearSession();
    setAuthenticated(false);
    setMe(null);
    setSelectedVisitId(null);
  }

  if (!authenticated) {
    return (
      <Login
        onSuccess={() => {
          setAuthenticated(true);
          setMessage("Acesso realizado.");
        }}
      />
    );
  }

  const selectedVisit = bootstrap?.visits.find((item) => item.id === selectedVisitId) ?? null;

  return (
    <div className="app-shell">
      <header className="topbar">
        <div>
          <span className="brand-kicker">VW Engenharia</span>
          <strong>{selectedVisit ? "Visita tecnica" : "Operacao de campo"}</strong>
        </div>
        <div className="top-actions">
          <span className={online ? "connection online" : "connection offline"}>
            {online ? <Cloud size={16} /> : <CloudOff size={16} />}
            {online ? "Online" : "Offline"}
          </span>
          {pending > 0 && <span className="sync-pill">{pending} pendente(s)</span>}
          <button className="icon-button" onClick={logout} title="Sair">
            <LogOut size={18} />
          </button>
        </div>
      </header>

      {message && (
        <div className="message" onClick={() => setMessage(null)}>
          {message}
        </div>
      )}

      {selectedVisit && bootstrap ? (
        <VisitScreen
          visit={selectedVisit}
          bootstrap={bootstrap}
          onBack={() => setSelectedVisitId(null)}
          onCommand={commandVisit}
          onAnswer={saveAnswer}
          onMeasurement={saveMeasurement}
          busy={busy}
        />
      ) : (
        <Home
          me={me}
          bootstrap={bootstrap}
          busy={busy}
          pending={pending}
          onRefresh={async () => {
            if (online) await syncOutbox();
            await loadFieldData();
          }}
          onOpenVisit={setSelectedVisitId}
        />
      )}
    </div>
  );
}

function Login({ onSuccess }: { onSuccess: () => void }) {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  async function submit(event: React.FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError("");
    try {
      await login(email, password);
      onSuccess();
    } catch {
      setError("Email ou senha invalidos.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <main className="login-page">
      <section className="login-card">
        <div className="brand-mark">VW</div>
        <span className="brand-kicker">VW Engenharia</span>
        <h1>Operacao em campo</h1>
        <p>Visitas, checklist, medicoes e ocorrencias em um unico lugar.</p>
        <form onSubmit={submit}>
          <label>
            Email
            <input
              type="email"
              autoComplete="username"
              value={email}
              onChange={(event) => setEmail(event.target.value)}
              required
            />
          </label>
          <label>
            Senha
            <input
              type="password"
              autoComplete="current-password"
              value={password}
              onChange={(event) => setPassword(event.target.value)}
              required
            />
          </label>
          {error && <div className="form-error">{error}</div>}
          <button className="primary-button" disabled={busy}>
            {busy ? "Entrando..." : "Entrar"}
          </button>
        </form>
      </section>
    </main>
  );
}

function Home({
  me,
  bootstrap,
  busy,
  pending,
  onRefresh,
  onOpenVisit,
}: {
  me: Me | null;
  bootstrap: Bootstrap | null;
  busy: boolean;
  pending: number;
  onRefresh: () => Promise<void>;
  onOpenVisit: (id: string) => void;
}) {
  const visits = useMemo(
    () =>
      [...(bootstrap?.visits ?? [])].sort(
        (a, b) => new Date(a.scheduled_for).getTime() - new Date(b.scheduled_for).getTime(),
      ),
    [bootstrap],
  );
  const stations = new Map((bootstrap?.stations ?? []).map((station) => [station.id, station]));

  return (
    <main className="content">
      <section className="welcome">
        <div>
          <span className="eyebrow">Hoje em campo</span>
          <h1>{me ? `Ola, ${me.user.name.split(" ")[0]}` : "Suas visitas"}</h1>
          <p>{me?.tenant.name ?? "Dados sincronizados para trabalho em campo."}</p>
        </div>
        <button className="secondary-button" onClick={() => void onRefresh()} disabled={busy}>
          <RefreshCw size={17} className={busy ? "spin" : ""} />
          Sincronizar
        </button>
      </section>

      <section className="metric-grid">
        <div className="metric-card">
          <Route />
          <strong>{visits.filter((v) => v.status === "PROGRAMADA").length}</strong>
          <span>Programadas</span>
        </div>
        <div className="metric-card">
          <Wrench />
          <strong>{visits.filter((v) => v.status === "EM_EXECUCAO").length}</strong>
          <span>Em execucao</span>
        </div>
        <div className="metric-card">
          <CheckCircle2 />
          <strong>{visits.filter((v) => v.status === "AGUARDANDO_REVISAO").length}</strong>
          <span>Concluidas</span>
        </div>
        <div className="metric-card">
          <Cloud />
          <strong>{pending}</strong>
          <span>A sincronizar</span>
        </div>
      </section>

      <section className="section-card">
        <div className="section-heading">
          <div>
            <span className="eyebrow">Agenda</span>
            <h2>Visitas atribuidas</h2>
          </div>
        </div>

        <div className="visit-list">
          {visits.length === 0 && <div className="empty-state">Nenhuma visita no periodo sincronizado.</div>}
          {visits.map((visit) => {
            const station = stations.get(visit.station_id);
            return (
              <button
                className="visit-card"
                key={visit.id}
                onClick={() => onOpenVisit(visit.id)}
              >
                <div className="visit-time">
                  {new Intl.DateTimeFormat("pt-BR", {
                    hour: "2-digit",
                    minute: "2-digit",
                  }).format(new Date(visit.scheduled_for))}
                </div>
                <div className="visit-main">
                  <strong>{station?.name ?? "Estacao"}</strong>
                  <span>{station?.code ?? station?.station_type ?? "Visita tecnica"}</span>
                </div>
                <span className={`status status-${visit.status.toLowerCase()}`}>
                  {statusLabel(visit.status)}
                </span>
              </button>
            );
          })}
        </div>
      </section>
    </main>
  );
}

function VisitScreen({
  visit,
  bootstrap,
  onBack,
  onCommand,
  onAnswer,
  onMeasurement,
  busy,
}: {
  visit: Visit;
  bootstrap: Bootstrap;
  onBack: () => void;
  onCommand: (visit: Visit, action: "start" | "finish") => Promise<void>;
  onAnswer: (visitId: string, itemId: string, value: unknown) => Promise<void>;
  onMeasurement: (visitId: string, type: string, value: string, unit: string) => Promise<void>;
  busy: boolean;
}) {
  const station = bootstrap.stations.find((item) => item.id === visit.station_id);
  const items = bootstrap.items
    .filter((item) => item.template_id === visit.checklist_template_id)
    .sort((a, b) => a.position - b.position);
  const answerMap = new Map(
    bootstrap.answers
      .filter((answer) => answer.visit_id === visit.id)
      .map((answer) => [answer.item_id, answer.value_json]),
  );

  return (
    <main className="content visit-screen">
      <button className="back-button" onClick={onBack}>
        <ArrowLeft size={18} />
        Voltar para agenda
      </button>

      <section className="visit-hero">
        <div>
          <span className="eyebrow">{station?.code ?? "Estacao"}</span>
          <h1>{station?.name ?? "Visita tecnica"}</h1>
          <p>
            {new Intl.DateTimeFormat("pt-BR", {
              dateStyle: "medium",
              timeStyle: "short",
            }).format(new Date(visit.scheduled_for))}
          </p>
        </div>
        <span className={`status status-${visit.status.toLowerCase()}`}>
          {statusLabel(visit.status)}
        </span>
      </section>

      {visit.status === "PROGRAMADA" && (
        <button
          className="primary-button action-wide"
          disabled={busy}
          onClick={() => void onCommand(visit, "start")}
        >
          Iniciar visita
        </button>
      )}

      {visit.status === "EM_EXECUCAO" && (
        <>
          <section className="section-card">
            <span className="eyebrow">Qualidade</span>
            <h2>Medicoes</h2>
            <div className="measurement-grid">
              <MeasurementInput
                label="pH"
                unit="pH"
                onSave={(value) => onMeasurement(visit.id, "PH", value, "pH")}
              />
              <MeasurementInput
                label="Cloro"
                unit="mg/L"
                onSave={(value) => onMeasurement(visit.id, "CLORO", value, "mg/L")}
              />
            </div>
          </section>

          <section className="section-card">
            <span className="eyebrow">Checklist</span>
            <h2>Inspecao da estacao</h2>
            <div className="checklist">
              {items.map((item) => (
                <ChecklistField
                  key={item.id}
                  item={item}
                  value={answerMap.get(item.id)}
                  onSave={(value) => onAnswer(visit.id, item.id, value)}
                />
              ))}
              {items.length === 0 && (
                <div className="empty-state">Esta visita nao possui checklist configurado.</div>
              )}
            </div>
          </section>

          <button
            className="primary-button action-wide"
            disabled={busy}
            onClick={() => void onCommand(visit, "finish")}
          >
            <CheckCircle2 size={18} />
            Finalizar visita
          </button>
        </>
      )}

      {visit.status === "AGUARDANDO_REVISAO" && (
        <section className="completion-card">
          <CheckCircle2 size={28} />
          <div>
            <strong>Visita concluida</strong>
            <span>Os dados estao prontos para revisao da supervisao.</span>
          </div>
        </section>
      )}
    </main>
  );
}

function MeasurementInput({
  label,
  unit,
  onSave,
}: {
  label: string;
  unit: string;
  onSave: (value: string) => Promise<void>;
}) {
  const [value, setValue] = useState("");
  return (
    <div className="measurement-box">
      <label>{label}</label>
      <div>
        <input
          inputMode="decimal"
          value={value}
          onChange={(event) => setValue(event.target.value.replace(",", "."))}
          placeholder="0.00"
        />
        <span>{unit}</span>
      </div>
      <button
        className="small-button"
        disabled={!value}
        onClick={() => {
          void onSave(value);
          setValue("");
        }}
      >
        <Save size={15} /> Salvar
      </button>
    </div>
  );
}

function ChecklistField({
  item,
  value,
  onSave,
}: {
  item: ChecklistItem;
  value: unknown;
  onSave: (value: unknown) => Promise<void>;
}) {
  if (item.answer_type === "BOOLEAN") {
    return (
      <div className="check-row">
        <div>
          <strong>{item.label}</strong>
          {item.required && <span className="required">Obrigatorio</span>}
        </div>
        <div className="segmented">
          <button
            className={value === true ? "selected" : ""}
            onClick={() => void onSave(true)}
          >
            Sim
          </button>
          <button
            className={value === false ? "selected danger" : ""}
            onClick={() => void onSave(false)}
          >
            Nao
          </button>
        </div>
      </div>
    );
  }

  if (item.answer_type === "SELECT" || item.answer_type === "ASSET_STATUS") {
    const options =
      item.options_json ??
      (item.answer_type === "ASSET_STATUS"
        ? ["OPERANDO", "DESLIGADO", "EM_MANUTENCAO", "AGUARDANDO_MANUTENCAO"]
        : []);
    return (
      <label className="field-row">
        <span>
          {item.label} {item.required && <em>*</em>}
        </span>
        <select
          value={typeof value === "string" ? value : ""}
          onChange={(event) => void onSave(event.target.value)}
        >
          <option value="">Selecione</option>
          {options.map((option) => (
            <option key={option} value={option}>
              {option.replaceAll("_", " ")}
            </option>
          ))}
        </select>
      </label>
    );
  }

  return (
    <TextChecklistField
      item={item}
      initial={value == null ? "" : String(value)}
      onSave={onSave}
    />
  );
}

function TextChecklistField({
  item,
  initial,
  onSave,
}: {
  item: ChecklistItem;
  initial: string;
  onSave: (value: unknown) => Promise<void>;
}) {
  const [value, setValue] = useState(initial);
  return (
    <label className="field-row">
      <span>
        {item.label} {item.required && <em>*</em>}
      </span>
      <div className="inline-save">
        <input
          value={value}
          inputMode={item.answer_type === "NUMBER" ? "decimal" : undefined}
          onChange={(event) => setValue(event.target.value)}
        />
        <button className="small-button" onClick={() => void onSave(value)}>
          <Save size={15} />
        </button>
      </div>
    </label>
  );
}
