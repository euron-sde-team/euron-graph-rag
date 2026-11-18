"use client";

import {
  Area,
  AreaChart,
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import { formatDate } from "@/lib/format";
import { predicateLabel, typeColor, typeLabel } from "@/lib/graph";

const axis = { fontSize: 11, fill: "var(--subtle)" };
const tooltip = {
  contentStyle: {
    background: "var(--card)",
    border: "1px solid var(--border)",
    borderRadius: 8,
    fontSize: 12,
    boxShadow: "var(--shadow-md)",
  },
  labelStyle: { color: "var(--foreground)", fontWeight: 600 },
  itemStyle: { color: "var(--muted-foreground)" },
  cursor: { fill: "var(--muted)" },
};

/** Entities per type, one bar each in the type's own colour. */
export function TypeBars({ data }: { data: { type: string; count: number }[] }) {
  const rows = data.map((d) => ({ ...d, label: typeLabel(d.type) }));
  return (
    <div
      role="img"
      aria-label={`Entities by type: ${rows.map((r) => `${r.label} ${r.count}`).join(", ")}`}
    >
      <ResponsiveContainer width="100%" height={Math.max(160, rows.length * 30)}>
        <BarChart data={rows} layout="vertical" margin={{ left: 4, right: 24, top: 4, bottom: 4 }}>
          <CartesianGrid horizontal={false} stroke="var(--border)" />
          <XAxis
            type="number"
            tick={axis}
            axisLine={false}
            tickLine={false}
            allowDecimals={false}
          />
          <YAxis
            type="category"
            dataKey="label"
            width={92}
            tick={axis}
            axisLine={false}
            tickLine={false}
          />
          <Tooltip {...tooltip} formatter={(value) => [value, "Entities"]} />
          <Bar dataKey="count" radius={[0, 4, 4, 0]} barSize={14} isAnimationActive={false}>
            {rows.map((row) => (
              <Cell key={row.type} fill={typeColor(row.type)} />
            ))}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}

/** The most common relation verbs. */
export function PredicateBars({ data }: { data: { predicate: string; count: number }[] }) {
  const rows = data.slice(0, 8).map((d) => ({ ...d, label: predicateLabel(d.predicate) }));
  return (
    <div
      role="img"
      aria-label={`Relations by kind: ${rows.map((r) => `${r.label} ${r.count}`).join(", ")}`}
    >
      <ResponsiveContainer width="100%" height={Math.max(160, rows.length * 28)}>
        <BarChart data={rows} layout="vertical" margin={{ left: 4, right: 24, top: 4, bottom: 4 }}>
          <CartesianGrid horizontal={false} stroke="var(--border)" />
          <XAxis
            type="number"
            tick={axis}
            axisLine={false}
            tickLine={false}
            allowDecimals={false}
          />
          <YAxis
            type="category"
            dataKey="label"
            width={104}
            tick={axis}
            axisLine={false}
            tickLine={false}
          />
          <Tooltip {...tooltip} formatter={(value) => [value, "Relations"]} />
          <Bar
            dataKey="count"
            fill="var(--community-0)"
            radius={[0, 4, 4, 0]}
            barSize={12}
            isAnimationActive={false}
          />
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}

/** Questions per day over the last two weeks. */
export function TrafficChart({ data }: { data: { day: string; queries: number }[] }) {
  const rows = data.map((d) => ({ ...d, label: formatDate(d.day).replace(/, \d{4}$/, "") }));
  return (
    <div
      role="img"
      aria-label={`Questions per day: ${rows.map((r) => `${r.label} ${r.queries}`).join(", ")}`}
    >
      <ResponsiveContainer width="100%" height={190}>
        <AreaChart data={rows} margin={{ left: -18, right: 8, top: 8, bottom: 0 }}>
          <defs>
            <linearGradient id="traffic" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor="var(--community-0)" stopOpacity={0.4} />
              <stop offset="100%" stopColor="var(--community-0)" stopOpacity={0.03} />
            </linearGradient>
          </defs>
          <CartesianGrid vertical={false} stroke="var(--border)" />
          <XAxis
            dataKey="label"
            tick={axis}
            axisLine={false}
            tickLine={false}
            interval="preserveStartEnd"
            minTickGap={24}
          />
          <YAxis tick={axis} axisLine={false} tickLine={false} allowDecimals={false} />
          <Tooltip {...tooltip} formatter={(value) => [value, "Questions"]} />
          <Area
            type="monotone"
            dataKey="queries"
            stroke="var(--community-0)"
            strokeWidth={2}
            fill="url(#traffic)"
            isAnimationActive={false}
          />
        </AreaChart>
      </ResponsiveContainer>
    </div>
  );
}
