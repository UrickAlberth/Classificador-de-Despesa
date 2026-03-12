import type { ProgressStep } from "../types";

type StepTrackerProps = {
  steps: ProgressStep[];
  progressPercent: number;
};

function statusLabel(status: ProgressStep["status"]) {
  switch (status) {
    case "done":
      return "Concluída";
    case "active":
      return "Em andamento";
    case "error":
      return "Falhou";
    default:
      return "Pendente";
  }
}

export function StepTracker({ steps, progressPercent }: StepTrackerProps) {
  return (
    <section className="card tracker-card">
      <div className="section-heading">
        <h2>Andamento da análise</h2>
        <p>Acompanhe cada etapa do processamento técnico da solicitação.</p>
      </div>

      <div className="progress-shell" aria-label="progresso geral">
        <div className="progress-fill" style={{ width: `${progressPercent}%` }} />
      </div>
      <p className="progress-text">{progressPercent}% concluído</p>

      <ol className="step-list">
        {steps.map((step) => (
          <li key={step.id} className={`step-item status-${step.status}`}>
            <span className="step-marker" aria-hidden="true" />
            <div>
              <strong>{step.label}</strong>
              <p>{step.description}</p>
            </div>
            <span className="step-status-badge">{statusLabel(step.status)}</span>
          </li>
        ))}
      </ol>
    </section>
  );
}