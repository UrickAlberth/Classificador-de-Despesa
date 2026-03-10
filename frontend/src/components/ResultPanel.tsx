import type { AnalysisResponse } from "../types";

type ResultPanelProps = {
  result: AnalysisResponse | null;
  error: string | null;
};

export function ResultPanel({ result, error }: ResultPanelProps) {
  return (
    <section className="card">
      <h2>Resultado</h2>

      {error && <p className="error">{error}</p>}

      {!error && !result && <p className="muted">Preencha os campos e execute a análise para visualizar o retorno.</p>}

      {result && (
        <div className="result-stack">
          <p>
            <strong>Compatibilidade CNAE:</strong> {result.compatibilidade_cnae}
          </p>
          <p>
            <strong>Cruzamento obrigatório:</strong> {result.cruzamento_obrigatorio_realizado ? "Sim" : "Não"}
          </p>

          <h3>Sugestões</h3>
          {result.sugestoes.map((sugestao) => (
            <article key={`${sugestao.item_catmas_codigo}-${sugestao.item_despesa_tabela_8_codigo}`} className="suggestion-card">
              <p>
                <strong>Item CATMAS:</strong> {sugestao.item_catmas} ({sugestao.item_catmas_codigo})
              </p>
              <p>
                <strong>Status CATMAS:</strong> {sugestao.item_catmas_status}
              </p>
              <p>
                <strong>Correspondência exata CATMAS:</strong> {sugestao.correspondencia_exata_catmas ? "Sim" : "Não"}
              </p>
              <p>
                <strong>Grau de similaridade CATMAS:</strong> {sugestao.grau_similaridade_catmas.toFixed(4)}
              </p>
              <p>
                <strong>Validação da linha de fornecimento:</strong> {sugestao.linha_fornecimento_compativel}
              </p>
              <p>
                <strong>Tabela 3:</strong> {sugestao.categoria_economica_tabela_3_codigo} - {sugestao.categoria_economica_tabela_3_descricao}
              </p>
              <p>
                <strong>Tabela 4:</strong> {sugestao.grupo_natureza_despesa_tabela_4_codigo} - {sugestao.grupo_natureza_despesa_tabela_4_descricao}
              </p>
              <p>
                <strong>Tabela 5:</strong> {sugestao.modalidade_aplicacao_tabela_5_codigo} - {sugestao.modalidade_aplicacao_tabela_5_descricao}
              </p>
              <p>
                <strong>Tabela 7:</strong> {sugestao.elemento_despesa_tabela_7_codigo} - {sugestao.elemento_despesa_tabela_7_descricao}
              </p>
              <p>
                <strong>Tabela 8:</strong> {sugestao.item_despesa_tabela_8_codigo} - {sugestao.item_despesa_tabela_8_descricao}
              </p>
              <p>
                <strong>Código de Tributação:</strong> {sugestao.codigo_tributacao_nacional} - {sugestao.codigo_tributacao_nacional_descricao}
              </p>
              <p>
                <strong>Requer validação humana:</strong> {sugestao.requer_validacao_humana ? "Sim" : "Não"}
              </p>
              <p>
                <strong>Motivo da validação:</strong> {sugestao.motivo_validacao_humana}
              </p>
              <p>
                <strong>Justificativa:</strong> {sugestao.justificativa}
              </p>

              {sugestao.itens_semelhantes_catmas.length > 0 && (
                <>
                  <p>
                    <strong>Itens semelhantes CATMAS:</strong>
                  </p>
                  <ul>
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

          <h3>Alertas</h3>
          <ul>
            {result.alertas.map((alerta) => (
              <li key={alerta}>{alerta}</li>
            ))}
          </ul>

          <h3>Alinhamento normativo</h3>
          <ul>
            {result.alinhamento_normativo.map((norma) => (
              <li key={norma}>{norma}</li>
            ))}
          </ul>

          <h3>Observações técnicas</h3>
          <ul>
            {result.observacoes_tecnicas.map((observacao) => (
              <li key={observacao}>{observacao}</li>
            ))}
          </ul>

          <h3>Fontes consultadas</h3>
          <ul>
            {result.fontes_consultadas.map((fonte) => (
              <li key={fonte}>{fonte}</li>
            ))}
          </ul>
        </div>
      )}
    </section>
  );
}