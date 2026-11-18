"use client";

import { keepPreviousData, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { api, proj } from "@/lib/api";
import type {
  ApiKey,
  ApiKeyCreated,
  AuditEvent,
  Build,
  Chunk,
  Community,
  CommunityDetail,
  Document,
  DocumentDetail,
  DuplicateGroup,
  Entity,
  EntityDetail,
  EntityListItem,
  Explore,
  GraphSettings,
  IngestResult,
  Me,
  Member,
  Overview,
  Page,
  Project,
  QueryResponse,
  QuerySummary,
  Role,
  SearchMode,
  SystemInfo,
  TreeNode,
  User,
} from "@/lib/types";

export const qk = {
  system: ["system"] as const,
  me: ["me"] as const,
  project: (p: string) => ["project", p] as const,
  overview: (p: string) => ["overview", p] as const,
  documents: (p: string) => ["documents", p] as const,
  document: (p: string, id: string) => ["document", p, id] as const,
  graph: (p: string) => ["graph", p] as const,
  entity: (p: string, id: string) => ["entity", p, id] as const,
  communities: (p: string) => ["communities", p] as const,
  community: (p: string, id: string) => ["community", p, id] as const,
  builds: (p: string) => ["builds", p] as const,
  queries: (p: string) => ["queries", p] as const,
  members: (p: string) => ["members", p] as const,
  apiKeys: (p: string) => ["api-keys", p] as const,
  activity: (p: string) => ["activity", p] as const,
};

const BUSY = new Set(["queued", "processing", "running"]);

// Accounts --------------------------------------------------------------------------------

export function useSystemInfo() {
  return useQuery({
    queryKey: qk.system,
    queryFn: () => api<SystemInfo>("/api/v1/system/info"),
    staleTime: 300_000,
  });
}

export function useMe() {
  return useQuery({ queryKey: qk.me, queryFn: () => api<Me>("/api/v1/auth/me"), retry: false });
}

export function useLogin() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (body: { email: string; password: string }) =>
      api<{ user: User }>("/api/v1/auth/login", { method: "POST", json: body }),
    onSuccess: () => client.invalidateQueries({ queryKey: qk.me }),
  });
}

export function useSignup() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (body: { email: string; name: string; password: string }) =>
      api<{ user: User }>("/api/v1/auth/signup", { method: "POST", json: body }),
    onSuccess: () => client.invalidateQueries({ queryKey: qk.me }),
  });
}

export function useLogout() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: () => api<void>("/api/v1/auth/logout", { method: "POST" }),
    onSettled: () => client.clear(),
  });
}

export function useChangePassword() {
  return useMutation({
    mutationFn: (body: { current_password: string; new_password: string }) =>
      api<{ user: User }>("/api/v1/auth/password", { method: "POST", json: body }),
  });
}

// Projects --------------------------------------------------------------------------------

export function useProject(project: string) {
  return useQuery({ queryKey: qk.project(project), queryFn: () => api<Project>(proj(project)) });
}

export function useCreateProject() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (body: { name: string; description: string }) =>
      api<Project>("/api/v1/projects", { method: "POST", json: body }),
    onSuccess: () => client.invalidateQueries({ queryKey: qk.me }),
  });
}

export function useUpdateProject(project: string) {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (body: { name?: string; description?: string; settings?: GraphSettings }) =>
      api<Project>(proj(project), { method: "PATCH", json: body }),
    onSuccess: () => {
      client.invalidateQueries({ queryKey: qk.project(project) });
      client.invalidateQueries({ queryKey: qk.me });
    },
  });
}

export function useMembers(project: string) {
  return useQuery({
    queryKey: qk.members(project),
    queryFn: () => api<Member[]>(`${proj(project)}/members`),
  });
}

export function useMemberActions(project: string) {
  const client = useQueryClient();
  const refresh = () => client.invalidateQueries({ queryKey: qk.members(project) });
  return {
    add: useMutation({
      mutationFn: (body: { email: string; name?: string; role: Role }) =>
        api<{ member: Member; temporary_password: string | null }>(`${proj(project)}/members`, {
          method: "POST",
          json: body,
        }),
      onSuccess: refresh,
    }),
    change: useMutation({
      mutationFn: ({ userId, role }: { userId: string; role: Role }) =>
        api<Member>(`${proj(project)}/members/${userId}`, { method: "PATCH", json: { role } }),
      onSuccess: refresh,
    }),
    remove: useMutation({
      mutationFn: (userId: string) =>
        api<void>(`${proj(project)}/members/${userId}`, { method: "DELETE" }),
      onSuccess: refresh,
    }),
  };
}

export function useApiKeys(project: string) {
  return useQuery({
    queryKey: qk.apiKeys(project),
    queryFn: () => api<ApiKey[]>(`${proj(project)}/api-keys`),
  });
}

