import { useEffect, useMemo, useState } from "react";

import { api } from "../lib/api";
import type { MaterialRequest } from "./Materials";
import type { AdminStation } from "./OperationalAdmin";

type InventoryItem = {
  id: string;
  code: string;
  name: string;
  unit: string;
  current_quantity: string | number;
  minimum_quantity: string | number;
  notes: string | null;
  is_active: boolean;
};

type InventoryMovement = {
  id: string;
  inventory_item_id: string;
  movement_type: string;
  quantity: string | number;
  balance_after: string | number;
  unit_cost: string | number | null;
  station_id: string | null;
  material_request_id: string | null;
  occurred_at: string;
  notes: string | null;
};

type InventorySummary = {
  active_items: number;
  low_stock_items: number;
  zero_stock_items: number;
  total_quantity: string | number;
};

export default function InventoryAdmin({
  requests,
  stations,
  onChanged,
}: {
  requests: MaterialRequest[];
  stations: AdminStation[];
  onChanged: () => Promise<void>;
}) {
  const [items, setItems] = useState<InventoryItem[]>([]);
  const [movements, setMovements] = useState<InventoryMovement[]>([]);
  const [summary, setSummary] = useState<InventorySummary | null>(null);
  const [code, setCode] = useState("");
  const [name, setName] = useState("");
  const [unit, setUnit] = useState("un");
  const [minimum, setMinimum] = useState("0");
  const [movementItemId, setMovementItemId] = useState("");
  const [movementType, setMovementType] = useState("ENTRADA");
  const [movementQuantity, setMovementQuantity] = useState("");
  const [movementCost, setMovementCost] = useState("");
  const [movementNotes, setMovementNotes] = useState("");
  const [issueSelection, setIssueSelection] = useState<Record<string, string>>({});
  const [busy, setBusy] = useState(false);
  const [feedback, setFeedback] = useState<string | null>(null);

  const stationMap = useMemo(
    () => new Map(stations.map((station) => [station.id, station])),
    [stations],
  );
  const itemMap = useMemo(
    () => new Map(items.map((item) => [item.id, item])),
    [items],
  );

  async function load() {
    try {
      const [itemList, movementList, inventorySummary] = await Promise.all([
        api<InventoryItem[]>("/api/v1/inventory/items?active_only=false"),
        api<InventoryMovement[]>("/api/v1/inventory/movements?limit=100"),
        api<InventorySummary>("/api/v1/inventory/summary"),
      ]);
      setItems(itemList);
      setMovements(movementList);
      setSummary(inventorySummary);
    } catch {
      setFeedback("Nao foi possivel carregar o estoque.");
    }
  }

  useEffect(() => {
    void load();
  }, []);

  async function createItem() {
    if (code.trim().length < 1 || name.trim().length < 2 || unit.trim().length < 1) {
      setFeedback("Informe codigo, nome e unidade.");
      return;
    }
    setBusy(true);
    try {
      await api("/api/v1/inventory/items", {
        method: "POST",
        body: JSON.stringify({
          code: code.trim(),
          name: name.trim(),
          unit: unit.trim(),
          minimum_quantity: Number(minimum.replace(",", ".")) || 0,
        }),
      });
      setCode("");
      setName("");
      setMinimum("0");
      setFeedback("Item de estoque criado.");
      await load();
      await onChanged();
    } catch {
      setFeedback("Nao foi possivel criar o item. Verifique se o codigo ja existe.");
    } finally {
      setBusy(false);
    }
  }

  async function createMovement() {
    if (!movementItemId || !movementQuantity) {
      setFeedback("Selecione o item e informe a quantidade.");
      return;
    }
    setBusy(true);
    try {
      await api("/api/v1/inventory/movements", {
        method: "POST",
        body: JSON.stringify({
          inventory_item_id: movementItemId,
          movement_type: movementType,
          quantity: Number(movementQuantity.replace(",", ".")),
          unit_cost: movementCost ? Number(movementCost.replace(",", ".")) : null,
          occurred_at: new Date().toISOString(),
          notes: movementNotes.trim() || null,
        }),
      });
      setMovementQuantity("");
      setMovementCost("");
      setMovementNotes("");
      setFeedback("Movimento registrado.");
      await load();
      await onChanged();
    } catch {
      setFeedback("Movimento recusado. Confira o saldo e os dados informados.");
    } finally {
      setBusy(false);
    }
  }

  async function issueRequest(request: MaterialRequest) {
    const itemId = issueSelection[request.id] || request.inventory_item_id || "";
    if (!itemId) {
      setFeedback("Selecione o item do estoque para atender a solicitacao.");
      return;
    }
    setBusy(true);
    try {
      await api("/api/v1/material-requests/" + request.id + "/issue", {
        method: "POST",
        body: JSON.stringify({
          inventory_item_id: itemId,
          quantity: request.quantity == null ? null : Number(request.quantity),
          notes: "Baixa realizada pelo cockpit de estoque.",
        }),
      });
      setFeedback("Material baixado e solicitacao atendida.");
      await load();
      await onChanged();
    } catch {
      setFeedback("Nao foi possivel atender pelo estoque. Verifique o saldo disponivel.");
    } finally {
      setBusy(false);
    }
  }

  async function toggleItem(item: InventoryItem) {
    setBusy(true);
    try {
      await api("/api/v1/inventory/items/" + item.id, {
        method: "PATCH",
        body: JSON.stringify({ is_active: !item.is_active }),
      });
      await load();
      await onChanged();
    } catch {
      setFeedback("Nao foi possivel alterar o item.");
    } finally {
      setBusy(false);
    }
  }

  const activeItems = items.filter((item) => item.is_active);
  const materialRequests = requests.filter(
    (request) =>
      request.category === "MATERIAL" &&
      !["ATENDIDA", "CANCELADA"].includes(request.status),
  );

  return (
    <section className="section-card">
      <div className="section-heading">
        <div>
          <span className="eyebrow">Estoque operacional</span>
          <h2>Materiais e consumo</h2>
          <p className="section-copy">
            Saldo auditavel por movimentos. Nenhuma saida pode deixar estoque negativo.
          </p>
        </div>
        <div className="admin-summary">
          <span><strong>{summary?.active_items ?? 0}</strong> itens</span>
          <span><strong>{summary?.low_stock_items ?? 0}</strong> abaixo do minimo</span>
          <span><strong>{summary?.zero_stock_items ?? 0}</strong> zerados</span>
        </div>
      </div>

      <div className="inventory-grid">
        <div>
          <h3>Saldo atual</h3>
          <div className="admin-list">
            {items.map((item) => {
              const quantity = Number(item.current_quantity);
              const minimumQuantity = Number(item.minimum_quantity);
              const low = item.is_active && quantity <= minimumQuantity;
              return (
                <div className="admin-row" key={item.id}>
                  <div>
                    <strong>{item.name}</strong>
                    <span>
                      {item.code} · minimo {minimumQuantity} {item.unit}
                    </span>
                  </div>
                  <div className="admin-actions">
                    <span className={low ? "status inventory-low" : "status status-revisada"}>
                      {quantity} {item.unit}
                    </span>
                    <button className="text-button" disabled={busy} onClick={() => void toggleItem(item)}>
                      {item.is_active ? "Inativar" : "Reativar"}
                    </button>
                  </div>
                </div>
              );
            })}
            {items.length === 0 && <div className="empty-state">Nenhum item de estoque cadastrado.</div>}
          </div>
        </div>

        <div className="inventory-side">
          <div className="compact-form admin-create-form">
            <h3>Novo item</h3>
            <div className="compact-form-grid">
              <label>Codigo<input value={code} onChange={(e) => setCode(e.target.value)} placeholder="CLORO-PAST" /></label>
              <label>Nome<input value={name} onChange={(e) => setName(e.target.value)} placeholder="Pastilha de cloro" /></label>
              <label>Unidade<input value={unit} onChange={(e) => setUnit(e.target.value)} placeholder="un" /></label>
              <label>Estoque minimo<input inputMode="decimal" value={minimum} onChange={(e) => setMinimum(e.target.value)} /></label>
            </div>
            <button className="small-button" disabled={busy} onClick={() => void createItem()}>
              Criar item
            </button>
          </div>

          <div className="compact-form admin-create-form">
            <h3>Registrar movimento</h3>
            <div className="compact-form-grid">
              <label>
                Item
                <select value={movementItemId} onChange={(e) => setMovementItemId(e.target.value)}>
                  <option value="">Selecione</option>
                  {activeItems.map((item) => (
                    <option key={item.id} value={item.id}>{item.name}</option>
                  ))}
                </select>
              </label>
              <label>
                Tipo
                <select value={movementType} onChange={(e) => setMovementType(e.target.value)}>
                  <option value="ENTRADA">Entrada</option>
                  <option value="SAIDA">Saida</option>
                  <option value="AJUSTE_POSITIVO">Ajuste positivo</option>
                  <option value="AJUSTE_NEGATIVO">Ajuste negativo</option>
                </select>
              </label>
              <label>
                Quantidade
                <input inputMode="decimal" value={movementQuantity} onChange={(e) => setMovementQuantity(e.target.value)} />
              </label>
              <label>
                Custo unitario
                <input inputMode="decimal" value={movementCost} onChange={(e) => setMovementCost(e.target.value)} placeholder="Opcional" />
              </label>
            </div>
            <label className="full-field">
              Observacao
              <input value={movementNotes} onChange={(e) => setMovementNotes(e.target.value)} />
            </label>
            <button className="small-button" disabled={busy} onClick={() => void createMovement()}>
              Registrar
            </button>
          </div>
        </div>
      </div>

      <div className="inventory-requests">
        <h3>Atender solicitacoes com estoque</h3>
        <div className="ops-list">
          {materialRequests.slice(0, 20).map((request) => (
            <div className="ops-row" key={request.id}>
              <div>
                <strong>{request.item_name}</strong>
                <span>
                  {(stationMap.get(request.station_id)?.name ?? "Estacao") +
                    (request.quantity ? " · " + request.quantity + " " + (request.unit ?? "") : "")}
                </span>
              </div>
              <div className="inventory-issue">
                <select
                  value={issueSelection[request.id] || request.inventory_item_id || ""}
                  onChange={(event) =>
                    setIssueSelection((current) => ({
                      ...current,
                      [request.id]: event.target.value,
                    }))
                  }
                >
                  <option value="">Item do estoque</option>
                  {activeItems.map((item) => (
                    <option key={item.id} value={item.id}>
                      {item.name} · {item.current_quantity} {item.unit}
                    </option>
                  ))}
                </select>
                <button className="small-button" disabled={busy} onClick={() => void issueRequest(request)}>
                  Baixar e atender
                </button>
              </div>
            </div>
          ))}
          {materialRequests.length === 0 && (
            <div className="empty-state">Nenhuma solicitacao de material pendente.</div>
          )}
        </div>
      </div>

      <div className="inventory-history">
        <h3>Ultimos movimentos</h3>
        <div className="admin-list">
          {movements.slice(0, 20).map((movement) => (
            <div className="admin-row" key={movement.id}>
              <div>
                <strong>{itemMap.get(movement.inventory_item_id)?.name ?? "Item"}</strong>
                <span>
                  {movement.movement_type.replaceAll("_", " ")} · {movement.quantity} · saldo {movement.balance_after}
                </span>
              </div>
              <span className="sla">
                {new Intl.DateTimeFormat("pt-BR", {
                  dateStyle: "short",
                  timeStyle: "short",
                }).format(new Date(movement.occurred_at))}
              </span>
            </div>
          ))}
        </div>
      </div>

      {feedback && <span className="inline-feedback">{feedback}</span>}
    </section>
  );
}
