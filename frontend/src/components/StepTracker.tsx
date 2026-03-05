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
    <section className="card">
      <h2>Andamento da análise</h2>
      <div className="progress-shell" aria-label="progresso geral">
        <div className="progress-fill" style={{ width: `${progressPercent}%` }} />
      </div>
      <p className="progress-text">{progressPercent}% concluído</p>

      <ol className="step-list">
        {steps.map((step) => (
          <li key={step.id} className={`step-item status-${step.status}`}>
            <div>
              <strong>{step.label}</strong>
              <p>{step.description}</p>
            </div>
            <span>{statusLabel(step.status)}</span>
          </li>
        ))}
      </ol>
    </section>
  );
}