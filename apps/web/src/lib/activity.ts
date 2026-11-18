import type { AuditEvent } from "@/lib/types";

const text = (value: unknown, fallback = ""): string =>
  typeof value === "string" || typeof value === "number" ? String(value) : fallback;

const PHRASES: Record<string, (d: Record<string, unknown>) => string> = {
  "project.created": () => "created the project",
  "project.updated": () => "updated the project details",
  "member.added": (d) => `added ${text(d.email, "a member")} as ${text(d.role, "a member")}`,
  "member.role_changed": (d) => `changed a member's role to ${text(d.role)}`,
  "member.removed": () => "removed a member",
  "document.added": (d) => `added ${text(d.external_id, "a document")}`,
  "document.updated": () => "edited a document",
  "document.reprocessed": () => "reprocessed a document",
  "document.deleted": (d) =>
    `deleted ${text(d.external_id, "a document")} (${text(d.entities_removed, "0")} entities removed)`,
  "entity.updated": (d) => `edited the entity ${text(d.name)}`,
  "entity.deleted": (d) => `deleted the entity ${text(d.name)}`,
  "entity.merged": (d) => `merged ${text(d.merged, "some")} entities into one`,
  "build.requested": () => "requested a graph rebuild",
  "api_key.created": (d) => `created the API key ${text(d.name)}`,
  "api_key.revoked": (d) => `revoked the API key ${text(d.name)}`,
};

/** "Maya Iyer merged 2 entities into one": the actor plus a readable phrase. */
export function describeEvent(event: AuditEvent): { actor: string; phrase: string } {
  const phrase = PHRASES[event.action]?.(event.details) ?? event.action.replace(/[._]/g, " ");
  return { actor: event.actor ?? "An API key", phrase };
}