export function useApiKeyActions(project: string) {
  const client = useQueryClient();
  const refresh = () => client.invalidateQueries({ queryKey: qk.apiKeys(project) });
  return {
    create: useMutation({
      mutationFn: (body: {
        name: string;
        role: "viewer" | "editor";
        expires_in_days: number | null;
      }) => api<ApiKeyCreated>(`${proj(project)}/api-keys`, { method: "POST", json: body }),
      onSuccess: refresh,
    }),
    revoke: useMutation({
      mutationFn: (id: string) =>
        api<void>(`${proj(project)}/api-keys/${id}`, { method: "DELETE" }),
      onSuccess: refresh,
    }),
  };
}

export function useActivity(project: string) {
  return useQuery({
    queryKey: qk.activity(project),
    queryFn: () => api<Page<AuditEvent>>(`${proj(project)}/activity?limit=50`),
  });
}

// Documents -------------------------------------------------------------------------------

export type DocumentFilters = { status?: string; q?: string };

export function useDocuments(project: string, filters: DocumentFilters = {}) {
  const params = new URLSearchParams({ limit: "100" });
  if (filters.status) params.set("status", filters.status);
  if (filters.q) params.set("q", filters.q);
  return useQuery({
    queryKey: [...qk.documents(project), filters],
    queryFn: () => api<Page<Document>>(`${proj(project)}/documents?${params}`),
    placeholderData: keepPreviousData,
    // Follow the pipeline while anything is still moving through it.
    refetchInterval: (query) =>
      query.state.data?.items.some((d) => BUSY.has(d.status)) ? 2000 : false,
  });
}

export function useDocument(project: string, id: string) {
  return useQuery({
    queryKey: qk.document(project, id),
    queryFn: () => api<DocumentDetail>(`${proj(project)}/documents/${id}`),
    refetchInterval: (query) =>
      query.state.data && BUSY.has(query.state.data.status) ? 2000 : false,
  });
}

export function useChunks(project: string, id: string, offset: number) {
  return useQuery({
    queryKey: ["chunks", project, id, offset],
    queryFn: () =>
      api<Page<Chunk>>(`${proj(project)}/documents/${id}/chunks?limit=20&offset=${offset}`),
    placeholderData: keepPreviousData,
  });
}

function useRefreshGraph(project: string) {
  const client = useQueryClient();
  return () => {
    for (const key of [
      qk.documents(project),
      ["document", project],
      qk.overview(project),
      qk.graph(project),
      qk.communities(project),
      qk.builds(project),
      ["entity", project],
    ]) {
      client.invalidateQueries({ queryKey: key });
    }
    client.invalidateQueries({ queryKey: qk.me });
  };
}

export function useIngest(project: string) {
  const refresh = useRefreshGraph(project);
  return {
    upload: useMutation({
      mutationFn: ({ files, metadata }: { files: File[]; metadata: Record<string, unknown> }) => {
        const form = new FormData();
        for (const file of files) form.append("files", file);
        if (Object.keys(metadata).length) form.append("metadata", JSON.stringify(metadata));
        return api<IngestResult>(`${proj(project)}/documents`, { method: "POST", body: form });
      },
      onSuccess: refresh,
    }),
    importSources: useMutation({
      mutationFn: (items: Record<string, unknown>[]) =>
        api<IngestResult>(`${proj(project)}/documents/import`, { method: "POST", json: { items } }),
      onSuccess: refresh,
    }),
  };
}

export function useDocumentActions(project: string) {
  const refresh = useRefreshGraph(project);
  return {
    reprocess: useMutation({
      mutationFn: (id: string) =>
        api<Document>(`${proj(project)}/documents/${id}/reprocess`, { method: "POST" }),
      onSuccess: refresh,
    }),
    remove: useMutation({
      mutationFn: (id: string) =>
        api<void>(`${proj(project)}/documents/${id}`, { method: "DELETE" }),
      onSuccess: refresh,
    }),
  };
}

// The graph -------------------------------------------------------------------------------

export type EntityFilters = {
  q?: string;
  types?: string[];
  community?: string;
  document?: string;
  sort?: string;
  level?: number;
  offset?: number;
  limit?: number;
};

function entityParams(f: EntityFilters): URLSearchParams {
  const params = new URLSearchParams();
  if (f.q) params.set("q", f.q);
  for (const type of f.types ?? []) params.append("type", type);
  if (f.community) params.set("community", f.community);
  if (f.document) params.set("document", f.document);
  if (f.sort) params.set("sort", f.sort);
  if (f.level !== undefined) params.set("level", String(f.level));
  params.set("limit", String(f.limit ?? 50));
  params.set("offset", String(f.offset ?? 0));
  return params;
}

export function useEntities(project: string, filters: EntityFilters) {
  return useQuery({
    queryKey: [...qk.graph(project), "entities", filters],
    queryFn: () =>
      api<Page<EntityListItem>>(`${proj(project)}/graph/entities?${entityParams(filters)}`),
    placeholderData: keepPreviousData,
  });
}

export function useEntity(project: string, id: string | null) {
  return useQuery({
    queryKey: qk.entity(project, id ?? ""),
    queryFn: () => api<EntityDetail>(`${proj(project)}/graph/entities/${id}`),
    enabled: id !== null,
  });
}

