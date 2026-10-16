import { useCallback, useEffect, useState } from "react";

import {
  outboxCount,
  syncQueueErrors,
  syncQueueSummary,
  type SyncQueueSummary,
} from "../offline/db";
import { syncOutbox } from "./sync";

export type SyncQueueError = {
  id: string;
  kind: "command" | "upload";
  label: string;
  error: string;
  createdAt: string;
};

const EMPTY_SUMMARY: SyncQueueSummary = {
  commands: 0,
  uploads: 0,
  failedCommands: 0,
  failedUploads: 0,
  failed: 0,
  total: 0,
};

export function useOfflineSync() {
  const [summary, setSummary] = useState<SyncQueueSummary>(EMPTY_SUMMARY);
  const [errors, setErrors] = useState<SyncQueueError[]>([]);
  const [syncing, setSyncing] = useState(false);

  const refresh = useCallback(async () => {
    const [count, nextSummary, nextErrors] = await Promise.all([
      outboxCount(),
      syncQueueSummary(),
      syncQueueErrors(),
    ]);
    setSummary({ ...nextSummary, total: count });
    setErrors(nextErrors);
    return nextSummary;
  }, []);

  const syncNow = useCallback(async () => {
    if (!navigator.onLine || syncing) {
      return { synced: 0, summary };
    }
    setSyncing(true);
    try {
      const synced = await syncOutbox();
      const nextSummary = await refresh();
      return { synced, summary: nextSummary };
    } finally {
      setSyncing(false);
    }
  }, [refresh, summary, syncing]);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  return {
    summary,
    errors,
    syncing,
    refresh,
    syncNow,
  };
}
