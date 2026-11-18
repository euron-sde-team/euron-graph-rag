"use client";

import { ArrowLeft, ArrowRight, Crosshair, Pencil, Trash2 } from "lucide-react";
import Link from "next/link";
import { useState, type FormEvent } from "react";
import { toast } from "sonner";

import { TypeBadge } from "@/components/graph/type-badge";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogFooter } from "@/components/ui/dialog";
import { ErrorNotice, Skeleton } from "@/components/ui/feedback";
import { Input, Label, NativeSelect, Textarea } from "@/components/ui/input";
import { formatNumber } from "@/lib/format";
import { ENTITY_TYPES, communityColor, predicateLabel, typeLabel } from "@/lib/graph";
import { useEntity, useEntityActions } from "@/lib/queries";
import { highlightParts } from "@/lib/text";
import type { EntityDetail, Neighbor } from "@/lib/types";

function Marked({ text, terms }: { text: string; terms: string[] }) {
  return (
    <>
      {highlightParts(text, terms).map((part, i) =>
        part.match ? (
          <mark key={i} className="bg-highlight text-foreground rounded-sm px-0.5">
            {part.text}
          </mark>
        ) : (
          <span key={i}>{part.text}</span>
        ),
      )}
    </>
  );
}

function RelationList({
  items,
  icon,
  title,
  onSelect,
}: {
  items: Neighbor[];
  icon: React.ReactNode;
  title: string;
  onSelect?: (id: string) => void;
}) {
  if (!items.length) return null;
  return (
    <section aria-label={title}>
      <h3 className="text-subtle mb-1.5 flex items-center gap-1.5 text-[11px] font-medium tracking-wider uppercase [&_svg]:size-3">
        {icon}
        {title}
      </h3>
      <ul className="space-y-1.5">
        {items.map((n) => (
          <li key={n.relation.id} className="text-[13px] leading-snug">
            <button
              type="button"
              onClick={() => onSelect?.(n.entity.id)}
              className="hover:bg-muted -mx-1 w-full rounded-md px-1 py-0.5 text-left"
            >
              <span className="text-muted-foreground">{predicateLabel(n.relation.predicate)}</span>{" "}
              <span className="font-medium">{n.entity.name}</span>
              {n.relation.evidence_count > 1 ? (
                <span className="text-subtle ml-1 text-[11.5px]">
                  ({n.relation.evidence_count} sources)
                </span>
              ) : null}
            </button>
          </li>
        ))}
      </ul>
    </section>
  );
}

