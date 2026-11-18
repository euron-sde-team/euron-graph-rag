import Link from "next/link";

import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { formatDuration } from "@/lib/format";
import type { CommunityUse, Step } from "@/lib/types";

const LABELS: Record<string, string> = {
  embed: "Embed the question",
  passages: "Find passages",
  seeds: "Pick seed entities",
  expand: "Walk the graph",
  rank: "Rank passages",
  communities: "Choose community reports",
  map: "Map: points per report",
  reduce: "Reduce: best points",
  answer: "Compose the answer",
  total: "Total",
};

/** The steps a question went through, each with its detail and share of the time. */
export function Trace({ steps }: { steps: Step[] }) {
  const parts = steps.filter((s) => s.name !== "total");
  const total = Math.max(
    1,
    steps.find((s) => s.name === "total")?.ms ?? parts.reduce((a, s) => a + s.ms, 0),
  );
  return (
    <Card>
      <CardHeader>
        <CardTitle>How it was answered</CardTitle>
      </CardHeader>
      <CardContent>
        <ol className="space-y-3">
          {parts.map((step, i) => (
            <li key={step.name} className="grid grid-cols-[1.5rem_1fr_auto] items-start gap-x-2.5">
              <span className="bg-muted text-muted-foreground mt-0.5 flex size-5 items-center justify-center rounded-full text-[11px] font-medium">
                {i + 1}
              </span>
              <div className="min-w-0">
                <p className="text-[13px] font-medium">{LABELS[step.name] ?? step.name}</p>
                {step.detail ? (
                  <p className="text-muted-foreground text-[12px]">{step.detail}</p>
                ) : null}
                <div className="bg-muted mt-1.5 h-1 overflow-hidden rounded-full">
                  <div
                    className="bg-primary h-full rounded-full"
                    style={{ width: `${Math.max(2, Math.min(100, (step.ms / total) * 100))}%` }}
                  />
                </div>
              </div>
              <span className="text-subtle text-[11.5px] tabular-nums">
                {formatDuration(step.ms)}
              </span>
            </li>
          ))}
        </ol>
      </CardContent>
    </Card>
  );
}

export function CommunitiesUsed({
  communities,
  project,
}: {
  communities: CommunityUse[];
  project: string;
}) {
  if (!communities.length) return null;
  return (
    <Card>
      <CardHeader>
        <CardTitle>Communities used</CardTitle>
      </CardHeader>
      <CardContent>
        <ul className="space-y-2.5">
          {communities.slice(0, 6).map((c) => (
            <li key={c.id}>
              <Link
                href={`/p/${project}/communities?c=${c.id}`}
                className="hover:bg-muted -mx-1.5 block rounded-md px-1.5 py-1"
              >
                <p className="flex items-center gap-2 text-[13px] font-medium">
                  <span className="truncate">{c.title}</span>
                  <Badge tone="outline">L{c.level}</Badge>
                </p>
                {c.points[0] ? (
                  <p className="text-muted-foreground mt-0.5 line-clamp-2 text-[12px]">
                    {c.points[0]}
                  </p>
                ) : null}
              </Link>
            </li>
          ))}
        </ul>
      </CardContent>
    </Card>
  );
}
