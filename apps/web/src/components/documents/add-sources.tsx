"use client";

import { FileText, Globe, Upload } from "lucide-react";
import { useRef, useState, type FormEvent } from "react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogFooter, DialogTrigger } from "@/components/ui/dialog";
import { ErrorNotice } from "@/components/ui/feedback";
import { FieldHint, Input, Label, Textarea } from "@/components/ui/input";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { formatBytes } from "@/lib/format";
import { useIngest } from "@/lib/queries";
import type { IngestResult } from "@/lib/types";

function report(result: IngestResult) {
  const parts: string[] = [];
  if (result.created.length) parts.push(`${result.created.length} added`);
  if (result.duplicates.length) parts.push(`${result.duplicates.length} already there`);
  if (result.rejected.length) parts.push(`${result.rejected.length} rejected`);
  const message = parts.join(", ") || "Nothing to add";
  if (result.rejected.length) toast.warning(`${message}: ${result.rejected[0]?.message}`);
  else toast.success(message);
}

/** Files, pasted text or a URL: the three ways a source enters the pipeline. */
export function AddSources({
  project,
  maxMb,
  extensions,
}: {
  project: string;
  maxMb: number;
  extensions: string[];
}) {
  const [open, setOpen] = useState(false);
  const { upload, importSources } = useIngest(project);
  const input = useRef<HTMLInputElement>(null);
  const [files, setFiles] = useState<File[]>([]);
  const [title, setTitle] = useState("");
  const [text, setText] = useState("");
  const [url, setUrl] = useState("");
  const error = (upload.error ?? importSources.error)?.message;

  function done(result: IngestResult) {
    report(result);
    setOpen(false);
    setFiles([]);
    setTitle("");
    setText("");
    setUrl("");
  }

  async function sendFiles(event: FormEvent) {
    event.preventDefault();
    done(await upload.mutateAsync({ files, metadata: {} }));
  }
  async function sendText(event: FormEvent) {
    event.preventDefault();
    done(await importSources.mutateAsync([{ type: "text", title, text, format: "markdown" }]));
  }
  async function sendUrl(event: FormEvent) {
    event.preventDefault();
    done(await importSources.mutateAsync([{ type: "url", url }]));
  }

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>
        <Button>
          <Upload /> Add documents
        </Button>
      </DialogTrigger>
      <DialogContent
        title="Add documents"
        description="Each source is parsed, split into passages, embedded and mined for entities and relations."
        className="w-[min(92vw,34rem)]"
      >
        <Tabs defaultValue="files">
          <TabsList>
            <TabsTrigger value="files">Files</TabsTrigger>
            <TabsTrigger value="text">Text</TabsTrigger>
            <TabsTrigger value="url">Web page</TabsTrigger>
          </TabsList>
          <TabsContent value="files" className="pt-4">
            <form onSubmit={sendFiles} className="space-y-4">
              <button
                type="button"
                onClick={() => input.current?.click()}
                className="border-input hover:bg-muted flex w-full flex-col items-center gap-1.5 rounded-xl border border-dashed px-4 py-8 text-center transition-colors"
              >
                <FileText className="text-subtle size-6" aria-hidden />
                <span className="text-[13.5px] font-medium">Choose files</span>
                <span className="text-muted-foreground text-[12px]">
                  {extensions.join(" ")} up to {maxMb} MB each
                </span>
              </button>
              <input
                ref={input}
                type="file"
                multiple
                hidden
                aria-label="Files to upload"
                accept={extensions.join(",")}
                onChange={(e) => setFiles([...(e.target.files ?? [])])}
              />
              {files.length ? (
                <ul className="text-[12.5px]">
                  {files.map((f) => (
                    <li key={f.name} className="flex justify-between py-0.5">
                      <span className="truncate">{f.name}</span>
                      <span className="text-subtle tabular-nums">{formatBytes(f.size)}</span>
                    </li>
                  ))}
                </ul>
              ) : null}
              {error ? <ErrorNotice message={error} /> : null}
              <DialogFooter>
                <Button type="submit" disabled={!files.length || upload.isPending}>
                  Upload {files.length || ""}
                </Button>
              </DialogFooter>
            </form>
          </TabsContent>
          <TabsContent value="text" className="pt-4">
            <form onSubmit={sendText} className="space-y-3">
              <div className="space-y-1.5">
                <Label htmlFor="source-title">Title</Label>
                <Input
                  id="source-title"
                  value={title}
                  onChange={(e) => setTitle(e.target.value)}
                  required
                />
              </div>
              <div className="space-y-1.5">
                <Label htmlFor="source-text">Text</Label>
                <Textarea
                  id="source-text"
                  rows={8}
                  value={text}
                  onChange={(e) => setText(e.target.value)}
                  required
                />
                <FieldHint>
                  Markdown is fine; headings become part of the location of each passage.
                </FieldHint>
              </div>
              {error ? <ErrorNotice message={error} /> : null}
              <DialogFooter>
                <Button
                  type="submit"
                  disabled={!title.trim() || !text.trim() || importSources.isPending}
                >
                  Add text
                </Button>
              </DialogFooter>
            </form>
          </TabsContent>
          <TabsContent value="url" className="pt-4">
            <form onSubmit={sendUrl} className="space-y-3">
              <div className="space-y-1.5">
                <Label htmlFor="source-url">Address</Label>
                <Input
                  id="source-url"
                  type="url"
                  placeholder="https://example.com/article"
                  value={url}
                  onChange={(e) => setUrl(e.target.value)}
                  required
                />
                <FieldHint>
                  <Globe className="mr-1 inline size-3.5" aria-hidden />
                  The page is fetched by the worker; private network addresses are refused.
                </FieldHint>
              </div>
              {error ? <ErrorNotice message={error} /> : null}
              <DialogFooter>
                <Button type="submit" disabled={!url.trim() || importSources.isPending}>
                  Add page
                </Button>
              </DialogFooter>
            </form>
          </TabsContent>
        </Tabs>
      </DialogContent>
    </Dialog>
  );
}
