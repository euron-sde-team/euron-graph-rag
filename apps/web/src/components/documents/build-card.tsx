"use client";

import { Hammer } from "lucide-react";
import { toast } from "sonner";

import { StatusBadge } from "@/components/status";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { formatRelative } from "@/lib/format";
import { useBuilds, useRebuild } from "@/lib/queries";

/** The latest graph build: when it ran, what it produced, and a button to run another. */
export function BuildCard({ project, editable }: { project: string; editable: boolean }) {
  const builds = useBuilds(project);
  const rebuild = useRebuild(project);
  const latest = builds.data?.items[0];
  const stats = latest?.stats ?? {};

  async function run() {
    try {
      await rebuild.mutateAsync();
      toast.success("Build queued");
    } catch (error) {
      toast.error((error as Error).message);
    }
  }

  return (
    <Card>
      <CardContent className="flex flex-wrap items-center gap-x-8 gap-y-3 py-4">
        <div className="flex items-center gap-3">
          <span className="bg-accent text-accent-foreground flex size-9 items-center justify-center rounded-lg">
            <Hammer className="size-4" aria-hidden />
          </span>
          <div>
            <p className="text-[13.5px] font-medium">Graph build</p>
            <p className="text-muted-foreground text-[12.5px]">
              {latest
                ? `${latest.status === "completed" ? "Finished" : "Started"} ${formatRelative(latest.finished_at ?? latest.created_at)}, ${latest.trigger}`
                : "No build has run yet"}
            </p>
          </div>
          {latest ? <StatusBadge status={latest.status} error={latest.error} /> : null}
        </div>
        {latest?.status === "completed" ? (
          <dl className="text-muted-foreground flex flex-wrap gap-x-6 gap-y-1 text-[12.5px]">
            {[
              ["entities", stats.entities],
              ["relations", stats.relations],
              ["merged duplicates", stats.merged],
              ["communities", stats.communities],
              ["modularity", stats.modularity],
            ].map(([label, value]) => (
              <div key={label as string} className="flex gap-1.5">
                <dd className="text-foreground font-medium tabular-nums">{value ?? 0}</dd>
                <dt>{label}</dt>
              </div>
            ))}
          </dl>
        ) : null}
        {editable ? (
          <Button
            variant="secondary"
            size="sm"
            className="ml-auto"
            disabled={
              rebuild.isPending || latest?.status === "queued" || latest?.status === "running"
            }
            onClick={run}
          >
            Rebuild communities
          </Button>
        ) : null}
      </CardContent>
    </Card>
  );
}
