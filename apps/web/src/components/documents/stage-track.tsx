import { cn } from "@/lib/cn";
import type { Document, PipelineStage } from "@/lib/types";

const STEPS: { stage: PipelineStage; label: string }[] = [
  { stage: "queued", label: "Queued" },
  { stage: "parsing", label: "Parse" },
  { stage: "embedding", label: "Embed" },
  { stage: "extracting", label: "Extract" },
  { stage: "done", label: "Graph" },
];

/** Five pips for the document's journey; the current step pulses while the work runs. */
export function StageTrack({ document }: { document: Pick<Document, "stage" | "status"> }) {
  const failed = document.status === "failed";
  const current =
    document.status === "ready" ? STEPS.length : STEPS.findIndex((s) => s.stage === document.stage);
  return (
    <ol
      className="flex items-center gap-1"
      aria-label={`Pipeline: ${failed ? "failed" : document.status}`}
    >
      {STEPS.map((step, i) => {
        const done = i < current;
        const active = i === current && !failed;
        return (
          <li key={step.stage} className="flex items-center gap-1">
            <span
              title={step.label}
              className={cn(
                "size-2 rounded-full",
                done && "bg-success",
                active && "bg-primary animate-pulse-dot",
                !done && !active && "bg-border",
                failed && i === Math.max(current, 0) && "bg-danger",
              )}
            />
            <span className="sr-only">{step.label}</span>
          </li>
        );
      })}
    </ol>
  );
}
