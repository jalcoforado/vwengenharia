import { useEffect, useMemo, useState } from "react";
import {
  AlertTriangle,
  ArrowLeft,
  Bot,
  Camera,
  CheckCircle2,
  ClipboardCheck,
  Cloud,
  CloudOff,
  LogOut,
  RefreshCw,
  Route,
  Save,
  Send,
  ShieldCheck,
  Wrench,
} from "lucide-react";

import { api, clearSession, hasSession, login } from "./lib/api";
import { cacheValue, outboxCount, queueUpload, readCache } from "./offline/db";
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

type DashboardOverview = {
  active_stations: number;
  unavailable_assets: number;
  visits_waiting_review: number;
  open_occurrences: number;
  open_work_orders: number;
  overdue_work_orders: number;
  critical_work_orders: number;
};

type WorkOrder = {
  id: string;
  station_id: string;
  priority: string;
  status: string;
  description: string;
  sla_due_at: string;
  assigned_membership_id: string | null;
};

type SoniaAnswer = {
  run_id: string;
  answer: string;
  tool_trace: Array<{ tool: string; arguments: Record<string, unknown>; result_count: number | null }>;
  provider: string;
  model: string;
};

type Occurrence = {
  id: string;
  station_id: string;
  occurrence_type: string;
  severity: string;
  status: string;
  description: string;
  detected_at: string;
};

