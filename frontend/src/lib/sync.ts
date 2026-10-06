import { api } from "./api";
import { db, type OutboxItem } from "../offline/db";

export async function runOrQueue<T>(
  item: OutboxItem,
  onlineAction: () => Promise<T>,
): Promise<{ queued: boolean; result?: T }> {
  if (!navigator.onLine) {
    await db.outbox.put(item);
    return { queued: true };
  }

  try {
    const result = await onlineAction();
    return { queued: false, result };
  } catch (error) {
    const status =
      typeof error === "object" && error !== null && "status" in error
        ? Number((error as { status: number }).status)
        : 0;
    if (status === 0 || status >= 500) {
      await db.outbox.put(item);
      return { queued: true };
    }
    throw error;
  }
}

export async function syncOutbox(): Promise<number> {
  if (!navigator.onLine) return 0;
  const items = await db.outbox.orderBy("createdAt").toArray();
  let synced = 0;

  for (const item of items) {
    try {
      await api(item.path, {
        method: item.method,
        body: JSON.stringify(item.body),
      });
      await db.outbox.delete(item.id);
      synced += 1;
    } catch (error) {
      const status =
        typeof error === "object" && error !== null && "status" in error
          ? Number((error as { status: number }).status)
          : 0;
      await db.outbox.update(item.id, {
        lastError: status ? `HTTP ${status}` : "Falha de conexao",
      });
      if (status >= 400 && status < 500) break;
    }
  }

  return synced;
}
