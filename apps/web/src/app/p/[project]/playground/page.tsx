"use client";

import { History, Search, Sparkles } from "lucide-react";
import { useParams } from "next/navigation";
import { useMemo, useState, type FormEvent } from "react";

import { ForceGraph, type GraphEdge, type GraphNode } from "@/components/graph/force-graph";
import { AnswerCard, Sources } from "@/components/playground/answer";
import { CommunitiesUsed, Trace } from "@/components/playground/trace";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { EmptyState, ErrorNotice, Spinner } from "@/components/ui/feedback";
import { FieldHint, Input, Label, NativeSelect } from "@/components/ui/input";
import { PageBody, PageHeader } from "@/components/ui/page";
import { cn } from "@/lib/cn";
import { formatRelative } from "@/lib/format";
import { fetchQuery, useAsk, useCommunityTree, useQueryHistory } from "@/lib/queries";
import type { QueryResponse, SearchMode } from "@/lib/types";

const MODES: { mode: SearchMode; label: string; hint: string }[] = [
  {
    mode: "local",
    label: "Local",
    hint: "Starts from the entities in the question, walks their neighbourhood and cites passages. Best for specific facts.",
  },
  {
    mode: "global",
    label: "Global",
    hint: "Maps every community report against the question and reduces the best points. Best for themes across the corpus.",
  },
  {
    mode: "hybrid",
    label: "Hybrid",
    hint: "Both: passages from the neighbourhood plus the strongest community reports.",
  },
];

const SAMPLES: [SearchMode, string][] = [
  ["local", "Who founded Helios Robotics?"],
  ["hybrid", "How does Helios Robotics depend on its suppliers and investors?"],
  ["global", "How is predictive maintenance used in port terminals?"],
];

