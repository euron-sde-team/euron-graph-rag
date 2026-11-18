"use client";

import { Network, X } from "lucide-react";
import { useParams, useRouter, useSearchParams } from "next/navigation";
import { Suspense, useDeferredValue, useMemo, useState } from "react";

import { EntityPanel } from "@/components/graph/entity-panel";
import { ForceGraph, type GraphEdge, type GraphNode } from "@/components/graph/force-graph";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent } from "@/components/ui/card";
import { EmptyState, ErrorNotice, Skeleton } from "@/components/ui/feedback";
import { Input, NativeSelect } from "@/components/ui/input";
import { PageBody, PageHeader } from "@/components/ui/page";
import { cn } from "@/lib/cn";
import { formatNumber } from "@/lib/format";
import { COMMUNITY_COLORS, ENTITY_TYPES, communityColor, typeColor, typeLabel } from "@/lib/graph";
import { useExplore, useOverview, useProject } from "@/lib/queries";
import { canEdit } from "@/lib/roles";

function Explorer() {
  const { project } = useParams<{ project: string }>();
  const router = useRouter();
  const params = useSearchParams();
  const focus = params.get("focus");
  const [query, setQuery] = useState("");
  const [types, setTypes] = useState<string[]>([]);
  const [colorBy, setColorBy] = useState<"type" | "community">("type");
  const [level, setLevel] = useState(0);
  const [limit, setLimit] = useState(120);
  const [selected, setSelected] = useState<string | null>(null);
  const q = useDeferredValue(query);

  const projectQuery = useProject(project);
  const overview = useOverview(project);
  const explore = useExplore(project, {
    q,
    types,
    focus,
    hops: 1,
    level,
    limit,
  });

  const nodes: GraphNode[] = useMemo(
    () =>
      (explore.data?.nodes ?? []).map((n) => ({
        id: n.id,
        name: n.name,
        type: n.type,
        importance: n.importance,
        degree: n.degree,
        communityOrdinal: n.community_ordinal,
        emphasis: n.id === focus,
      })),
    [explore.data, focus],
  );
  const edges: GraphEdge[] = useMemo(() => explore.data?.edges ?? [], [explore.data]);
  const counts = new Map((overview.data?.entity_types ?? []).map((t) => [t.type, t.count]));
  const levels = overview.data?.community_levels ?? [];
  const focusNode = nodes.find((n) => n.id === focus);

  function setFocus(id: string | null) {
    const next = new URLSearchParams(params.toString());
    if (id) next.set("focus", id);
    else next.delete("focus");
    router.replace(`/p/${project}/graph${next.size ? `?${next}` : ""}`);
    setSelected(id);
  }

  const toggle = (type: string) =>
    setTypes((old) => (old.includes(type) ? old.filter((t) => t !== type) : [...old, type]));

  return (
    <PageBody className="max-w-[88rem]">
      <PageHeader
        title="Graph explorer"
        description={
          explore.data
            ? `${formatNumber(nodes.length)} of ${formatNumber(explore.data.total_entities)} entities and ${formatNumber(edges.length)} of ${formatNumber(explore.data.total_relations)} relations shown. Drag to move, scroll to zoom, double-click a node to focus on its neighbourhood.`
            : "Entities as nodes, relations as edges."
        }
      />
      <div className="mb-4 flex flex-wrap items-center gap-2">
        <Input
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="Filter by name or description"
          aria-label="Filter entities"
          className="h-9 w-64"
        />
        <div className="flex flex-wrap gap-1.5" role="group" aria-label="Entity types">
          {ENTITY_TYPES.map((type) => {
            const on = types.includes(type);
            return (
              <button
                key={type}
                type="button"
                aria-pressed={on}
                onClick={() => toggle(type)}
                className={cn(
                  "inline-flex items-center gap-1.5 rounded-md border px-2 py-1 text-[12.5px] transition-colors",
                  on
                    ? "border-primary bg-accent text-accent-foreground"
                    : "border-border text-muted-foreground hover:bg-muted",
                )}
              >
                <span
                  aria-hidden
                  className="size-2.5 rounded-full"
                  style={{ backgroundColor: typeColor(type) }}
                />
                {typeLabel(type)}
                <span className="text-subtle tabular-nums">{counts.get(type) ?? 0}</span>
              </button>
            );
          })}
        </div>
        <div className="ml-auto flex items-center gap-2">
          <NativeSelect
            aria-label="Colour by"
            value={colorBy}
            onChange={(e) => setColorBy(e.target.value as "type" | "community")}
            className="h-9 w-40"
          >
            <option value="type">Colour by type</option>
            <option value="community">Colour by community</option>
          </NativeSelect>
          {colorBy === "community" && levels.length > 1 ? (
            <NativeSelect
              aria-label="Community level"
              value={level}
              onChange={(e) => setLevel(Number(e.target.value))}
              className="h-9 w-32"
            >
              {levels.map((l) => (
                <option key={l.level} value={l.level}>
                  Level {l.level}
                </option>
              ))}
            </NativeSelect>
          ) : null}
          <NativeSelect
            aria-label="Nodes shown"
            value={limit}
            onChange={(e) => setLimit(Number(e.target.value))}
            className="h-9 w-32"
          >
            {[40, 80, 120, 200, 300].map((n) => (
              <option key={n} value={n}>
                {n} nodes
              </option>
            ))}
          </NativeSelect>
        </div>
      </div>
      {focus ? (
        <div className="mb-3 flex items-center gap-2">
          <Badge tone="primary">
            Neighbourhood of {focusNode?.name ?? "the selected entity"}
            <button type="button" aria-label="Show the whole graph" onClick={() => setFocus(null)}>
              <X />
            </button>
          </Badge>
        </div>
      ) : null}
      {explore.error ? <ErrorNotice message={explore.error.message} /> : null}
      <div className="grid gap-4 xl:grid-cols-[minmax(0,1fr)_22rem]">
        <div className="min-w-0 space-y-3">
          {!explore.data ? (
            <Skeleton className="h-[560px]" />
          ) : nodes.length === 0 ? (
            <Card>
              <EmptyState
                icon={<Network />}
                title="Nothing to show"
                description="No entity matches these filters, or documents are still being processed."
              />
            </Card>
          ) : (
            <ForceGraph
              nodes={nodes}
              edges={edges}
              colorBy={colorBy}
              selectedId={selected}
              onSelect={setSelected}
              onOpen={setFocus}
            />
          )}
          {colorBy === "community" && explore.data?.communities.length ? (
            <ul className="flex flex-wrap gap-x-4 gap-y-1.5" aria-label="Communities">
              {explore.data.communities.slice(0, 12).map((c) => (
                <li
                  key={c.id}
                  className="text-muted-foreground flex items-center gap-1.5 text-[12px]"
                >
                  <span
                    aria-hidden
                    className="size-2.5 rounded-full"
                    style={{ backgroundColor: communityColor(c.ordinal % COMMUNITY_COLORS) }}
                  />
                  <span className="max-w-[16rem] truncate">{c.title}</span>
                  <span className="text-subtle tabular-nums">{c.count}</span>
                </li>
              ))}
            </ul>
          ) : null}
        </div>
        <Card className="h-fit xl:sticky xl:top-4">
          <CardContent className="pt-5">
            {selected ? (
              <EntityPanel
                project={project}
                entityId={selected}
                editable={canEdit(projectQuery.data?.role)}
                onFocus={setFocus}
                onSelectEntity={setSelected}
                onDeleted={() => setSelected(null)}
              />
            ) : (
              <div className="text-muted-foreground space-y-3 text-[13px]">
                <p className="text-foreground text-[14px] font-medium">Select an entity</p>
                <p>
                  Click a node to see what it is, how it connects and which passages say so. Press
                  Enter on a focused node, or double-click, to explore only its neighbourhood.
                </p>
                <p>
                  Node size shows importance (connections and mentions). Edges point from the
                  subject to the object of a relation.
                </p>
              </div>
            )}
          </CardContent>
        </Card>
      </div>
    </PageBody>
  );
}

export default function GraphPage() {
  return (
    <Suspense fallback={<Skeleton className="m-8 h-96" />}>
      <Explorer />
    </Suspense>
  );
}
