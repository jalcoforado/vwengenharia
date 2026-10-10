import { useEffect, useMemo, useState } from "react";
import {
  AlertTriangle,
  ArrowRight,
  ArrowLeft,
  Camera,
  CalendarDays,
  CheckCircle2,
  ClipboardCheck,
  Clock3,
  Cloud,
  LayoutDashboard,
  Activity,
  Database,
  Settings2,
  CloudOff,
  LogOut,
  RefreshCw,
  Route,
  Save,
  Search,
  ShieldCheck,
  Sparkles,
  Shield,
  UserRound,
  Wrench,
} from "lucide-react";

import AppLoading from "./components/AppLoading";
import AuditViewer from "./components/AuditViewer";
import InboxPanel from "./components/InboxPanel";
import LegacyMigrationAdmin from "./components/LegacyMigrationAdmin";
import ChecklistAdmin from "./components/ChecklistAdmin";
import ClientPortal from "./components/ClientPortal";
import ClientAccessAdmin from "./components/ClientAccessAdmin";
import WorkOrdersAdmin from "./components/WorkOrdersAdmin";
import StationOverview from "./components/StationOverview";
import { AccountSettings, IntegrationSettings } from "./components/SettingsPanels";
import {
  MaterialRequestsAdmin,
  type MaterialRequest,
  VisitMaterialRequestForm,
} from "./components/Materials";
import OperationalAdmin, {
  type AdminStation,
  type AssetRecord,
  type AssetTypeRecord,
  type ClientRecord,
  type DevelopmentRecord,
} from "./components/OperationalAdmin";
import { api, clearSession, downloadApi, hasSession, login, openApiDocument } from "./lib/api";
import { formatBytes, optimizeEvidenceImage } from "./lib/media";
import { useOfflineSync, type SyncQueueError } from "./lib/useOfflineSync";
import { cacheValue, outboxCount, queueUpload, readCache, type SyncQueueSummary } from "./offline/db";
import { runOrQueue, syncOutbox } from "./lib/sync";
import { SyncControl, SyncHealthCard } from "./components/SyncStatus";
import Toast from "./components/Toast";
import mwLogo from "./assets/mw-logo.png";
import mwSymbol from "./assets/mw-symbol.png";

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
  occurrence_id: string | null;
  station_id: string;
  asset_id: string | null;
  priority: string;
  status: string;
  description: string;
  sla_due_at: string;
  assigned_membership_id: string | null;
  started_at: string | null;
  completed_at: string | null;
  validated_at: string | null;
  created_at: string;
  updated_at: string;
};

type TeamMember = {
  membership_id: string;
  user_id: string;
  email: string;
  name: string;
  role: string;
  is_active: boolean;
};

type VisitPlan = {
  id: string;
  station_id: string;
  technician_membership_id: string;
  checklist_template_id: string | null;
  frequency_days: number;
  start_at: string;
  end_at: string | null;
  next_due_at: string;
  is_active: boolean;
  notes: string | null;
};

type ChecklistTemplateSummary = {
  id: string;
  name: string;
  version: number;
  is_active: boolean;
};

type MaintenancePlan = {
  id: string;
  asset_id: string;
  assigned_membership_id: string | null;
  maintenance_type: string;
  frequency_days: number;
  next_due_at: string;
  last_completed_at: string | null;
  instructions: string | null;
  is_active: boolean;
};

type MaintenanceSummary = {
  active_plans: number;
  overdue_plans: number;
  due_next_7_days: number;
  executions_last_30_days: number;
};

type OperationalAlert = {
  kind: string;
  severity: string;
  title: string;
  message: string;
  entity_type: string;
  entity_id: string;
  due_at: string | null;
};

