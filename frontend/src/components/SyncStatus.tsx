import { AlertTriangle, Cloud, CloudOff, RefreshCw } from "lucide-react";

import type { SyncQueueSummary } from "../offline/db";
import type { SyncQueueError } from "../lib/useOfflineSync";

export function SyncControl({
  online,
  summary,
  syncing,
  onSync,
}: {
  online: boolean;
  summary: SyncQueueSummary;
  syncing: boolean;
  onSync: () => Promise<void>;
}) {
  const className =
    summary.failed > 0
      ? "sync-control sync-control-error"
      : summary.total > 0
        ? "sync-control sync-control-pending"
        : "sync-control sync-control-ok";

  return (
    <button
      className={className}
      onClick={() => void onSync()}
      disabled={!online || syncing}
      title={
        !online
          ? "Sem conexão. Os dados permanecem salvos no aparelho."
          : summary.failed > 0
            ? "Há itens com falha. Clique para tentar novamente."
            : summary.total > 0
              ? "Clique para sincronizar agora."
              : "Tudo sincronizado."
      }
    >
      <RefreshCw size={15} className={syncing ? "spin" : ""} />
      <span>
        {syncing
          ? "Sincronizando"
          : summary.failed > 0
            ? `${summary.failed} falha(s)`
            : summary.total > 0
              ? `${summary.total} pendente(s)`
              : "Sincronizado"}
      </span>
    </button>
  );
}

export function SyncHealthCard({
  online,
  summary,
  errors,
  syncing,
  onSync,
}: {
  online: boolean;
  summary: SyncQueueSummary;
  errors: SyncQueueError[];
  syncing: boolean;
  onSync: () => Promise<void>;
}) {
  if (online && summary.total === 0) return null;

  return (
    <section className={summary.failed > 0 ? "sync-health-card sync-health-error" : "sync-health-card"}>
      <div className="sync-health-main">
        <div className="sync-health-icon">
          {!online ? <CloudOff size={20} /> : summary.failed > 0 ? <AlertTriangle size={20} /> : <Cloud size={20} />}
        </div>
        <div>
          <strong>
            {!online
              ? "Trabalho offline protegido"
              : summary.failed > 0
                ? "Sincronização precisa de atenção"
                : "Dados aguardando sincronização"}
          </strong>
          <span>
            {summary.commands} operação(oes) · {summary.uploads} arquivo(s)
            {summary.failed > 0 ? ` · ${summary.failed} com falha` : ""}
          </span>
        </div>
      </div>

      {online && (
        <button className="small-button" disabled={syncing} onClick={() => void onSync()}>
          <RefreshCw size={15} className={syncing ? "spin" : ""} />
          {syncing ? "Sincronizando..." : "Tentar agora"}
        </button>
      )}

      {errors.length > 0 && (
        <div className="sync-error-list">
          {errors.slice(0, 4).map((item) => (
            <div className="sync-error-row" key={item.kind + item.id}>
              <span>{item.kind === "upload" ? "Arquivo" : "Operação"}</span>
              <strong>{item.label}</strong>
              <em>{item.error}</em>
            </div>
          ))}
        </div>
      )}
    </section>
  );
}
