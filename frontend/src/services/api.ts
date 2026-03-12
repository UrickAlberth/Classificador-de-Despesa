import type { AnalysisRequest, AnalysisResponse } from "../types";

const API_BASE_URL =
  import.meta.env.VITE_API_BASE_URL?.replace(/\/$/, "") ?? "http://127.0.0.1:8000";

export async function healthcheck(): Promise<boolean> {
  const response = await fetch(`${API_BASE_URL}/health`);
  return response.ok;
}

export async function analisarDespesa(payload: AnalysisRequest): Promise<AnalysisResponse> {
  const response = await fetch(`${API_BASE_URL}/analisar`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify(payload),
  });

  if (!response.ok) {
    let detail = "Falha ao processar análise.";
    try {
      const errorBody = (await response.json()) as { detail?: string };
      detail = errorBody.detail ?? detail;
    } catch {
      detail = response.statusText || detail;
    }
    throw new Error(detail);
  }

  return (await response.json()) as AnalysisResponse;
}

export async function analisarDespesaComArquivos(
  payload: AnalysisRequest,
  files: File[]
): Promise<AnalysisResponse> {
  const formData = new FormData();
  formData.append("finalidade", payload.finalidade);
  formData.append("objeto_contratacao", payload.objeto_contratacao ?? "");
  formData.append("texto_documentos", payload.texto_documentos ?? "");
  formData.append("cnpj", payload.cnpj ?? "");
  formData.append("cnae_empresa", payload.cnae_empresa ?? "");
  formData.append("permitir_multiplas_classificacoes", String(payload.permitir_multiplas_classificacoes));
  formData.append("max_sugestoes", String(payload.max_sugestoes));

  for (const file of files) {
    formData.append("arquivos", file, file.name);
  }

  const response = await fetch(`${API_BASE_URL}/analisar-com-arquivos`, {
    method: "POST",
    body: formData,
  });

  if (!response.ok) {
    let detail = "Falha ao processar análise com arquivos.";
    try {
      const errorBody = (await response.json()) as { detail?: string };
      detail = errorBody.detail ?? detail;
    } catch {
      detail = response.statusText || detail;
    }
    throw new Error(detail);
  }

  return (await response.json()) as AnalysisResponse;
}

export { API_BASE_URL };