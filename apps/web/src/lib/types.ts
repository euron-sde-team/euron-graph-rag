/** Shapes of the API's responses (see docs/api/openapi.json). */

export type Role = "owner" | "editor" | "viewer";

export type Page<T> = { items: T[]; total: number; limit: number; offset: number };

export type User = { id: string; email: string; name: string; is_admin: boolean };

export type ProjectSummary = {
  id: string;
  slug: string;
  name: string;
  role: Role;
  document_count: number;
  entity_count: number;
  member_count: number;
};

export type Me = { user: User; projects: ProjectSummary[] };

export type GraphSettings = {
  entity_types: string[];
  chunk_tokens: number;
  overlap_tokens: number;
  community_levels: number;
  resolution: number;
  auto_build: boolean;
};

export type Project = {
  id: string;
  slug: string;
  name: string;
  description: string;
  role: Role;
  settings: GraphSettings;
  graph_version: number;
  created_at: string;
};

export type Member = {
  user_id: string;
  email: string;
  name: string;
  role: Role;
  joined_at: string;
};

export type AuditEvent = {
  id: string;
  action: string;
  target_type: string;
  target_id: string | null;
  details: Record<string, unknown>;
  actor: string | null;
  created_at: string;
};

export type ApiKey = {
  id: string;
  name: string;
  prefix: string;
  role: "viewer" | "editor";
  created_at: string;
  last_used_at: string | null;
  expires_at: string | null;
  revoked_at: string | null;
};

export type ApiKeyCreated = ApiKey & { key: string };

export type ProviderInfo = { provider: string; model: string; deterministic: boolean };

export type SystemInfo = {
  product_name: string;
  version: string;
  extractor: ProviderInfo;
  reporter: ProviderInfo;
  answerer: ProviderInfo;
  embedding: { provider: string; model: string; dim: number };
  supported_dims: number[];
  search_modes: string[];
  entity_types: string[];
  max_upload_mb: number;
  accepted_extensions: string[];
  allow_signup: boolean;
  needs_setup: boolean;
};

export type JobStatus = "queued" | "processing" | "ready" | "failed";
export type PipelineStage = "queued" | "parsing" | "embedding" | "extracting" | "done";

export type Document = {
  id: string;
  external_id: string;
  title: string;
  source_type: "file" | "url" | "text";
  source_uri: string | null;
  kind: string | null;
  size_bytes: number;
  metadata: Record<string, unknown>;
  status: JobStatus;
  stage: PipelineStage;
  error: string | null;
  section_count: number;
  token_count: number;
  chunk_count: number;
  entity_count: number;
  relation_count: number;
  created_at: string;
  parsed_at: string | null;
  extracted_at: string | null;
};

export type DocumentEntity = { id: string; name: string; type: string; mentions: number };
export type DocumentDetail = Document & { entities: DocumentEntity[] };

export type Chunk = {
  id: string;
  ordinal: number;
  heading: string;
  location: string;
  text: string;
  token_count: number;
};

export type IngestResult = {
  created: Document[];
  duplicates: Document[];
  rejected: { name: string; code: string; message: string }[];
};

export type CommunityRef = { id: string; level: number; ordinal: number; title: string };

export type Entity = {
  id: string;
  name: string;
  type: string;
  description: string;
  aliases: string[];
  mention_count: number;
  degree: number;
  importance: number;
};

export type EntityListItem = Entity & { community: CommunityRef | null };
export type EntityBrief = { id: string; name: string; type: string; degree: number };

export type Relation = {
  id: string;
  source_id: string;
  target_id: string;
  predicate: string;
  description: string;
  weight: number;
  evidence_count: number;
};

export type Neighbor = {
  relation: Relation;
  direction: "in" | "out";
  entity: EntityBrief;
  quote: string;
  chunk_id: string | null;
};

export type EntitySource = {
  chunk_id: string;
  document_id: string;
  document_title: string;
  location: string;
  heading: string;
  text: string;
  surface: string;
  count: number;
};

export type EntityDetail = Entity & {
  created_at: string;
  communities: CommunityRef[];
  neighbors: Neighbor[];
  sources: EntitySource[];
};

