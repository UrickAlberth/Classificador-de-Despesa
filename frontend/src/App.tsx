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

  async function handleSubmit(payload: AnalysisRequest) {
    await runAnalysis(payload);
  }

  return (
    <main className="layout">
      <header className="page-header card">
        <h1>Classificador de Despesa com IA</h1>
        <p>Painel de execução do fluxo completo: entrada, cruzamento e retorno da classificação.</p>
        <p>
          <strong>API:</strong> {API_BASE_URL}
        </p>
        <p>
          <strong>Status:</strong>{" "}
          {isApiOnline === null ? "Verificando..." : isApiOnline ? "Online" : "Offline"}
        </p>
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