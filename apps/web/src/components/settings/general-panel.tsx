"use client";

import { useState, type FormEvent } from "react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { FieldHint, Input, Label, Textarea } from "@/components/ui/input";
import { Switch } from "@/components/ui/switch";
import { ENTITY_TYPES, typeLabel } from "@/lib/graph";
import { useUpdateProject } from "@/lib/queries";
import { cn } from "@/lib/cn";
import type { GraphSettings, Project } from "@/lib/types";

function GraphSettingsCard({ project, editable }: { project: Project; editable: boolean }) {
  const update = useUpdateProject(project.slug);
  const [draft, setDraft] = useState<GraphSettings>(project.settings);

  function toggle(type: string) {
    const has = draft.entity_types.includes(type);
    const next = has ? draft.entity_types.filter((t) => t !== type) : [...draft.entity_types, type];
    if (next.length) setDraft({ ...draft, entity_types: next });
  }
  const number =
    (key: "chunk_tokens" | "overlap_tokens" | "community_levels" | "resolution") =>
    (event: { target: { value: string } }) =>
      setDraft({ ...draft, [key]: Number(event.target.value) });

  async function submit(event: FormEvent) {
    event.preventDefault();
    try {
      await update.mutateAsync({ settings: draft });
      toast.success("Graph settings saved. Reprocess documents to apply them to existing ones.");
    } catch (error) {
      toast.error((error as Error).message);
    }
  }

  return (
    <Card className="mt-5">
      <CardHeader>
        <CardTitle>Graph pipeline</CardTitle>
        <CardDescription>
          How documents become a graph. Changes apply to documents ingested afterwards.
        </CardDescription>
      </CardHeader>
      <CardContent>
        <form onSubmit={submit} className="max-w-xl space-y-5">
          <fieldset className="space-y-2">
            <legend className="text-[13px] font-medium">Entity types</legend>
            <div className="flex flex-wrap gap-1.5">
              {ENTITY_TYPES.map((type) => {
                const on = draft.entity_types.includes(type);
                return (
                  <button
                    key={type}
                    type="button"
                    disabled={!editable}
                    aria-pressed={on}
                    onClick={() => toggle(type)}
                    className={cn(
                      "rounded-md border px-2 py-1 text-[12.5px] transition-colors",
                      on
                        ? "border-primary bg-accent text-accent-foreground"
                        : "border-border text-muted-foreground hover:bg-muted",
                    )}
                  >
                    {typeLabel(type)}
                  </button>
                );
              })}
            </div>
            <FieldHint>The extractor only emits these; anything else becomes Other.</FieldHint>
          </fieldset>
          <div className="grid grid-cols-2 gap-4 sm:grid-cols-4">
            <div className="space-y-1.5">
              <Label htmlFor="chunk-tokens">Chunk tokens</Label>
              <Input
                id="chunk-tokens"
                type="number"
                min={60}
                max={800}
                value={draft.chunk_tokens}
                onChange={number("chunk_tokens")}
                disabled={!editable}
              />
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="overlap-tokens">Overlap</Label>
              <Input
                id="overlap-tokens"
                type="number"
                min={0}
                max={200}
                value={draft.overlap_tokens}
                onChange={number("overlap_tokens")}
                disabled={!editable}
              />
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="levels">Levels</Label>
              <Input
                id="levels"
                type="number"
                min={1}
                max={4}
                value={draft.community_levels}
                onChange={number("community_levels")}
                disabled={!editable}
              />
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="resolution">Resolution</Label>
              <Input
                id="resolution"
                type="number"
                min={0.2}
                max={3}
                step={0.1}
                value={draft.resolution}
                onChange={number("resolution")}
                disabled={!editable}
              />
            </div>
          </div>
          <div className="flex items-center gap-3">
            <Switch
              id="auto-build"
              checked={draft.auto_build}
              onCheckedChange={(auto_build) => setDraft({ ...draft, auto_build })}
              disabled={!editable}
            />
            <Label htmlFor="auto-build">Rebuild communities after every ingested document</Label>
          </div>
          {editable ? (
            <Button type="submit" disabled={update.isPending}>
              Save graph settings
            </Button>
          ) : null}
        </form>
      </CardContent>
    </Card>
  );
}

export function GeneralPanel({ project, editable }: { project: Project; editable: boolean }) {
  const update = useUpdateProject(project.slug);
  const [name, setName] = useState(project.name);
  const [description, setDescription] = useState(project.description);

  async function submit(event: FormEvent) {
    event.preventDefault();
    try {
      await update.mutateAsync({ name, description });
      toast.success("Project updated");
    } catch (error) {
      toast.error((error as Error).message);
    }
  }

  return (
    <>
      <Card>
        <CardContent className="pt-5">
          <form onSubmit={submit} className="max-w-xl space-y-4">
            <div className="space-y-1.5">
              <Label htmlFor="settings-name">Name</Label>
              <Input
                id="settings-name"
                value={name}
                onChange={(e) => setName(e.target.value)}
                disabled={!editable}
                required
              />
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="settings-description">Description</Label>
              <Textarea
                id="settings-description"
                value={description}
                onChange={(e) => setDescription(e.target.value)}
                disabled={!editable}
              />
            </div>
            <div className="space-y-1.5">
              <p className="text-[13px] font-medium">Address</p>
              <FieldHint>
                The API serves this project under{" "}
                <code className="font-mono">/api/v1/projects/{project.slug}</code>; the id{" "}
                <code className="font-mono">{project.id}</code> works too.
              </FieldHint>
            </div>
            {editable ? (
              <Button type="submit" disabled={update.isPending || !name.trim()}>
                Save changes
              </Button>
            ) : (
              <FieldHint>Only owners can change project settings.</FieldHint>
            )}
          </form>
        </CardContent>
      </Card>
      <GraphSettingsCard
        key={JSON.stringify(project.settings)}
        project={project}
        editable={editable}
      />
    </>
  );
}
