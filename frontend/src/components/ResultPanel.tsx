import type { AnalysisResponse } from "../types";

type ResultPanelProps = {
  result: AnalysisResponse | null;
  error: string | null;
};

export function ResultPanel({ result, error }: ResultPanelProps) {
  return (
    <section className="card result-card">
      <div className="section-heading">
        <h2>Resultado da análise</h2>
        <p>Visualização consolidada para decisão técnica, validação e auditoria.</p>
      </div>

      {error && <p className="error">{error}</p>}

      {!error && !result && <p className="muted">Preencha os campos e execute a análise para visualizar o retorno.</p>}

      {result && (
        <div className="result-stack">
          <div className="result-kpis">
            <article className="kpi-box">
              <span className="kpi-label">Compatibilidade CNAE</span>
              <strong className="kpi-value">{result.compatibilidade_cnae}</strong>
            </article>
            <article className="kpi-box">
              <span className="kpi-label">Cruzamento obrigatório</span>
              <strong className="kpi-value">{result.cruzamento_obrigatorio_realizado ? "Realizado" : "Não realizado"}</strong>
            </article>
            <article className="kpi-box">
              <span className="kpi-label">Sugestões retornadas</span>
              <strong className="kpi-value">{result.sugestoes.length}</strong>
            </article>
          </div>

          <h3 className="result-section-title">Sugestões classificatórias</h3>
          {result.sugestoes.map((sugestao) => (
            <article key={`${sugestao.item_catmas_codigo}-${sugestao.item_despesa_tabela_8_codigo}`} className="suggestion-card">
              <header className="suggestion-header">
                <h4>{sugestao.item_catmas}</h4>
                <span className="suggestion-code">CATMAS {sugestao.item_catmas_codigo}</span>
              </header>

              <div className="suggestion-grid">
                <p><strong>Status CATMAS:</strong> {sugestao.item_catmas_status}</p>
                <p><strong>Correspondência exata:</strong> {sugestao.correspondencia_exata_catmas ? "Sim" : "Não"}</p>
                <p><strong>Similaridade:</strong> {sugestao.grau_similaridade_catmas.toFixed(4)}</p>
                <p><strong>Linha de fornecimento:</strong> {sugestao.linha_fornecimento_compativel}</p>
              </div>

              <div className="budget-list">
                <p><strong>Tabela 3:</strong> {sugestao.categoria_economica_tabela_3_codigo} - {sugestao.categoria_economica_tabela_3_descricao}</p>
                <p><strong>Tabela 4:</strong> {sugestao.grupo_natureza_despesa_tabela_4_codigo} - {sugestao.grupo_natureza_despesa_tabela_4_descricao}</p>
                <p><strong>Tabela 5:</strong> {sugestao.modalidade_aplicacao_tabela_5_codigo} - {sugestao.modalidade_aplicacao_tabela_5_descricao}</p>
                <p><strong>Tabela 7:</strong> {sugestao.elemento_despesa_tabela_7_codigo} - {sugestao.elemento_despesa_tabela_7_descricao}</p>
                <p><strong>Tabela 8:</strong> {sugestao.item_despesa_tabela_8_codigo} - {sugestao.item_despesa_tabela_8_descricao}</p>
              </div>

              <p><strong>Código de Tributação:</strong> {sugestao.codigo_tributacao_nacional} - {sugestao.codigo_tributacao_nacional_descricao}</p>
              <p><strong>Requer validação humana:</strong> {sugestao.requer_validacao_humana ? "Sim" : "Não"}</p>
              <p><strong>Motivo da validação:</strong> {sugestao.motivo_validacao_humana}</p>
              <p><strong>Justificativa:</strong> {sugestao.justificativa}</p>

              {sugestao.itens_semelhantes_catmas.length > 0 && (
                <>
                  <p><strong>Itens semelhantes CATMAS:</strong></p>
                  <ul className="result-list">
                    {sugestao.itens_semelhantes_catmas.map((similar) => (
                      <li key={`${similar.codigo}-${similar.descricao}`}>
                        {similar.codigo} - {similar.descricao} ({similar.situacao}) | similaridade {similar.grau_similaridade.toFixed(4)}
                      </li>
                    ))}
                  </ul>
                </>
              )}
            </article>
          ))}

          <h3 className="result-section-title">Alertas</h3>
          <ul className="result-list">
            {result.alertas.map((alerta) => (
              <li key={alerta}>{alerta}</li>
            ))}
          </ul>

          <h3 className="result-section-title">Alinhamento normativo</h3>
          <ul className="result-list">
            {result.alinhamento_normativo.map((norma) => (
              <li key={norma}>{norma}</li>
            ))}
          </ul>

          <h3 className="result-section-title">Observações técnicas</h3>
          <ul className="result-list">
            {result.observacoes_tecnicas.map((observacao) => (
              <li key={observacao}>{observacao}</li>
            ))}
          </ul>

          <h3 className="result-section-title">Fontes consultadas</h3>
          <ul className="result-list">
            {result.fontes_consultadas.map((fonte) => (
              <li key={fonte}>{fonte}</li>
            ))}
          </ul>
        </div>
      )}
    </section>
  );
}