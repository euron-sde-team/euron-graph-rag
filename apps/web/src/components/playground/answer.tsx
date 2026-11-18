"use client";

import { BookOpen, Layers } from "lucide-react";
import Link from "next/link";
import { Fragment } from "react";

import { Badge } from "@/components/ui/badge";
import { Card, CardContent } from "@/components/ui/card";
import { cn } from "@/lib/cn";
import { formatDuration } from "@/lib/format";
import { answerParts } from "@/lib/text";
import type { Citation, QueryResponse } from "@/lib/types";

export function citationId(n: number): string {
  return `source-${n}`;
}

function CitationChip({ n, citation }: { n: number; citation?: Citation }) {
  return (
    <a
      href={`#${citationId(n)}`}
      title={citation?.label}
      aria-label={`Source ${n}${citation ? `: ${citation.label}` : ""}`}
      className="bg-accent text-accent-foreground hover:bg-primary hover:text-primary-foreground mx-0.5 inline-flex h-[18px] min-w-[18px] items-center justify-center rounded px-1 align-text-top text-[11px] font-semibold no-underline transition-colors"
    >
      {n}
    </a>
  );
}

/** The answer text with each [n] marker turned into a link to its source card. */
export function AnswerCard({ result }: { result: QueryResponse }) {
  const byN = new Map(result.citations.map((c) => [c.n, c]));
  return (
    <Card>
      <CardContent className="py-5">
        <div className="mb-3 flex flex-wrap items-center gap-2">
          <Badge tone="primary">{result.mode}</Badge>
          <Badge tone="outline">
            {result.answerer === "local" ? "extractive answer" : result.answerer}
          </Badge>
          <span className="text-subtle text-[12px]">
            {formatDuration(result.latency_ms)}
            {result.cached ? ", from cache" : ""}
          </span>
        </div>
        <p className="text-[15px] leading-relaxed" data-testid="answer">
          {answerParts(result.answer).map((part, i) =>
            part.kind === "text" ? (
              <Fragment key={i}>{part.text}</Fragment>
            ) : (
              <CitationChip key={i} n={part.n} citation={byN.get(part.n)} />
            ),
          )}
        </p>
      </CardContent>
    </Card>
  );
}

/** Every numbered source the answer could cite; the ones it did cite are marked. */
export function Sources({ project, citations }: { project: string; citations: Citation[] }) {
  if (!citations.length) return null;
  return (
    <section aria-label="Sources" className="space-y-2.5">
      <h2 className="text-subtle text-[11px] font-medium tracking-wider uppercase">
        Sources ({citations.filter((c) => c.cited).length} cited of {citations.length})
      </h2>
      <ul className="space-y-2.5">
        {citations.map((c) => (
          <li
            key={c.n}
            id={citationId(c.n)}
            className={cn(
              "bg-card border-border scroll-mt-20 rounded-xl border p-3.5 target:ring-2 target:ring-[var(--ring)]",
              !c.cited && "opacity-80",
            )}
          >
            <div className="mb-1.5 flex flex-wrap items-center gap-2">
              <span className="bg-accent text-accent-foreground inline-flex size-5 items-center justify-center rounded text-[11px] font-semibold">
                {c.n}
              </span>
              {c.kind === "chunk" ? (
                <BookOpen className="text-subtle size-3.5" aria-hidden />
              ) : (
                <Layers className="text-subtle size-3.5" aria-hidden />
              )}
              {c.document_id ? (
                <Link
                  href={`/p/${project}/documents/${c.document_id}`}
                  className="text-[13px] font-medium hover:underline"
                >
                  {c.label}
                </Link>
              ) : (
                <Link
                  href={`/p/${project}/communities?c=${c.id}`}
                  className="text-[13px] font-medium hover:underline"
                >
                  {c.label}
                </Link>
              )}
              {c.cited ? (
                <Badge tone="success">cited</Badge>
              ) : (
                <Badge tone="neutral">retrieved</Badge>
              )}
              <span className="text-subtle ml-auto text-[11.5px] tabular-nums">
                score {c.score.toFixed(2)}
              </span>
            </div>
            <p className="text-muted-foreground text-[12.5px] leading-relaxed">{c.snippet}</p>
            {c.supports.length ? (
              <p className="text-subtle mt-1.5 text-[11.5px]">
                Backed by {c.supports.length} source passage{c.supports.length > 1 ? "s" : ""}
              </p>
            ) : null}
          </li>
        ))}
      </ul>
    </section>
  );
}
