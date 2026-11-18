"use client";

import {
  FileText,
  Layers,
  LayoutDashboard,
  Menu,
  Network,
  ScanSearch,
  Settings,
  Users,
  X,
} from "lucide-react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect, useState, type ReactNode } from "react";

import { Wordmark } from "@/components/brand";
import { ProjectSwitcher } from "@/components/shell/project-switcher";
import { UserMenu } from "@/components/shell/user-menu";
import { Button } from "@/components/ui/button";
import { EmptyState, Skeleton, Spinner } from "@/components/ui/feedback";
import { ApiError } from "@/lib/api";
import { cn } from "@/lib/cn";
import { formatCompact } from "@/lib/format";
import { useMe, useOverview } from "@/lib/queries";
import { runtimeEnv } from "@/lib/runtime-env";
import { LAST_PROJECT_KEY, writeLocal } from "@/lib/storage";
import type { Me, ProjectSummary } from "@/lib/types";

const NAV = [
  { segment: "", label: "Overview", icon: LayoutDashboard },
  { segment: "documents", label: "Documents", icon: FileText },
  { segment: "graph", label: "Graph explorer", icon: Network },
  { segment: "entities", label: "Entities", icon: Users },
  { segment: "communities", label: "Communities", icon: Layers },
  { segment: "playground", label: "Playground", icon: ScanSearch },
  { segment: "settings", label: "Settings", icon: Settings },
] as const;

function GraphSummary({ project }: { project: string }) {
  const overview = useOverview(project);
  const data = overview.data;
  if (!data) {
    return (
      <div className="space-y-1.5 px-2.5">
        <Skeleton className="h-6" />
        <Skeleton className="h-6" />
      </div>
    );
  }
  const busy = data.pipeline.queued + data.pipeline.processing;
  return (
    <div className="px-2.5">
      <dl className="space-y-1.5 text-[12.5px]">
        {[
          ["Documents", data.counts.documents],
          ["Entities", data.counts.entities],
          ["Relations", data.counts.relations],
          ["Communities", data.counts.communities],
        ].map(([label, value]) => (
          <div key={label} className="flex justify-between">
            <dt className="text-muted-foreground">{label}</dt>
            <dd className="font-medium tabular-nums">{formatCompact(Number(value))}</dd>
          </div>
        ))}
      </dl>
      {busy || data.pending_build ? (
        <p className="text-primary flex items-center gap-1.5 pt-1 text-[12px]">
          <span className="bg-primary animate-pulse-dot size-1.5 rounded-full" aria-hidden />
          {busy ? `${busy} document${busy > 1 ? "s" : ""} in the pipeline` : "Building communities"}
        </p>
      ) : null}
    </div>
  );
}

function Sidebar({
  me,
  current,
  onNavigate,
}: {
  me: Me;
  current: ProjectSummary;
  onNavigate?: () => void;
}) {
  const pathname = usePathname();
  const base = `/p/${current.slug}`;
  return (
    <div className="border-sidebar-border bg-sidebar flex h-full w-64 flex-col border-r">
      <div className="px-3 pt-3 pb-2">
        <ProjectSwitcher current={current} all={me.projects} />
      </div>
      <nav className="mt-1 space-y-0.5 px-3" aria-label="Project">
        {NAV.map(({ segment, label, icon: Icon }) => {
          const href = segment ? `${base}/${segment}` : base;
          const active = segment ? pathname.startsWith(href) : pathname === base;
          return (
            <Link
              key={label}
              href={href}
              onClick={onNavigate}
              aria-current={active ? "page" : undefined}
              className={cn(
                "flex items-center gap-2.5 rounded-lg px-2.5 py-1.5 text-[13.5px] transition-colors [&_svg]:size-4",
                active
                  ? "bg-card text-foreground ring-border font-medium shadow-sm ring-1"
                  : "text-muted-foreground hover:bg-muted hover:text-foreground",
              )}
            >
              <Icon className={active ? "text-primary" : ""} />
              {label}
            </Link>
          );
        })}
      </nav>
      <div className="mt-6 flex min-h-0 flex-1 flex-col">
        <p className="text-subtle px-5 pb-1.5 text-[11px] font-medium tracking-wider uppercase">
          Graph
        </p>
        <div className="scroll-quiet min-h-0 flex-1 overflow-y-auto px-3 pb-3">
          <GraphSummary project={current.slug} />
        </div>
      </div>
      <div className="border-sidebar-border border-t p-3">
        <UserMenu user={me.user} />
      </div>
    </div>
  );
}

export function AppShell({ project, children }: { project: string; children: ReactNode }) {
  const router = useRouter();
  const pathname = usePathname();
  const me = useMe();
  const [drawer, setDrawer] = useState(false);
  const unauthorized = me.error instanceof ApiError && me.error.status === 401;
  const current = me.data?.projects.find((p) => p.slug === project || p.id === project);

  useEffect(() => {
    if (unauthorized) router.replace(`/login?next=${encodeURIComponent(pathname)}`);
  }, [unauthorized, pathname, router]);

  useEffect(() => {
    if (current) writeLocal(LAST_PROJECT_KEY, current.slug);
  }, [current]);

  if (me.isLoading || unauthorized) {
    return (
      <div className="flex h-dvh items-center justify-center">
        <Spinner className="size-5" />
      </div>
    );
  }
  if (me.error || !me.data) {
    return (
      <EmptyState
        className="h-dvh"
        title="GraphRAG is unreachable"
        description={me.error?.message ?? "Try again shortly."}
      />
    );
  }
  if (!current) {
    return (
      <EmptyState
        className="h-dvh"
        title="Project not found"
        description="It does not exist, or you are not a member."
        action={
          <Button asChild variant="secondary">
            <Link href="/">Go to my projects</Link>
          </Button>
        }
      />
    );
  }

  return (
    <div className="flex h-dvh overflow-hidden">
      <aside className="hidden lg:block">
        <Sidebar me={me.data} current={current} />
      </aside>
      {drawer ? (
        <div className="fixed inset-0 z-40 lg:hidden">
          <button
            type="button"
            aria-label="Close menu"
            className="absolute inset-0 bg-black/40"
            onClick={() => setDrawer(false)}
          />
          <div className="animate-fade-in relative h-full w-64">
            <Sidebar me={me.data} current={current} onNavigate={() => setDrawer(false)} />
          </div>
        </div>
      ) : null}
      <div className="flex min-w-0 flex-1 flex-col">
        <header className="border-border flex h-12 items-center justify-between border-b px-3 lg:hidden">
          <Button
            variant="ghost"
            size="icon-sm"
            aria-label="Open menu"
            onClick={() => setDrawer(true)}
          >
            {drawer ? <X /> : <Menu />}
          </Button>
          <Wordmark name={runtimeEnv().productName} className="[&_svg]:size-6" />
          <span className="size-8" />
        </header>
        <main className="scroll-quiet min-h-0 flex-1 overflow-y-auto">{children}</main>
      </div>
    </div>
  );
}
