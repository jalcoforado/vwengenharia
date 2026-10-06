import Dexie, { type Table } from "dexie";

export type OutboxItem = {
  id: string;
  method: "POST" | "PUT" | "PATCH";
  path: string;
  body: unknown;
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
  cache!: Table<CacheRecord, string>;

  constructor() {
    super("vwengenharia");
    this.version(1).stores({
      outbox: "id, createdAt",
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

export async function enqueue(item: OutboxItem) {
  await db.outbox.put(item);
}

export async function outboxCount() {
  return db.outbox.count();
}
