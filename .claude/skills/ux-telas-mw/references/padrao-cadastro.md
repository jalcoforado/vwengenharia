# Padrão de tela de cadastro

Referência viva: `frontend/src/components/ContractingPartyAdmin.tsx` (a mais enxuta que segue o
padrão completo). `CollaboratorAdmin.tsx`, `ProcessUnitAdmin.tsx` e os cadastros dentro de
`OperationalAdmin.tsx` seguem o mesmo esqueleto. Leia a referência antes de escrever uma tela nova
e copie a estrutura, não só a aparência.

## Peças compartilhadas (`components/AdminTable.tsx`)

| Peça | Para quê |
| --- | --- |
| `Avatar` | Círculo com as iniciais do nome |
| `useSort<K>(inicial)` | Estado de ordenação e `sortBy(items, valor)` |
| `TableHead` | Cabeçalho ordenável da tabela; recebe `[chave, rótulo, classe]` |
| `useFormPanel()` | `open`, `ref`, `show()`, `hide()`: abre o formulário, rola até ele e foca o primeiro campo |
| `useRowMenu()` + `RowMenu` | Menu ⋮ da linha, posicionado fora da rolagem da lista |

## Esqueleto

```tsx
type SortKey = "name" | "type" | "contact" | "status";
const SORT_COLUMNS: [SortKey, string, string][] = [
  ["name", "Nome", "collab-col-name"],
  ["type", "Tipo", "collab-col-category"],
  ["contact", "Contato", "collab-col-contact"],
  ["status", "Status", "collab-col-status"],
];

export default function CoisaAdmin({ items, onChanged }: Props) {
  const [search, setSearch] = useState("");
  const [editingId, setEditingId] = useState<string | null>(null);
  const [expandedId, setExpandedId] = useState<string | null>(null); // consulta aberta
  const [feedback, setFeedback] = useState<string | null>(null);     // dentro do formulário
  const [rowFeedback, setRowFeedback] = useState<string | null>(null); // acima da lista
  const [busy, setBusy] = useState(false);
  const { sortKey, sortAsc, toggleSort, sortBy } = useSort<SortKey>("name");
  const { menu, openMenu, closeMenu } = useRowMenu();
  const panel = useFormPanel();

  // Busca por texto e, com 3+ dígitos, por números sem pontuação (CPF/CNPJ, telefone).
  const term = search.trim().toLowerCase();
  const termDigits = term.replace(/\D/g, "");
  const visible = items.filter(/* ... */);
  const sorted = sortBy(visible, (item, key) => /* valor de ordenação por coluna */ item.name);

  function openNew() { resetForm(); setFeedback(null); panel.show(); }
  function closeForm() { resetForm(); setFeedback(null); panel.hide(); }
  function startEdit(item: Coisa) { /* preenche os campos */ setFeedback(null); panel.show(); }

  async function save() {
    // 1. valida na tela, campo a campo, com mensagem que diz o que falta
    // 2. envia (POST novo / PATCH edição) com documento normalizado e telefone formatado
    // 3. edição: setRowFeedback("... atualizado.") e closeForm()
    //    novo: resetForm() e setFeedback("... cadastrado. O formulário segue aberto para o próximo.")
    // 4. erro: 409 → duplicado; 422 → "Confira os dados"; outros → mensagem genérica
  }

  return (
    <div className="admin-stack">
      {panel.open && (
        <div className="compact-form admin-create-form" ref={panel.ref}>
          <h3 className="form-title">{/* ícone + "Novo ..." ou "Editar ..." */}</h3>
          <div className="compact-form-grid">{/* labels com campos; form-span-2 para largos */}</div>
          <p className="required-hint"><b className="required-mark">*</b> Obrigatório.</p>
          <div className="admin-actions form-submit">
            <button className="primary-button" onClick={() => void save()}>...</button>
            <button className="text-button" onClick={closeForm}>{editingId ? "Cancelar" : "Fechar"}</button>
          </div>
          {feedback && <span className="inline-feedback">{feedback}</span>}
        </div>
      )}
      <div className="client-list-column">
        <div className="admin-toolbar">
          <label className="search-field">{/* <Search /> + input com aria-label */}</label>
          {!panel.open && <button className="primary-button" onClick={openNew}>Novo ...</button>}
        </div>
        {rowFeedback && <span className="inline-feedback" role="status">{rowFeedback}</span>}
        <div className="admin-list collab-table" role="table" aria-label="...">
          <TableHead columns={SORT_COLUMNS} sortKey={sortKey} sortAsc={sortAsc} onSort={toggleSort} />
          {sorted.map((item) => (
            <div className="client-entry" key={item.id}>
              <div className={item.is_active ? "collab-row" : "collab-row collab-row-inactive"} role="row">
                {/* .collab-person (Avatar + nome + resumo), .collab-col-category (chip),
                    .collab-col-contact, .collab-col-status, .collab-actions (olho, lápis, ⋮) */}
              </div>
              {expandedId === item.id && <CoisaDetails item={item} />}
            </div>
          ))}
          {/* vazio: "Nenhum ... cadastrado." com o próximo passo
              sem resultado: "Nenhum ... encontrado para "x". Confira a grafia ou limpe a busca." */}
        </div>
        {menu && menuItem && <RowMenu menu={menu} items={menuItems} busy={busy} onClose={closeMenu} />}
      </div>
    </div>
  );
}
```

## Largura das colunas

As colunas vêm de `.admin-stack .collab-head/.collab-row` em `styles.css`:

- padrão: nome flexível + 150 + 150 + 96 + 114 px (até 3 ícones de ação);
- `.collab-table-wide`: coluna de tipo mais larga (200 px) para rótulos longos;
- `.collab-table-actions-4`: coluna de ações para 4 ícones.

Abaixo de 820 px a coluna de contato some; abaixo de 650 px a linha vira nome + ações. Ao criar
uma variação, siga o mesmo esquema de classes modificadoras em vez de mexer nas regras base.

## Consulta somente leitura

Componente separado (ex.: `PartyDetails.tsx`, `DevelopmentDetails.tsx`), renderizado logo abaixo
da linha:

```tsx
<div className="client-contacts development-details">
  <section>
    <span className="eyebrow">Título da seção</span>
    <dl className="detail-grid">
      <Field label="Nome" value={item.name} />
      {/* Field mostra "—" quando o valor é vazio */}
    </dl>
  </section>
  <section>{/* listas relacionadas em .client-contact-row, com etiquetas de status */}</section>
</div>
```

Carregue dados extras dentro da consulta (com `useEffect` e indicação de "Carregando...") em vez
de pesar a lista principal.
