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

class VWOfflineDB extends Dexie {
  outbox!: Table<OutboxItem, string>;
  pendingUploads!: Table<PendingUpload, string>;
  cache!: Table<CacheRecord, string>;

  constructor() {
    super("vwengenharia");
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

export const db = new VWOfflineDB();

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
