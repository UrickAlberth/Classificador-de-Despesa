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
            <article key={`${sugestao.item_catmas_codigo}-${sugestao.item_despesa_tabela_8}`} className="suggestion-card">
              <p>
                <strong>Item CATMAS:</strong> {sugestao.item_catmas} ({sugestao.item_catmas_codigo})
              </p>
              <p>
                <strong>Status CATMAS:</strong> {sugestao.item_catmas_status}
              </p>
              <p>
                <strong>Tabela 3:</strong> {sugestao.categoria_economica_tabela_3}
              </p>
              <p>
                <strong>Tabela 4:</strong> {sugestao.grupo_natureza_despesa_tabela_4}
              </p>
              <p>
                <strong>Tabela 5:</strong> {sugestao.modalidade_aplicacao_tabela_5}
              </p>
              <p>
                <strong>Tabela 7:</strong> {sugestao.elemento_despesa_tabela_7}
              </p>
              <p>
                <strong>Tabela 8:</strong> {sugestao.item_despesa_tabela_8}
              </p>
              <p>
                <strong>Código de Tributação:</strong> {sugestao.codigo_tributacao_nacional}
              </p>
              <p>
                <strong>Justificativa:</strong> {sugestao.justificativa}
              </p>
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