export default function PlaygroundPage() {
  const { project } = useParams<{ project: string }>();
  const ask = useAsk(project);
  const history = useQueryHistory(project);
  const tree = useCommunityTree(project);
  const [question, setQuestion] = useState("");
  const [mode, setMode] = useState<SearchMode>("hybrid");
  const [topK, setTopK] = useState(6);
  const [hops, setHops] = useState(1);
  const [level, setLevel] = useState<number | null>(null);
  const [result, setResult] = useState<QueryResponse | null>(null);
  const [selected, setSelected] = useState<string | null>(null);

  const levels = useMemo(
    () => [...new Set((tree.data ?? []).map((n) => n.level))].sort(),
    [tree.data],
  );

  async function run(next?: { question: string; mode: SearchMode }) {
    const q = (next?.question ?? question).trim();
    const m = next?.mode ?? mode;
    if (q.length < 3) return;
    setQuestion(q);
    setMode(m);
    try {
      const response = await ask.mutateAsync({ question: q, mode: m, top_k: topK, hops, level });
      setResult(response);
      setSelected(null);
    } catch {
      // The error renders from the mutation state below.
    }
  }

  function submit(event: FormEvent) {
    event.preventDefault();
    void run();
  }

  async function reopen(id: string) {
    const response = await fetchQuery(project, id);
    setResult(response);
    setQuestion(response.question);
    setMode(response.mode);
    setSelected(null);
  }

  const nodes: GraphNode[] = useMemo(
    () =>
      (result?.nodes ?? []).map((n) => ({
        id: n.id,
        name: n.name,
        type: n.type,
        importance: n.score * 10 + n.degree * 0.3,
        degree: n.degree,
        emphasis: n.role === "seed",
      })),
    [result],
  );
  const edges: GraphEdge[] = useMemo(
    () =>
      (result?.edges ?? []).map((e) => ({
        id: e.id,
        source: e.source_id,
        target: e.target_id,
        predicate: e.predicate,
        weight: e.weight,
      })),
    [result],
  );
  const selectedNode = result?.nodes.find((n) => n.id === selected);

  return (
    <PageBody className="max-w-[88rem]">
      <PageHeader
        title="Query playground"
        description="Ask a question and see exactly which entities, relations and community reports answered it."
      />
      <div className="grid grid-cols-1 gap-5 xl:grid-cols-[minmax(0,1fr)_22rem]">
        <div className="min-w-0 space-y-5">
          <Card>
            <CardContent className="pt-5">
              <form onSubmit={submit} className="space-y-4">
                <div className="space-y-1.5">
                  <Label htmlFor="question">Question</Label>
                  <div className="flex gap-2">
                    <Input
                      id="question"
                      value={question}
                      onChange={(e) => setQuestion(e.target.value)}
                      placeholder="Who founded Helios Robotics?"
                      className="h-10"
                      autoComplete="off"
                    />
                    <Button
                      type="submit"
                      disabled={ask.isPending || question.trim().length < 3}
                      className="h-10"
                    >
                      {ask.isPending ? <Spinner className="text-primary-foreground" /> : <Search />}
                      Ask
                    </Button>
                  </div>
                </div>
                <fieldset className="space-y-2">
                  <legend className="text-[13px] font-medium">Search mode</legend>
                  <div className="flex flex-wrap gap-2" role="radiogroup" aria-label="Search mode">
                    {MODES.map((m) => (
                      <button
                        key={m.mode}
                        type="button"
                        role="radio"
                        aria-checked={mode === m.mode}
                        onClick={() => setMode(m.mode)}
                        className={cn(
                          "rounded-lg border px-3 py-1.5 text-[13px] font-medium transition-colors",
                          mode === m.mode
                            ? "border-primary bg-accent text-accent-foreground"
                            : "border-border text-muted-foreground hover:bg-muted",
                        )}
                      >
                        {m.label}
                      </button>
                    ))}
                  </div>
                  <FieldHint>{MODES.find((m) => m.mode === mode)?.hint}</FieldHint>
                </fieldset>
                <div className="grid grid-cols-2 gap-3 sm:max-w-md sm:grid-cols-3">
                  <div className="space-y-1.5">
                    <Label htmlFor="top-k">Passages</Label>
                    <NativeSelect
                      id="top-k"
                      value={topK}
                      onChange={(e) => setTopK(Number(e.target.value))}
                    >
                      {[3, 6, 10, 15].map((n) => (
                        <option key={n} value={n}>
                          {n}
                        </option>
                      ))}
                    </NativeSelect>
                  </div>
                  <div className="space-y-1.5">
                    <Label htmlFor="hops">Hops</Label>
                    <NativeSelect
                      id="hops"
                      value={hops}
                      onChange={(e) => setHops(Number(e.target.value))}
                    >
                      {[0, 1, 2, 3].map((n) => (
                        <option key={n} value={n}>
                          {n}
                        </option>
                      ))}
                    </NativeSelect>
                  </div>
                  <div className="space-y-1.5">
                    <Label htmlFor="level">Community level</Label>
                    <NativeSelect
                      id="level"
                      value={level ?? ""}
                      onChange={(e) =>
                        setLevel(e.target.value === "" ? null : Number(e.target.value))
                      }
                    >
                      <option value="">Auto</option>
                      {levels.map((l) => (
                        <option key={l} value={l}>
                          Level {l}
                        </option>
                      ))}
                    </NativeSelect>
                  </div>
                </div>
              </form>
            </CardContent>
          </Card>

          {ask.error ? <ErrorNotice message={ask.error.message} /> : null}

          {!result && !ask.isPending ? (
            <Card>
              <EmptyState
                icon={<Sparkles />}
                title="Ask the graph"
                description="Try one of these, or write your own."
                action={
                  <div className="flex flex-wrap justify-center gap-2">
                    {SAMPLES.map(([m, q]) => (
                      <Button
                        key={q}
                        variant="secondary"
                        size="sm"
                        className="h-auto max-w-full shrink py-1.5 text-left whitespace-normal"
                        onClick={() => void run({ question: q, mode: m })}
                      >
                        {q}
                      </Button>
                    ))}
                  </div>
                }
              />
            </Card>
          ) : null}

          {result ? (
            <div className="space-y-5" aria-live="polite">
              <AnswerCard result={result} />
              {result.nodes.length ? (
                <section aria-label="Graph used">
                  <h2 className="text-subtle mb-2 flex flex-wrap items-center gap-2 text-[11px] font-medium tracking-wider uppercase">
                    Subgraph used
                    <Badge tone="outline">
                      {result.nodes.filter((n) => n.role === "seed").length} seeds
                    </Badge>
                    <Badge tone="outline">
                      {result.nodes.filter((n) => n.role === "neighbor").length} neighbours
                    </Badge>
                    <Badge tone="outline">{result.edges.length} relations</Badge>
                  </h2>
                  <ForceGraph
                    nodes={nodes}
                    edges={edges}
                    colorBy="type"
                    selectedId={selected}
                    onSelect={setSelected}
                    height={420}
                    label="Entities and relations used for this answer"
                  />
                  {selectedNode ? (
                    <p className="text-muted-foreground mt-2 text-[12.5px]">
                      <span className="text-foreground font-medium">{selectedNode.name}</span> was a{" "}
                      {selectedNode.role} with score {selectedNode.score.toFixed(2)} and{" "}
                      {selectedNode.degree} connections.
                    </p>
                  ) : null}
                </section>
              ) : null}
              <Sources project={project} citations={result.citations} />
            </div>
          ) : null}
        </div>

        <aside className="space-y-5">
          {result ? (
            <>
              <Trace steps={result.steps} />
              <CommunitiesUsed communities={result.communities} project={project} />
            </>
          ) : null}
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <History className="text-subtle size-4" aria-hidden /> Recent questions
              </CardTitle>
              <CardDescription>Select one to see its answer and graph again.</CardDescription>
            </CardHeader>
            <CardContent>
              {history.data?.items.length ? (
                <ul className="space-y-1">
                  {history.data.items.map((item) => (
                    <li key={item.id}>
                      <button
                        type="button"
                        onClick={() => void reopen(item.id)}
                        className="hover:bg-muted -mx-1.5 w-[calc(100%+0.75rem)] rounded-md px-1.5 py-1.5 text-left"
                      >
                        <p className="line-clamp-2 text-[13px]">{item.question}</p>
                        <p className="text-subtle mt-0.5 flex items-center gap-1.5 text-[11.5px]">
                          <Badge tone="outline">{item.mode}</Badge>
                          {item.citation_count} cited, {formatRelative(item.created_at)}
                        </p>
                      </button>
                    </li>
                  ))}
                </ul>
              ) : (
                <p className="text-muted-foreground text-[13px]">Nothing asked yet.</p>
              )}
            </CardContent>
          </Card>
        </aside>
      </div>
    </PageBody>
  );
}