export type ExploreNode = {
  id: string;
  name: string;
  type: string;
  degree: number;
  importance: number;
  mention_count: number;
  community_id: string | null;
  community_ordinal: number | null;
};

export type ExploreEdge = {
  id: string;
  source: string;
  target: string;
  predicate: string;
  weight: number;
};

export type Explore = {
  nodes: ExploreNode[];
  edges: ExploreEdge[];
  total_entities: number;
  total_relations: number;
  truncated: boolean;
  types: { type: string; count: number }[];
  communities: { id: string; ordinal: number; title: string; count: number }[];
  focus: string | null;
};

export type DuplicateMember = {
  id: string;
  name: string;
  type: string;
  mention_count: number;
  reason: string;
};
export type DuplicateGroup = { survivor: DuplicateMember; members: DuplicateMember[] };

export type Community = {
  id: string;
  parent_id: string | null;
  level: number;
  ordinal: number;
  title: string;
  summary: string;
  entity_count: number;
  relation_count: number;
  rank: number;
  reporter: string;
};

export type SourceRef = {
  chunk_id: string;
  document_id: string;
  document_title: string;
  location: string;
};

export type Finding = { summary: string; explanation: string; sources: SourceRef[] };

export type CommunityDetail = Community & {
  findings: Finding[];
  members: EntityBrief[];
  children: Community[];
  parent: Community | null;
};

export type TreeNode = {
  id: string;
  parent_id: string | null;
  level: number;
  title: string;
  entity_count: number;
  rank: number;
};

export type Build = {
  id: string;
  status: "queued" | "running" | "completed" | "failed";
  trigger: string;
  params: Record<string, unknown>;
  stats: {
    entities?: number;
    relations?: number;
    merged?: number;
    communities?: number;
    levels?: number[];
    modularity?: number;
    isolated?: number;
    seconds?: number;
  };
  error: string | null;
  attempts: number;
  created_at: string;
  started_at: string | null;
  finished_at: string | null;
};

export type SearchMode = "local" | "global" | "hybrid";

export type Citation = {
  n: number;
  kind: "chunk" | "community";
  id: string;
  label: string;
  snippet: string;
  score: number;
  cited: boolean;
  document_id: string | null;
  document_title: string | null;
  location: string | null;
  supports: string[];
};

export type NodeUse = {
  id: string;
  name: string;
  type: string;
  role: "seed" | "neighbor";
  score: number;
  degree: number;
};

export type EdgeUse = {
  id: string;
  source_id: string;
  target_id: string;
  predicate: string;
  weight: number;
};

export type CommunityUse = {
  id: string;
  level: number;
  title: string;
  score: number;
  points: string[];
};

export type Step = { name: string; detail: string; ms: number };

export type QueryResponse = {
  id: string;
  mode: SearchMode;
  question: string;
  answer: string;
  answerer: string;
  citations: Citation[];
  nodes: NodeUse[];
  edges: EdgeUse[];
  communities: CommunityUse[];
  steps: Step[];
  latency_ms: number;
  prompt_tokens: number;
  completion_tokens: number;
  cached: boolean;
  created_at: string;
};

export type QuerySummary = {
  id: string;
  mode: SearchMode;
  question: string;
  answer: string;
  answerer: string;
  citation_count: number;
  latency_ms: number;
  cached: boolean;
  created_at: string;
};

export type Overview = {
  counts: {
    documents: number;
    chunks: number;
    entities: number;
    relations: number;
    communities: number;
    queries: number;
  };
  pipeline: { queued: number; processing: number; ready: number; failed: number };
  entity_types: { type: string; count: number }[];
  predicates: { predicate: string; count: number }[];
  community_levels: { level: number; count: number }[];
  top_entities: {
    id: string;
    name: string;
    type: string;
    degree: number;
    mention_count: number;
  }[];
  traffic: { day: string; queries: number; avg_latency_ms: number }[];
  modes: { mode: SearchMode; queries: number; avg_latency_ms: number }[];
  latest_build: Build | null;
  pending_build: Build | null;
  graph_version: number;
};
