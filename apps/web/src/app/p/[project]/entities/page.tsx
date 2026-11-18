"use client";

import { ChevronLeft, ChevronRight, GitMerge, Search } from "lucide-react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { useDeferredValue, useState } from "react";
import { toast } from "sonner";

import { EntityPanel } from "@/components/graph/entity-panel";
import { TypeBadge } from "@/components/graph/type-badge";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { EmptyState, ErrorNotice, Skeleton } from "@/components/ui/feedback";
import { Input, NativeSelect } from "@/components/ui/input";
import { PageBody, PageHeader } from "@/components/ui/page";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { cn } from "@/lib/cn";
import { formatNumber } from "@/lib/format";
import { ENTITY_TYPES, communityColor, typeLabel } from "@/lib/graph";
import { useDuplicates, useEntities, useEntityActions, useProject } from "@/lib/queries";
import { canEdit } from "@/lib/roles";

const PAGE = 25;

function Duplicates({ project, editable }: { project: string; editable: boolean }) {
  const query = useDuplicates(project);
  const { merge } = useEntityActions(project);

  async function apply(survivor: string, members: string[]) {
    try {
      const result = await merge.mutateAsync({ survivor_id: survivor, entity_ids: members });
      toast.success(`Merged ${result.merged} ${result.merged === 1 ? "entity" : "entities"}`);
    } catch (error) {
      toast.error((error as Error).message);
    }
  }

  if (query.error) return <ErrorNotice message={query.error.message} />;
  if (!query.data) return <Skeleton className="h-40" />;
  if (!query.data.length) {
    return (
      <Card>
        <EmptyState
          icon={<GitMerge />}
          title="No duplicates left"
          description="Every build merges names that clearly mean the same thing. Nothing else looks alike."
        />
      </Card>
    );
  }
  return (
    <div className="space-y-3">
      <p className="text-muted-foreground text-[13px]">
        What the next build will merge. Review a group, or merge it now.
      </p>
      {query.data.map((group) => (
        <Card key={group.survivor.id}>
          <CardContent className="flex flex-wrap items-center justify-between gap-3 py-4">
            <div className="min-w-0">
              <p className="text-[14px] font-medium">
                {group.survivor.name} <TypeBadge type={group.survivor.type} className="ml-1" />
              </p>
              <p className="text-muted-foreground mt-1 text-[12.5px]">
                absorbs{" "}
                {group.members.map((m, i) => (
                  <span key={m.id}>
                    {i ? ", " : ""}
                    <span className="text-foreground">{m.name}</span>{" "}
                    <Badge tone="outline">{m.reason}</Badge>
                  </span>
                ))}
              </p>
            </div>
            {editable ? (
              <Button
                variant="secondary"
                size="sm"
                disabled={merge.isPending}
                onClick={() =>
                  apply(
                    group.survivor.id,
                    group.members.map((m) => m.id),
                  )
                }
              >
                <GitMerge /> Merge
              </Button>
            ) : null}
          </CardContent>
        </Card>
      ))}
    </div>
  );
}

