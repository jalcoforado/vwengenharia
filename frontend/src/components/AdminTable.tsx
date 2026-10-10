import { useEffect, useRef, useState, type ReactNode } from "react";
import { ArrowUpDown } from "lucide-react";

// Pecas comuns das listas em tabela dos Cadastros (Colaboradores e Responsaveis).

export function initials(name: string): string {
  const words = name.trim().split(/\s+/).filter(Boolean);
  return ((words[0]?.[0] ?? "") + (words[1]?.[0] ?? "")).toUpperCase() || "?";
}

function avatarTone(name: string): number {
  let hash = 0;
  for (const char of name) hash = (hash + char.charCodeAt(0)) % 3;
  return hash;
}

export function Avatar({ name }: { name: string }) {
  return (
    <span className={"collab-avatar collab-avatar-" + avatarTone(name)} aria-hidden="true">
      {initials(name)}
    </span>
  );
}

export function useSort<K extends string>(initial: K) {
  const [sortKey, setSortKey] = useState<K>(initial);
  const [sortAsc, setSortAsc] = useState(true);

  function toggleSort(key: K) {
    if (key === sortKey) setSortAsc(!sortAsc);
    else { setSortKey(key); setSortAsc(true); }
  }

  function sortBy<T extends { name: string }>(items: T[], value: (item: T, key: K) => string): T[] {
    return [...items].sort((a, b) => {
      const result =
        value(a, sortKey).localeCompare(value(b, sortKey), "pt-BR") || a.name.localeCompare(b.name, "pt-BR");
      return sortAsc ? result : -result;
    });
  }

  return { sortKey, sortAsc, toggleSort, sortBy };
}

export function TableHead<K extends string>({
  columns,
  sortKey,
  sortAsc,
  onSort,
}: {
  columns: [K, string, string][];
  sortKey: K;
  sortAsc: boolean;
  onSort: (key: K) => void;
}) {
  return (
    <div className="collab-head" role="row">
      {columns.map(([key, text, className]) => (
        <button
          key={key}
          role="columnheader"
          className={"collab-sort " + className + (sortKey === key ? " active" : "")}
          aria-sort={sortKey === key ? (sortAsc ? "ascending" : "descending") : "none"}
          onClick={() => onSort(key)}
        >
          {text} <ArrowUpDown size={13} />
        </button>
      ))}
      <span role="columnheader" className="collab-col-actions">Ações</span>
    </div>
  );
}

// Formulario recolhivel acima da lista. Abre em "Novo" e em "Editar", rola ate ele e foca o primeiro campo.
export function useFormPanel() {
  const [open, setOpen] = useState(false);
  const [shown, setShown] = useState(0);
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open || !ref.current) return;
    const reduceMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    ref.current.scrollIntoView({ behavior: reduceMotion ? "auto" : "smooth", block: "start" });
    ref.current.querySelector<HTMLElement>("input, select")?.focus({ preventScroll: true });
  }, [open, shown]);

  return {
    open,
    ref,
    show: () => { setOpen(true); setShown((count) => count + 1); },
    hide: () => setOpen(false),
  };
}

type MenuState = { id: string; top: number; right: number } | null;

// Menu "mais acoes" da linha. Fica em position: fixed para nao ser cortado pela rolagem da lista.
export function useRowMenu() {
  const [menu, setMenu] = useState<MenuState>(null);

  useEffect(() => {
    if (!menu) return;
    const close = () => setMenu(null);
    const onPointer = (event: MouseEvent) => {
      if (!(event.target as HTMLElement).closest(".row-menu, .row-menu-trigger")) close();
    };
    const onKey = (event: KeyboardEvent) => { if (event.key === "Escape") close(); };
    window.document.addEventListener("mousedown", onPointer);
    window.document.addEventListener("keydown", onKey);
    window.addEventListener("scroll", close, true);
    window.addEventListener("resize", close);
    return () => {
      window.document.removeEventListener("mousedown", onPointer);
      window.document.removeEventListener("keydown", onKey);
      window.removeEventListener("scroll", close, true);
      window.removeEventListener("resize", close);
    };
  }, [menu]);

  function openMenu(id: string, trigger: HTMLElement) {
    if (menu?.id === id) return setMenu(null);
    const rect = trigger.getBoundingClientRect();
    setMenu({ id, top: rect.bottom + 6, right: window.innerWidth - rect.right });
  }

  return { menu, openMenu, closeMenu: () => setMenu(null) };
}

export type RowMenuItem = { text: string; run: () => void; danger?: boolean };

export function RowMenu({
  menu,
  items,
  busy,
  onClose,
}: {
  menu: NonNullable<MenuState>;
  items: RowMenuItem[];
  busy: boolean;
  onClose: () => void;
}): ReactNode {
  return (
    <div className="row-menu" role="menu" style={{ top: menu.top, right: menu.right }}>
      {items.map((item) => (
        <button
          key={item.text}
          role="menuitem"
          className={item.danger ? "row-menu-danger" : undefined}
          disabled={busy}
          onClick={() => { onClose(); item.run(); }}
        >
          {item.text}
        </button>
      ))}
    </div>
  );
}
