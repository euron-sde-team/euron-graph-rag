"use client";

import { ChevronRight, Layers, Network } from "lucide-react";
import Link from "next/link";
import { useParams, useRouter, useSearchParams } from "next/navigation";
import { Suspense, useMemo, useState } from "react";

import { TypeBadge } from "@/components/graph/type-badge";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent } from "@/components/ui/card";
import { EmptyState, ErrorNotice, Skeleton } from "@/components/ui/feedback";
import { PageBody, PageHeader } from "@/components/ui/page";
import { cn } from "@/lib/cn";
import { formatNumber } from "@/lib/format";
import { communityColor } from "@/lib/graph";
import { useCommunity, useCommunityTree } from "@/lib/queries";
import type { TreeNode } from "@/lib/types";

function Branch({
  node,
  childMap,
  depth,
  selected,
  open,
  toggle,
  select,
  roots,
}: {
  node: TreeNode;
  childMap: Map<string | null, TreeNode[]>;
  depth: number;
  selected: string | null;
  open: Set<string>;
  toggle: (id: string) => void;
  select: (id: string) => void;
  roots: TreeNode[];
}) {
  const kids = childMap.get(node.id) ?? [];
  const expanded = open.has(node.id);
  const ordinal = roots.findIndex((r) => r.id === node.id);
  return (
    <li>
      <div
        className={cn(
          "flex items-center gap-1 rounded-lg pr-2 transition-colors",
          selected === node.id ? "bg-accent" : "hover:bg-muted",
        )}
        style={{ paddingLeft: depth * 16 }}
      >
        {kids.length ? (
          <button
            type="button"
            aria-label={`${expanded ? "Collapse" : "Expand"} ${node.title}`}
            aria-expanded={expanded}
            onClick={() => toggle(node.id)}
            className="text-subtle hover:text-foreground flex size-6 shrink-0 items-center justify-center"
          >
            <ChevronRight className={cn("size-4 transition-transform", expanded && "rotate-90")} />
          </button>
        ) : (
          <span className="size-6 shrink-0" />
        )}
        <button
          type="button"
          onClick={() => select(node.id)}
          aria-current={selected === node.id ? "true" : undefined}
          className="flex min-w-0 flex-1 items-center gap-2 py-1.5 text-left text-[13px]"
        >
          {depth === 0 ? (
            <span
              aria-hidden
              className="size-2.5 shrink-0 rounded-full"
              style={{ backgroundColor: communityColor(ordinal >= 0 ? ordinal : 0) }}
            />
          ) : null}
          <span className={cn("min-w-0 flex-1 truncate", depth === 0 && "font-medium")}>
            {node.title}
          </span>
          <span className="text-muted-foreground text-[11.5px] tabular-nums">
            {node.entity_count}
          </span>
        </button>
      </div>
      {expanded && kids.length ? (
        <ul>
          {kids.map((kid) => (
            <Branch
              key={kid.id}
              node={kid}
              childMap={childMap}
              depth={depth + 1}
              selected={selected}
              open={open}
              toggle={toggle}
              select={select}
              roots={roots}
            />
          ))}
        </ul>
      ) : null}
    </li>
  );
}

