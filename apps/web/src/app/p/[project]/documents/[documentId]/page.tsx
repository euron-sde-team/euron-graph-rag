"use client";

import { ArrowLeft, Download } from "lucide-react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { useState } from "react";

import { StageTrack } from "@/components/documents/stage-track";
import { TypeBadge } from "@/components/graph/type-badge";
import { StatusBadge } from "@/components/status";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { ErrorNotice, Skeleton } from "@/components/ui/feedback";
import { PageBody, PageHeader } from "@/components/ui/page";
import { apiUrl, proj } from "@/lib/api";
import { formatBytes, formatDate, formatNumber } from "@/lib/format";
import { useChunks, useDocument } from "@/lib/queries";

const PAGE = 20;

export default function DocumentPage() {
  const { project, documentId } = useParams<{ project: string; documentId: string }>();
  const query = useDocument(project, documentId);
  const [offset, setOffset] = useState(0);
  const chunks = useChunks(project, documentId, offset);
  const doc = query.data;

  if (query.error) {
    return (
      <PageBody>
        <ErrorNotice message={query.error.message} />
      </PageBody>
    );
  }
  if (!doc) {
    return (
      <PageBody>
        <Skeleton className="h-64" />
      </PageBody>
    );
  }

  return (
    <PageBody>
      <Link
        href={`/p/${project}/documents`}
        className="text-muted-foreground hover:text-foreground mb-3 inline-flex items-center gap-1.5 text-[13px]"
      >
        <ArrowLeft className="size-3.5" aria-hidden /> Documents
      </Link>
      <PageHeader
        title={doc.title}
        description={`${doc.source_type === "url" ? doc.source_uri : doc.external_id}, added ${formatDate(doc.created_at)}`}
        actions={
          doc.size_bytes ? (
            <Button asChild variant="secondary" size="sm">
              <a href={apiUrl(`${proj(project)}/documents/${doc.id}/file`)} download>
                <Download /> Original ({formatBytes(doc.size_bytes)})
              </a>
            </Button>
          ) : null
        }
      />
      {doc.error ? <ErrorNotice message={doc.error} className="mb-4" /> : null}
      <div className="mb-5 grid gap-3 sm:grid-cols-2 lg:grid-cols-5">
        {[
          ["Status", <StatusBadge key="s" status={doc.status} error={doc.error} />],
          ["Pipeline", <StageTrack key="p" document={doc} />],
          ["Passages", formatNumber(doc.chunk_count)],
          ["Entities", formatNumber(doc.entity_count)],
          ["Relations", formatNumber(doc.relation_count)],
        ].map(([label, value]) => (
          <Card key={label as string}>
            <CardContent className="py-3.5">
              <p className="text-subtle text-[11.5px]">{label}</p>
              <div className="mt-1 text-[17px] font-semibold tabular-nums">{value}</div>
            </CardContent>
          </Card>
        ))}
      </div>
      <div className="grid grid-cols-1 gap-4 lg:grid-cols-[minmax(0,1fr)_20rem]">
        <Card>
          <CardHeader>
            <CardTitle>Passages</CardTitle>
            <CardDescription>
              The units that are embedded, searched and cited. {formatNumber(doc.token_count)}{" "}
              tokens in {doc.section_count} sections.
            </CardDescription>
          </CardHeader>
          <CardContent>
            {!chunks.data ? (
              <Skeleton className="h-48" />
            ) : (
              <ol className="space-y-3">
                {chunks.data.items.map((chunk) => (
                  <li key={chunk.id} className="border-border rounded-lg border p-3">
                    <p className="text-subtle mb-1 text-[11.5px]">
                      #{chunk.ordinal + 1} · {chunk.location} · {chunk.token_count} tokens
                    </p>
                    <p className="text-[13px] leading-relaxed whitespace-pre-line">{chunk.text}</p>
                  </li>
                ))}
              </ol>
            )}
            {(chunks.data?.total ?? 0) > PAGE ? (
              <div className="mt-4 flex justify-end gap-2">
                <Button
                  variant="secondary"
                  size="sm"
                  disabled={offset === 0}
                  onClick={() => setOffset(offset - PAGE)}
                >
                  Previous
                </Button>
                <Button
                  variant="secondary"
                  size="sm"
                  disabled={offset + PAGE >= (chunks.data?.total ?? 0)}
                  onClick={() => setOffset(offset + PAGE)}
                >
                  Next
                </Button>
              </div>
            ) : null}
          </CardContent>
        </Card>
        <Card className="h-fit">
          <CardHeader>
            <CardTitle>Strongest entities</CardTitle>
            <CardDescription>Most mentioned in this document.</CardDescription>
          </CardHeader>
          <CardContent>
            {doc.entities.length === 0 ? (
              <p className="text-muted-foreground text-[13px]">Nothing extracted yet.</p>
            ) : (
              <ul className="space-y-1.5">
                {doc.entities.map((entity) => (
                  <li key={entity.id}>
                    <Link
                      href={`/p/${project}/graph?focus=${entity.id}`}
                      className="hover:bg-muted flex items-center justify-between gap-2 rounded-md px-2 py-1.5"
                    >
                      <span className="min-w-0">
                        <span className="block truncate text-[13px] font-medium">
                          {entity.name}
                        </span>
                        <TypeBadge type={entity.type} />
                      </span>
                      <span className="text-subtle text-[12px] tabular-nums">
                        {entity.mentions}x
                      </span>
                    </Link>
                  </li>
                ))}
              </ul>
            )}
          </CardContent>
        </Card>
      </div>
    </PageBody>
  );
}
