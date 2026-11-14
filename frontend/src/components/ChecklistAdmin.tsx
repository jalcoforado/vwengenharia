import { useEffect, useState } from "react";

import { api } from "../lib/api";

export type ChecklistTemplate = {
  id: string;
  name: string;
  version: number;
  is_active: boolean;
};

type ChecklistItem = {
  id: string;
  template_id: string;
  code: string;
  label: string;
  answer_type: string;
  required: boolean;
  position: number;
  options_json: string[] | null;
};

type Props = {
  templates: ChecklistTemplate[];
  onChanged: () => Promise<void>;
};

export default function ChecklistAdmin({ templates, onChanged }: Props) {
  const [selectedId, setSelectedId] = useState(templates[0]?.id ?? "");
  const [items, setItems] = useState<ChecklistItem[]>([]);
  const [templateName, setTemplateName] = useState("");
  const [templateVersion, setTemplateVersion] = useState("1");
  const [code, setCode] = useState("");
  const [label, setLabel] = useState("");
  const [answerType, setAnswerType] = useState("BOOLEAN");
  const [required, setRequired] = useState(false);
  const [options, setOptions] = useState("");
  const [feedback, setFeedback] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    if (!selectedId && templates.length) setSelectedId(templates[0].id);
  }, [selectedId, templates]);

  useEffect(() => {
    if (!selectedId) {
      setItems([]);
      return;
    }
    void api<ChecklistItem[]>("/api/v1/checklist-templates/" + selectedId + "/items")
      .then(setItems)
      .catch(() => setFeedback("Não foi possível carregar os itens do checklist."));
  }, [selectedId]);

  async function createTemplate() {
    if (templateName.trim().length < 2) {
      setFeedback("Informe o nome do checklist.");
      return;
    }
    setBusy(true);
    try {
      const created = await api<ChecklistTemplate>("/api/v1/checklist-templates", {
        method: "POST",
        body: JSON.stringify({
          name: templateName.trim(),
          version: Number(templateVersion),
        }),
      });
      setTemplateName("");
      setTemplateVersion("1");
      setSelectedId(created.id);
      setFeedback("Checklist criado.");
      await onChanged();
    } catch {
      setFeedback("Não foi possível criar o checklist.");
    } finally {
      setBusy(false);
    }
  }

  async function addItem() {
    if (!selectedId || code.trim().length < 1 || label.trim().length < 2) {
      setFeedback("Selecione o checklist e informe código e pergunta.");
      return;
    }

    const optionList =
      answerType === "SELECT"
        ? options.split(",").map((item) => item.trim()).filter(Boolean)
        : null;

    if (answerType === "SELECT" && !optionList?.length) {
      setFeedback("Informe ao menos uma opção para o campo de seleção.");
      return;
    }

    setBusy(true);
    try {
      await api("/api/v1/checklist-templates/" + selectedId + "/items", {
        method: "POST",
        body: JSON.stringify({
          code: code.trim().toUpperCase().replace(/[^A-Z0-9_-]+/g, "_"),
          label: label.trim(),
          answer_type: answerType,
          required,
          position: items.length * 10 + 10,
          options_json: optionList,
        }),
      });
      setCode("");
      setLabel("");
      setRequired(false);
      setOptions("");
      setFeedback("Campo adicionado.");
      setItems(await api<ChecklistItem[]>("/api/v1/checklist-templates/" + selectedId + "/items"));
    } catch {
      setFeedback("Não foi possível adicionar o campo.");
    } finally {
      setBusy(false);
    }
  }

  const selected = templates.find((template) => template.id === selectedId);

  return (
    <section className="section-card">
      <div className="section-heading">
        <div>
          <span className="eyebrow">Configuração</span>
          <h2>Checklists de campo</h2>
          <p className="section-copy">
            Versões publicadas permanecem históricas; alterações relevantes devem criar uma nova versão.
          </p>
        </div>
      </div>

      <div className="admin-panel">
        <div>
          <label className="full-field">
            Checklist
            <select value={selectedId} onChange={(event) => setSelectedId(event.target.value)}>
              <option value="">Selecione</option>
              {templates.map((template) => (
                <option key={template.id} value={template.id}>
                  {template.name + " v" + template.version}
                </option>
              ))}
            </select>
          </label>

          <div className="admin-list checklist-admin-list">
            {items.map((item) => (
              <div className="admin-row" key={item.id}>
                <div>
                  <strong>{item.label}</strong>
                  <span>
                    {item.code + " · " + item.answer_type.replaceAll("_", " ") +
                      (item.required ? " · obrigatório" : "")}
                  </span>
                </div>
                <span className="status">{item.position}</span>
              </div>
            ))}
            {selected && items.length === 0 && (
              <div className="empty-state">Esse checklist ainda não possui campos.</div>
            )}
          </div>
        </div>

        <div className="admin-double-form">
          <div className="compact-form admin-create-form">
            <h3>Novo checklist</h3>
            <div className="compact-form-grid">
              <label>
                Nome
                <input value={templateName} onChange={(event) => setTemplateName(event.target.value)} />
              </label>
              <label>
                Versão
                <input
                  inputMode="numeric"
                  value={templateVersion}
                  onChange={(event) => setTemplateVersion(event.target.value)}
                />
              </label>
            </div>
            <button className="small-button" disabled={busy} onClick={() => void createTemplate()}>
              Criar checklist
            </button>
          </div>

          <div className="compact-form admin-create-form">
            <h3>Adicionar campo</h3>
            <div className="compact-form-grid">
              <label>
                Código
                <input value={code} onChange={(event) => setCode(event.target.value)} placeholder="GRADE_LIMPA" />
              </label>
              <label>
                Tipo
                <select value={answerType} onChange={(event) => setAnswerType(event.target.value)}>
                  <option value="BOOLEAN">Sim / Não</option>
                  <option value="NUMBER">Número</option>
                  <option value="TEXT">Texto</option>
                  <option value="SELECT">Seleção</option>
                  <option value="ASSET_STATUS">Status de equipamento</option>
                </select>
              </label>
            </div>
            <label className="full-field">
              Pergunta
              <input value={label} onChange={(event) => setLabel(event.target.value)} />
            </label>
            {answerType === "SELECT" && (
              <label className="full-field">
                Opções separadas por vírgula
                <input value={options} onChange={(event) => setOptions(event.target.value)} />
              </label>
            )}
            <label className="checkbox-field">
              <input
                type="checkbox"
                checked={required}
                onChange={(event) => setRequired(event.target.checked)}
              />
              Campo obrigatório para finalizar a visita
            </label>
            <button className="small-button" disabled={busy || !selectedId} onClick={() => void addItem()}>
              Adicionar campo
            </button>
          </div>
        </div>
      </div>

      {feedback && <span className="inline-feedback">{feedback}</span>}
    </section>
  );
}
