import { cn } from "@/lib/cn";

/** Three linked nodes, the smallest graph: documents turned into connected knowledge. */
export function BrandMark({ className }: { className?: string }) {
  return (
    <svg viewBox="0 0 64 64" aria-hidden className={cn("size-7", className)}>
      <rect width="64" height="64" rx="16" fill="var(--primary)" />
      <path
        d="M20 42 L32 20 L45 40 M20 42 L45 40"
        fill="none"
        stroke="var(--primary-foreground)"
        strokeWidth="3"
        strokeLinejoin="round"
        opacity="0.75"
      />
      <circle cx="32" cy="20" r="7" fill="var(--primary-foreground)" />
      <circle cx="20" cy="42" r="5.5" fill="var(--primary-foreground)" opacity="0.9" />
      <circle cx="45" cy="40" r="5" fill="var(--primary-foreground)" opacity="0.8" />
    </svg>
  );
}

export function Wordmark({ name, className }: { name: string; className?: string }) {
  return (
    <span className={cn("flex items-center gap-2.5", className)}>
      <BrandMark />
      <span className="text-[15px] font-semibold tracking-tight">{name}</span>
    </span>
  );
}
