import { FormEvent, useState } from "react";

import type { AnalysisRequest } from "../types";

type RequestFormProps = {
  disabled: boolean;
  onSubmit: (payload: AnalysisRequest) => Promise<void>;
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
    });
  }

  return (
    <section className="card">
      <h2>Entrada da análise</h2>
      <form onSubmit={handleSubmit} className="form-grid">
        <label>
          Finalidade
          <textarea
            required
            minLength={10}
            value={form.finalidade}
            onChange={(event) => handleChange("finalidade", event.target.value)}
            placeholder="Descreva a finalidade da contratação"
            disabled={disabled}
          />
        </label>

        <label>
          Objeto da contratação
          <textarea
            required
            minLength={10}
            value={form.objeto_contratacao}
            onChange={(event) => handleChange("objeto_contratacao", event.target.value)}
            placeholder="Descreva o objeto contratado"
            disabled={disabled}
          />
        </label>

        <label>
          Texto dos documentos (opcional)
          <textarea
            rows={5}
            value={form.texto_documentos}
            onChange={(event) => handleChange("texto_documentos", event.target.value)}
            placeholder="Trechos de CI, ETP, TR, contrato ou anexos"
            disabled={disabled}
          />
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

        <label className="checkbox-label">
          <input
            type="checkbox"
            checked={form.permitir_multiplas_classificacoes}
            onChange={(event) => handleChange("permitir_multiplas_classificacoes", event.target.checked)}
            disabled={disabled}
          />
          Permitir múltiplas classificações
        </label>

        <button type="submit" disabled={disabled}>
          {disabled ? "Analisando..." : "Iniciar análise"}
        </button>
      </form>
    </section>
  );
}