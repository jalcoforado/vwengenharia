import Dexie, { type Table } from "dexie";

export interface LocalVisit {
  id: string;
  stationId: string;
  scheduledFor: string;
  status: string;
  revision: number;
  payload: Record<string, unknown>;
  cachedAt: string;
}

export interface LocalChecklistTemplate {
  id: string;
  payload: Record<string, unknown>;
  cachedAt: string;
}

export interface OutboxCommand {
  id?: number;
  clientOperationId: string;
  method: "POST" | "PUT" | "PATCH";
  path: string;
  body: Record<string, unknown>;
  createdAt: string;
  attempts: number;
  lastError?: string;
}

class FieldDatabase extends Dexie {
  visits!: Table<LocalVisit, string>;
  templates!: Table<LocalChecklistTemplate, string>;
  outbox!: Table<OutboxCommand, number>;

  constructor() {
    super("vwengenharia-field");
    this.version(1).stores({
      visits: "id,status,scheduledFor,cachedAt",
      templates: "id,cachedAt",
      outbox: "++id,&clientOperationId,createdAt,attempts",
    });
  }
}

export const fieldDb = new FieldDatabase();
