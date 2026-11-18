export type TextPart = { text: string; match: boolean };

/** Split `text` so each (case-insensitive) occurrence of any term is its own part. */
export function highlightParts(text: string, terms: string[]): TextPart[] {
  const cleaned = [...new Set(terms.map((t) => t.trim()).filter((t) => t.length > 1))].sort(
    (a, b) => b.length - a.length,
  );
  if (!cleaned.length) return [{ text, match: false }];
  const pattern = new RegExp(
    `(${cleaned.map((t) => t.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")).join("|")})`,
    "gi",
  );
  return text
    .split(pattern)
    .filter((part) => part !== "")
    .map((part) => ({
      text: part,
      match: cleaned.some((t) => t.toLowerCase() === part.toLowerCase()),
    }));
}

/** Pull the [n] citation markers out of an answer, in order of first appearance. */
export function citationMarkers(answer: string): number[] {
  const seen: number[] = [];
  for (const match of answer.matchAll(/\[(\d{1,3})\]/g)) {
    const n = Number(match[1]);
    if (!seen.includes(n)) seen.push(n);
  }
  return seen;
}

export type AnswerPart = { kind: "text"; text: string } | { kind: "cite"; n: number };

/** The answer as text and citation parts, so each [n] can render as a chip. */
export function answerParts(answer: string): AnswerPart[] {
  const parts: AnswerPart[] = [];
  let last = 0;
  for (const match of answer.matchAll(/\[(\d{1,3})\]/g)) {
    const index = match.index ?? 0;
    if (index > last) parts.push({ kind: "text", text: answer.slice(last, index) });
    parts.push({ kind: "cite", n: Number(match[1]) });
    last = index + match[0].length;
  }
  if (last < answer.length) parts.push({ kind: "text", text: answer.slice(last) });
  return parts;
}
