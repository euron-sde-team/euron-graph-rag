"use client";

import {
  ArrowRight,
  FileText,
  Layers,
  MessageSquareText,
  Network,
  Share2,
  Shapes,
} from "lucide-react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { useMemo } from "react";

import { PredicateBars, TrafficChart, TypeBars } from "@/components/charts";
import { BuildCard } from "@/components/documents/build-card";
import { ForceGraph } from "@/components/graph/force-graph";
import { TypeBadge } from "@/components/graph/type-badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { EmptyState, ErrorNotice, Skeleton } from "@/components/ui/feedback";
import { PageBody, PageHeader } from "@/components/ui/page";
import { formatCompact, formatDuration, formatNumber } from "@/lib/format";
import { useExplore, useOverview, useProject, useSystemInfo } from "@/lib/queries";
import { canEdit } from "@/lib/roles";

function Stat({
  icon: Icon,
  label,
  value,
  hint,
}: {
  icon: typeof FileText;
  label: string;
  value: number;
  hint?: string;
}) {
  return (
    <Card>
      <CardContent className="flex items-center gap-3 py-4">
        <span className="bg-accent text-accent-foreground flex size-9 shrink-0 items-center justify-center rounded-lg">
          <Icon className="size-4" aria-hidden />
        </span>
        <div className="min-w-0">
          <p className="text-subtle text-[11.5px]">{label}</p>
          <p className="text-[20px] leading-tight font-semibold tabular-nums">
            {formatCompact(value)}
          </p>
          {hint ? <p className="text-subtle truncate text-[11px]">{hint}</p> : null}
        </div>
      </CardContent>
    </Card>
  );
}

export default function OverviewPage() {
  const { project } = useParams<{ project: string }>();
  const projectQuery = useProject(project);
  const overview = useOverview(project);
  const system = useSystemInfo();
  const preview = useExplore(project, { limit: 48, level: 0 });
  const data = overview.data;
  const nodes = useMemo(
    () =>
      (preview.data?.nodes ?? []).map((n) => ({
        id: n.id,
        name: n.name,
        type: n.type,
        importance: n.importance,
        degree: n.degree,
        communityOrdinal: n.community_ordinal,
      })),
    [preview.data],
  );

  return (
    <PageBody className="max-w-[88rem]">
      <PageHeader
        title={projectQuery.data?.name ?? "Overview"}
        description={
          projectQuery.data?.description || "A knowledge graph built from your documents."
        }
        actions={
          <Button asChild>
            <Link href={`/p/${project}/playground`}>
              <MessageSquareText /> Ask a question
            </Link>
          </Button>
        }
      />
      {overview.error ? <ErrorNotice message={overview.error.message} /> : null}
      {!data ? (
        <div className="grid gap-4 sm:grid-cols-3 xl:grid-cols-6">
          {Array.from({ length: 6 }, (_, i) => (
            <Skeleton key={i} className="h-20" />
          ))}
        </div>
      ) : (
        <div className="space-y-5">
          <div className="grid gap-4 sm:grid-cols-3 xl:grid-cols-6">
            <Stat
              icon={FileText}
              label="Documents"
              value={data.counts.documents}
              hint={`${data.pipeline.ready} ready`}
            />
            <Stat icon={Shapes} label="Passages" value={data.counts.chunks} />
            <Stat icon={Network} label="Entities" value={data.counts.entities} />
            <Stat icon={Share2} label="Relations" value={data.counts.relations} />
            <Stat
              icon={Layers}
              label="Communities"
              value={data.counts.communities}
              hint={`${data.community_levels.length} levels`}
            />
            <Stat icon={MessageSquareText} label="Questions" value={data.counts.queries} />
          </div>

          <BuildCard project={project} editable={canEdit(projectQuery.data?.role)} />

          {data.counts.entities === 0 ? (
            <Card>
              <EmptyState
                icon={<FileText />}
                title="Add your first documents"
                description="The graph appears as soon as documents have been parsed and mined for entities."
                action={
                  <Button asChild>
                    <Link href={`/p/${project}/documents`}>Go to documents</Link>
                  </Button>
                }
              />
            </Card>
          ) : (
            <div className="grid grid-cols-1 gap-5 xl:grid-cols-[minmax(0,1.5fr)_minmax(0,1fr)]">
              <Card>
                <CardHeader className="flex-row items-start justify-between gap-3">
                  <div>
                    <CardTitle>The graph at a glance</CardTitle>
                    <CardDescription>
                      The most important entities and how they connect.
                    </CardDescription>
                  </div>
                  <Button asChild variant="secondary" size="sm">
                    <Link href={`/p/${project}/graph`}>
                      Open explorer <ArrowRight />
                    </Link>
                  </Button>
                </CardHeader>
                <CardContent>
                  {preview.data ? (
                    <ForceGraph
                      nodes={nodes}
                      edges={preview.data.edges}
                      colorBy="community"
                      selectedId={null}
                      onSelect={() => undefined}
                      height={430}
                      label="The graph at a glance"
                    />
                  ) : (
                    <Skeleton className="h-[430px]" />
                  )}
                </CardContent>
              </Card>
              <div className="space-y-5">
                <Card>
                  <CardHeader>
                    <CardTitle>Entities by type</CardTitle>
                  </CardHeader>
                  <CardContent>
                    <TypeBars data={data.entity_types} />
                  </CardContent>
                </Card>
                <Card>
                  <CardHeader>
                    <CardTitle>Most connected</CardTitle>
                  </CardHeader>
                  <CardContent>
                    <ol className="space-y-1">
                      {data.top_entities.map((entity, i) => (
                        <li key={entity.id}>
                          <Link
                            href={`/p/${project}/graph?focus=${entity.id}`}
                            className="hover:bg-muted -mx-2 flex items-center gap-3 rounded-md px-2 py-1.5"
                          >
                            <span className="text-subtle w-4 text-[12px] tabular-nums">
                              {i + 1}
                            </span>
                            <span className="min-w-0 flex-1">
                              <span className="block truncate text-[13px] font-medium">
                                {entity.name}
                              </span>
                              <TypeBadge type={entity.type} />
                            </span>
                            <span className="text-muted-foreground text-[12px] tabular-nums">
                              {entity.degree} links
                            </span>
                          </Link>
                        </li>
                      ))}
                    </ol>
                  </CardContent>
                </Card>
              </div>
            </div>
          )}

          <div className="grid grid-cols-1 gap-5 lg:grid-cols-3">
            <Card>
              <CardHeader>
                <CardTitle>Relations by kind</CardTitle>
              </CardHeader>
              <CardContent>
                <PredicateBars data={data.predicates} />
              </CardContent>
            </Card>
            <Card className="lg:col-span-2">
              <CardHeader>
                <CardTitle>Questions, last two weeks</CardTitle>
                <CardDescription>
                  {data.modes
                    .map((m) => `${m.mode}: ${m.queries} (${formatDuration(m.avg_latency_ms)} avg)`)
                    .join(" · ") || "No questions yet."}
                </CardDescription>
              </CardHeader>
              <CardContent>
                <TrafficChart data={data.traffic} />
              </CardContent>
            </Card>
          </div>
          {system.data ? (
            <p className="text-subtle text-[12px]">
              Extraction: {system.data.extractor.provider}/{system.data.extractor.model}.
              Embeddings: {system.data.embedding.provider} (
              {formatNumber(system.data.embedding.dim)} dimensions). Answers:{" "}
              {system.data.answerer.provider}/{system.data.answerer.model}.
            </p>
          ) : null}
        </div>
      )}
    </PageBody>
  );
}