export type ExploreFilters = {
  q?: string;
  types?: string[];
  community?: string;
  focus?: string | null;
  hops?: number;
  level?: number;
  limit?: number;
  minWeight?: number;
};

export function useExplore(project: string, f: ExploreFilters) {
  const params = new URLSearchParams();
  if (f.q) params.set("q", f.q);
  for (const type of f.types ?? []) params.append("type", type);
  if (f.community) params.set("community", f.community);
  if (f.focus) params.set("focus", f.focus);
  if (f.hops) params.set("hops", String(f.hops));
  params.set("level", String(f.level ?? 0));
  params.set("limit", String(f.limit ?? 120));
  if (f.minWeight) params.set("min_weight", String(f.minWeight));
  return useQuery({
    queryKey: [...qk.graph(project), "explore", f],
    queryFn: () => api<Explore>(`${proj(project)}/graph/explore?${params}`),
    placeholderData: keepPreviousData,
  });
}

export function useDuplicates(project: string) {
  return useQuery({
    queryKey: [...qk.graph(project), "duplicates"],
    queryFn: () => api<DuplicateGroup[]>(`${proj(project)}/graph/duplicates`),
  });
}

export function useEntityActions(project: string) {
  const refresh = useRefreshGraph(project);
  return {
    update: useMutation({
      mutationFn: ({
        id,
        ...body
      }: {
        id: string;
        name?: string;
        type?: string;
        description?: string;
      }) => api<Entity>(`${proj(project)}/graph/entities/${id}`, { method: "PATCH", json: body }),
      onSuccess: refresh,
    }),
    remove: useMutation({
      mutationFn: (id: string) =>
        api<void>(`${proj(project)}/graph/entities/${id}`, { method: "DELETE" }),
      onSuccess: refresh,
    }),
    merge: useMutation({
      mutationFn: (body: { survivor_id: string; entity_ids: string[] }) =>
        api<{ survivor: Entity; merged: number }>(`${proj(project)}/graph/merge`, {
          method: "POST",
          json: body,
        }),
      onSuccess: refresh,
    }),
  };
}

// Communities and builds ------------------------------------------------------------------

export function useCommunityTree(project: string) {
  return useQuery({
    queryKey: [...qk.communities(project), "tree"],
    queryFn: () => api<TreeNode[]>(`${proj(project)}/communities/tree`),
  });
}

export function useCommunities(project: string, level: number | null, q: string) {
  const params = new URLSearchParams({ limit: "100" });
  if (level !== null) params.set("level", String(level));
  if (q) params.set("q", q);
  return useQuery({
    queryKey: [...qk.communities(project), "list", level, q],
    queryFn: () => api<Page<Community>>(`${proj(project)}/communities?${params}`),
    placeholderData: keepPreviousData,
  });
}

export function useCommunity(project: string, id: string | null) {
  return useQuery({
    queryKey: qk.community(project, id ?? ""),
    queryFn: () => api<CommunityDetail>(`${proj(project)}/communities/${id}`),
    enabled: id !== null,
  });
}

export function useBuilds(project: string) {
  return useQuery({
    queryKey: qk.builds(project),
    queryFn: () => api<Page<Build>>(`${proj(project)}/builds?limit=10`),
    refetchInterval: (query) =>
      query.state.data?.items.some((b) => BUSY.has(b.status)) ? 2000 : false,
  });
}

export function useRebuild(project: string) {
  const refresh = useRefreshGraph(project);
  return useMutation({
    mutationFn: () => api<Build>(`${proj(project)}/builds`, { method: "POST" }),
    onSuccess: refresh,
  });
}

// Questions -------------------------------------------------------------------------------

export type AskRequest = {
  question: string;
  mode: SearchMode;
  top_k: number;
  hops: number;
  level: number | null;
};

export function useAsk(project: string) {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (body: AskRequest) =>
      api<QueryResponse>(`${proj(project)}/query`, {
        method: "POST",
        json: { ...body, cache: false },
      }),
    onSuccess: () => {
      client.invalidateQueries({ queryKey: qk.queries(project) });
      client.invalidateQueries({ queryKey: qk.overview(project) });
    },
  });
}

export function useQueryHistory(project: string) {
  return useQuery({
    queryKey: qk.queries(project),
    queryFn: () => api<Page<QuerySummary>>(`${proj(project)}/queries?limit=12`),
  });
}

export function useOverview(project: string) {
  return useQuery({
    queryKey: qk.overview(project),
    queryFn: () => api<Overview>(`${proj(project)}/overview`),
    refetchInterval: (query) => {
      const data = query.state.data;
      return data && (data.pending_build || data.pipeline.queued + data.pipeline.processing > 0)
        ? 3000
        : false;
    },
  });
}

export async function fetchQuery(project: string, id: string): Promise<QueryResponse> {
  return api<QueryResponse>(`${proj(project)}/queries/${id}`);
}
