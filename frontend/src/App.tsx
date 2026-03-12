import { useEffect, useState } from "react";

import { RequestForm } from "./components/RequestForm";
import { ResultPanel } from "./components/ResultPanel";
import { StepTracker } from "./components/StepTracker";
import { useAnalysis } from "./hooks/useAnalysis";
import { API_BASE_URL, healthcheck } from "./services/api";
import type { AnalysisRequest } from "./types";

function App() {
  const { steps, progressPercent, isLoading, result, error, runAnalysis, resetState } = useAnalysis();
  const [isApiOnline, setIsApiOnline] = useState<boolean | null>(null);

  useEffect(() => {
    let isMounted = true;

    healthcheck()
      .then((ok) => {
        if (isMounted) {
          setIsApiOnline(ok);
        }
      })
      .catch(() => {
        if (isMounted) {
          setIsApiOnline(false);
        }
      });

    return () => {
      isMounted = false;
    };
  }, []);

  async function handleSubmit(payload: AnalysisRequest, files: File[]) {
    await runAnalysis({ payload, files });
  }

  return (
    <main className="layout">
      <header className="page-header card">
        <div className="header-topline">Tribunal de Justiça de Minas Gerais</div>
        <div className="header-main">
          <div>
            <h1>Classificador de Despesa com IA</h1>
            <p className="header-subtitle">
              Plataforma para apoio técnico à classificação econômica e validações fiscais com rastreabilidade.
            </p>
          </div>
          <div className="status-block" aria-live="polite">
            <span className="status-label">Status da API</span>
            <span
              className={`status-pill ${
                isApiOnline === null ? "status-checking" : isApiOnline ? "status-online" : "status-offline"
              }`}
            >
              {isApiOnline === null ? "Verificando" : isApiOnline ? "Online" : "Offline"}
            </span>
          </div>
        </div>
        <p className="api-hint">
          Endpoint conectado: <span>{API_BASE_URL}</span>
        </p>
        <div className="header-strip">
          <span>Análise orientada por objeto da contratação</span>
          <span>Leitura de anexos com OCR</span>
          <span>Saída estruturada para CATMAS e tabelas orçamentárias</span>
        </div>
      </header>

      <section className="columns">
        <div className="left-column">
          <RequestForm disabled={isLoading} onSubmit={handleSubmit} onClearResult={resetState} />
          <StepTracker steps={steps} progressPercent={progressPercent} />
        </div>
        <div className="right-column">
          <ResultPanel result={result} error={error} />
        </div>
      </section>
    </main>
  );
}

export default App;