type Occurrence = {
  id: string;
  station_id: string;
  asset_id?: string | null;
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
  const { summary: syncSummary, errors: syncErrors, syncing, refresh: refreshSync, syncNow } = useOfflineSync();
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState<string | null>(null);

  async function refreshPending() {
    setPending(await outboxCount());
    await refreshSync();
  }

  async function loadFieldData() {
    setBusy(true);
    setMessage(null);
    try {
      if (navigator.onLine && authenticated) {
        const who = await api<Me>("/api/v1/auth/me");
        setMe(who);
        if (who.role === "CLIENTE") {
          setBootstrap(null);
          return;
        }
        const data = await api<Bootstrap>("/api/v1/field/bootstrap");
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

    let preparedFile = file;
    let optimizationMessage = "";
    if (file.type.startsWith("image/")) {
      try {
        const optimized = await optimizeEvidenceImage(file);
        preparedFile = optimized.file;
        if (optimized.optimizedBytes < optimized.originalBytes) {
          optimizationMessage =
            ` Imagem otimizada de ${formatBytes(optimized.originalBytes)} para ${formatBytes(optimized.optimizedBytes)}.`;
        }
      } catch {
        preparedFile = file;
      }
    }

    const operationId = uuid();
    await queueUpload({
      id: operationId,
      visitId,
      filename: preparedFile.name || `evidencia-${operationId}`,
      contentType: preparedFile.type,
      sizeBytes: preparedFile.size,
      blob: preparedFile,
      createdAt: new Date().toISOString(),
    });
    setMessage("Evidencia salva com seguranca no aparelho." + optimizationMessage);
    await refreshPending();

    if (navigator.onLine) {
      const synced = await syncOutbox();
      if (synced > 0) {
        setMessage("Evidencia enviada e confirmada." + optimizationMessage);
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

  if (authenticated && busy && !me) return <AppLoading />;

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
        <div className="topbar-brand">
          <span className="brand-logo-tile">
            <img src={mwSymbol} alt="" />
          </span>
          <div>
            <span className="brand-kicker">MW Engenharia</span>
            <strong>
              {me?.role === "CLIENTE"
                ? "Portal do cliente"
                : selectedVisit
                  ? "Visita tecnica"
                  : isManagement
                    ? "Cockpit operacional"
                    : "Operacao de campo"}
            </strong>
          </div>
        </div>
        <div className="top-actions">
          <span className={online ? "connection online" : "connection offline"}>
            {online ? <Cloud size={16} /> : <CloudOff size={16} />}
            {online ? "Online" : "Offline"}
          </span>
          <SyncControl
            online={online}
            summary={syncSummary}
            syncing={syncing}
            onSync={async () => {
              const result = await syncNow();
              setPending(result.summary.total);
              if (result.synced > 0) await loadFieldData();
            }}
          />
          <button className="icon-button" onClick={() => void logout()} title="Sair">
            <LogOut size={18} />
          </button>
        </div>
      </header>

      {message && (
        <Toast
          message={message}
          tone={
            /nao foi possivel|falha|erro/i.test(message)
              ? "warning"
              : /sucesso|confirmada|sincronizado|salva/i.test(message)
                ? "success"
                : "info"
          }
          onClose={() => setMessage(null)}
        />
      )}

      {me?.role === "CLIENTE" ? (
        <ClientPortal userName={me.user.name} />
      ) : selectedVisit && bootstrap ? (
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
          online={online}
          syncing={syncing}
          syncSummary={syncSummary}
          syncErrors={syncErrors}
          onSync={async () => {
            const result = await syncNow();
            setPending(result.summary.total);
            if (result.synced > 0) await loadFieldData();
          }}
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
        <img className="login-logo" src={mwLogo} alt="MW Engenharia" />
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
  online,
  syncing,
  syncSummary,
  syncErrors,
  onSync,
  onRefresh,
  onOpenVisit,
}: {
  me: Me | null;
  bootstrap: Bootstrap | null;
  busy: boolean;
  pending: number;
  online: boolean;
  syncing: boolean;
  syncSummary: SyncQueueSummary;
  syncErrors: SyncQueueError[];
  onSync: () => Promise<void>;
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
  const [visitSearch, setVisitSearch] = useState("");
  const [visitStatus, setVisitStatus] = useState("ALL");
  const filteredVisits = visits.filter((visit) => {
    const station = stations.get(visit.station_id);
    const haystack = [
      station?.name,
      station?.code,
      station?.station_type,
      statusLabel(visit.status),
    ]
      .filter(Boolean)
      .join(" ")
      .toLowerCase();
    const matchesSearch = !visitSearch.trim() || haystack.includes(visitSearch.trim().toLowerCase());
    const matchesStatus = visitStatus === "ALL" || visit.status === visitStatus;
    return matchesSearch && matchesStatus;
  });

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

      <SyncHealthCard
        online={online}
        summary={syncSummary}
        errors={syncErrors}
        syncing={syncing}
        onSync={onSync}
      />

      <section className="section-card">
        <div className="section-heading">
          <div>
            <span className="eyebrow">Agenda</span>
            <h2>Visitas atribuidas</h2>
          </div>
        </div>

        <div className="list-toolbar">
          <label className="search-field">
            <Search size={16} />
            <input
              value={visitSearch}
              onChange={(event) => setVisitSearch(event.target.value)}
              placeholder="Buscar estacao, codigo ou status"
            />
          </label>
          <select value={visitStatus} onChange={(event) => setVisitStatus(event.target.value)}>
            <option value="ALL">Todos os status</option>
            <option value="PROGRAMADA">Programadas</option>
            <option value="EM_EXECUCAO">Em execucao</option>
            <option value="AGUARDANDO_REVISAO">Concluidas</option>
            <option value="DEVOLVIDA">Devolvidas</option>
            <option value="REVISADA">Revisadas</option>
          </select>
        </div>

        <div className="visit-list">
          {visits.length === 0 && (
            <div className="empty-state empty-state-positive">
              <CheckCircle2 size={22} />
              <strong>Nenhuma visita atribuida</strong>
              <span>Sua agenda sincronizada esta livre neste momento.</span>
            </div>
          )}
          {visits.length > 0 && filteredVisits.length === 0 && (
            <div className="empty-state">
              <Search size={22} />
              <strong>Nenhum resultado encontrado</strong>
              <span>Altere a busca ou o filtro de status para ver outras visitas.</span>
              <button
                className="small-button"
                onClick={() => {
                  setVisitSearch("");
                  setVisitStatus("ALL");
                }}
              >
                Limpar filtros
              </button>
            </div>
          )}
          {filteredVisits.map((visit) => {
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

      <AccountSettings />
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
  const visitAnswers = bootstrap.answers.filter((answer) => answer.visit_id === visit.id);
  const answerMap = new Map(
    visitAnswers.map((answer) => [answer.item_id, answer.value_json]),
  );
  const requiredItems = items.filter((item) => item.required);
  const answeredItemIds = new Set(visitAnswers.map((answer) => answer.item_id));
  const requiredAnswered = requiredItems.filter((item) => answeredItemIds.has(item.id)).length;
  const checklistAnswered = items.filter((item) => answeredItemIds.has(item.id)).length;
  const checklistProgress = items.length
    ? Math.round((checklistAnswered / items.length) * 100)
    : 100;
  const canFinish = requiredAnswered === requiredItems.length;

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

      {visit.status === "EM_EXECUCAO" && (
        <section className="visit-progress-card" aria-label="Progresso da visita">
          <div className="visit-progress-heading">
            <div>
              <span className="eyebrow">Progresso</span>
              <strong>{checklistProgress}% do checklist</strong>
            </div>
            <span className={canFinish ? "progress-ready" : "progress-pending"}>
              {canFinish ? "Obrigatorios preenchidos" : `${requiredAnswered}/${requiredItems.length} obrigatorios`}
            </span>
          </div>
          <div className="progress-track" aria-hidden="true">
            <span style={{ width: checklistProgress + "%" }} />
          </div>
        </section>
      )}

      {visit.status === "EM_EXECUCAO" && (
        <nav className="visit-step-nav" aria-label="Etapas da visita">
          {[
            ["visit-measurements", "1", "Medicoes"],
            ["visit-evidence", "2", "Evidencias"],
            ["visit-checklist", "3", "Checklist"],
            ["visit-occurrence", "4", "Ocorrencia"],
            ["visit-materials", "5", "Materiais"],
          ].map(([target, number, label]) => (
            <button
              key={target}
              onClick={() => document.getElementById(target)?.scrollIntoView({ behavior: "smooth", block: "start" })}
            >
              <span>{number}</span>
              <strong>{label}</strong>
            </button>
          ))}
        </nav>
      )}

      {visit.status === "PROGRAMADA" && (
        <button
          className="primary-button action-wide"
          disabled={busy}
          onClick={() => void onCommand(visit, "start")}
        >
          Iniciar visita
        </button>
      )}

      {["AGUARDANDO_REVISAO", "REVISADA", "DEVOLVIDA"].includes(visit.status) && (
        <button
          className="secondary-button action-wide"
          disabled={busy}
          onClick={() => void openApiDocument(`/api/v1/reports/visits/${visit.id}.html`)}
        >
          Relatorio da visita
        </button>
      )}

      {visit.status === "EM_EXECUCAO" && (
        <>
          <section id="visit-measurements" className="section-card visit-step-card">
            <div className="visit-step-heading">
              <span className="visit-step-number">1</span>
              <div><span className="eyebrow">Qualidade</span><h2>Medicoes</h2></div>
            </div>
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

          <section id="visit-evidence" className="section-card visit-step-card">
            <div className="visit-step-heading">
              <span className="visit-step-number">2</span>
              <div><span className="eyebrow">Evidencias</span><h2>Fotos e arquivos</h2></div>
            </div>
            <EvidenceCapture onFile={(file) => onEvidence(visit.id, file)} />
          </section>

          <section id="visit-checklist" className="section-card visit-step-card">
            <div className="visit-step-heading">
              <span className="visit-step-number">3</span>
              <div><span className="eyebrow">Checklist</span><h2>Inspecao da estacao</h2></div>
            </div>
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

          <section id="visit-occurrence" className="section-card visit-step-card">
            <div className="visit-step-heading">
              <span className="visit-step-number">4</span>
              <div><span className="eyebrow">Ocorrencia</span><h2>Encontrou algum problema?</h2></div>
            </div>
            <OccurrenceForm visit={visit} />
          </section>

          <section id="visit-materials" className="section-card visit-step-card">
            <div className="visit-step-heading">
              <span className="visit-step-number">5</span>
              <div><span className="eyebrow">Materiais e servicos</span><h2>Precisa solicitar algo?</h2></div>
            </div>
            <VisitMaterialRequestForm visit={visit} />
          </section>

          <div className="visit-finish-bar">
            <div className="visit-finish-status">
              <strong>{canFinish ? "Pronto para finalizar" : "Complete os itens obrigatorios"}</strong>
              <span>{checklistAnswered} de {items.length} item(ns) respondido(s)</span>
            </div>
            <button
              className="primary-button"
              disabled={busy || !canFinish}
              onClick={() => void onCommand(visit, "finish")}
            >
              <CheckCircle2 size={18} />
              Finalizar visita
            </button>
          </div>
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
  const [visits, setVisits] = useState<Visit[]>([]);
  const [stations, setStations] = useState<Station[]>([]);
  const [adminStations, setAdminStations] = useState<AdminStation[]>([]);
  const [clients, setClients] = useState<ClientRecord[]>([]);
  const [developments, setDevelopments] = useState<DevelopmentRecord[]>([]);
  const [assetTypes, setAssetTypes] = useState<AssetTypeRecord[]>([]);
  const [assets, setAssets] = useState<AssetRecord[]>([]);
  const [team, setTeam] = useState<TeamMember[]>([]);
  const [visitPlans, setVisitPlans] = useState<VisitPlan[]>([]);
  const [templates, setTemplates] = useState<ChecklistTemplateSummary[]>([]);
  const [maintenancePlans, setMaintenancePlans] = useState<MaintenancePlan[]>([]);
  const [maintenanceSummary, setMaintenanceSummary] = useState<MaintenanceSummary | null>(null);
  const [alerts, setAlerts] = useState<OperationalAlert[]>([]);
  const [materialRequests, setMaterialRequests] = useState<MaterialRequest[]>([]);
  const [selectedStationId, setSelectedStationId] = useState<string | null>(null);
  const [managementView, setManagementView] = useState<
    "OVERVIEW" | "OPERATIONS" | "REGISTERS" | "CONFIG" | "GOVERNANCE"
  >("OVERVIEW");
  const [busy, setBusy] = useState(false);
  const [notice, setNotice] = useState<string | null>(null);

  async function load() {
    setBusy(true);
    try {
      const [
        summary,
        orders,
        occurrenceList,
        visitList,
        stationList,
        clientList,
        developmentList,
        assetTypeList,
        assetList,
        teamList,
        planList,
        templateList,
        maintenancePlanList,
        maintenanceOverview,
        alertList,
        materialRequestList,
      ] = await Promise.all([
        api<DashboardOverview>("/api/v1/dashboard/overview"),
        api<WorkOrder[]>("/api/v1/work-orders?limit=100"),
        api<Occurrence[]>("/api/v1/occurrences?limit=100"),
        api<Visit[]>("/api/v1/visits?limit=200"),
        api<AdminStation[]>("/api/v1/stations?limit=500"),
        api<ClientRecord[]>("/api/v1/clients?limit=500"),
        api<DevelopmentRecord[]>("/api/v1/developments?limit=500"),
        api<AssetTypeRecord[]>("/api/v1/asset-types?limit=500"),
        api<AssetRecord[]>("/api/v1/assets?limit=1000"),
        api<TeamMember[]>("/api/v1/team?active_only=true"),
        api<VisitPlan[]>("/api/v1/visit-plans?active_only=false"),
        api<ChecklistTemplateSummary[]>("/api/v1/checklist-templates"),
        api<MaintenancePlan[]>("/api/v1/maintenance/plans?active_only=false"),
        api<MaintenanceSummary>("/api/v1/maintenance/summary"),
        api<OperationalAlert[]>("/api/v1/alerts"),
        api<MaterialRequest[]>("/api/v1/material-requests?limit=500"),
      ]);
      setOverview(summary);
      setWorkOrders(orders);
      setOccurrences(occurrenceList);
      setVisits(visitList);
      setReviews(visitList.filter((visit) => visit.status === "AGUARDANDO_REVISAO"));
      setAdminStations(stationList);
      setStations(
        stationList.map((station) => ({
          id: station.id,
          name: station.name,
          code: station.code,
          station_type: station.station_type,
        })),
      );
      setClients(clientList);
      setDevelopments(developmentList);
      setAssetTypes(assetTypeList);
      setAssets(assetList);
      setTeam(teamList);
      setVisitPlans(planList);
      setTemplates(templateList);
      setMaintenancePlans(maintenancePlanList);
      setMaintenanceSummary(maintenanceOverview);
      setAlerts(alertList);
      setMaterialRequests(materialRequestList);
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

  async function generateAgenda() {
    setBusy(true);
    try {
      const result = await api<{
        generated: number;
        already_existing: number;
        plans_processed: number;
      }>("/api/v1/visit-plans/generate", {
        method: "POST",
        body: JSON.stringify({ horizon_days: 30 }),
      });
      setNotice(
        result.generated > 0
          ? `${result.generated} visita(s) adicionada(s) aos proximos 30 dias.`
          : "Agenda ja estava atualizada para os proximos 30 dias.",
      );
      await load();
    } catch {
      setNotice("Nao foi possivel gerar a agenda.");
      setBusy(false);
    }
  }

  const stationMap = new Map(stations.map((station) => [station.id, station]));
  const teamMap = new Map(team.map((member) => [member.membership_id, member]));
  const now = Date.now();
  const sortedOrders = [...workOrders].sort(
    (a, b) => new Date(a.sla_due_at).getTime() - new Date(b.sla_due_at).getTime(),
  );
  const overdueOrders = overview?.overdue_work_orders ?? 0;
  const criticalOrders = overview?.critical_work_orders ?? 0;
  const waitingReview = overview?.visits_waiting_review ?? 0;
  const attentionCount = overdueOrders + criticalOrders + waitingReview;
  const operationHealthy = attentionCount === 0 && alerts.length === 0;
  const startOfToday = new Date();
  startOfToday.setHours(0, 0, 0, 0);
  const endOfToday = new Date(startOfToday);
  endOfToday.setDate(endOfToday.getDate() + 1);
  const endOfWeek = new Date(startOfToday);
  endOfWeek.setDate(endOfWeek.getDate() + 7);
  const scheduledVisits = visits
    .filter((visit) => !["REVISADA", "CANCELADA"].includes(visit.status))
    .sort((a, b) => new Date(a.scheduled_for).getTime() - new Date(b.scheduled_for).getTime());
  const todayVisits = scheduledVisits.filter((visit) => {
    const time = new Date(visit.scheduled_for).getTime();
    return time >= startOfToday.getTime() && time < endOfToday.getTime();
  });
  const overdueVisits = scheduledVisits.filter(
    (visit) =>
      visit.status === "PROGRAMADA" &&
      new Date(visit.scheduled_for).getTime() < startOfToday.getTime(),
  );
  const nextSevenDaysVisits = scheduledVisits.filter((visit) => {
    const time = new Date(visit.scheduled_for).getTime();
    return time >= startOfToday.getTime() && time < endOfWeek.getTime();
  });

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

      <nav className="management-nav" aria-label="Areas do ERP">
        {[
          { value: "OVERVIEW", label: "Visao geral", Icon: LayoutDashboard },
          { value: "OPERATIONS", label: "Operacao", Icon: Activity },
          { value: "REGISTERS", label: "Cadastros", Icon: Database },
          { value: "CONFIG", label: "Configuracao", Icon: Settings2 },
          { value: "GOVERNANCE", label: "Governanca", Icon: Shield },
        ].map(({ value, label, Icon }) => (
          <button
            key={value}
            className={managementView === value ? "management-nav-item active" : "management-nav-item"}
            onClick={() => {
              setManagementView(value as typeof managementView);
              if (value !== "REGISTERS") setSelectedStationId(null);
            }}
          >
            <Icon size={16} strokeWidth={2} />
            <span>{label}</span>
          </button>
        ))}
      </nav>

      {managementView === "OVERVIEW" && (
        <>
      <section className={operationHealthy ? "command-hero command-hero-healthy" : "command-hero"}>
        <div className="command-hero-main">
          <div className="command-hero-icon">
            {operationHealthy ? <ShieldCheck size={22} /> : <Sparkles size={22} />}
          </div>
          <div>
            <span className="eyebrow">Resumo executivo</span>
            <h2>{operationHealthy ? "Operacao sob controle" : attentionCount + " ponto(s) pedem atencao"}</h2>
            <p>
              {operationHealthy
                ? "Sem excecoes criticas agora. Continue acompanhando a agenda e a manutencao preventiva."
                : "Priorize SLA vencido, OS critica e visitas aguardando revisao antes das tarefas de rotina."}
            </p>
          </div>
        </div>
        <div className="command-hero-actions">
          <button className="primary-button" onClick={() => setManagementView("OPERATIONS")}>
            Abrir operacao
            <ArrowRight size={16} />
          </button>
          <button className="secondary-button" onClick={() => void load()} disabled={busy}>
            <RefreshCw size={16} className={busy ? "spin" : ""} />
            Atualizar agora
          </button>
        </div>
      </section>

      <section className="attention-strip" aria-label="Resumo de pendencias">
        <button className={overdueOrders > 0 ? "attention-item attention-danger" : "attention-item"} onClick={() => setManagementView("OPERATIONS")}>
          <AlertTriangle size={17} />
          <span><strong>{overdueOrders}</strong> SLA vencido(s)</span>
          <ArrowRight size={15} />
        </button>
        <button className={criticalOrders > 0 ? "attention-item attention-warning" : "attention-item"} onClick={() => setManagementView("OPERATIONS")}>
          <ShieldCheck size={17} />
          <span><strong>{criticalOrders}</strong> OS critica(s)</span>
          <ArrowRight size={15} />
        </button>
        <button className={waitingReview > 0 ? "attention-item attention-info" : "attention-item"} onClick={() => setManagementView("OVERVIEW")}>
          <Clock3 size={17} />
          <span><strong>{waitingReview}</strong> para revisar</span>
          <ArrowRight size={15} />
        </button>
      </section>

      <InboxPanel />

      <section className="quick-actions">
        <button
          className="secondary-button"
          onClick={() => void downloadApi("/api/v1/reports/visits.csv", "visitas.csv")}
        >
          Exportar visitas
        </button>
        <button
          className="secondary-button"
          onClick={() => void downloadApi("/api/v1/reports/work-orders.csv", "ordens-servico.csv")}
        >
          Exportar OS
        </button>
        <button
          className="secondary-button"
          onClick={() => void downloadApi("/api/v1/reports/maintenance.csv", "manutencao-preventiva.csv")}
        >
          Exportar manutencao
        </button>
      </section>

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

      <section className="section-card alert-center">
        <div className="section-heading">
          <div>
            <span className="eyebrow">Atencao</span>
            <h2>Alertas operacionais</h2>
          </div>
          <span className="status">{alerts.length}</span>
        </div>
        <div className="ops-list">
          {alerts.slice(0, 12).map((alert) => (
            <div className="ops-row" key={alert.kind + "-" + alert.entity_id}>
              <div>
                <strong>{alert.title}</strong>
                <span>{alert.message}</span>
              </div>
              <div className="ops-meta">
                <span className={"priority priority-" + alert.severity.toLowerCase()}>
                  {alert.severity}
                </span>
                {alert.due_at && (
                  <span className="sla">
                    {new Intl.DateTimeFormat("pt-BR", {
                      dateStyle: "short",
                      timeStyle: "short",
                    }).format(new Date(alert.due_at))}
                  </span>
                )}
              </div>
            </div>
          ))}
          {alerts.length === 0 && <div className="empty-state">Nenhum alerta operacional.</div>}
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

        </>
      )}

      {managementView === "CONFIG" && (
        <>
      <div className="management-grid">
        <section className="section-card">
          <div className="section-heading">
            <div>
              <span className="eyebrow">Planejamento</span>
              <h2>Planos de visita</h2>
            </div>
            <button
              className="small-button"
              disabled={busy}
              onClick={() => void generateAgenda()}
            >
              <RefreshCw size={15} />
              Gerar 30 dias
            </button>
          </div>
          <div className="ops-list">
            {visitPlans.slice(0, 12).map((plan) => (
              <div className="ops-row" key={plan.id}>
                <div>
                  <strong>{stationMap.get(plan.station_id)?.name ?? "Estacao"}</strong>
                  <span>
                    A cada {plan.frequency_days} dia(s) · {teamMap.get(plan.technician_membership_id)?.name ?? "Tecnico"}
                  </span>
                </div>
                <span className={plan.is_active ? "status status-revisada" : "status"}>
                  {plan.is_active ? "Ativo" : "Pausado"}
                </span>
              </div>
            ))}
            {visitPlans.length === 0 && (
              <div className="empty-state">Nenhum plano recorrente cadastrado.</div>
            )}
          </div>
          <VisitPlanForm
            stations={stations}
            team={team}
            templates={templates}
            onCreated={load}
          />
        </section>

        <section className="section-card">
          <span className="eyebrow">Equipe</span>
          <h2>Tecnicos e manutencao</h2>
          <div className="ops-list">
            {team
              .filter((member) => ["TECNICO", "MANUTENCAO"].includes(member.role))
              .map((member) => (
                <div className="ops-row" key={member.membership_id}>
                  <div>
                    <strong>{member.name}</strong>
                    <span>{member.email}</span>
                  </div>
                  <span className="status">{member.role}</span>
                </div>
              ))}
          </div>
          {["ADMIN", "SUPERADMIN"].includes(me.role) && (
            <TeamMemberForm onCreated={load} />
          )}
        </section>
      </div>

        </>
      )}

      {managementView === "REGISTERS" && (
        <>
      <OperationalAdmin
        clients={clients}
        developments={developments}
        stations={adminStations}
        assetTypes={assetTypes}
        assets={assets}
        onChanged={load}
        onOpenStation={setSelectedStationId}
      />

      {selectedStationId && (
        <StationOverview
          stationId={selectedStationId}
          onClose={() => setSelectedStationId(null)}
        />
      )}

        </>
      )}

      {managementView === "CONFIG" && (
        <>
          <ChecklistAdmin templates={templates} onChanged={load} />
          {["SUPERADMIN", "ADMIN"].includes(me.role) && (
            <ClientAccessAdmin clients={clients} team={team} />
          )}
          <AccountSettings />
        </>
      )}

      {managementView === "OPERATIONS" && (
        <>
      <section className="section-card agenda-command">
        <div className="section-heading">
          <div>
            <span className="eyebrow">Agenda operacional</span>
            <h2>Proximas visitas</h2>
            <p className="section-copy">Priorize atrasos e organize a equipe sem perder o contexto da operacao.</p>
          </div>
          <button className="secondary-button" onClick={() => setManagementView("CONFIG")}>
            <CalendarDays size={16} />
            Planejar agenda
          </button>
        </div>

        <div className="agenda-summary">
          <div className={overdueVisits.length ? "agenda-summary-item agenda-summary-danger" : "agenda-summary-item"}>
            <strong>{overdueVisits.length}</strong>
            <span>Atrasadas</span>
          </div>
          <div className="agenda-summary-item">
            <strong>{todayVisits.length}</strong>
            <span>Hoje</span>
          </div>
          <div className="agenda-summary-item">
            <strong>{nextSevenDaysVisits.length}</strong>
            <span>Proximos 7 dias</span>
          </div>
        </div>

        <div className="agenda-timeline">
          {scheduledVisits.slice(0, 16).map((visit) => {
            const scheduled = new Date(visit.scheduled_for);
            const isOverdue =
              visit.status === "PROGRAMADA" && scheduled.getTime() < startOfToday.getTime();
            const technician = teamMap.get(visit.technician_membership_id);
            return (
              <div className={isOverdue ? "agenda-row agenda-row-overdue" : "agenda-row"} key={visit.id}>
                <div className="agenda-date">
                  <span>{new Intl.DateTimeFormat("pt-BR", { weekday: "short" }).format(scheduled).replace(".", "")}</span>
                  <strong>{new Intl.DateTimeFormat("pt-BR", { day: "2-digit" }).format(scheduled)}</strong>
                  <small>{new Intl.DateTimeFormat("pt-BR", { month: "short" }).format(scheduled).replace(".", "")}</small>
                </div>
                <div className="agenda-main">
                  <div>
                    <strong>{stationMap.get(visit.station_id)?.name ?? "Estacao"}</strong>
                    <span>
                      {new Intl.DateTimeFormat("pt-BR", { hour: "2-digit", minute: "2-digit" }).format(scheduled)}
                      {" · "}
                      {technician?.name ?? "Sem tecnico"}
                    </span>
                  </div>
                  <div className="agenda-meta">
                    {isOverdue && <span className="sla overdue">Atrasada</span>}
                    <span className={"status status-" + visit.status.toLowerCase()}>
                      {statusLabel(visit.status)}
                    </span>
                  </div>
                </div>
              </div>
            );
          })}
          {scheduledVisits.length === 0 && (
            <div className="empty-state">
              Agenda sem visitas pendentes. Gere o proximo ciclo em Configuracao.
            </div>
          )}
        </div>
      </section>

      <MaterialRequestsAdmin
        requests={materialRequests}
        stations={adminStations}
        onChanged={load}
      />

      <WorkOrdersAdmin
        orders={workOrders}
        occurrences={occurrences}
        stations={adminStations}
        assets={assets}
        team={team}
        onChanged={load}
      />

      <MaintenanceAdmin
        plans={maintenancePlans}
        summary={maintenanceSummary}
        assets={assets}
        stations={adminStations}
        team={team}
        onChanged={load}
      />

        </>
      )}

      {managementView === "GOVERNANCE" && (
        <>
          <section className="quick-actions">
            <button
              className="secondary-button"
              onClick={() => void downloadApi("/api/v1/reports/visits.csv", "visitas.csv")}
            >
              Exportar visitas
            </button>
            <button
              className="secondary-button"
              onClick={() => void downloadApi("/api/v1/reports/work-orders.csv", "ordens-servico.csv")}
            >
              Exportar OS
            </button>
            <button
              className="secondary-button"
              onClick={() => void downloadApi("/api/v1/reports/maintenance.csv", "manutencao-preventiva.csv")}
            >
              Exportar manutencao
            </button>
          </section>
          {["SUPERADMIN", "ADMIN", "GESTOR"].includes(me.role) && (
            <AuditViewer team={team} />
          )}
          {["SUPERADMIN", "ADMIN"].includes(me.role) && <IntegrationSettings />}
          {["SUPERADMIN", "ADMIN"].includes(me.role) && (
            <LegacyMigrationAdmin stations={adminStations} team={team} />
          )}
        </>
      )}

      {managementView === "OVERVIEW" && (
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
      )}
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
          : "Fotos sao otimizadas automaticamente. Videos curtos ou PDF de ate 50 MB."}
      </p>
    </div>
  );
}


function VisitPlanForm({
  stations,
  team,
  templates,
  onCreated,
}: {
  stations: Station[];
  team: TeamMember[];
  templates: ChecklistTemplateSummary[];
  onCreated: () => Promise<void>;
}) {
  const fieldTeam = team.filter((member) =>
    ["TECNICO", "MANUTENCAO"].includes(member.role),
  );
  const [stationId, setStationId] = useState("");
  const [technicianId, setTechnicianId] = useState("");
  const [templateId, setTemplateId] = useState("");
  const [frequencyDays, setFrequencyDays] = useState("7");
  const [startAt, setStartAt] = useState("");
  const [feedback, setFeedback] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function submit() {
    if (!stationId || !technicianId || !startAt) {
      setFeedback("Selecione estacao, tecnico e inicio.");
      return;
    }
    setBusy(true);
    try {
      await api("/api/v1/visit-plans", {
        method: "POST",
        body: JSON.stringify({
          station_id: stationId,
          technician_membership_id: technicianId,
          checklist_template_id: templateId || null,
          frequency_days: Number(frequencyDays),
          start_at: new Date(startAt).toISOString(),
        }),
      });
      setFeedback("Plano criado.");
      setStationId("");
      setTechnicianId("");
      setTemplateId("");
      setStartAt("");
      await onCreated();
    } catch {
      setFeedback("Nao foi possivel criar o plano.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="compact-form">
      <h3>Novo plano</h3>
      <div className="compact-form-grid">
        <label>
          Estacao
          <select value={stationId} onChange={(event) => setStationId(event.target.value)}>
            <option value="">Selecione</option>
            {stations.map((station) => (
              <option key={station.id} value={station.id}>{station.name}</option>
            ))}
          </select>
        </label>
        <label>
          Tecnico
          <select value={technicianId} onChange={(event) => setTechnicianId(event.target.value)}>
            <option value="">Selecione</option>
            {fieldTeam.map((member) => (
              <option key={member.membership_id} value={member.membership_id}>
                {member.name} · {member.role}
              </option>
            ))}
          </select>
        </label>
        <label>
          Checklist
          <select value={templateId} onChange={(event) => setTemplateId(event.target.value)}>
            <option value="">Sem checklist</option>
            {templates.map((template) => (
              <option key={template.id} value={template.id}>
                {template.name} v{template.version}
              </option>
            ))}
          </select>
        </label>
        <label>
          Frequencia
          <select value={frequencyDays} onChange={(event) => setFrequencyDays(event.target.value)}>
            <option value="1">Diaria</option>
            <option value="7">Semanal</option>
            <option value="14">Quinzenal</option>
            <option value="30">Mensal</option>
          </select>
        </label>
        <label>
          Primeira visita
          <input
            type="datetime-local"
            value={startAt}
            onChange={(event) => setStartAt(event.target.value)}
          />
        </label>
      </div>
      <button className="small-button" disabled={busy} onClick={() => void submit()}>
        {busy ? "Criando..." : "Criar plano"}
      </button>
      {feedback && <span className="inline-feedback">{feedback}</span>}
    </div>
  );
}


function TeamMemberForm({ onCreated }: { onCreated: () => Promise<void> }) {
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [role, setRole] = useState("TECNICO");
  const [feedback, setFeedback] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function submit() {
    if (!name.trim() || !email.trim() || password.length < 12) {
      setFeedback("Informe nome, email e senha inicial com pelo menos 12 caracteres.");
      return;
    }
    setBusy(true);
    try {
      await api("/api/v1/team", {
        method: "POST",
        body: JSON.stringify({
          name: name.trim(),
          email: email.trim(),
          password,
          role,
        }),
      });
      setFeedback("Membro adicionado.");
      setName("");
      setEmail("");
      setPassword("");
      await onCreated();
    } catch {
      setFeedback("Nao foi possivel adicionar o membro.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="compact-form">
      <h3>Adicionar membro</h3>
      <div className="compact-form-grid">
        <label>
          Nome
          <input value={name} onChange={(event) => setName(event.target.value)} />
        </label>
        <label>
          Email
          <input
            type="email"
            value={email}
            onChange={(event) => setEmail(event.target.value)}
          />
        </label>
        <label>
          Perfil
          <select value={role} onChange={(event) => setRole(event.target.value)}>
            <option value="TECNICO">Tecnico</option>
            <option value="MANUTENCAO">Manutencao</option>
            <option value="SUPERVISOR">Supervisor</option>
            <option value="GESTOR">Gestor</option>
            <option value="CLIENTE">Cliente</option>
          </select>
        </label>
        <label>
          Senha inicial
          <input
            type="password"
            value={password}
            onChange={(event) => setPassword(event.target.value)}
          />
        </label>
      </div>
      <button className="small-button" disabled={busy} onClick={() => void submit()}>
        {busy ? "Adicionando..." : "Adicionar membro"}
      </button>
      {feedback && <span className="inline-feedback">{feedback}</span>}
    </div>
  );
}


function MaintenanceAdmin({
  plans,
  summary,
  assets,
  stations,
  team,
  onChanged,
}: {
  plans: MaintenancePlan[];
  summary: MaintenanceSummary | null;
  assets: AssetRecord[];
  stations: AdminStation[];
  team: TeamMember[];
  onChanged: () => Promise<void>;
}) {
  const [assetId, setAssetId] = useState("");
  const [memberId, setMemberId] = useState("");
  const [frequencyDays, setFrequencyDays] = useState("30");
  const [nextDueAt, setNextDueAt] = useState("");
  const [instructions, setInstructions] = useState("");
  const [feedback, setFeedback] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const assetMap = new Map(assets.map((item) => [item.id, item]));
  const stationMap = new Map(stations.map((item) => [item.id, item]));
  const memberMap = new Map(team.map((item) => [item.membership_id, item]));
  const fieldTeam = team.filter((item) => ["TECNICO", "MANUTENCAO"].includes(item.role));
  const now = Date.now();

  async function createPlan() {
    if (!assetId || !nextDueAt) {
      setFeedback("Selecione o ativo e informe a primeira manutencao.");
      return;
    }
    setBusy(true);
    try {
      await api("/api/v1/maintenance/plans", {
        method: "POST",
        body: JSON.stringify({
          asset_id: assetId,
          assigned_membership_id: memberId || null,
          maintenance_type: "PREVENTIVA",
          frequency_days: Number(frequencyDays),
          next_due_at: new Date(nextDueAt).toISOString(),
          instructions: instructions.trim() || null,
        }),
      });
      setAssetId("");
      setMemberId("");
      setNextDueAt("");
      setInstructions("");
      setFeedback("Plano preventivo criado.");
      await onChanged();
    } catch {
      setFeedback("Nao foi possivel criar o plano de manutencao.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className="section-card">
      <div className="section-heading">
        <div>
          <span className="eyebrow">Manutencao</span>
          <h2>Preventivas e vencimentos</h2>
        </div>
        <div className="admin-summary">
          <span><strong>{summary?.active_plans ?? 0}</strong> planos</span>
          <span><strong>{summary?.overdue_plans ?? 0}</strong> vencidos</span>
          <span><strong>{summary?.due_next_7_days ?? 0}</strong> proximos 7 dias</span>
        </div>
      </div>

      <div className="admin-panel">
        <div className="admin-list">
          {[...plans]
            .sort((a, b) => new Date(a.next_due_at).getTime() - new Date(b.next_due_at).getTime())
            .map((plan) => {
              const asset = assetMap.get(plan.asset_id);
              const station = asset ? stationMap.get(asset.station_id) : undefined;
              const overdue = plan.is_active && new Date(plan.next_due_at).getTime() < now;
              return (
                <div className="admin-row" key={plan.id}>
                  <div>
                    <strong>{asset?.name ?? "Ativo"}</strong>
                    <span>
                      {(station?.name ?? "Estacao") + " · a cada " + plan.frequency_days + " dias · " +
                        (memberMap.get(plan.assigned_membership_id ?? "")?.name ?? "Sem responsavel")}
                    </span>
                  </div>
                  <span className={overdue ? "sla overdue" : "sla"}>
                    {overdue
                      ? "Vencida"
                      : new Intl.DateTimeFormat("pt-BR", { dateStyle: "short" }).format(new Date(plan.next_due_at))}
                  </span>
                </div>
              );
            })}
          {plans.length === 0 && <div className="empty-state">Nenhum plano preventivo cadastrado.</div>}
        </div>

        <div className="compact-form admin-create-form">
          <h3>Nova preventiva</h3>
          <div className="compact-form-grid">
            <label>
              Ativo
              <select value={assetId} onChange={(event) => setAssetId(event.target.value)}>
                <option value="">Selecione</option>
                {assets.filter((item) => item.is_active).map((item) => (
                  <option key={item.id} value={item.id}>
                    {(stationMap.get(item.station_id)?.name ?? "Estacao") + " · " + item.name}
                  </option>
                ))}
              </select>
            </label>
            <label>
              Responsavel
              <select value={memberId} onChange={(event) => setMemberId(event.target.value)}>
                <option value="">Sem responsavel fixo</option>
                {fieldTeam.map((item) => (
                  <option key={item.membership_id} value={item.membership_id}>{item.name}</option>
                ))}
              </select>
            </label>
            <label>
              Periodicidade
              <select value={frequencyDays} onChange={(event) => setFrequencyDays(event.target.value)}>
                <option value="7">7 dias</option>
                <option value="15">15 dias</option>
                <option value="30">30 dias</option>
                <option value="60">60 dias</option>
                <option value="90">90 dias</option>
                <option value="180">180 dias</option>
                <option value="365">Anual</option>
              </select>
            </label>
            <label>
              Proxima manutencao
              <input type="datetime-local" value={nextDueAt} onChange={(event) => setNextDueAt(event.target.value)} />
            </label>
          </div>
          <label className="full-field">
            Instrucoes
            <textarea
              rows={3}
              value={instructions}
              onChange={(event) => setInstructions(event.target.value)}
              placeholder="Ex.: limpar, lubrificar, conferir rolamentos e registrar evidencia."
            />
          </label>
          <button className="small-button" disabled={busy} onClick={() => void createPlan()}>
            {busy ? "Salvando..." : "Criar preventiva"}
          </button>
          {feedback && <span className="inline-feedback">{feedback}</span>}
        </div>
      </div>
    </section>
  );
}
