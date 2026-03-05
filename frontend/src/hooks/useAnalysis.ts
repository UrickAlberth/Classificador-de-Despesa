import { useMemo, useState } from "react";

import { analisarDespesa } from "../services/api";
import type { AnalysisRequest, AnalysisResponse, ProgressStep } from "../types";

const initialSteps: ProgressStep[] = [
  {
    id: "validacao",
    label: "Validação local",
    description: "Conferindo preenchimento dos campos obrigatórios.",
    status: "pending",
  },
  {
    id: "envio",
    label: "Envio para API",
    description: "Transmitindo dados para o serviço de classificação.",
    status: "pending",
  },
  {
    id: "processamento",
    label: "Processamento",
    description: "Aguardando retorno de classificação e validações.",
    status: "pending",
  },
  {
    id: "finalizacao",
    label: "Finalização",
    description: "Consolidando resultado para exibição no painel.",
    status: "pending",
  },
];

function setStepStatus(steps: ProgressStep[], id: string, status: ProgressStep["status"]): ProgressStep[] {
  return steps.map((step) => (step.id === id ? { ...step, status } : step));
}

export function useAnalysis() {
  const [steps, setSteps] = useState<ProgressStep[]>(initialSteps);
  const [isLoading, setIsLoading] = useState(false);
  const [result, setResult] = useState<AnalysisResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  const progressPercent = useMemo(() => {
    const doneCount = steps.filter((step) => step.status === "done").length;
    return Math.round((doneCount / steps.length) * 100);
  }, [steps]);

  function resetState() {
    setSteps(initialSteps);
    setResult(null);
    setError(null);
  }

  async function runAnalysis(payload: AnalysisRequest) {
    resetState();
    setIsLoading(true);

    setSteps((current) => setStepStatus(current, "validacao", "active"));
    await new Promise((resolve) => setTimeout(resolve, 250));
    setSteps((current) => setStepStatus(setStepStatus(current, "validacao", "done"), "envio", "active"));

    try {
      const pendingResponse = analisarDespesa(payload);

      setSteps((current) => setStepStatus(setStepStatus(current, "envio", "done"), "processamento", "active"));

      const response = await pendingResponse;

      setSteps((current) => setStepStatus(setStepStatus(current, "processamento", "done"), "finalizacao", "active"));
      await new Promise((resolve) => setTimeout(resolve, 200));
      setSteps((current) => setStepStatus(current, "finalizacao", "done"));
      setResult(response);
    } catch (caughtError) {
      const message = caughtError instanceof Error ? caughtError.message : "Erro inesperado na análise.";
      setError(message);
      setSteps((current) => {
        const updated = current.map((step) =>
          step.status === "active" || step.status === "pending" ? { ...step, status: "error" as const } : step
        );
        return updated;
      });
    } finally {
      setIsLoading(false);
    }
  }

  return {
    steps,
    progressPercent,
    isLoading,
    result,
    error,
    resetState,
    runAnalysis,
  };
}