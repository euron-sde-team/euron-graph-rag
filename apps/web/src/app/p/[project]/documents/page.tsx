"use client";

import { FileText, Globe, MoreHorizontal, RotateCw, Trash2, Type } from "lucide-react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { useDeferredValue, useState } from "react";
import { toast } from "sonner";

import { AddSources } from "@/components/documents/add-sources";
import { BuildCard } from "@/components/documents/build-card";
import { StageTrack } from "@/components/documents/stage-track";
import { StatusBadge } from "@/components/status";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { EmptyState, ErrorNotice, Skeleton } from "@/components/ui/feedback";
import { Input, NativeSelect } from "@/components/ui/input";
import { PageBody, PageHeader } from "@/components/ui/page";
import { formatBytes, formatNumber, formatRelative } from "@/lib/format";
import { useDocumentActions, useDocuments, useProject, useSystemInfo } from "@/lib/queries";
import { canEdit } from "@/lib/roles";
import type { Document } from "@/lib/types";

const SOURCE_ICON = { file: FileText, url: Globe, text: Type } as const;

export default function DocumentsPage() {
  const { project } = useParams<{ project: string }>();
  const projectQuery = useProject(project);
  const system = useSystemInfo();
  const editable = canEdit(projectQuery.data?.role);
  const [search, setSearch] = useState("");
  const [status, setStatus] = useState("");
  const q = useDeferredValue(search);
  const documents = useDocuments(project, { q, status });
  const actions = useDocumentActions(project);

  async function reprocess(doc: Document) {
    try {
      await actions.reprocess.mutateAsync(doc.id);
      toast.success(`${doc.title} is being processed again`);
    } catch (error) {
      toast.error((error as Error).message);
    }
  }
  async function remove(doc: Document) {
    if (!window.confirm(`Delete "${doc.title}" and the graph facts only it supports?`)) return;
    try {
      await actions.remove.mutateAsync(doc.id);
      toast.success("Document deleted");
    } catch (error) {
      toast.error((error as Error).message);
    }
  }

  return (
    <PageBody className="max-w-[88rem]">
      <PageHeader
        title="Documents"
        description="Everything the graph is built from, and where each source is in the pipeline."
        actions={
          editable && system.data ? (
            <AddSources
              project={project}
              maxMb={system.data.max_upload_mb}
              extensions={system.data.accepted_extensions}
            />
          ) : null
        }
      />
      <div className="mb-4">
        <BuildCard project={project} editable={editable} />
      </div>
      <div className="mb-3 flex flex-wrap items-center gap-2">
        <Input
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          placeholder="Search documents"
          aria-label="Search documents"
          className="h-9 w-64"
        />
        <NativeSelect
          aria-label="Status"
          value={status}
          onChange={(e) => setStatus(e.target.value)}
          className="h-9 w-40"
        >
          <option value="">Any status</option>
          <option value="processing">Processing</option>
          <option value="queued">Queued</option>
          <option value="ready">Ready</option>
          <option value="failed">Failed</option>
        </NativeSelect>
        <span className="text-muted-foreground ml-auto text-[13px] tabular-nums">
          {formatNumber(documents.data?.total ?? 0)} documents
        </span>
      </div>
      {documents.error ? <ErrorNotice message={documents.error.message} /> : null}
      <Card className="overflow-hidden">
        {!documents.data ? (
          <Skeleton className="h-64" />
        ) : documents.data.items.length === 0 ? (
          <EmptyState
            icon={<FileText />}
            title="No documents yet"
            description="Upload files, paste text or add a web page to start building the graph."
          />
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full min-w-[56rem] text-left text-[13px]">
              <thead className="text-subtle bg-muted/50 text-[11.5px] tracking-wide uppercase">
                <tr>
                  <th className="px-4 py-2 font-medium">Document</th>
                  <th className="px-3 py-2 font-medium">Pipeline</th>
                  <th className="px-3 py-2 text-right font-medium">Passages</th>
                  <th className="px-3 py-2 text-right font-medium">Entities</th>
                  <th className="px-3 py-2 text-right font-medium">Relations</th>
                  <th className="px-3 py-2 font-medium">Status</th>
                  <th className="px-3 py-2 font-medium">Added</th>
                  <th className="w-10 px-2 py-2">
                    <span className="sr-only">Actions</span>
                  </th>
                </tr>
              </thead>
              <tbody className="divide-border divide-y">
                {documents.data.items.map((doc) => {
                  const Icon = SOURCE_ICON[doc.source_type];
                  return (
                    <tr key={doc.id} className="hover:bg-muted/40 transition-colors">
                      <td className="px-4 py-2.5">
                        <Link
                          href={`/p/${project}/documents/${doc.id}`}
                          className="flex items-center gap-2.5 font-medium hover:underline"
                        >
                          <Icon className="text-subtle size-4 shrink-0" aria-hidden />
                          <span className="max-w-[24rem] truncate">{doc.title}</span>
                        </Link>
                        <p className="text-subtle mt-0.5 pl-[26px] text-[11.5px]">
                          {doc.kind ?? doc.source_type}
                          {doc.size_bytes ? `, ${formatBytes(doc.size_bytes)}` : ""}
                        </p>
                      </td>
                      <td className="px-3 py-2.5">
                        <StageTrack document={doc} />
                      </td>
                      <td className="px-3 py-2.5 text-right tabular-nums">{doc.chunk_count}</td>
                      <td className="px-3 py-2.5 text-right tabular-nums">{doc.entity_count}</td>
                      <td className="px-3 py-2.5 text-right tabular-nums">{doc.relation_count}</td>
                      <td className="px-3 py-2.5">
                        <StatusBadge status={doc.status} error={doc.error} />
                      </td>
                      <td className="text-muted-foreground px-3 py-2.5 whitespace-nowrap">
                        {formatRelative(doc.created_at)}
                      </td>
                      <td className="px-2 py-2.5">
                        {editable ? (
                          <DropdownMenu>
                            <DropdownMenuTrigger asChild>
                              <Button
                                variant="ghost"
                                size="icon-sm"
                                aria-label={`Actions for ${doc.title}`}
                              >
                                <MoreHorizontal />
                              </Button>
                            </DropdownMenuTrigger>
                            <DropdownMenuContent align="end">
                              <DropdownMenuItem
                                disabled={doc.status === "queued" || doc.status === "processing"}
                                onSelect={() => reprocess(doc)}
                              >
                                <RotateCw /> Process again
                              </DropdownMenuItem>
                              <DropdownMenuItem onSelect={() => remove(doc)}>
                                <Trash2 /> Delete
                              </DropdownMenuItem>
                            </DropdownMenuContent>
                          </DropdownMenu>
                        ) : null}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </Card>
    </PageBody>
  );
}