function EditDialog({
  project,
  entity,
  open,
  onOpenChange,
}: {
  project: string;
  entity: EntityDetail;
  open: boolean;
  onOpenChange: (open: boolean) => void;
}) {
  const { update } = useEntityActions(project);
  const [name, setName] = useState(entity.name);
  const [type, setType] = useState(entity.type);
  const [description, setDescription] = useState(entity.description);

  async function submit(event: FormEvent) {
    event.preventDefault();
    try {
      await update.mutateAsync({ id: entity.id, name, type, description });
      toast.success("Entity updated");
      onOpenChange(false);
    } catch (error) {
      toast.error((error as Error).message);
    }
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent title="Edit entity" description="Renaming keeps the old name as an alias.">
        <form onSubmit={submit} className="space-y-4">
          <div className="space-y-1.5">
            <Label htmlFor="entity-name">Name</Label>
            <Input
              id="entity-name"
              value={name}
              onChange={(e) => setName(e.target.value)}
              required
            />
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="entity-type">Type</Label>
            <NativeSelect id="entity-type" value={type} onChange={(e) => setType(e.target.value)}>
              {ENTITY_TYPES.map((t) => (
                <option key={t} value={t}>
                  {typeLabel(t)}
                </option>
              ))}
            </NativeSelect>
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="entity-description">Description</Label>
            <Textarea
              id="entity-description"
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              rows={4}
            />
          </div>
          <DialogFooter>
            <Button type="button" variant="ghost" onClick={() => onOpenChange(false)}>
              Cancel
            </Button>
            <Button type="submit" disabled={update.isPending || !name.trim()}>
              Save
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}

/** One entity: what it is, how it connects, and the passages that say so. */
export function EntityPanel({
  project,
  entityId,
  editable,
  onFocus,
  onSelectEntity,
  onDeleted,
}: {
  project: string;
  entityId: string;
  editable: boolean;
  onFocus?: (id: string) => void;
  onSelectEntity?: (id: string) => void;
  onDeleted?: () => void;
}) {
  const query = useEntity(project, entityId);
  const { remove } = useEntityActions(project);
  const [editing, setEditing] = useState(false);
  const entity = query.data;

  if (query.error) return <ErrorNotice message={query.error.message} />;
  if (!entity) {
    return (
      <div className="space-y-3">
        <Skeleton className="h-6 w-2/3" />
        <Skeleton className="h-16" />
        <Skeleton className="h-32" />
      </div>
    );
  }
  const terms = [entity.name, ...entity.aliases];
  const outgoing = entity.neighbors.filter((n) => n.direction === "out");
  const incoming = entity.neighbors.filter((n) => n.direction === "in");

  async function destroy() {
    if (!entity || !window.confirm(`Delete ${entity.name} and its relations?`)) return;
    try {
      await remove.mutateAsync(entity.id);
      toast.success("Entity deleted");
      onDeleted?.();
    } catch (error) {
      toast.error((error as Error).message);
    }
  }

  return (
    <div className="space-y-5">
      <div>
        <div className="flex flex-wrap items-start justify-between gap-2">
          <div className="min-w-0">
            <h2 className="text-[17px] font-semibold tracking-tight break-words">{entity.name}</h2>
            <TypeBadge type={entity.type} />
          </div>
          <div className="flex items-center gap-1.5">
            {onFocus ? (
              <Button variant="secondary" size="sm" onClick={() => onFocus(entity.id)}>
                <Crosshair /> Focus
              </Button>
            ) : null}
            {editable ? (
              <>
                <Button
                  variant="ghost"
                  size="icon-sm"
                  aria-label="Edit entity"
                  onClick={() => setEditing(true)}
                >
                  <Pencil />
                </Button>
                <Button variant="ghost" size="icon-sm" aria-label="Delete entity" onClick={destroy}>
                  <Trash2 />
                </Button>
              </>
            ) : null}
          </div>
        </div>
        {entity.description ? (
          <p className="text-muted-foreground mt-2 text-[13.5px] leading-relaxed">
            {entity.description}
          </p>
        ) : null}
        {entity.aliases.length ? (
          <p className="text-subtle mt-2 text-[12.5px]">
            Also written as {entity.aliases.map((a) => `"${a}"`).join(", ")}
          </p>
        ) : null}
        <dl className="mt-3 grid grid-cols-3 gap-2 text-center">
          {[
            ["Mentions", entity.mention_count],
            ["Connections", entity.degree],
            ["Sources", entity.sources.length],
          ].map(([label, value]) => (
            <div key={label} className="bg-muted rounded-lg px-2 py-1.5">
              <dt className="text-muted-foreground text-[11px]">{label}</dt>
              <dd className="text-[15px] font-semibold tabular-nums">
                {formatNumber(Number(value))}
              </dd>
            </div>
          ))}
        </dl>
        {entity.communities.length ? (
          <div className="mt-3 flex flex-wrap gap-1.5">
            {entity.communities.map((c) => (
              <Link
                key={c.id}
                href={`/p/${project}/communities?c=${c.id}`}
                className="hover:bg-muted border-border inline-flex max-w-full items-center gap-1.5 rounded-md border px-1.5 py-0.5 text-[12px]"
              >
                <span
                  aria-hidden
                  className="size-2 shrink-0 rounded-full"
                  style={{ backgroundColor: communityColor(c.ordinal) }}
                />
                <span className="truncate">{c.title}</span>
                <Badge tone="outline">L{c.level}</Badge>
              </Link>
            ))}
          </div>
        ) : null}
      </div>

      <RelationList
        items={outgoing}
        icon={<ArrowRight />}
        title="Outgoing"
        onSelect={onSelectEntity}
      />
      <RelationList
        items={incoming}
        icon={<ArrowLeft />}
        title="Incoming"
        onSelect={onSelectEntity}
      />

      <section aria-label="Sources">
        <h3 className="text-subtle mb-1.5 text-[11px] font-medium tracking-wider uppercase">
          Source passages
        </h3>
        <ul className="space-y-2.5">
          {entity.sources.slice(0, 6).map((source) => (
            <li key={source.chunk_id} className="border-border rounded-lg border p-2.5">
              <p className="text-muted-foreground mb-1 text-[11.5px]">
                <Link
                  href={`/p/${project}/documents/${source.document_id}`}
                  className="text-foreground font-medium hover:underline"
                >
                  {source.document_title}
                </Link>{" "}
                · {source.location}
              </p>
              <p className="text-[12.5px] leading-relaxed">
                <Marked
                  text={source.text.length > 360 ? `${source.text.slice(0, 360)}...` : source.text}
                  terms={terms}
                />
              </p>
            </li>
          ))}
        </ul>
      </section>
      {editable ? (
        <EditDialog
          key={entity.id}
          project={project}
          entity={entity}
          open={editing}
          onOpenChange={setEditing}
        />
      ) : null}
    </div>
  );
}