export default function EntitiesPage() {
  const { project } = useParams<{ project: string }>();
  const projectQuery = useProject(project);
  const editable = canEdit(projectQuery.data?.role);
  const [search, setSearch] = useState("");
  const [type, setType] = useState("");
  const [sort, setSort] = useState("importance");
  const [offset, setOffset] = useState(0);
  const [selected, setSelected] = useState<string | null>(null);
  const q = useDeferredValue(search);
  const entities = useEntities(project, {
    q,
    types: type ? [type] : [],
    sort,
    offset,
    limit: PAGE,
    level: 0,
  });
  const duplicates = useDuplicates(project);
  const total = entities.data?.total ?? 0;

  return (
    <PageBody className="max-w-[88rem]">
      <PageHeader
        title="Entities"
        description="Every person, organization, place, product and idea the documents mention, resolved across sources."
      />
      <Tabs defaultValue="all">
        <TabsList>
          <TabsTrigger value="all">All entities</TabsTrigger>
          <TabsTrigger value="duplicates">
            Duplicates{duplicates.data?.length ? ` (${duplicates.data.length})` : ""}
          </TabsTrigger>
        </TabsList>
        <TabsContent value="all" className="pt-4">
          <div className="mb-3 flex flex-wrap items-center gap-2">
            <div className="relative">
              <Search aria-hidden className="text-subtle absolute top-2.5 left-2.5 size-4" />
              <Input
                value={search}
                onChange={(e) => {
                  setSearch(e.target.value);
                  setOffset(0);
                }}
                placeholder="Search entities"
                aria-label="Search entities"
                className="h-9 w-64 pl-8"
              />
            </div>
            <NativeSelect
              aria-label="Type"
              value={type}
              onChange={(e) => {
                setType(e.target.value);
                setOffset(0);
              }}
              className="h-9 w-44"
            >
              <option value="">All types</option>
              {ENTITY_TYPES.map((t) => (
                <option key={t} value={t}>
                  {typeLabel(t)}
                </option>
              ))}
            </NativeSelect>
            <NativeSelect
              aria-label="Sort"
              value={sort}
              onChange={(e) => setSort(e.target.value)}
              className="h-9 w-44"
            >
              <option value="importance">Most important</option>
              <option value="mentions">Most mentioned</option>
              <option value="name">Name</option>
              <option value="type">Type</option>
            </NativeSelect>
            <span className="text-muted-foreground ml-auto text-[13px] tabular-nums">
              {formatNumber(total)} entities
            </span>
          </div>
          {entities.error ? <ErrorNotice message={entities.error.message} /> : null}
          <div className="grid gap-4 xl:grid-cols-[minmax(0,1fr)_24rem]">
            <Card className="overflow-hidden">
              {!entities.data ? (
                <Skeleton className="h-96" />
              ) : entities.data.items.length === 0 ? (
                <EmptyState title="No entities match" description="Try another search or type." />
              ) : (
                <table className="w-full text-left text-[13px]">
                  <thead className="text-subtle bg-muted/50 text-[11.5px] tracking-wide uppercase">
                    <tr>
                      <th className="px-4 py-2 font-medium">Entity</th>
                      <th className="px-3 py-2 font-medium">Type</th>
                      <th className="hidden px-3 py-2 font-medium md:table-cell">Community</th>
                      <th className="px-3 py-2 text-right font-medium">Mentions</th>
                      <th className="px-4 py-2 text-right font-medium">Links</th>
                    </tr>
                  </thead>
                  <tbody className="divide-border divide-y">
                    {entities.data.items.map((entity) => (
                      <tr
                        key={entity.id}
                        className={cn(
                          "hover:bg-muted/50 cursor-pointer transition-colors",
                          selected === entity.id && "bg-accent/60",
                        )}
                        onClick={() => setSelected(entity.id)}
                      >
                        <td className="px-4 py-2.5">
                          <button
                            type="button"
                            aria-pressed={selected === entity.id}
                            onClick={(e) => {
                              e.stopPropagation();
                              setSelected(entity.id);
                            }}
                            className="text-left font-medium"
                          >
                            {entity.name}
                          </button>
                          {entity.aliases.length ? (
                            <span className="text-subtle ml-2 text-[11.5px]">
                              +{entity.aliases.length} alias{entity.aliases.length > 1 ? "es" : ""}
                            </span>
                          ) : null}
                        </td>
                        <td className="px-3 py-2.5">
                          <TypeBadge type={entity.type} />
                        </td>
                        <td className="hidden px-3 py-2.5 md:table-cell">
                          {entity.community ? (
                            <Link
                              href={`/p/${project}/communities?c=${entity.community.id}`}
                              onClick={(e) => e.stopPropagation()}
                              className="text-muted-foreground hover:text-foreground inline-flex max-w-[15rem] items-center gap-1.5"
                            >
                              <span
                                aria-hidden
                                className="size-2 shrink-0 rounded-full"
                                style={{
                                  backgroundColor: communityColor(entity.community.ordinal),
                                }}
                              />
                              <span className="truncate">{entity.community.title}</span>
                            </Link>
                          ) : (
                            <span className="text-subtle">None</span>
                          )}
                        </td>
                        <td className="px-3 py-2.5 text-right tabular-nums">
                          {entity.mention_count}
                        </td>
                        <td className="px-4 py-2.5 text-right tabular-nums">{entity.degree}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              )}
              {total > PAGE ? (
                <div className="border-border flex items-center justify-between border-t px-4 py-2.5">
                  <span className="text-muted-foreground text-[12.5px] tabular-nums">
                    {offset + 1} to {Math.min(offset + PAGE, total)} of {total}
                  </span>
                  <div className="flex gap-1.5">
                    <Button
                      variant="secondary"
                      size="icon-sm"
                      aria-label="Previous page"
                      disabled={offset === 0}
                      onClick={() => setOffset(Math.max(0, offset - PAGE))}
                    >
                      <ChevronLeft />
                    </Button>
                    <Button
                      variant="secondary"
                      size="icon-sm"
                      aria-label="Next page"
                      disabled={offset + PAGE >= total}
                      onClick={() => setOffset(offset + PAGE)}
                    >
                      <ChevronRight />
                    </Button>
                  </div>
                </div>
              ) : null}
            </Card>
            <Card className="h-fit xl:sticky xl:top-4">
              <CardHeader className={selected ? "sr-only" : undefined}>
                <CardTitle>Entity details</CardTitle>
                <CardDescription>Select a row to read its relations and sources.</CardDescription>
              </CardHeader>
              <CardContent className="pt-5">
                {selected ? (
                  <EntityPanel
                    project={project}
                    entityId={selected}
                    editable={editable}
                    onSelectEntity={setSelected}
                    onDeleted={() => setSelected(null)}
                  />
                ) : null}
              </CardContent>
            </Card>
          </div>
        </TabsContent>
        <TabsContent value="duplicates" className="pt-4">
          <Duplicates project={project} editable={editable} />
        </TabsContent>
      </Tabs>
    </PageBody>
  );
}
