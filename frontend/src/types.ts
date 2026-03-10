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
  correspondencia_exata_catmas: boolean;
  grau_similaridade_catmas: number;
  categoria_economica_tabela_3_codigo: string;
  categoria_economica_tabela_3_descricao: string;
  grupo_natureza_despesa_tabela_4_codigo: string;
  grupo_natureza_despesa_tabela_4_descricao: string;
  modalidade_aplicacao_tabela_5_codigo: string;
  modalidade_aplicacao_tabela_5_descricao: string;
  elemento_despesa_tabela_7_codigo: string;
  elemento_despesa_tabela_7_descricao: string;
  item_despesa_tabela_8_codigo: string;
  item_despesa_tabela_8_descricao: string;
  codigo_tributacao_nacional: string;
  codigo_tributacao_nacional_descricao: string;
  linha_fornecimento_compativel: string;
  requer_validacao_humana: boolean;
  motivo_validacao_humana: string;
  itens_semelhantes_catmas: {
    codigo: string;
    descricao: string;
    situacao: string;
    grau_similaridade: number;
  }[];
  justificativa: string;
};

export type AnalysisResponse = {
  sugestoes: ClassificationSuggestion[];
  cruzamento_obrigatorio_realizado: boolean;
  compatibilidade_cnae: string;
  alertas: string[];
  observacoes_tecnicas: string[];
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