function Detail({
  project,
  id,
  select,
}: {
  project: string;
  id: string;
  select: (id: string) => void;
}) {
  const query = useCommunity(project, id);
  const community = query.data;
  if (query.error) return <ErrorNotice message={query.error.message} />;
  if (!community) return <Skeleton className="h-96" />;
  return (
    <div className="space-y-5">
      <div>
        <div className="flex flex-wrap items-center gap-2">
          <Badge tone="primary">Level {community.level}</Badge>
          <span className="text-subtle text-[12.5px]">
            {formatNumber(community.entity_count)} entities,{" "}
            {formatNumber(community.relation_count)} relations
          </span>
          <Badge tone="outline">
            {community.reporter === "local" ? "template report" : community.reporter}
          </Badge>
        </div>
        <h2 className="mt-2 text-[19px] font-semibold tracking-tight">{community.title}</h2>
        {community.parent ? (
          <p className="text-muted-foreground mt-1 text-[12.5px]">
            Part of{" "}
            <button
              type="button"
              className="text-foreground underline"
              onClick={() => select(community.parent!.id)}
            >
              {community.parent.title}
            </button>
          </p>
        ) : null}
        <p className="mt-3 text-[14px] leading-relaxed">{community.summary}</p>
      </div>
      {community.findings.length ? (
        <section aria-label="Findings">
          <h3 className="text-subtle mb-2 text-[11px] font-medium tracking-wider uppercase">
            Findings
          </h3>
          <ol className="space-y-2.5">
            {community.findings.map((finding, i) => (
              <li key={i} className="border-border rounded-lg border p-3">
                <p className="text-[13.5px] font-medium">{finding.summary}</p>
                {finding.explanation ? (
                  <p className="text-muted-foreground mt-1 text-[12.5px] leading-relaxed">
                    {finding.explanation}
                  </p>
                ) : null}
                {finding.sources.length ? (
                  <p className="mt-1.5 flex flex-wrap gap-1.5">
                    {finding.sources.slice(0, 3).map((s) => (
                      <Link
                        key={s.chunk_id}
                        href={`/p/${project}/documents/${s.document_id}`}
                        className="text-subtle hover:text-foreground text-[11.5px] underline"
                      >
                        {s.document_title}, {s.location}
                      </Link>
                    ))}
                  </p>
                ) : null}
              </li>
            ))}
          </ol>
        </section>
      ) : null}
      {community.children.length ? (
        <section aria-label="Sub-communities">
          <h3 className="text-subtle mb-2 text-[11px] font-medium tracking-wider uppercase">
            Sub-communities
          </h3>
          <ul className="grid gap-2 sm:grid-cols-2">
            {community.children.map((child) => (
              <li key={child.id}>
                <button
                  type="button"
                  onClick={() => select(child.id)}
                  className="hover:bg-muted border-border w-full rounded-lg border p-2.5 text-left"
                >
                  <p className="text-[13px] font-medium">{child.title}</p>
                  <p className="text-subtle text-[11.5px]">{child.entity_count} entities</p>
                </button>
              </li>
            ))}
          </ul>
        </section>
      ) : null}
      <section aria-label="Members">
        <h3 className="text-subtle mb-2 text-[11px] font-medium tracking-wider uppercase">
          Members
        </h3>
        <ul className="flex flex-wrap gap-1.5">
          {community.members.slice(0, 40).map((member) => (
            <li key={member.id}>
              <Link
                href={`/p/${project}/graph?focus=${member.id}`}
                className="hover:bg-muted border-border inline-flex items-center gap-1.5 rounded-md border px-2 py-1 text-[12.5px]"
              >
                <TypeBadge type={member.type} className="[&>span:last-child]:sr-only" />
                {member.name}
              </Link>
            </li>
          ))}
        </ul>
      </section>
    </div>
  );
}

function Communities() {
  const { project } = useParams<{ project: string }>();
  const router = useRouter();
  const params = useSearchParams();
  const tree = useCommunityTree(project);
  const selected = params.get("c");
  const [open, setOpen] = useState<Set<string>>(new Set());

  const { children, roots } = useMemo(() => {
    const map = new Map<string | null, TreeNode[]>();
    for (const node of tree.data ?? []) {
      const list = map.get(node.parent_id) ?? [];
      list.push(node);
      map.set(node.parent_id, list);
    }
    return { children: map, roots: map.get(null) ?? [] };
  }, [tree.data]);

  const active = selected ?? roots[0]?.id ?? null;
  const select = (id: string) => router.replace(`/p/${project}/communities?c=${id}`);
  const toggle = (id: string) =>
    setOpen((old) => {
      const next = new Set(old);
      if (!next.delete(id)) next.add(id);
      return next;
    });
  const levels = new Set((tree.data ?? []).map((n) => n.level)).size;

  return (
    <PageBody className="max-w-[88rem]">
      <PageHeader
        title="Communities"
        description="Clusters of closely connected entities, detected hierarchically. Each one carries a generated report that global search reads."
      />
      {tree.error ? <ErrorNotice message={tree.error.message} /> : null}
      {!tree.data ? (
        <Skeleton className="h-96" />
      ) : tree.data.length === 0 ? (
        <Card>
          <EmptyState
            icon={<Layers />}
            title="No communities yet"
            description="Communities appear after the first graph build. Add documents, or request a rebuild from the overview."
            action={
              <Link href={`/p/${project}/documents`} className="text-primary text-[13px] underline">
                Go to documents
              </Link>
            }
          />
        </Card>
      ) : (
        <div className="grid grid-cols-1 gap-4 lg:grid-cols-[22rem_minmax(0,1fr)]">
          <Card className="h-fit">
            <CardContent className="pt-4">
              <p className="text-subtle mb-2 flex items-center gap-1.5 px-1 text-[11.5px]">
                <Network className="size-3.5" aria-hidden />
                {formatNumber(tree.data.length)} communities in {levels} level
                {levels === 1 ? "" : "s"}
              </p>
              <ul aria-label="Community hierarchy" className="space-y-0.5">
                {roots.map((root) => (
                  <Branch
                    key={root.id}
                    node={root}
                    childMap={children}
                    depth={0}
                    selected={active}
                    open={open}
                    toggle={toggle}
                    select={select}
                    roots={roots}
                  />
                ))}
              </ul>
            </CardContent>
          </Card>
          <Card>
            <CardContent className="pt-5">
              {active ? (
                <Detail key={active} project={project} id={active} select={select} />
              ) : null}
            </CardContent>
          </Card>
        </div>
      )}
    </PageBody>
  );
}

export default function CommunitiesPage() {
  return (
    <Suspense fallback={<Skeleton className="m-8 h-96" />}>
      <Communities />
    </Suspense>
  );
}
