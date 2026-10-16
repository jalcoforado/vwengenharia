import Dexie, { type Table } from "dexie";

export type OutboxItem = {
  id: string;
  method: "POST" | "PUT" | "PATCH";
  path: string;
  body: unknown;
  createdAt: string;
  lastError?: string;
};

export type PendingUpload = {
  id: string;
  visitId: string;
  filename: string;
  contentType: string;
  sizeBytes: number;
  caption?: string;
  blob: Blob;
  createdAt: string;
  lastError?: string;
};

export type CacheRecord = {
  key: string;
  value: unknown;
  savedAt: string;
};

export type SyncQueueSummary = {
  commands: number;
  uploads: number;
  failedCommands: number;
  failedUploads: number;
  failed: number;
  total: number;
};

// Nome anterior do banco offline. Dados pendentes (outbox/uploads) nos
// aparelhos de campo sao copiados para o banco novo na primeira abertura.
const LEGACY_DB_NAME = "vwengenharia";

class MWOfflineDB extends Dexie {
  outbox!: Table<OutboxItem, string>;
  pendingUploads!: Table<PendingUpload, string>;
  cache!: Table<CacheRecord, string>;

  constructor() {
    super("mwengenharia");
    this.version(1).stores({
      outbox: "id, createdAt",
      cache: "key, savedAt",
    });
    this.version(2).stores({
      outbox: "id, createdAt",
      pendingUploads: "id, visitId, createdAt",
      cache: "key, savedAt",
    });
  }
}

export const db = new MWOfflineDB();

db.on("ready", async () => {
  if (!(await Dexie.exists(LEGACY_DB_NAME))) {
    return;
  }
  const legacy = new Dexie(LEGACY_DB_NAME);
  await legacy.open();
  const names = new Set(legacy.tables.map((table) => table.name));
  const [outbox, uploads, cache] = await Promise.all([
    names.has("outbox") ? legacy.table<OutboxItem, string>("outbox").toArray() : [],
    names.has("pendingUploads")
      ? legacy.table<PendingUpload, string>("pendingUploads").toArray()
      : [],
    names.has("cache") ? legacy.table<CacheRecord, string>("cache").toArray() : [],
  ]);
  await db.transaction("rw", db.outbox, db.pendingUploads, db.cache, async () => {
    await db.outbox.bulkPut(outbox);
    await db.pendingUploads.bulkPut(uploads);
    await db.cache.bulkPut(cache);
  });
  legacy.close();
  await Dexie.delete(LEGACY_DB_NAME);
});

export async function cacheValue(key: string, value: unknown) {
  await db.cache.put({ key, value, savedAt: new Date().toISOString() });
}

export async function readCache<T>(key: string): Promise<T | null> {
  const record = await db.cache.get(key);
  return (record?.value as T | undefined) ?? null;
}

export async function queueUpload(item: PendingUpload) {
  await db.pendingUploads.put(item);
}

export async function outboxCount() {
  const [commands, uploads] = await Promise.all([
    db.outbox.count(),
    db.pendingUploads.count(),
  ]);
  return commands + uploads;
}


export async function syncQueueSummary(): Promise<SyncQueueSummary> {
  const [commands, uploads] = await Promise.all([
    db.outbox.toArray(),
    db.pendingUploads.toArray(),
  ]);
  const failedCommands = commands.filter((item) => Boolean(item.lastError)).length;
  const failedUploads = uploads.filter((item) => Boolean(item.lastError)).length;
  return {
    commands: commands.length,
    uploads: uploads.length,
    failedCommands,
    failedUploads,
    failed: failedCommands + failedUploads,
    total: commands.length + uploads.length,
  };
}

export async function syncQueueErrors(limit = 8) {
  const [commands, uploads] = await Promise.all([
    db.outbox.orderBy("createdAt").reverse().toArray(),
    db.pendingUploads.orderBy("createdAt").reverse().toArray(),
  ]);
  return [
    ...commands
      .filter((item) => item.lastError)
      .map((item) => ({
        id: item.id,
        kind: "command" as const,
        label: item.path,
        error: item.lastError ?? "Falha pendente",
        createdAt: item.createdAt,
      })),
    ...uploads
      .filter((item) => item.lastError)
      .map((item) => ({
        id: item.id,
        kind: "upload" as const,
        label: item.filename,
        error: item.lastError ?? "Upload pendente",
        createdAt: item.createdAt,
      })),
  ]
    .sort((a, b) => b.createdAt.localeCompare(a.createdAt))
    .slice(0, limit);
}
