import { cn } from "@/lib/cn";
import { typeColor, typeLabel } from "@/lib/graph";

/** An entity type as a coloured dot and a name. */
export function TypeBadge({ type, className }: { type: string; className?: string }) {
  return (
    <span
      className={cn(
        "text-muted-foreground inline-flex items-center gap-1.5 text-[12.5px]",
        className,
      )}
    >
      <span
        aria-hidden
        className="size-2.5 shrink-0 rounded-full"
        style={{ backgroundColor: typeColor(type) }}
      />
      {typeLabel(type)}
    </span>
  );
}
