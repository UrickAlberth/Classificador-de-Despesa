import { FormEvent, useState } from "react";

import type { AnalysisRequest } from "../types";

type RequestFormProps = {
  disabled: boolean;
  onSubmit: (payload: AnalysisRequest, files: File[]) => Promise<void>;
  onClearResult: () => void;
};

const initialForm: AnalysisRequest = {
  finalidade: "",
  objeto_contratacao: "",
  texto_documentos: "",
  cnpj: "",
  cnae_empresa: "",
  permitir_multiplas_classificacoes: true,
  max_sugestoes: 3,
};

export function RequestForm({ disabled, onSubmit, onClearResult }: RequestFormProps) {
  const [form, setForm] = useState<AnalysisRequest>(initialForm);
  const [files, setFiles] = useState<File[]>([]);
  const requiresManualObject = files.length === 0;

  function handleChange<K extends keyof AnalysisRequest>(key: K, value: AnalysisRequest[K]) {
    setForm((current) => ({ ...current, [key]: value }));
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    onClearResult();
    await onSubmit({
      ...form,
      texto_documentos: form.texto_documentos?.trim() || undefined,
      cnpj: form.cnpj?.trim() || undefined,
      cnae_empresa: form.cnae_empresa?.trim() || undefined,
    }, files);
  }

  return (
    <section className="card form-card">
      <div className="section-heading">
        <h2>Entrada da análise</h2>
        <p>Preencha os campos essenciais e anexe documentos para extração automática do objeto da contratação.</p>
      </div>

      <form onSubmit={handleSubmit} className="form-grid">
        <div className="form-section">
          <h3>Objeto e finalidade</h3>

          <label>
            Finalidade do gasto
            <textarea
              required
              minLength={10}
              value={form.finalidade}
              onChange={(event) => handleChange("finalidade", event.target.value)}
              placeholder="Descreva o propósito administrativo da contratação"
              disabled={disabled}
            />
          </label>

          <label>
            Objeto da contratação
            <textarea
              required={requiresManualObject}
              minLength={10}
              value={form.objeto_contratacao}
              onChange={(event) => handleChange("objeto_contratacao", event.target.value)}
              placeholder="Descreva o objeto. Se estiver em branco, o sistema tenta inferir pelos anexos."
              disabled={disabled}
            />
            <small className="muted">
              {requiresManualObject
                ? "Sem anexos, este campo é obrigatório (mínimo de 10 caracteres)."
                : "Com anexos, este campo pode ficar em branco para inferência automática por OCR."}
            </small>
          </label>

          <label>
            Texto dos documentos (opcional)
            <textarea
              rows={5}
              value={form.texto_documentos}
              onChange={(event) => handleChange("texto_documentos", event.target.value)}
              placeholder="Cole trechos de CI, ETP, TR, contrato ou outros documentos."
              disabled={disabled}
            />
          </label>
        </div>

        <div className="form-section">
          <h3>Anexos para leitura automática</h3>
          <label>
            Arquivos (OCR)
            <input
              type="file"
              multiple
              accept=".pdf,.png,.jpg,.jpeg,.tif,.tiff,.bmp,.webp,.txt,.csv,.md,.html"
              onChange={(event) => setFiles(Array.from(event.target.files ?? []))}
              disabled={disabled}
            />
            <small className="muted">
              {files.length > 0
                ? `${files.length} arquivo(s) selecionado(s) para OCR com Mistral Document AI.`
                : "Nenhum arquivo selecionado. Sem anexos, a etapa de OCR é omitida automaticamente."}
            </small>
          </label>

          <div className="form-row">
            <label>
              CNPJ (opcional)
              <input
                value={form.cnpj}
                onChange={(event) => handleChange("cnpj", event.target.value)}
                placeholder="00.000.000/0000-00"
                disabled={disabled}
              />
            </label>

            <label>
              CNAE da empresa (opcional)
              <input
                value={form.cnae_empresa}
                onChange={(event) => handleChange("cnae_empresa", event.target.value)}
                placeholder="6204-0/00"
                disabled={disabled}
              />
            </label>

            <label>
              Máximo de sugestões
              <input
                type="number"
                min={1}
                max={10}
                value={form.max_sugestoes}
                onChange={(event) => handleChange("max_sugestoes", Number(event.target.value))}
                disabled={disabled}
              />
            </label>
          </div>
        </div>

        <label className="checkbox-label">
          <input
            type="checkbox"
            checked={form.permitir_multiplas_classificacoes}
            onChange={(event) => handleChange("permitir_multiplas_classificacoes", event.target.checked)}
            disabled={disabled}
          />
          Permitir múltiplas classificações
        </label>

        <div className="form-actions">
          <button type="submit" disabled={disabled}>
            {disabled ? "Analisando..." : "Iniciar análise"}
          </button>
        </div>
      </form>
    </section>
  );
}