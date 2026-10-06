import { api } from "./api";
import { db, type OutboxItem } from "../offline/db";

type PresignResponse = {
  attachment: { id: string };
  upload_url: string;
  expires_in: number;
  required_headers: Record<string, string>;
};

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

async function syncCommands(): Promise<number> {
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
      if (!navigator.onLine) break;
    }
  }

  return synced;
}

async function syncUploads(): Promise<number> {
  const uploads = await db.pendingUploads.orderBy("createdAt").toArray();
  let synced = 0;

  for (const item of uploads) {
    try {
      const presign = await api<PresignResponse>(
        `/api/v1/visits/${item.visitId}/attachments/presign`,
        {
          method: "POST",
          body: JSON.stringify({
            filename: item.filename,
            content_type: item.contentType,
            size_bytes: item.sizeBytes,
            caption: item.caption ?? null,
            client_operation_id: item.id,
          }),
        },
      );

      const uploadResponse = await fetch(presign.upload_url, {
        method: "PUT",
        headers: presign.required_headers,
        body: item.blob,
      });
      if (!uploadResponse.ok) {
        throw new Error(`storage_upload_${uploadResponse.status}`);
      }

      await api(`/api/v1/attachments/${presign.attachment.id}/complete`, {
        method: "POST",
      });
      await db.pendingUploads.delete(item.id);
      synced += 1;
    } catch (error) {
      const status =
        typeof error === "object" && error !== null && "status" in error
          ? Number((error as { status: number }).status)
          : 0;
      await db.pendingUploads.update(item.id, {
        lastError: status ? `HTTP ${status}` : "Upload pendente",
      });
      if (status >= 400 && status < 500) break;
      if (!navigator.onLine) break;
    }
  }

  return synced;
}

export async function syncOutbox(): Promise<number> {
  if (!navigator.onLine) return 0;
  const commands = await syncCommands();
  const uploads = await syncUploads();
  return commands + uploads;
}