const MANAGEMENT_ROLES = new Set(["SUPERADMIN", "ADMIN", "GESTOR", "SUPERVISOR"]);
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

  async function saveEvidence(visitId: string, file: File) {
    const allowed = new Set([
      "image/jpeg",
      "image/png",
      "image/webp",
      "video/mp4",
      "video/quicktime",
      "application/pdf",
    ]);
    if (!allowed.has(file.type)) {
      setMessage("Formato de arquivo nao suportado.");
      return;
    }
    if (file.size > 50_000_000) {
      setMessage("A evidencia deve ter no maximo 50 MB.");
      return;
    }

    const operationId = uuid();
    await queueUpload({
      id: operationId,
      visitId,
      filename: file.name || `evidencia-${operationId}`,
      contentType: file.type,
      sizeBytes: file.size,
      blob: file,
      createdAt: new Date().toISOString(),
    });
    setMessage("Evidencia salva no aparelho.");
    await refreshPending();

    if (navigator.onLine) {
      const synced = await syncOutbox();
      if (synced > 0) {
        setMessage("Evidencia enviada e confirmada.");
        await loadFieldData();
      }
      await refreshPending();
    }
  }

  async function logout() {
    await clearSession();
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
  const isManagement = Boolean(me && MANAGEMENT_ROLES.has(me.role));

  return (
    <div className="app-shell">
      <header className="topbar">
        <div>
          <span className="brand-kicker">VW Engenharia</span>
          <strong>{selectedVisit ? "Visita tecnica" : isManagement ? "Cockpit operacional" : "Operacao de campo"}</strong>
        </div>
        <div className="top-actions">
          <span className={online ? "connection online" : "connection offline"}>
            {online ? <Cloud size={16} /> : <CloudOff size={16} />}
            {online ? "Online" : "Offline"}
          </span>
          {pending > 0 && <span className="sync-pill">{pending} pendente(s)</span>}
          <button className="icon-button" onClick={() => void logout()} title="Sair">
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
          onEvidence={saveEvidence}
          busy={busy}
        />
      ) : isManagement && me ? (
        <SupervisorHome me={me} />
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
  onEvidence,
  busy,
}: {
  visit: Visit;
  bootstrap: Bootstrap;
  onBack: () => void;
  onCommand: (visit: Visit, action: "start" | "finish") => Promise<void>;
  onAnswer: (visitId: string, itemId: string, value: unknown) => Promise<void>;
  onMeasurement: (visitId: string, type: string, value: string, unit: string) => Promise<void>;
  onEvidence: (visitId: string, file: File) => Promise<void>;
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
            <span className="eyebrow">Evidencias</span>
            <h2>Fotos e arquivos</h2>
            <EvidenceCapture onFile={(file) => onEvidence(visit.id, file)} />
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

          <section className="section-card">
            <span className="eyebrow">Ocorrencia</span>
            <h2>Encontrou algum problema?</h2>
            <OccurrenceForm visit={visit} />
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


function SupervisorHome({ me }: { me: Me }) {
  const [overview, setOverview] = useState<DashboardOverview | null>(null);
  const [workOrders, setWorkOrders] = useState<WorkOrder[]>([]);
  const [occurrences, setOccurrences] = useState<Occurrence[]>([]);
  const [reviews, setReviews] = useState<Visit[]>([]);
  const [stations, setStations] = useState<Station[]>([]);
  const [busy, setBusy] = useState(false);
  const [notice, setNotice] = useState<string | null>(null);

  async function load() {
    setBusy(true);
    try {
      const [summary, orders, occurrenceList, visitList, stationList] = await Promise.all([
        api<DashboardOverview>("/api/v1/dashboard/overview"),
        api<WorkOrder[]>("/api/v1/work-orders?limit=100"),
        api<Occurrence[]>("/api/v1/occurrences?limit=100"),
        api<Visit[]>("/api/v1/visits?limit=200"),
        api<Station[]>("/api/v1/stations?limit=500"),
      ]);
      setOverview(summary);
      setWorkOrders(orders);
      setOccurrences(occurrenceList);
      setReviews(visitList.filter((visit) => visit.status === "AGUARDANDO_REVISAO"));
      setStations(stationList);
    } catch {
      setNotice("Nao foi possivel atualizar o cockpit.");
    } finally {
      setBusy(false);
    }
  }

  useEffect(() => {
    void load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  async function reviewVisit(visitId: string, decision: "APROVAR" | "DEVOLVER") {
    setBusy(true);
    try {
      await api(`/api/v1/visits/${visitId}/review`, {
        method: "POST",
        body: JSON.stringify({
          decision,
          notes: decision === "APROVAR" ? "Revisao operacional aprovada." : "Devolvida para ajuste.",
        }),
      });
      setNotice(decision === "APROVAR" ? "Visita aprovada." : "Visita devolvida ao tecnico.");
      await load();
    } catch {
      setNotice("Nao foi possivel registrar a revisao.");
      setBusy(false);
    }
  }

  const stationMap = new Map(stations.map((station) => [station.id, station]));
  const now = Date.now();
  const sortedOrders = [...workOrders].sort(
    (a, b) => new Date(a.sla_due_at).getTime() - new Date(b.sla_due_at).getTime(),
  );

  return (
    <main className="content">
      <section className="welcome">
        <div>
          <span className="eyebrow">Gestao operacional</span>
          <h1>Ola, {me.user.name.split(" ")[0]}</h1>
          <p>{me.tenant.name} · visao consolidada da operacao</p>
        </div>
        <button className="secondary-button" onClick={() => void load()} disabled={busy}>
          <RefreshCw size={17} className={busy ? "spin" : ""} />
          Atualizar
        </button>
      </section>

      {notice && <div className="message" onClick={() => setNotice(null)}>{notice}</div>}

      <SoniaPanel />

      <section className="metric-grid management-metrics">
        <div className="metric-card">
          <Route />
          <strong>{overview?.active_stations ?? "—"}</strong>
          <span>Estacoes ativas</span>
        </div>
        <div className="metric-card">
          <Wrench />
          <strong>{overview?.open_work_orders ?? "—"}</strong>
          <span>OS abertas</span>
        </div>
        <div className="metric-card danger-metric">
          <AlertTriangle />
          <strong>{overview?.overdue_work_orders ?? "—"}</strong>
          <span>OS fora do SLA</span>
        </div>
        <div className="metric-card">
          <ClipboardCheck />
          <strong>{overview?.visits_waiting_review ?? "—"}</strong>
          <span>Aguardando revisao</span>
        </div>
        <div className="metric-card">
          <ShieldCheck />
          <strong>{overview?.critical_work_orders ?? "—"}</strong>
          <span>OS criticas</span>
        </div>
        <div className="metric-card">
          <AlertTriangle />
          <strong>{overview?.open_occurrences ?? "—"}</strong>
          <span>Ocorrencias abertas</span>
        </div>
      </section>

      <div className="management-grid">
        <section className="section-card">
          <div className="section-heading">
            <div>
              <span className="eyebrow">Prioridade</span>
              <h2>Ordens de servico</h2>
            </div>
          </div>
          <div className="ops-list">
            {sortedOrders.slice(0, 12).map((order) => {
              const overdue =
                !["VALIDADA", "CANCELADA"].includes(order.status) &&
                new Date(order.sla_due_at).getTime() < now;
              return (
                <div className="ops-row" key={order.id}>
                  <div>
                    <strong>{stationMap.get(order.station_id)?.name ?? "Estacao"}</strong>
                    <span>{order.description}</span>
                  </div>
                  <div className="ops-meta">
                    <span className={`priority priority-${order.priority.toLowerCase()}`}>
                      {order.priority}
                    </span>
                    <span className={overdue ? "sla overdue" : "sla"}>
                      {overdue ? "SLA vencido" : order.status.replaceAll("_", " ")}
                    </span>
                  </div>
                </div>
              );
            })}
            {sortedOrders.length === 0 && <div className="empty-state">Nenhuma OS aberta.</div>}
          </div>
        </section>

        <section className="section-card">
          <span className="eyebrow">Qualidade</span>
          <h2>Visitas para revisar</h2>
          <div className="ops-list">
            {reviews.slice(0, 10).map((visit) => (
              <div className="review-row" key={visit.id}>
                <div>
                  <strong>{stationMap.get(visit.station_id)?.name ?? "Estacao"}</strong>
                  <span>
                    {new Intl.DateTimeFormat("pt-BR", {
                      dateStyle: "short",
                      timeStyle: "short",
                    }).format(new Date(visit.finished_at ?? visit.scheduled_for))}
                  </span>
                </div>
                <div className="review-actions">
                  <button
                    className="small-button"
                    disabled={busy}
                    onClick={() => void reviewVisit(visit.id, "APROVAR")}
                  >
                    Aprovar
                  </button>
                  <button
                    className="small-button warning-button"
                    disabled={busy}
                    onClick={() => void reviewVisit(visit.id, "DEVOLVER")}
                  >
                    Devolver
                  </button>
                </div>
              </div>
            ))}
            {reviews.length === 0 && <div className="empty-state">Fila de revisao em dia.</div>}
          </div>
        </section>
      </div>

      <section className="section-card">
        <span className="eyebrow">Ocorrencias</span>
        <h2>Atencao operacional recente</h2>
        <div className="ops-list">
          {occurrences
            .filter((item) => !["RESOLVIDA", "CANCELADA"].includes(item.status))
            .slice(0, 10)
            .map((item) => (
              <div className="ops-row" key={item.id}>
                <div>
                  <strong>{stationMap.get(item.station_id)?.name ?? "Estacao"} · {item.occurrence_type}</strong>
                  <span>{item.description}</span>
                </div>
                <span className={`priority priority-${item.severity.toLowerCase()}`}>
                  {item.severity}
                </span>
              </div>
            ))}
        </div>
      </section>
    </main>
  );
}


function OccurrenceForm({ visit }: { visit: Visit }) {
  const [occurrenceType, setOccurrenceType] = useState("FALHA_EQUIPAMENTO");
  const [severity, setSeverity] = useState("MEDIA");
  const [description, setDescription] = useState("");
  const [feedback, setFeedback] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function submit() {
    if (description.trim().length < 3) {
      setFeedback("Descreva brevemente o problema encontrado.");
      return;
    }
    const operationId = uuid();
    const body = {
      visit_id: visit.id,
      station_id: visit.station_id,
      occurrence_type: occurrenceType,
      severity,
      description: description.trim(),
      detected_at: new Date().toISOString(),
    };
    setBusy(true);
    try {
      const result = await runOrQueue<Occurrence>(
        {
          id: operationId,
          method: "POST",
          path: "/api/v1/occurrences",
          body,
          createdAt: new Date().toISOString(),
        },
        () =>
          api<Occurrence>("/api/v1/occurrences", {
            method: "POST",
            body: JSON.stringify(body),
          }),
      );
      setFeedback(
        result.queued
          ? "Ocorrencia salva no aparelho. Sera enviada quando houver conexao."
          : "Ocorrencia registrada para a supervisao.",
      );
      setDescription("");
    } catch {
      setFeedback("Nao foi possivel registrar a ocorrencia.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="occurrence-form">
      <div className="occurrence-controls">
        <label>
          Tipo
          <select value={occurrenceType} onChange={(event) => setOccurrenceType(event.target.value)}>
            <option value="FALHA_EQUIPAMENTO">Falha de equipamento</option>
            <option value="LIMPEZA">Limpeza</option>
            <option value="CLORACAO">Cloracao</option>
            <option value="ESTRUTURA">Estrutura</option>
            <option value="OUTRO">Outro</option>
          </select>
        </label>
        <label>
          Criticidade
          <select value={severity} onChange={(event) => setSeverity(event.target.value)}>
            <option value="BAIXA">Baixa</option>
            <option value="MEDIA">Media</option>
            <option value="ALTA">Alta</option>
            <option value="CRITICA">Critica</option>
          </select>
        </label>
      </div>
      <label>
        Descricao
        <textarea
          value={description}
          onChange={(event) => setDescription(event.target.value)}
          placeholder="Ex.: Aerador II parado e com ruido antes da parada."
          rows={3}
        />
      </label>
      <button className="small-button" disabled={busy} onClick={() => void submit()}>
        <AlertTriangle size={15} />
        {busy ? "Salvando..." : "Registrar ocorrencia"}
      </button>
      {feedback && <span className="inline-feedback">{feedback}</span>}
    </div>
  );
}


function EvidenceCapture({ onFile }: { onFile: (file: File) => Promise<void> }) {
  const [busy, setBusy] = useState(false);
  const [lastName, setLastName] = useState<string | null>(null);

  async function selected(file: File | undefined) {
    if (!file) return;
    setBusy(true);
    try {
      await onFile(file);
      setLastName(file.name || "Evidencia capturada");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="evidence-capture">
      <label className="evidence-button">
        <Camera size={20} />
        <span>{busy ? "Salvando..." : "Adicionar foto ou arquivo"}</span>
        <input
          type="file"
          accept="image/jpeg,image/png,image/webp,video/mp4,video/quicktime,application/pdf"
          capture="environment"
          disabled={busy}
          onChange={(event) => {
            const file = event.target.files?.[0];
            void selected(file);
            event.target.value = "";
          }}
        />
      </label>
      <p>
        {lastName
          ? `${lastName} salvo. O envio sera retomado automaticamente se estiver offline.`
          : "Fotos, videos curtos ou PDF de ate 50 MB."}
      </p>
    </div>
  );
}


function SoniaPanel() {
  const [question, setQuestion] = useState("");
  const [answer, setAnswer] = useState<SoniaAnswer | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function ask() {
    const text = question.trim();
    if (text.length < 3) return;
    setBusy(true);
    setError(null);
    try {
      const result = await api<SoniaAnswer>("/api/v1/ai/ask", {
        method: "POST",
        body: JSON.stringify({ question: text }),
      });
      setAnswer(result);
    } catch (err) {
      const detail =
        typeof err === "object" && err !== null && "detail" in err
          ? String((err as { detail: unknown }).detail)
          : "";
      setError(
        detail === "ai_provider_disabled"
          ? "SonIA pronta, mas o provedor de IA ainda nao foi habilitado neste ambiente."
          : "Nao foi possivel consultar a SonIA agora.",
      );
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className="sonia-card">
      <div className="sonia-heading">
        <div className="sonia-icon"><Bot size={22} /></div>
        <div>
          <span className="eyebrow">made iAnalisys</span>
          <h2>SonIA Operacional</h2>
          <p>Pergunte sobre riscos, SLA, ocorrencias, ativos e estacoes.</p>
        </div>
      </div>
      <div className="sonia-input">
        <input
          value={question}
          onChange={(event) => setQuestion(event.target.value)}
          placeholder="Ex.: Quais sao os riscos mais criticos da operacao agora?"
          onKeyDown={(event) => {
            if (event.key === "Enter") void ask();
          }}
        />
        <button className="primary-button" disabled={busy || question.trim().length < 3} onClick={() => void ask()}>
          <Send size={17} />
          {busy ? "Analisando..." : "Perguntar"}
        </button>
      </div>
      {error && <div className="sonia-error">{error}</div>}
      {answer && (
        <div className="sonia-answer">
          <strong>SonIA</strong>
          <p>{answer.answer}</p>
          {answer.tool_trace.length > 0 && (
            <span>
              Consultas usadas: {answer.tool_trace.map((item) => item.tool).join(", ")}
            </span>
          )}
        </div>
      )}
    </section>
  );
}
