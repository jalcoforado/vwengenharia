import {
  fieldDb,
  type LocalChecklistTemplate,
  type LocalVisit,
  type OutboxCommand,
} from "./db";

export function newClientOperationId(): string {
  return crypto.randomUUID();
}

export async function queueMutation(
  path: string,
  method: OutboxCommand["method"],
  body: Record<string, unknown>,
): Promise<string> {
  const clientOperationId =
    typeof body.client_operation_id === "string"
      ? body.client_operation_id
      : newClientOperationId();

  await fieldDb.outbox.add({
    clientOperationId,
    method,
    path,
    body: { ...body, client_operation_id: clientOperationId },
    createdAt: new Date().toISOString(),
    attempts: 0,
  });
  return clientOperationId;
}

export async function cacheVisits(
  visits: Array<Record<string, unknown>>,
): Promise<void> {
  const now = new Date().toISOString();
  const rows: LocalVisit[] = visits.map((visit) => ({
    id: String(visit.id),
    stationId: String(visit.station_id),
    scheduledFor: String(visit.scheduled_for),
    status: String(visit.status),
    revision: Number(visit.revision ?? 1),
    payload: visit,
    cachedAt: now,
  }));
  await fieldDb.transaction("rw", fieldDb.visits, async () => {
    await fieldDb.visits.bulkPut(rows);
  });
}

export async function cacheChecklistTemplate(
  template: Record<string, unknown>,
): Promise<void> {
  const row: LocalChecklistTemplate = {
    id: String(template.id),
    payload: template,
    cachedAt: new Date().toISOString(),
  };
  await fieldDb.templates.put(row);
}

export interface SyncResult {
  sent: number;
  pending: number;
  stoppedReason?: "offline" | "unauthorized" | "server_error";
}

export async function flushOutbox(
  apiBase: string,
  accessToken: string,
): Promise<SyncResult> {
  if (!navigator.onLine) {
    return { sent: 0, pending: await fieldDb.outbox.count(), stoppedReason: "offline" };
  }

  const commands = await fieldDb.outbox.orderBy("createdAt").toArray();
  let sent = 0;

  for (const command of commands) {
    if (command.id === undefined) continue;

    try {
      const response = await fetch(`${apiBase}${command.path}`, {
        method: command.method,
        headers: {
          Authorization: `Bearer ${accessToken}`,
          "Content-Type": "application/json",
        },
        body: JSON.stringify(command.body),
      });

      if (response.status === 401) {
        return {
          sent,
          pending: await fieldDb.outbox.count(),
          stoppedReason: "unauthorized",
        };
      }

      if (!response.ok) {
        await fieldDb.outbox.update(command.id, {
          attempts: command.attempts + 1,
          lastError: `HTTP ${response.status}`,
        });
        return {
          sent,
          pending: await fieldDb.outbox.count(),
          stoppedReason: "server_error",
        };
      }

      await fieldDb.outbox.delete(command.id);
      sent += 1;
    } catch (error) {
      await fieldDb.outbox.update(command.id, {
        attempts: command.attempts + 1,
        lastError: error instanceof Error ? error.message : "network_error",
      });
      return {
        sent,
        pending: await fieldDb.outbox.count(),
        stoppedReason: "offline",
      };
    }
  }

  return { sent, pending: await fieldDb.outbox.count() };
}
