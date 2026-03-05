export type AnalysisRequest = {
  finalidade: string;
  objeto_contratacao: string;
  texto_documentos?: string;
  cnpj?: string;
  cnae_empresa?: string;
  permitir_multiplas_classificacoes: boolean;
  max_sugestoes: number;
};

export type ClassificationSuggestion = {
  item_catmas: string;
  item_catmas_codigo: string;
  item_catmas_status: string;
  item_catmas_linhas_fornecimento: string;
  categoria_economica_tabela_3: string;
  grupo_natureza_despesa_tabela_4: string;
  modalidade_aplicacao_tabela_5: string;
  elemento_despesa_tabela_7: string;
  item_despesa_tabela_8: string;
  codigo_tributacao_nacional: string;
  justificativa: string;
};

export type AnalysisResponse = {
  sugestoes: ClassificationSuggestion[];
  cruzamento_obrigatorio_realizado: boolean;
  compatibilidade_cnae: string;
  alertas: string[];
  alinhamento_normativo: string[];
  fontes_consultadas: string[];
};

export type StepStatus = "pending" | "active" | "done" | "error";

export type ProgressStep = {
  id: string;
  label: string;
  description: string;
  status: StepStatus;
};