"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import Link from "next/link";
import { signOut } from "next-auth/react";
import { useAuthToken } from "@/lib/useAuthToken";
import {
  getQueryHistory,
  getQueryLogDetail,
  getSavedEvidence,
  getScenarioDetails,
  getSessionStatus,
  logSessionEvent,
  queryAgentStream,
  removeEvidence,
  saveEvidence,
  updateEvidenceAnnotation,
  type Artifact,
  type Citation,
  type PendingFollowUp,
  type QueryLogDetail,
  type ReferencePanel,
  type SavedEvidence,
  type ScenarioDetail,
  type SessionStatus,
} from "@/lib/api";

const ACCENT_BG = "bg-emerald-500";
const ACCENT_BG_HOVER = "hover:bg-emerald-600";
const ACCENT_TEXT = "text-emerald-400";
const ACCENT_RING = "focus:ring-emerald-500";

const AGENTS = [
  { id: "analyst", label: "Data Analyst", subtitle: "SQL & Metrics Expert", icon: "database", color: "blue" },
  { id: "ux_researcher", label: "UX Researcher", subtitle: "User Behavior Specialist", icon: "person_search", color: "purple" },
  { id: "engineering_lead", label: "Engineering Lead", subtitle: "SRE & Systems Expert", icon: "terminal", color: "amber" },
] as const;

const QUICK_SUGGESTIONS: Record<string, string[]> = {
  analyst: ["Show daily order trends", "Break down checkout by platform", "What changed at the payment step?"],
  ux_researcher: ["What are users complaining about?", "Show ticket themes", "What does the usability study say?"],
  engineering_lead: ["Any recent payment deployments?", "Show payment error patterns", "Which services regressed?"],
};

const AGENT_INTROS: Record<string, { greeting: string; capabilities: string[] }> = {
  analyst: {
    greeting: "Hello, I'm the Data Analyst. I work the numbers and help investigate trends, funnels, segments, and customer-level behavior.",
    capabilities: ["Order and payment trends", "Platform and segment breakdowns", "Customer-level transaction history"],
  },
  ux_researcher: {
    greeting: "Hello, I'm the UX Researcher. I pull qualitative evidence from reviews, support tickets, and research notes.",
    capabilities: ["Support and review themes", "Usability evidence and quotes", "Recent UX change context"],
  },
  engineering_lead: {
    greeting: "Hello, I'm the Engineering Lead. I inspect deployments, service health, error patterns, and architecture clues.",
    capabilities: ["Deployment timelines", "Latency and error regressions", "Architecture and dependency clues"],
  },
};

interface ChatMessage {
  id: string;
  role: "user" | "agent";
  agent?: string;
  content: string;
  timestamp: string;
  queryLogId?: number;
  artifacts?: Artifact[];
  citations?: Citation[];
  warnings?: string[];
}

interface AgentGuidance {
  pendingFollowUp: PendingFollowUp | null;
  suggestions: string[];
}

function AgentIcon({ agent, size = "sm" }: { agent: string; size?: "sm" | "md" }) {
  const agentInfo = AGENTS.find((item) => item.id === agent);
  if (!agentInfo) return null;
  const colorMap: Record<string, string> = {
    blue: "bg-sky-500/15 text-sky-400",
    purple: "bg-violet-500/15 text-violet-400",
    amber: "bg-amber-500/15 text-amber-400",
  };
  return (
    <div className={`${size === "md" ? "size-10" : "size-8"} rounded-lg ${colorMap[agentInfo.color]} flex items-center justify-center shrink-0`}>
      <span className={`material-symbols-outlined ${size === "md" ? "text-base" : "text-sm"}`}>{agentInfo.icon}</span>
    </div>
  );
}

function MissionCard({ title, problem, onOpen }: { title: string; problem: string; onOpen: () => void }) {
  return (
    <button
      onClick={onOpen}
      className="flex items-center gap-3 px-5 py-2 rounded-lg bg-slate-100 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 hover:border-emerald-500/50 transition-colors text-left"
    >
      <span className={`material-symbols-outlined text-xl ${ACCENT_TEXT}`}>assignment</span>
      <div className="flex flex-col">
        <span className="text-sm font-bold text-slate-900 dark:text-slate-200">{title}</span>
        <span className="text-[10px] text-slate-500 font-medium truncate max-w-[440px]">
          {problem} <span className="text-emerald-500/80">open brief & sources</span>
        </span>
      </div>
    </button>
  );
}

function ReferenceModal({
  open,
  tab,
  onTabChange,
  onClose,
  reference,
}: {
  open: boolean;
  tab: "brief" | "sources";
  onTabChange: (tab: "brief" | "sources") => void;
  onClose: () => void;
  reference?: ReferencePanel;
}) {
  if (!open) return null;
  const brief = reference?.mission_brief;
  const sourceCatalog = reference?.source_catalog || [];
  const glossary = reference?.glossary || [];

  return (
    <div className="fixed inset-0 z-50 bg-slate-950/45 backdrop-blur-sm flex items-center justify-center p-6">
      <div className="w-full max-w-5xl max-h-[88vh] overflow-hidden rounded-2xl border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-900 shadow-2xl">
        <div className="flex items-center justify-between px-5 py-4 border-b border-slate-200 dark:border-slate-800">
          <div>
            <h3 className="text-lg font-semibold text-slate-900 dark:text-slate-100">Scenario Reference</h3>
            <p className="text-sm text-slate-500">Static context belongs here. Candidates decide what to save as evidence.</p>
          </div>
          <button onClick={onClose} className="text-slate-500 hover:text-slate-700 dark:hover:text-slate-200">
            <span className="material-symbols-outlined">close</span>
          </button>
        </div>
        <div className="px-5 pt-4 flex gap-2 border-b border-slate-200 dark:border-slate-800">
          {[
            { id: "brief", label: "Brief" },
            { id: "sources", label: "Sources & Dictionary" },
          ].map((item) => (
            <button
              key={item.id}
              onClick={() => onTabChange(item.id as "brief" | "sources")}
              className={`px-3 py-2 text-sm font-medium rounded-t-lg border ${
                tab === item.id
                  ? "border-slate-300 dark:border-slate-700 border-b-white dark:border-b-slate-900 text-slate-900 dark:text-slate-100"
                  : "border-transparent text-slate-500 hover:text-slate-700 dark:hover:text-slate-300"
              }`}
            >
              {item.label}
            </button>
          ))}
        </div>
        <div className="overflow-y-auto max-h-[calc(88vh-120px)] px-5 py-5">
          {tab === "brief" ? (
            <div className="space-y-5">
              <section>
                <p className="text-[11px] uppercase tracking-widest text-slate-500 font-bold mb-2">Problem</p>
                <p className="text-sm text-slate-700 dark:text-slate-300 leading-relaxed">{brief?.problem}</p>
              </section>
              <section>
                <p className="text-[11px] uppercase tracking-widest text-slate-500 font-bold mb-2">Objective</p>
                <p className="text-sm text-slate-700 dark:text-slate-300 leading-relaxed">{brief?.objective}</p>
              </section>
              {!!brief?.notes?.length && (
                <section>
                  <p className="text-[11px] uppercase tracking-widest text-slate-500 font-bold mb-2">Notes</p>
                  <div className="space-y-2">
                    {brief.notes.map((note) => (
                      <div key={note} className="flex items-start gap-2 text-sm text-slate-700 dark:text-slate-300">
                        <span className="mt-1 size-1.5 rounded-full bg-emerald-400 shrink-0" />
                        <span>{note}</span>
                      </div>
                    ))}
                  </div>
                </section>
              )}
            </div>
          ) : (
            <div className="space-y-5">
              {sourceCatalog.map((domain) => (
                <section key={domain.domain} className="rounded-xl border border-slate-200 dark:border-slate-800 overflow-hidden">
                  <div className="px-4 py-3 bg-slate-50 dark:bg-slate-800/40 border-b border-slate-200 dark:border-slate-800">
                    <div className="flex items-center justify-between gap-3">
                      <div>
                        <p className="text-sm font-semibold text-slate-900 dark:text-slate-100">{domain.domain}</p>
                        <p className="text-xs text-slate-500">Visible to {AGENTS.find((item) => item.id === domain.agent)?.label || domain.agent}</p>
                      </div>
                      <span className="text-[10px] px-2 py-1 rounded-full bg-slate-200 dark:bg-slate-700 text-slate-600 dark:text-slate-300 font-semibold">
                        {domain.sources.length} sources
                      </span>
                    </div>
                  </div>
                  <div className="p-4 space-y-4">
                    {domain.sources.map((source) => (
                      <div key={source.name} className="rounded-lg border border-slate-200 dark:border-slate-800 overflow-hidden">
                        <div className="px-3 py-2 bg-white dark:bg-slate-900 border-b border-slate-200 dark:border-slate-800">
                          <p className="text-sm font-mono font-semibold text-slate-800 dark:text-slate-200">{source.name}</p>
                          <p className="text-xs text-slate-500 mt-1">{source.description}</p>
                        </div>
                        {source.fields.length > 0 ? (
                          <div className="overflow-x-auto">
                            <table className="min-w-full text-left text-xs">
                              <thead className="bg-slate-50 dark:bg-slate-800/40 text-slate-500 uppercase tracking-wide">
                                <tr>
                                  <th className="px-3 py-2">Field</th>
                                  <th className="px-3 py-2">Type</th>
                                  <th className="px-3 py-2">Description</th>
                                </tr>
                              </thead>
                              <tbody>
                                {source.fields.map((field) => (
                                  <tr key={field.name} className="border-t border-slate-200 dark:border-slate-800">
                                    <td className="px-3 py-2 font-mono text-slate-700 dark:text-slate-300">{field.name}</td>
                                    <td className="px-3 py-2 text-slate-500">{field.type}</td>
                                    <td className="px-3 py-2 text-slate-600 dark:text-slate-400">{field.description}</td>
                                  </tr>
                                ))}
                              </tbody>
                            </table>
                          </div>
                        ) : (
                          <div className="px-3 py-3 text-xs text-slate-500">Reference document, not a row-based dataset.</div>
                        )}
                      </div>
                    ))}
                  </div>
                </section>
              ))}
              {!!glossary.length && (
                <section className="rounded-xl border border-slate-200 dark:border-slate-800 p-4">
                  <p className="text-sm font-semibold text-slate-900 dark:text-slate-100 mb-3">Glossary</p>
                  <div className="space-y-2">
                    {glossary.map((item) => (
                      <div key={item.term}>
                        <span className="text-xs font-semibold text-slate-700 dark:text-slate-300">{item.term}</span>
                        <span className="text-xs text-slate-500"> — {item.definition}</span>
                      </div>
                    ))}
                  </div>
                </section>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

function MetricArtifactView({ artifact }: { artifact: Extract<Artifact, { kind: "metric" }> }) {
  return (
    <div className="rounded-xl border border-slate-200 dark:border-slate-700/50 bg-white/80 dark:bg-slate-900/40 px-4 py-5">
      <p className="text-[11px] uppercase tracking-widest text-slate-500 font-bold mb-2">Metric</p>
      <div className="flex items-end gap-2">
        <span className="text-3xl font-semibold text-slate-900 dark:text-slate-100">
          {typeof artifact.value === "number" ? artifact.value.toLocaleString() : artifact.value}
        </span>
        {artifact.unit && <span className="text-sm text-slate-500 pb-1">{artifact.unit}</span>}
      </div>
      {artifact.subtitle && <p className="text-xs text-slate-500 mt-2">{artifact.subtitle}</p>}
    </div>
  );
}

function BarChart({ artifact }: { artifact: Extract<Artifact, { kind: "chart" }> }) {
  if (!artifact.series.length || artifact.labels.length === 0) return null;
  const multiSeries = artifact.series.length > 1;
  const allValues = artifact.series.flatMap(s => s.values);
  const max = Math.max(...allValues, 1);
  const colors = [
    { bar: "from-emerald-500 to-emerald-300", dot: "bg-emerald-500" },
    { bar: "from-blue-500 to-blue-300", dot: "bg-blue-500" },
    { bar: "from-amber-500 to-amber-300", dot: "bg-amber-500" },
    { bar: "from-purple-500 to-purple-300", dot: "bg-purple-500" },
    { bar: "from-rose-500 to-rose-300", dot: "bg-rose-500" },
    { bar: "from-cyan-500 to-cyan-300", dot: "bg-cyan-500" },
  ];
  const unitSuffix = artifact.unit ? artifact.unit : "";
  const formatVal = (v: number) => {
    const s = typeof v === "number" && v % 1 !== 0 ? v.toFixed(1) : v.toLocaleString();
    return unitSuffix ? `${s}${unitSuffix}` : s;
  };

  if (!multiSeries) {
    const series = artifact.series[0];
    return (
      <div className="flex flex-col gap-2">
        {artifact.labels.map((label, index) => {
          const value = series.values[index] ?? 0;
          const pct = Math.max(6, (value / max) * 100);
          return (
            <div key={`${label}-${index}`} className="flex items-center gap-3">
              <span className="w-28 shrink-0 truncate text-[11px] text-slate-500">{label}</span>
              <div className="flex-1 h-4 rounded-full bg-slate-200 dark:bg-slate-800 overflow-hidden">
                <div className="h-full rounded-full bg-gradient-to-r from-emerald-500 to-emerald-300" style={{ width: `${pct}%` }} />
              </div>
              <span className="w-16 shrink-0 text-right text-[11px] font-mono text-slate-500">
                {formatVal(value)}
              </span>
            </div>
          );
        })}
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-3">
      <div className="flex flex-wrap gap-3 text-[11px] text-slate-500">
        {artifact.series.map((s, i) => (
          <span key={s.name} className="flex items-center gap-1.5">
            <span className={`w-2.5 h-2.5 rounded-sm ${colors[i % colors.length].dot}`} />
            {s.name}
          </span>
        ))}
      </div>
      {artifact.labels.map((label, idx) => {
        const delta = artifact.series.length === 2
          ? (artifact.series[1].values[idx] ?? 0) - (artifact.series[0].values[idx] ?? 0)
          : null;
        return (
          <div key={`${label}-${idx}`} className="flex flex-col gap-1">
            <div className="flex items-center justify-between">
              <span className="text-[11px] text-slate-500 truncate">{label}</span>
              {delta !== null && (
                <span className={`text-[10px] font-mono ${delta >= 0 ? "text-emerald-500" : "text-red-400"}`}>
                  {delta >= 0 ? "+" : ""}{typeof delta === "number" && delta % 1 !== 0 ? delta.toFixed(1) : delta}{unitSuffix}
                </span>
              )}
            </div>
            {artifact.series.map((s, sIdx) => {
              const value = s.values[idx] ?? 0;
              const pct = Math.max(6, (value / max) * 100);
              return (
                <div key={s.name} className="flex items-center gap-2">
                  <span className="w-14 shrink-0 truncate text-[10px] text-slate-400">{s.name}</span>
                  <div className="flex-1 h-3.5 rounded-full bg-slate-200 dark:bg-slate-800 overflow-hidden">
                    <div className={`h-full rounded-full bg-gradient-to-r ${colors[sIdx % colors.length].bar}`} style={{ width: `${pct}%` }} />
                  </div>
                  <span className="w-16 shrink-0 text-right text-[10px] font-mono text-slate-500">
                    {formatVal(value)}
                  </span>
                </div>
              );
            })}
          </div>
        );
      })}
    </div>
  );
}

function formatChartAxisValue(value: number, unit?: string) {
  if (Math.abs(value) >= 1000) {
    return `${(value / 1000).toFixed(value >= 10000 ? 0 : 1)}k${unit === "%" ? "%" : ""}`;
  }
  if (unit === "%") return `${Math.round(value)}%`;
  if (Number.isInteger(value)) return value.toLocaleString();
  return value.toFixed(1);
}

function getLabelTickIndices(total: number, maxTicks = 6) {
  if (total <= maxTicks) return Array.from({ length: total }, (_, index) => index);
  const step = Math.ceil((total - 1) / (maxTicks - 1));
  const indices = new Set<number>([0, total - 1]);
  for (let index = step; index < total - 1; index += step) {
    indices.add(index);
  }
  return Array.from(indices).sort((left, right) => left - right).slice(0, maxTicks);
}

function shortenDateLabel(label: string): string {
  const m = label.match(/^(\d{4})-(\d{2})(?:-(\d{2}))?/);
  if (!m) return label;
  const monthNum = parseInt(m[2], 10);
  const months = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
  if (monthNum < 1 || monthNum > 12) return label; // not a valid date (e.g. week number)
  const monthName = months[monthNum - 1];
  if (m[3]) return `${monthName} ${parseInt(m[3], 10)}`;
  return `${monthName} '${m[1].slice(2)}`;
}

function LineChart({ artifact }: { artifact: Extract<Artifact, { kind: "chart" }> }) {
  if (artifact.labels.length < 2) return <BarChart artifact={artifact} />;
  const palette = ["#10B981", "#38BDF8", "#F59E0B", "#A855F7", "#EC4899", "#EF4444"];
  const isDense = artifact.labels.length > 60;
  const width = isDense ? 600 : 360;
  const height = isDense ? 220 : 180;
  const padLeft = 48;
  const padTop = 12;
  const padBottom = 38;

  // Dual Y-axis: trust the backend's LLM-driven decision
  const needsDualAxis = artifact.dual_axis === true;

  const padRight = needsDualAxis ? 52 : 16;
  const plotWidth = width - padLeft - padRight;
  const plotHeight = height - padTop - padBottom;

  function axisScale(indices: number[]) {
    const vals = indices.flatMap((i) => artifact.series[i].values);
    const rMax = Math.max(...vals, 1);
    const rMin = Math.min(...vals, 0);
    const mn = rMin > 0 ? 0 : rMin;
    const rng = rMax - mn || 1;
    return { min: mn, max: rMax, range: rng };
  }

  const seriesMaxes = artifact.series.map((s) => Math.max(...s.values.map(Math.abs), 0));
  const overallMax = Math.max(...seriesMaxes, 1);
  const threshold = overallMax / 5;
  const primaryIndices = needsDualAxis
    ? artifact.series.map((_, i) => i).filter((i) => seriesMaxes[i] >= threshold)
    : artifact.series.map((_, i) => i);
  const secondaryIndices = needsDualAxis
    ? artifact.series.map((_, i) => i).filter((i) => seriesMaxes[i] < threshold)
    : [];

  const primary = axisScale(primaryIndices);
  const secondary = secondaryIndices.length > 0 ? axisScale(secondaryIndices) : primary;

  const primaryTicks = Array.from({ length: 5 }, (_, i) => primary.min + ((4 - i) / 4) * primary.range);
  const secondaryTicks = needsDualAxis
    ? Array.from({ length: 5 }, (_, i) => secondary.min + ((4 - i) / 4) * secondary.range)
    : [];

  const maxTicks = isDense ? 8 : 6;
  const labelTickIndices = getLabelTickIndices(artifact.labels.length, maxTicks);
  const strokeWidth = isDense ? 1.5 : 2.5;

  function yForValue(value: number, scale: { min: number; range: number }) {
    return padTop + (1 - (value - scale.min) / scale.range) * plotHeight;
  }

  const secondarySet = new Set(secondaryIndices);

  return (
    <div className="space-y-3">
      <svg viewBox={`0 0 ${width} ${height}`} className="w-full" style={{ aspectRatio: `${width}/${height}` }}>
        {/* Primary (left) Y-axis */}
        {primaryTicks.map((tickValue, index) => {
          const y = yForValue(tickValue, primary);
          return (
            <g key={`y-tick-${index}`}>
              <line
                x1={padLeft}
                x2={width - padRight}
                y1={y}
                y2={y}
                stroke="currentColor"
                className="text-slate-800/10 dark:text-white/10"
              />
              <text
                x={padLeft - 6}
                y={y + 4}
                textAnchor="end"
                fontSize={10}
                className="fill-slate-500"
              >
                {formatChartAxisValue(tickValue, artifact.unit)}
              </text>
            </g>
          );
        })}
        {/* Secondary (right) Y-axis — only for multi-measure charts */}
        {secondaryTicks.map((tickValue, index) => {
          const y = yForValue(tickValue, secondary);
          return (
            <g key={`y-tick-r-${index}`}>
              <text
                x={width - padRight + 6}
                y={y + 4}
                textAnchor="start"
                fontSize={10}
                className="fill-slate-400"
              >
                {formatChartAxisValue(tickValue, artifact.unit)}
              </text>
            </g>
          );
        })}
        <line
          x1={padLeft}
          x2={width - padRight}
          y1={height - padBottom}
          y2={height - padBottom}
          stroke="currentColor"
          className="text-slate-800/20 dark:text-white/10"
        />
        {artifact.series.map((series, seriesIndex) => {
          const scale = secondarySet.has(seriesIndex) ? secondary : primary;
          const points = series.values.map((value, index) => {
            const x = padLeft + (index / Math.max(artifact.labels.length - 1, 1)) * plotWidth;
            const y = yForValue(value, scale);
            return `${x},${y}`;
          });
          return (
            <polyline
              key={series.name}
              fill="none"
              stroke={palette[seriesIndex % palette.length]}
              strokeWidth={strokeWidth}
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeOpacity={0.85}
              strokeDasharray={secondarySet.has(seriesIndex) ? "6 3" : undefined}
              points={points.join(" ")}
            />
          );
        })}
        {labelTickIndices.map((index) => {
          const x = padLeft + (index / Math.max(artifact.labels.length - 1, 1)) * plotWidth;
          return (
            <g key={`x-tick-${index}`}>
              <line
                x1={x}
                x2={x}
                y1={height - padBottom}
                y2={height - padBottom + 4}
                stroke="currentColor"
                className="text-slate-800/20 dark:text-white/10"
              />
              <text
                x={x}
                y={height - padBottom + 16}
                textAnchor="middle"
                fontSize={8}
                className="fill-slate-500"
              >
                {shortenDateLabel(artifact.labels[index])}
              </text>
            </g>
          );
        })}
      </svg>
      <div className="flex flex-wrap gap-3">
        {artifact.series.map((series, index) => (
          <div key={series.name} className="flex items-center gap-2 text-[11px] text-slate-500">
            <span className="size-2 rounded-full" style={{ backgroundColor: palette[index % palette.length] }} />
            <span>{series.name}{needsDualAxis ? (secondarySet.has(index) ? " (right)" : " (left)") : ""}</span>
          </div>
        ))}
      </div>
    </div>
  );
}

function SingleFunnel({ labels, series, color }: {
  labels: string[];
  series: { name: string; values: number[] };
  color: { from: string; to: string };
}) {
  const max = Math.max(series.values[0] || 1, 1);
  return (
    <div className="space-y-2">
      <span className="text-[11px] font-medium text-zinc-300">{series.name}</span>
      {labels.map((label, index) => {
        const value = series.values[index] ?? 0;
        const previous = index === 0 ? null : series.values[index - 1];
        const pct = Math.max(18, (value / max) * 100);
        const drop = previous ? Math.round((1 - value / previous) * 100) : null;
        return (
          <div key={`${label}-${index}`} className="flex flex-col items-center">
            <div
              className={`h-7 rounded-lg bg-gradient-to-r ${color.from} ${color.to} flex items-center justify-between px-3 text-white text-[11px] w-full`}
              style={{ width: `${pct}%` }}
            >
              <span className="truncate">{label}</span>
              <span className="font-mono">{value.toLocaleString()}</span>
            </div>
            {drop !== null && drop > 0 && <span className="text-[10px] text-red-400 mt-1">-{drop}% drop</span>}
          </div>
        );
      })}
    </div>
  );
}

function FunnelChart({ artifact }: { artifact: Extract<Artifact, { kind: "chart" }> }) {
  if (!artifact.series.length || artifact.labels.length === 0) return null;
  const palette = [
    { from: "from-emerald-600", to: "to-emerald-400" },
    { from: "from-blue-600", to: "to-blue-400" },
    { from: "from-amber-600", to: "to-amber-400" },
    { from: "from-purple-600", to: "to-purple-400" },
  ];

  if (artifact.series.length === 1) {
    return <SingleFunnel labels={artifact.labels} series={artifact.series[0]} color={palette[0]} />;
  }

  // ── Multi-series: separate funnels stacked vertically ──
  return (
    <div className="space-y-5">
      {artifact.series.map((s, si) => (
        <SingleFunnel key={s.name} labels={artifact.labels} series={s} color={palette[si % palette.length]} />
      ))}
    </div>
  );
}

function PieChart({ artifact }: { artifact: Extract<Artifact, { kind: "chart" }> }) {
  const series = artifact.series[0];
  if (!series || artifact.labels.length === 0) return null;
  const total = series.values.reduce((sum, v) => sum + Math.abs(v), 0) || 1;
  const palette = ["#10B981", "#38BDF8", "#F59E0B", "#A855F7", "#EC4899", "#EF4444", "#F97316", "#84CC16"];
  const size = 140;
  const cx = size / 2;
  const cy = size / 2;
  const r = 52;
  const slices = series.values.reduce<{ path: string; color: string; label: string; value: number; pct: number; angle: number }[]>((acc, value, index) => {
    const prevAngle = acc.length > 0 ? acc[acc.length - 1].angle : -Math.PI / 2;
    const pct = Math.abs(value) / total;
    const sweep = pct * 2 * Math.PI;
    const endAngle = prevAngle + sweep;
    const x1 = cx + r * Math.cos(prevAngle);
    const y1 = cy + r * Math.sin(prevAngle);
    const x2 = cx + r * Math.cos(endAngle);
    const y2 = cy + r * Math.sin(endAngle);
    const largeArc = sweep > Math.PI ? 1 : 0;
    const path = `M ${cx} ${cy} L ${x1} ${y1} A ${r} ${r} 0 ${largeArc} 1 ${x2} ${y2} Z`;
    return [...acc, { path, color: palette[index % palette.length], label: artifact.labels[index], value, pct, angle: endAngle }];
  }, []);
  return (
    <div className="flex items-center gap-4">
      <svg viewBox={`0 0 ${size} ${size}`} className="w-32 shrink-0">
        {slices.map((slice, index) => (
          <path key={index} d={slice.path} fill={slice.color} opacity={0.85} />
        ))}
      </svg>
      <div className="flex flex-col gap-1">
        {slices.map((slice, index) => (
          <div key={index} className="flex items-center gap-2 text-[11px] text-slate-600 dark:text-slate-400">
            <span className="size-2 rounded-full shrink-0" style={{ backgroundColor: slice.color }} />
            <span className="truncate max-w-[120px]">{slice.label}</span>
            <span className="font-mono text-slate-500">{Math.round(slice.pct * 100)}%</span>
          </div>
        ))}
      </div>
    </div>
  );
}

function ScatterChart({ artifact }: { artifact: Extract<Artifact, { kind: "chart" }> }) {
  if (artifact.series.length < 2 || artifact.series[0].values.length === 0) return <BarChart artifact={artifact} />;
  const xSeries = artifact.series[0];
  const ySeries = artifact.series[1];
  const xs = xSeries.values;
  const ys = ySeries.values;
  const n = Math.min(xs.length, ys.length);
  const xMin = Math.min(...xs), xMax = Math.max(...xs, xMin + 1);
  const yMin = Math.min(...ys), yMax = Math.max(...ys, yMin + 1);
  const width = 360, height = 200, padLeft = 44, padBottom = 30, padTop = 12, padRight = 12;
  const plotWidth = width - padLeft - padRight;
  const plotHeight = height - padTop - padBottom;
  const toX = (v: number) => padLeft + ((v - xMin) / (xMax - xMin)) * plotWidth;
  const toY = (v: number) => padTop + (1 - (v - yMin) / (yMax - yMin)) * plotHeight;
  const yTicks = Array.from({ length: 5 }, (_, i) => yMin + ((4 - i) / 4) * (yMax - yMin));
  return (
    <svg viewBox={`0 0 ${width} ${height}`} className="w-full" style={{ aspectRatio: `${width}/${height}` }}>
      {yTicks.map((tick, i) => (
        <g key={i}>
          <line x1={padLeft} x2={width - padRight} y1={toY(tick)} y2={toY(tick)} stroke="currentColor" className="text-slate-800/10 dark:text-white/10" />
          <text x={padLeft - 5} y={toY(tick) + 4} textAnchor="end" fontSize={9} className="fill-slate-500">{formatChartAxisValue(tick, artifact.unit)}</text>
        </g>
      ))}
      <line x1={padLeft} x2={width - padRight} y1={height - padBottom} y2={height - padBottom} stroke="currentColor" className="text-slate-800/20 dark:text-white/10" />
      {Array.from({ length: n }, (_, i) => (
        <circle key={i} cx={toX(xs[i])} cy={toY(ys[i])} r={3} fill="#10B981" opacity={0.65} />
      ))}
      <text x={padLeft + plotWidth / 2} y={height - 4} textAnchor="middle" fontSize={9} className="fill-slate-500">{xSeries.name}</text>
      <text x={10} y={padTop + plotHeight / 2} textAnchor="middle" fontSize={9} className="fill-slate-500" transform={`rotate(-90, 10, ${padTop + plotHeight / 2})`}>{ySeries.name}</text>
    </svg>
  );
}

function HeatmapChart({ artifact }: { artifact: Extract<Artifact, { kind: "chart" }> }) {
  if (artifact.series.length === 0 || artifact.labels.length === 0) return null;
  const allValues = artifact.series.flatMap((s) => s.values);
  const minVal = Math.min(...allValues);
  const maxVal = Math.max(...allValues, minVal + 1);
  const toOpacity = (v: number) => 0.1 + 0.9 * ((v - minVal) / (maxVal - minVal));
  return (
    <div className="overflow-x-auto">
      <table className="text-[10px] border-collapse">
        <thead>
          <tr>
            <th className="px-2 py-1 text-slate-400"></th>
            {artifact.labels.map((label) => (
              <th key={label} className="px-2 py-1 text-slate-500 font-normal max-w-[60px] truncate">{shortenDateLabel(label)}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {artifact.series.map((s) => (
            <tr key={s.name}>
              <td className="px-2 py-1 text-slate-500 text-right font-medium whitespace-nowrap">{s.name}</td>
              {s.values.map((v, i) => (
                <td key={i} className="px-1 py-1 text-center font-mono text-slate-800 dark:text-white" style={{ backgroundColor: `rgba(16,185,129,${toOpacity(v)})` }}>
                  {formatChartAxisValue(v, artifact.unit)}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function HistogramChart({ artifact }: { artifact: Extract<Artifact, { kind: "chart" }> }) {
  // Histogram is a bar chart — buckets are just bars
  return <BarChart artifact={artifact} />;
}

function BoxPlotChart({ artifact }: { artifact: Extract<Artifact, { kind: "chart" }> }) {
  // Expects series with 5 values each: [min, Q1, median, Q3, max]
  const palette = ["#10B981", "#38BDF8", "#F59E0B", "#A855F7", "#EC4899"];
  const allVals = artifact.series.flatMap((s) => s.values);
  const globalMin = Math.min(...allVals);
  const globalMax = Math.max(...allVals, globalMin + 1);
  const width = 300;
  const height = 160;
  const padLeft = 48;
  const padRight = 16;
  const padTop = 12;
  const padBottom = 28;
  const plotWidth = width - padLeft - padRight;
  const plotHeight = height - padTop - padBottom;
  const toX = (v: number) => padLeft + ((v - globalMin) / (globalMax - globalMin)) * plotWidth;
  const boxHeight = Math.max(12, Math.floor(plotHeight / artifact.series.length) - 6);
  const ticks = Array.from({ length: 5 }, (_, i) => globalMin + (i / 4) * (globalMax - globalMin));
  return (
    <svg viewBox={`0 0 ${width} ${height}`} className="w-full" style={{ aspectRatio: `${width}/${height}` }}>
      {ticks.map((tick, i) => (
        <g key={i}>
          <line x1={toX(tick)} x2={toX(tick)} y1={padTop} y2={height - padBottom} stroke="currentColor" className="text-slate-800/10 dark:text-white/10" strokeDasharray="3 3" />
          <text x={toX(tick)} y={height - padBottom + 14} textAnchor="middle" fontSize={9} className="fill-slate-500">{formatChartAxisValue(tick, artifact.unit)}</text>
        </g>
      ))}
      {artifact.series.map((s, si) => {
        const [vMin, q1, median, q3, vMax] = s.values.length >= 5 ? s.values : [s.values[0], s.values[0], s.values[0], s.values[0], s.values[0]];
        const cy = padTop + si * (boxHeight + 6) + boxHeight / 2;
        const color = palette[si % palette.length];
        return (
          <g key={s.name}>
            <text x={padLeft - 4} y={cy + 4} textAnchor="end" fontSize={9} className="fill-slate-500">{s.name}</text>
            <line x1={toX(vMin)} x2={toX(vMax)} y1={cy} y2={cy} stroke={color} strokeWidth={1.5} opacity={0.5} />
            <line x1={toX(vMin)} x2={toX(vMin)} y1={cy - 5} y2={cy + 5} stroke={color} strokeWidth={1.5} />
            <line x1={toX(vMax)} x2={toX(vMax)} y1={cy - 5} y2={cy + 5} stroke={color} strokeWidth={1.5} />
            <rect x={toX(q1)} y={cy - boxHeight / 2} width={toX(q3) - toX(q1)} height={boxHeight} fill={color} opacity={0.2} stroke={color} strokeWidth={1.5} rx={2} />
            <line x1={toX(median)} x2={toX(median)} y1={cy - boxHeight / 2} y2={cy + boxHeight / 2} stroke={color} strokeWidth={2.5} />
          </g>
        );
      })}
    </svg>
  );
}

function TableArtifactView({ artifact }: { artifact: Extract<Artifact, { kind: "table" }> }) {
  const numericColumns = new Set(artifact.columns.filter((column) => artifact.rows.some((row) => typeof row[column] === "number")));
  const monospaceColumns = new Set(
    artifact.columns.filter((column) => /(^|_)(id|code|version|status)$/.test(column.toLowerCase()) || numericColumns.has(column))
  );

  return (
    <div className="space-y-2">
      {artifact.display_clarification && (
        <div className="flex items-start gap-2 rounded-lg bg-amber-500/10 border border-amber-500/20 p-3">
          <span className="material-symbols-outlined text-amber-500 text-[16px] mt-0.5">help</span>
          <p className="text-[12px] text-amber-600 dark:text-amber-400">{artifact.display_clarification}</p>
        </div>
      )}
    <div className="overflow-x-auto rounded-xl border border-slate-200 dark:border-slate-700/50">
      <table className="min-w-full text-left text-xs">
        <thead className="bg-slate-50 dark:bg-slate-800/40 text-slate-500 uppercase tracking-wide">
          <tr>
            {artifact.columns.slice(0, 6).map((column) => (
              <th key={column} className="px-3 py-2">{column}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {artifact.rows.map((row, rowIndex) => (
            <tr key={rowIndex} className="border-t border-slate-200 dark:border-slate-800">
              {artifact.columns.slice(0, 6).map((column) => (
                <td
                  key={`${rowIndex}-${column}`}
                  className={`px-3 py-2 align-top ${monospaceColumns.has(column) ? "font-mono" : ""} ${numericColumns.has(column) ? "text-right" : ""} text-slate-700 dark:text-slate-300`}
                >
                  {formatCell(row[column])}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
    </div>
  );
}

function TraceStep({
  icon, label, badge, badgeColor, children, defaultOpen = false,
}: {
  icon: string; label: string; badge?: string; badgeColor?: string; children?: React.ReactNode; defaultOpen?: boolean;
}) {
  const [open, setOpen] = useState(defaultOpen);
  return (
    <div className="relative pl-8">
      {/* vertical line */}
      <div className="absolute left-[11px] top-6 bottom-0 w-px bg-slate-200 dark:bg-slate-700" />
      {/* dot */}
      <div className="absolute left-0 top-[14px] size-[22px] rounded-full bg-slate-100 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 flex items-center justify-center">
        <span className="material-symbols-outlined text-[13px] text-emerald-500">{icon}</span>
      </div>
      <button
        onClick={() => setOpen(!open)}
        className="w-full flex items-center gap-2 py-3 text-left group"
      >
        <span className="text-[12px] font-semibold text-slate-700 dark:text-slate-200">{label}</span>
        {badge && (
          <span className={`px-1.5 py-0.5 rounded text-[9px] font-mono ${badgeColor || "bg-slate-200 dark:bg-slate-700 text-slate-500"}`}>
            {badge}
          </span>
        )}
        {children && (
          <span className="ml-auto material-symbols-outlined text-[14px] text-slate-400 group-hover:text-slate-600 dark:group-hover:text-slate-300 transition-transform" style={{ transform: open ? "rotate(180deg)" : undefined }}>
            expand_more
          </span>
        )}
      </button>
      {open && children && (
        <div className="pb-3">{children}</div>
      )}
    </div>
  );
}

interface LLMCallRecord {
  stage: string;
  step?: number;
  system_prompt?: string;
  user_payload?: Record<string, unknown>;
  raw_response?: string;
  parsed_result?: unknown;
  duration_ms?: number;
}

function RawLLMCalls({ calls }: { calls: LLMCallRecord[] }) {
  const [open, setOpen] = useState(false);
  if (!calls.length) return null;
  return (
    <div className="mt-2">
      <button
        onClick={() => setOpen(!open)}
        className="flex items-center gap-1.5 text-[10px] text-slate-400 hover:text-emerald-500 transition-colors group"
      >
        <span className="material-symbols-outlined text-[13px]" style={{ transform: open ? "rotate(90deg)" : undefined, transition: "transform 0.15s" }}>
          chevron_right
        </span>
        Raw LLM I/O ({calls.length} call{calls.length > 1 ? "s" : ""})
      </button>
      {open && (
        <div className="mt-2 space-y-3">
          {calls.map((call, i) => (
            <div key={i} className="rounded-lg bg-slate-900 dark:bg-slate-950 border border-slate-700/50 overflow-hidden">
              <div className="flex items-center gap-2 px-3 py-1.5 bg-slate-800/50 border-b border-slate-700/30">
                <span className="text-[10px] font-mono text-emerald-400">{call.stage}</span>
                {call.duration_ms !== undefined && <span className="text-[9px] text-slate-500 font-mono">{call.duration_ms}ms</span>}
              </div>
              <div className="p-2 space-y-1.5">
                <details className="group">
                  <summary className="text-[10px] text-slate-400 cursor-pointer hover:text-slate-300 select-none">System prompt</summary>
                  <pre className="mt-1 text-[9px] text-slate-400 font-mono whitespace-pre-wrap max-h-40 overflow-y-auto p-2 bg-slate-950 rounded">{call.system_prompt || "—"}</pre>
                </details>
                <details className="group">
                  <summary className="text-[10px] text-slate-400 cursor-pointer hover:text-slate-300 select-none">Payload</summary>
                  <pre className="mt-1 text-[9px] text-sky-400 font-mono whitespace-pre-wrap max-h-60 overflow-y-auto p-2 bg-slate-950 rounded">{JSON.stringify(call.user_payload, null, 2) || "—"}</pre>
                </details>
                <details className="group">
                  <summary className="text-[10px] text-slate-400 cursor-pointer hover:text-slate-300 select-none">Response</summary>
                  <pre className="mt-1 text-[9px] text-amber-400 font-mono whitespace-pre-wrap max-h-60 overflow-y-auto p-2 bg-slate-950 rounded">{call.raw_response || "—"}</pre>
                </details>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

function QueryLogModal({
  sessionId,
  queryLogId,
  onClose,
}: {
  sessionId: string;
  queryLogId: number;
  onClose: () => void;
}) {
  const [detail, setDetail] = useState<QueryLogDetail | null>(null);

  useEffect(() => {
    let isActive = true;
    getQueryLogDetail(sessionId, queryLogId)
      .then((value) => {
        if (isActive) {
          setDetail(value);
        }
      })
      .catch(console.error);

    return () => {
      isActive = false;
    };
  }, [sessionId, queryLogId]);

  return (
    <div className="fixed inset-0 z-[100] flex items-center justify-center bg-black/50 backdrop-blur-sm" onClick={onClose}>
      <div
        className="bg-white dark:bg-slate-900 rounded-2xl shadow-2xl w-full max-w-2xl max-h-[85vh] flex flex-col border border-slate-200 dark:border-slate-800"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-slate-200 dark:border-slate-800">
          <h3 className="text-sm font-bold text-slate-800 dark:text-slate-100 flex items-center gap-2">
            <span className="material-symbols-outlined text-emerald-500 text-lg">account_tree</span>
            Agent Execution Trace
          </h3>
          <div className="flex items-center gap-3">
            {detail?.trace?.total_duration_ms && (
              <span className="text-[11px] text-slate-400 font-mono">{detail.trace.total_duration_ms}ms total</span>
            )}
            <button onClick={onClose} className="text-slate-400 hover:text-slate-600 dark:hover:text-slate-200">
              <span className="material-symbols-outlined text-lg">close</span>
            </button>
          </div>
        </div>

        {/* Body */}
        <div className="flex-1 overflow-y-auto px-4 py-4">
          {!detail && (
            <div className="flex items-center justify-center py-10 text-slate-400 text-sm">
              <span className="material-symbols-outlined animate-spin mr-2">progress_activity</span>
              Loading trace...
            </div>
          )}

          {detail && (
            <div className="space-y-0">
              {/* Step 1: Intent */}
              <TraceStep icon="record_voice_over" label="Intent" badge={detail.trace?.conversation_turns ? `${detail.trace.conversation_turns} prior turns` : undefined} defaultOpen>
                <div className="rounded-lg bg-slate-50 dark:bg-slate-800/50 border border-slate-200 dark:border-slate-700 p-3 text-[12px] text-slate-600 dark:text-slate-300 space-y-2">
                  <div>
                    <p className="text-[10px] font-semibold text-slate-400 uppercase tracking-wider mb-0.5">Query</p>
                    <p className="text-slate-500 dark:text-slate-400 italic">&ldquo;{detail.query}&rdquo;</p>
                  </div>
                  {detail.trace?.effective_query && detail.trace.effective_query !== detail.query && (
                    <div>
                      <p className="text-[10px] font-semibold text-slate-400 uppercase tracking-wider mb-0.5">Resolved query</p>
                      <p className="text-slate-500 dark:text-slate-400 italic">&ldquo;{detail.trace.effective_query}&rdquo;</p>
                    </div>
                  )}
                  {detail.trace?.question_understanding && (
                    <div className="rounded bg-emerald-500/8 dark:bg-emerald-500/10 border-l-2 border-emerald-500 px-3 py-2">
                      <p className="text-[10px] font-semibold text-emerald-600 dark:text-emerald-400 uppercase tracking-wider mb-0.5">Understood as</p>
                      <p className="text-slate-700 dark:text-slate-200">{detail.trace.question_understanding}</p>
                    </div>
                  )}
                  {detail.trace?.sub_questions && (detail.trace.sub_questions as string[]).length > 0 && (
                    <div>
                      <p className="text-[10px] font-semibold text-slate-400 uppercase tracking-wider mb-1">Sub-questions</p>
                      <ul className="space-y-0.5">
                        {(detail.trace.sub_questions as string[]).map((sq, i) => (
                          <li key={i} className="flex items-start gap-1.5 text-[11px] text-slate-500 dark:text-slate-400">
                            <span className="text-emerald-500 mt-0.5">•</span>
                            {sq}
                          </li>
                        ))}
                      </ul>
                    </div>
                  )}
                </div>
                <RawLLMCalls calls={(detail.llm_calls || []).filter((c: LLMCallRecord) => c.stage === "planner")} />
              </TraceStep>

              {/* Step 2: Plan */}
              {detail.planner && Object.keys(detail.planner).length > 0 && (
                <TraceStep
                  icon="lightbulb"
                  label="Plan"
                  badge={detail.planner.complexity as string | undefined}
                  badgeColor={detail.planner.complexity === "multi_step" ? "bg-amber-500/15 text-amber-600 dark:text-amber-400" : "bg-slate-200 dark:bg-slate-700 text-slate-500"}
                  defaultOpen
                >
                  <div className="rounded-lg bg-slate-50 dark:bg-slate-800/50 border border-slate-200 dark:border-slate-700 p-3 space-y-2 text-[12px]">
                    {detail.planner.target_tables && (detail.planner.target_tables as string[]).length > 0 && (
                      <div>
                        <p className="text-[10px] font-semibold text-slate-400 uppercase tracking-wider mb-1">Target tables</p>
                        <div className="flex flex-wrap gap-1">
                          {(detail.planner.target_tables as string[]).map((t) => (
                            <span key={t} className="px-1.5 py-0.5 rounded-full bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 text-[10px] font-mono">{t}</span>
                          ))}
                        </div>
                      </div>
                    )}
                    {Array.isArray(detail.planner.sub_questions) && detail.planner.sub_questions.length > 0 && (
                      <div>
                        <p className="text-[10px] font-semibold text-slate-400 uppercase tracking-wider mb-1">Steps</p>
                        <ol className="space-y-0.5 list-decimal list-inside">
                          {(detail.planner.sub_questions as string[]).map((sq, i) => (
                            <li key={i} className="text-[11px] text-slate-500 dark:text-slate-400">{sq}</li>
                          ))}
                        </ol>
                      </div>
                    )}
                    {detail.planner.stop_condition && (
                      <p className="text-slate-400 dark:text-slate-500 text-[11px] italic">Stop: {detail.planner.stop_condition as string}</p>
                    )}
                  </div>
                </TraceStep>
              )}

              {/* Steps 3+: Attempts */}
              {detail.attempts.map((attempt, i) => {
                const isSuccess = attempt.status === "success";
                const isRejected = attempt.status === "rejected";
                const durationLabel = attempt.duration_ms ? `${attempt.duration_ms}ms` : undefined;
                const rowsLabel = attempt.rows_returned !== undefined ? `${attempt.rows_returned} rows` : undefined;
                const badge = [attempt.kind, durationLabel, rowsLabel].filter(Boolean).join(" · ");
                const criticIcon = isSuccess ? "check_circle" : isRejected ? "warning" : "error";
                return (
                  <TraceStep
                    key={i}
                    icon={criticIcon}
                    label={attempt.title || `Step ${attempt.attempt || i + 1}`}
                    badge={badge}
                    badgeColor={isSuccess ? "bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 font-mono text-[9px]" : isRejected ? "bg-amber-500/10 text-amber-600 dark:text-amber-400 font-mono text-[9px]" : "bg-red-500/10 text-red-600 font-mono text-[9px]"}
                  >
                    <div className="space-y-2">
                      {typeof attempt.reason === "string" && attempt.reason && (
                        <p className="text-[11px] text-slate-500 dark:text-slate-400 italic">{String(attempt.reason)}</p>
                      )}
                      {attempt.sql && (
                        <pre className="p-2 rounded bg-slate-900 dark:bg-slate-950 text-emerald-400 text-[10px] font-mono overflow-x-auto whitespace-pre-wrap leading-relaxed">
                          {attempt.sql}
                        </pre>
                      )}
                      {attempt.python_code && !attempt.sql && (
                        <pre className="p-2 rounded bg-slate-900 dark:bg-slate-950 text-sky-400 text-[10px] font-mono overflow-x-auto whitespace-pre-wrap leading-relaxed">
                          {attempt.python_code}
                        </pre>
                      )}
                      {attempt.error && (
                        <p className="text-[11px] text-red-500 bg-red-500/10 rounded p-2">{attempt.error}</p>
                      )}
                      {/* Critic verdict — shown for all attempts where critic ran */}
                      {attempt.critic_ok === true && (
                        <div className="flex items-center gap-1.5 text-[11px] text-emerald-500">
                          <span className="material-symbols-outlined text-[14px]">check_circle</span>
                          <span className="font-medium">Critic accepted</span>
                        </div>
                      )}
                      {attempt.critic_ok === false && (
                        <div className="rounded bg-amber-500/10 border border-amber-500/20 p-2">
                          <div className="flex items-center gap-1.5 text-[11px] text-amber-500 font-medium mb-1">
                            <span className="material-symbols-outlined text-[14px]">warning</span>
                            Critic rejected
                          </div>
                          {attempt.rejection_reason && (
                            <p className="text-[11px] text-slate-600 dark:text-slate-400">{String(attempt.rejection_reason)}</p>
                          )}
                          {attempt.suggested_fix && (
                            <p className="mt-1 text-[11px] text-amber-500/80">Fix: {String(attempt.suggested_fix)}</p>
                          )}
                        </div>
                      )}
                      {attempt.summary && (
                        <p className="text-[11px] text-slate-500 dark:text-slate-400">{attempt.summary}</p>
                      )}
                      <RawLLMCalls calls={(detail.llm_calls || []).filter((c: LLMCallRecord) => (c.stage === "action_chooser" || c.stage === "critic") && c.step === (attempt.attempt || i + 1))} />
                    </div>
                  </TraceStep>
                );
              })}

              {/* Artifact Rendering — chart inference */}
              {(() => {
                const chartCalls = (detail.llm_calls || []).filter((c: LLMCallRecord) => c.stage === "chart_inference" || c.stage === "vega_lite_generation");
                if (!chartCalls.length) return null;
                const call = chartCalls[0] as Record<string, unknown>;
                const spec = call?.parsed_result as Record<string, unknown> | null;
                const stage = String(call?.stage || "");
                const isVega = stage === "vega_lite_generation";
                const chartType = isVega ? (spec?.$schema ? "vega-lite" : String(spec?.chart_type || "unknown")) : String(spec?.chart_type || "unknown");
                const durationMs = call?.duration_ms;
                const errorMsg = spec?.error ? String(spec.error) : call?.error ? String(call.error) : "";
                const badgeText = errorMsg ? "failed" : chartType;
                const badgeColor = errorMsg
                  ? "bg-red-500/10 text-red-600 font-mono text-[9px]"
                  : "bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 font-mono text-[9px]";
                return (
                  <TraceStep icon="show_chart" label="Artifact Rendering" badge={`${String(badgeText)}${durationMs ? ` · ${String(durationMs)}ms` : ""}`} badgeColor={badgeColor}>
                    <div className="space-y-2">
                      {spec && !errorMsg && (
                        <div className="rounded-lg bg-slate-50 dark:bg-slate-800/50 border border-slate-200 dark:border-slate-700 p-3 text-[12px] space-y-1.5">
                          <p className="text-slate-700 dark:text-slate-200 font-medium">{isVega ? "Vega-Lite spec generated" : String(chartType)}</p>
                        </div>
                      )}
                      {errorMsg && (
                        <p className="text-[11px] text-red-500 bg-red-500/10 rounded p-2">{errorMsg}</p>
                      )}
                      <RawLLMCalls calls={chartCalls} />
                    </div>
                  </TraceStep>
                );
              })()}

              {/* Final: Response */}
              <TraceStep icon="chat" label="Response" badge={`${detail.artifacts.length} artifact${detail.artifacts.length !== 1 ? "s" : ""}`} defaultOpen>
                <div className="rounded-lg bg-slate-50 dark:bg-slate-800/50 border border-slate-200 dark:border-slate-700 p-3 text-[12px] text-slate-600 dark:text-slate-300 space-y-2">
                  <p className="whitespace-pre-wrap">{detail.response}</p>
                  {detail.warnings.length > 0 && (
                    <div className="space-y-1 pt-1 border-t border-slate-200 dark:border-slate-700">
                      {detail.warnings.map((w, wi) => (
                        <div key={wi} className="flex items-start gap-1.5 text-[11px] text-amber-500">
                          <span className="material-symbols-outlined text-[13px] mt-0.5">warning</span>
                          <span>{w}</span>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
                <RawLLMCalls calls={(detail.llm_calls || []).filter((c: LLMCallRecord) => c.stage === "synthesizer")} />
              </TraceStep>

              {detail.attempts.length === 0 && (!detail.planner || Object.keys(detail.planner).length === 0) && (
                <p className="text-center text-slate-400 text-sm py-8">No execution details available for this query.</p>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

function computeWeekEnd(dateStr: string): string | null {
  const m = dateStr.match(/^(\d{4})-(\d{2})-(\d{2})$/);
  if (!m) return null;
  const d = new Date(parseInt(m[1]), parseInt(m[2]) - 1, parseInt(m[3]));
  if (d.getDay() !== 1) return null; // not a Monday
  const end = new Date(d);
  end.setDate(end.getDate() + 6);
  return end.toISOString().slice(0, 10);
}

function isWeeklyDateSeries(labels: string[]): boolean {
  if (labels.length < 2) return false;
  // Check first few labels are Mondays ~7 days apart
  let count = 0;
  for (let i = 0; i < Math.min(labels.length, 3); i++) {
    if (computeWeekEnd(labels[i]) !== null) count++;
  }
  return count >= 2;
}

function ChartDataTable({ artifact }: { artifact: Extract<Artifact, { kind: "chart" }> }) {
  const weekly = isWeeklyDateSeries(artifact.labels);
  const columns = [
    artifact.labels.length > 0 ? "Week Start" : "",
    ...(weekly ? ["Week End"] : []),
    ...artifact.series.map((s) => s.name),
  ];
  return (
    <div className="max-h-52 overflow-auto rounded-lg border border-slate-200 dark:border-slate-700/50">
      <table className="w-full text-[11px]">
        <thead className="sticky top-0 bg-slate-100 dark:bg-slate-800">
          <tr>
            {columns.map((col) => (
              <th key={col} className="px-3 py-1.5 text-left font-semibold text-slate-600 dark:text-slate-300 whitespace-nowrap">
                {col}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {artifact.labels.map((label, i) => (
            <tr key={`${label}-${i}`} className="border-t border-slate-100 dark:border-slate-800 hover:bg-slate-50 dark:hover:bg-slate-800/50">
              <td className="px-3 py-1 text-slate-500 whitespace-nowrap">{label}</td>
              {weekly && (
                <td className="px-3 py-1 text-slate-500 whitespace-nowrap">{computeWeekEnd(label) ?? "—"}</td>
              )}
              {artifact.series.map((s) => (
                <td key={s.name} className="px-3 py-1 font-mono text-slate-700 dark:text-slate-300 text-right whitespace-nowrap">
                  {s.values[i] != null ? s.values[i].toLocaleString() : "—"}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function VegaLiteChart({ spec }: { spec: Record<string, unknown> }) {
  const containerRef = useRef<HTMLDivElement>(null);
  const viewRef = useRef<unknown>(null);

  useEffect(() => {
    if (!containerRef.current) return;
    let cancelled = false;
    import("vega-embed").then(({ default: vegaEmbed }) => {
      if (cancelled || !containerRef.current) return;
      vegaEmbed(containerRef.current, spec as never, {
        actions: false,
        renderer: "svg",
        config: {
          background: "transparent",
          view: { stroke: "transparent" },
          axis: { labelColor: "#94a3b8", titleColor: "#94a3b8", gridColor: "#1e293b", domainColor: "#334155" },
          legend: { labelColor: "#94a3b8", titleColor: "#94a3b8" },
          title: { color: "#e2e8f0" },
        },
      }).then((result) => {
        viewRef.current = result.view;
      });
    });
    return () => {
      cancelled = true;
      if (viewRef.current && typeof (viewRef.current as { finalize?: () => void }).finalize === "function") {
        (viewRef.current as { finalize: () => void }).finalize();
      }
    };
  }, [spec]);

  return <div ref={containerRef} className="w-full" />;
}

function VegaDataTable({ artifact }: { artifact: { columns?: string[]; rows?: Record<string, string | number | null>[] } }) {
  const columns = artifact.columns ?? [];
  const rows = artifact.rows ?? [];
  if (!columns.length || !rows.length) return <p className="text-[11px] text-slate-400">No underlying data available.</p>;
  return (
    <div className="overflow-x-auto rounded-lg border border-slate-700/50 max-h-48">
      <table className="w-full text-[11px]">
        <thead className="bg-slate-800/60 sticky top-0">
          <tr>{columns.map((c) => <th key={c} className="px-2 py-1 text-left font-medium text-slate-300 whitespace-nowrap">{c}</th>)}</tr>
        </thead>
        <tbody>
          {rows.slice(0, 50).map((row, ri) => (
            <tr key={ri} className="border-t border-slate-700/30 hover:bg-slate-800/30">
              {columns.map((c) => <td key={c} className="px-2 py-1 text-slate-400 whitespace-nowrap">{row[c] ?? ""}</td>)}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function ArtifactRenderer({ artifact }: { artifact: Artifact }) {
  const [showData, setShowData] = useState(false);

  if (artifact.kind === "metric") return <MetricArtifactView artifact={artifact} />;
  if (artifact.kind === "table") return <TableArtifactView artifact={artifact} />;

  // Vega-Lite chart — single render path, no chart type switching
  if (artifact.kind === "vega_chart") {
    return (
      <div>
        {showData ? <VegaDataTable artifact={artifact} /> : <VegaLiteChart spec={artifact.vega_spec} />}
        <button
          onClick={() => setShowData(!showData)}
          className="mt-2 flex items-center gap-1 text-[10px] text-slate-400 hover:text-emerald-500 transition-colors"
        >
          <span className="material-symbols-outlined text-sm">{showData ? "bar_chart" : "table_rows"}</span>
          <span>{showData ? "Show chart" : "View data"}</span>
        </button>
      </div>
    );
  }

  // Legacy chart rendering (backward compatibility with saved artifacts)
  const chartElement =
    artifact.chart_type === "line" ? <LineChart artifact={artifact} /> :
    artifact.chart_type === "dual_axis_line" ? <LineChart artifact={artifact} /> :
    artifact.chart_type === "funnel" ? <FunnelChart artifact={artifact} /> :
    artifact.chart_type === "pie" ? <PieChart artifact={artifact} /> :
    artifact.chart_type === "scatter" ? <ScatterChart artifact={artifact} /> :
    artifact.chart_type === "heatmap" ? <HeatmapChart artifact={artifact} /> :
    artifact.chart_type === "histogram" ? <HistogramChart artifact={artifact} /> :
    artifact.chart_type === "box" ? <BoxPlotChart artifact={artifact} /> :
    <BarChart artifact={artifact} />;

  return (
    <div>
      {showData ? <ChartDataTable artifact={artifact} /> : chartElement}
      <button
        onClick={() => setShowData(!showData)}
        className="mt-2 flex items-center gap-1 text-[10px] text-slate-400 hover:text-emerald-500 transition-colors"
      >
        <span className="material-symbols-outlined text-sm">{showData ? "bar_chart" : "table_rows"}</span>
        <span>{showData ? "Show chart" : "View data"}</span>
      </button>
    </div>
  );
}

function InlineArtifactCard({
  artifact,
  citation,
  queryLogId,
  savedEvidenceMap,
  draftAnnotation,
  onDraftChange,
  onSave,
}: {
  artifact: Artifact;
  citation: Citation | undefined;
  queryLogId?: number;
  savedEvidenceMap: Map<string, SavedEvidence>;
  draftAnnotation: string;
  onDraftChange: (value: string) => void;
  onSave: () => void;
}) {
  const citationId = citation?.citation_id || artifact.citation_ids[0];
  const savedKey = queryLogId && citationId ? `${queryLogId}:${citationId}` : "";
  const savedItem = savedKey ? savedEvidenceMap.get(savedKey) : undefined;
  const disabled = !queryLogId || !citationId;

  return (
    <div className="mt-3 rounded-xl border border-slate-200 dark:border-slate-700/50 bg-slate-50 dark:bg-slate-900/40 p-3">
      {/* Show saved annotation at top like a headline */}
      {savedItem?.annotation && (
        <div className="mb-3 rounded-lg bg-emerald-500/8 dark:bg-emerald-500/10 border-l-2 border-emerald-500 px-3 py-2">
          <p className="text-[13px] font-semibold leading-snug text-slate-900 dark:text-slate-100">{savedItem.annotation}</p>
        </div>
      )}
      <div className="flex items-start gap-3">
        <div className="flex-1 min-w-0">
          <p className="text-[12px] font-semibold text-slate-800 dark:text-slate-100 mb-1">{artifact.title}</p>
          {artifact.summary && <p className="text-[11px] text-slate-500 mb-3">{artifact.summary}</p>}
        </div>
        {savedItem ? (
          <span className="text-[10px] px-2 py-1 rounded-full bg-emerald-500/15 text-emerald-500 font-semibold">Saved</span>
        ) : (
          <button
            onClick={onSave}
            disabled={disabled}
            className="text-[10px] px-2 py-1 rounded-full border border-emerald-500/30 text-emerald-500 hover:bg-emerald-500/10 disabled:opacity-40"
          >
            Save to board
          </button>
        )}
      </div>
      <ArtifactRenderer artifact={artifact} />
      <div className="mt-3 flex flex-wrap gap-2">
        {citation && (
          <span className="px-2 py-1 rounded-full bg-slate-200 dark:bg-slate-800 text-[10px] text-slate-600 dark:text-slate-300">
            {citation.source}
          </span>
        )}
      </div>
      {!savedItem && !disabled && (
        <input
          className="mt-3 w-full rounded-lg border border-slate-300 dark:border-slate-700 bg-white dark:bg-slate-800 px-3 py-2 text-[13px] text-slate-700 dark:text-slate-200 outline-none focus:ring-2 focus:ring-emerald-500"
          placeholder="Add a note before saving (optional)"
          value={draftAnnotation}
          onChange={(event) => onDraftChange(event.target.value)}
        />
      )}
    </div>
  );
}

function SavedEvidenceCard({
  item,
  onRemove,
  onUpdate,
}: {
  item: SavedEvidence;
  onRemove: () => void;
  onUpdate: (annotation: string) => void;
}) {
  const [editing, setEditing] = useState(false);
  const [annotation, setAnnotation] = useState(item.annotation || "");
  const agentInfo = AGENTS.find((entry) => entry.id === item.agent);

  return (
    <div className="bg-slate-50 dark:bg-slate-800/30 rounded-xl border border-slate-200 dark:border-slate-700/50 p-4">
      {/* Annotation at top — like a PPT headline */}
      {!editing && item.annotation && (
        <div className="mb-3 rounded-lg bg-emerald-500/8 dark:bg-emerald-500/10 border-l-2 border-emerald-500 px-3 py-2.5">
          <p className="text-[14px] font-semibold leading-snug text-slate-900 dark:text-slate-100">{item.annotation}</p>
        </div>
      )}
      {editing && (
        <div className="mb-3">
          <p className="text-[10px] font-semibold text-emerald-600 dark:text-emerald-400 mb-1.5">Why this matters</p>
          <div className="flex gap-2">
            <input
              className="flex-1 rounded-lg border border-emerald-400/50 dark:border-emerald-600/50 bg-white dark:bg-slate-900 px-3 py-2 text-[13px] outline-none focus:ring-2 focus:ring-emerald-500"
              value={annotation}
              onChange={(event) => setAnnotation(event.target.value)}
              placeholder="Explain why this evidence supports your case..."
              autoFocus
            />
            <button
              onClick={() => {
                onUpdate(annotation);
                setEditing(false);
              }}
              className="px-3 py-2 rounded-lg bg-emerald-500 text-white text-[11px] font-semibold"
            >
              Save
            </button>
          </div>
        </div>
      )}
      <div className="flex items-center gap-2 mb-3">
        <AgentIcon agent={item.agent} />
        <div className="min-w-0">
          <p className="text-[10px] font-semibold text-slate-500">{agentInfo?.label}</p>
          <p className="text-[12px] font-semibold text-slate-900 dark:text-slate-100 truncate">{item.artifact.title}</p>
        </div>
        <span className="text-[10px] text-slate-500 ml-auto">{formatTime(item.saved_at)}</span>
      </div>
      <ArtifactRenderer artifact={item.artifact} />
      <div className="mt-3 flex flex-wrap gap-2">
        <span className="px-2 py-1 rounded-full bg-slate-200 dark:bg-slate-800 text-[10px] text-slate-600 dark:text-slate-300">
          {item.citation.source}
        </span>
      </div>
      <div className="mt-3 flex gap-2">
        <button
          onClick={() => {
            if (!editing) {
              setAnnotation(item.annotation || "");
            }
            setEditing((value) => !value);
          }}
          className="text-[10px] px-2.5 py-1 rounded-full border border-slate-300 dark:border-slate-700 text-slate-500 hover:text-slate-700 dark:hover:text-slate-200"
        >
          {editing ? "Cancel" : item.annotation ? "Edit note" : "Why this matters"}
        </button>
        <button
          onClick={onRemove}
          className="text-[10px] px-2.5 py-1 rounded-full border border-red-500/30 text-red-500 hover:bg-red-500/10"
        >
          Remove
        </button>
      </div>
    </div>
  );
}


export default function WorkspacePage() {
  const params = useParams();
  const router = useRouter();
  useAuthToken();
  const sessionId = params.sessionId as string;

  const [selectedAgent, setSelectedAgent] = useState<string>("analyst");
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [savedEvidence, setSavedEvidence] = useState<SavedEvidence[]>([]);
  const [agentGuidance, setAgentGuidance] = useState<Record<string, AgentGuidance>>({});
  const [input, setInput] = useState("");
  const [isQuerying, setIsQuerying] = useState(false);
  const [agentStatus, setAgentStatus] = useState("");
  const [status, setStatus] = useState<SessionStatus | null>(null);
  const [scenarioDetail, setScenarioDetail] = useState<ScenarioDetail | null>(null);
  const [timeLeft, setTimeLeft] = useState("30:00");
  const [referenceOpen, setReferenceOpen] = useState(false);
  const [referenceTab, setReferenceTab] = useState<"brief" | "sources">("brief");
  const [saveDrafts, setSaveDrafts] = useState<Record<string, string>>({});
  const [logModalQueryId, setLogModalQueryId] = useState<number | null>(null);
  const [theme, setTheme] = useState<"light" | "dark" | "system">("system");
  const [evidenceAgentFilter, setEvidenceAgentFilter] = useState<string>("all");
  const [evidenceTypeFilter, setEvidenceTypeFilter] = useState<string>("all");
  const [evidenceOrder, setEvidenceOrder] = useState<number[]>([]);
  const [dragOverId, setDragOverId] = useState<number | null>(null);
  const chatEndRef = useRef<HTMLDivElement>(null);
  const evidenceEndRef = useRef<HTMLDivElement>(null);

  const refreshSavedEvidence = useCallback(() => {
    getSavedEvidence(sessionId).then((data) => {
      setSavedEvidence(data.evidence);
      setEvidenceOrder((prev) => {
        const newIds = data.evidence.map((e: SavedEvidence) => e.id);
        const retained = prev.filter((id) => newIds.includes(id));
        const added = newIds.filter((id: number) => !retained.includes(id));
        return [...retained, ...added];
      });
    }).catch(console.error);
  }, [sessionId]);

  useEffect(() => {
    const stored = localStorage.getItem("simwork-theme") as "light" | "dark" | "system" | null;
    if (stored) setTheme(stored);
  }, []);

  useEffect(() => {
    const root = document.documentElement;
    localStorage.setItem("simwork-theme", theme);
    if (theme === "dark" || (theme === "system" && window.matchMedia("(prefers-color-scheme: dark)").matches)) {
      root.classList.add("dark");
    } else {
      root.classList.remove("dark");
    }
  }, [theme]);

  const cycleTheme = useCallback(() => {
    setTheme((prev) => (prev === "light" ? "dark" : prev === "dark" ? "system" : "light"));
  }, []);

  useEffect(() => {
    getSessionStatus(sessionId).then((data) => {
      if (data.status === "completed") {
        router.replace("/candidate");
        return;
      }
      setStatus(data);
    }).catch(console.error);
    getScenarioDetails(sessionId).then(setScenarioDetail).catch(console.error);
    getQueryHistory(sessionId).then((data) => {
      const nextMessages: ChatMessage[] = [];
      const nextGuidance: Record<string, AgentGuidance> = {};
      data.queries.forEach((item, index) => {
        nextMessages.push({
          id: `user-${item.query_log_id}-${index}`,
          role: "user",
          content: item.query,
          agent: item.agent,
          timestamp: item.timestamp,
        });
        nextMessages.push({
          id: `agent-${item.query_log_id}-${index}`,
          role: "agent",
          agent: item.agent,
          content: item.response,
          timestamp: item.timestamp,
          queryLogId: item.query_log_id,
          artifacts: item.artifacts,
          citations: item.citations,
          warnings: item.warnings,
        });
        nextGuidance[item.agent] = {
          pendingFollowUp: item.planner?.pending_follow_up || null,
          suggestions: item.planner?.next_steps || [],
        };
      });
      setMessages(nextMessages);
      setAgentGuidance(nextGuidance);
    }).catch(console.error);
    refreshSavedEvidence();
  }, [refreshSavedEvidence, sessionId]);

  useEffect(() => {
    if (!status) return;
    let remaining = status.time_remaining_minutes * 60;
    setTimeLeft(formatCountdown(remaining));
    if (remaining <= 0) {
      router.replace(`/complete/${sessionId}`);
      return;
    }
    const interval = setInterval(() => {
      remaining -= 1;
      if (remaining <= 0) {
        clearInterval(interval);
        router.replace(`/complete/${sessionId}`);
        return;
      }
      setTimeLeft(formatCountdown(remaining));
    }, 1000);
    return () => clearInterval(interval);
  }, [status, router, sessionId]);

  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  useEffect(() => {
    evidenceEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [savedEvidence]);

  const savedEvidenceMap = useMemo(() => {
    const map = new Map<string, SavedEvidence>();
    savedEvidence.forEach((item) => {
      map.set(`${item.query_log_id}:${item.citation_id}`, item);
    });
    return map;
  }, [savedEvidence]);

  const selectedAgentInfo = AGENTS.find((item) => item.id === selectedAgent)!;
  const selectedAgentSources = getAgentSources(selectedAgent, scenarioDetail?.reference_panel);
  const currentAgentGuidance = agentGuidance[selectedAgent];
  const currentPendingFollowUp = currentAgentGuidance?.pendingFollowUp || null;
  const currentSuggestions = currentPendingFollowUp?.choices?.length
    ? currentPendingFollowUp.choices
    : (currentAgentGuidance?.suggestions?.length ? currentAgentGuidance.suggestions : (QUICK_SUGGESTIONS[selectedAgent] || []));


  const sendQuery = useCallback(async (query: string, inputMode: "typed" | "suggestion" = "typed") => {
    if (!query.trim() || isQuerying) return;
    const now = new Date().toISOString();
    setMessages((prev) => [...prev, { id: `pending-user-${now}`, role: "user", content: query, agent: selectedAgent, timestamp: now }]);
    setIsQuerying(true);
    setAgentStatus("");
    try {
      const result = await queryAgentStream(
        sessionId, selectedAgent, query,
        (_stage, detail) => setAgentStatus(detail),
        inputMode,
      );
      const timestamp = new Date().toISOString();
      setMessages((prev) => [
        ...prev,
        {
          id: `agent-${result.query_log_id}-${timestamp}`,
          role: "agent",
          agent: selectedAgent,
          content: result.response,
          timestamp,
          queryLogId: result.query_log_id,
          artifacts: result.artifacts,
          citations: result.citations,
          warnings: result.warnings,
        },
      ]);
      setAgentGuidance((prev) => ({
        ...prev,
        [selectedAgent]: {
          pendingFollowUp: result.pending_follow_up || null,
          suggestions: result.next_steps || [],
        },
      }));
      getSessionStatus(sessionId).then(setStatus).catch(console.error);
    } catch (error: unknown) {
      const message = error instanceof Error ? error.message : "Query failed";
      setMessages((prev) => [
        ...prev,
        { id: `error-${Date.now()}`, role: "agent", agent: selectedAgent, content: `Error: ${message}`, timestamp: new Date().toISOString() },
      ]);
    } finally {
      setIsQuerying(false);
      setAgentStatus("");
    }
  }, [isQuerying, selectedAgent, sessionId]);

  const handleSend = useCallback(() => {
    if (!input.trim()) return;
    const query = input.trim();
    setInput("");
    sendQuery(query, "typed");
  }, [input, sendQuery]);

  const handleSaveArtifact = useCallback(async (message: ChatMessage, artifact: Artifact, citation: Citation | undefined) => {
    if (!message.queryLogId) return;
    const citationId = citation?.citation_id || artifact.citation_ids[0];
    if (!citationId) return;
    const key = `${message.queryLogId}:${citationId}`;
    try {
      await saveEvidence(sessionId, message.queryLogId, citationId, message.agent || selectedAgent, saveDrafts[key] || undefined);
      setSaveDrafts((prev) => ({ ...prev, [key]: "" }));
      refreshSavedEvidence();
      getSessionStatus(sessionId).then(setStatus).catch(console.error);
    } catch (error) {
      console.error(error);
    }
  }, [refreshSavedEvidence, saveDrafts, selectedAgent, sessionId]);

  const logUiEvent = useCallback((eventType: string, eventPayload: Record<string, unknown> = {}) => {
    logSessionEvent(sessionId, eventType, eventPayload).catch(() => undefined);
  }, [sessionId]);

  return (
    <div className="h-screen flex flex-col overflow-hidden bg-[#f6f6f8] dark:bg-[#101122] text-slate-900 dark:text-slate-100" style={{ fontFamily: "'Inter', sans-serif" }}>
      <ReferenceModal
        open={referenceOpen}
        tab={referenceTab}
        onTabChange={(tab) => {
          setReferenceTab(tab);
          logUiEvent("reference_tab_changed", { tab });
        }}
        onClose={() => setReferenceOpen(false)}
        reference={scenarioDetail?.reference_panel}
      />
      {logModalQueryId !== null && (
        <QueryLogModal
          key={logModalQueryId}
          sessionId={sessionId}
          queryLogId={logModalQueryId}
          onClose={() => setLogModalQueryId(null)}
        />
      )}

      <header className="flex items-center border-b border-slate-200 dark:border-slate-800 px-5 py-2 bg-white dark:bg-slate-900 shrink-0">
        <Link href="/candidate" className="flex items-center gap-3 shrink-0 hover:opacity-80 transition-opacity">
          <span className={`material-symbols-outlined text-2xl ${ACCENT_TEXT}`}>cognition</span>
          <h2 className="text-base font-bold tracking-tight text-slate-900 dark:text-white">SimWork</h2>
        </Link>
        <div className="flex-1 flex justify-center">
          <MissionCard
            title={scenarioDetail?.title || "Simulation"}
            problem={scenarioDetail?.problem_statement || "Investigate the issue and propose a recovery plan."}
            onOpen={() => {
              setReferenceTab("brief");
              setReferenceOpen(true);
              logUiEvent("reference_opened", { tab: "brief" });
            }}
          />
        </div>
        <div className="flex items-center gap-3 shrink-0">
          <button
            onClick={() => {
              setReferenceTab("sources");
              setReferenceOpen(true);
              logUiEvent("reference_opened", { tab: "sources" });
            }}
            className="rounded-lg h-9 px-4 bg-slate-100 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 text-xs font-semibold text-slate-700 dark:text-slate-300"
          >
            Sources
          </button>
          <div className="flex flex-col items-center px-4 py-1 rounded-lg bg-slate-100 dark:bg-slate-800 border border-slate-200 dark:border-slate-800 min-w-[80px]">
            <span className="text-[9px] uppercase tracking-widest text-slate-500 font-semibold">Time Left</span>
            <span className={`text-sm font-mono font-bold ${ACCENT_TEXT}`}>{timeLeft}</span>
          </div>
          <button
            onClick={() => router.push(`/complete/${sessionId}`)}
            className="rounded-lg h-9 px-4 bg-red-500/90 hover:bg-red-500 text-white text-xs font-bold transition-colors"
          >
            End Interview
          </button>
          <div className="h-5 w-px bg-slate-300 dark:bg-slate-700" />
          <button
            onClick={() => signOut({ callbackUrl: "/" })}
            className="flex items-center justify-center rounded-lg size-9 text-slate-400 hover:text-slate-600 dark:hover:text-slate-200 hover:bg-slate-100 dark:hover:bg-slate-800 transition-colors"
            title="Sign out"
          >
            <span className="material-symbols-outlined text-lg">logout</span>
          </button>
        </div>
      </header>

      <main className="flex flex-1 overflow-hidden">
        <aside className="w-72 flex flex-col border-r border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 overflow-hidden shrink-0">
          <div className="flex items-center gap-2 px-4 py-3 border-b border-slate-200 dark:border-slate-800">
            <span className={`material-symbols-outlined text-lg ${ACCENT_TEXT}`}>groups</span>
            <h3 className="text-[10px] font-bold uppercase tracking-widest text-slate-500">Team Panel</h3>
          </div>

          <div className="flex flex-col gap-1 p-2">
            {AGENTS.map((agent) => {
              const isSelected = selectedAgent === agent.id;
              const borderColor: Record<string, string> = {
                blue: "border-l-sky-400",
                purple: "border-l-violet-400",
                amber: "border-l-amber-400",
              };
              return (
                <button
                  key={agent.id}
                  onClick={() => {
                    if (selectedAgent !== agent.id) {
                      setSelectedAgent(agent.id);
                      logUiEvent("agent_selected", { agent: agent.id });
                    }
                  }}
                  className={`rounded-lg p-3 text-left transition-all ${
                    isSelected
                      ? `bg-slate-50 dark:bg-slate-800/50 border-l-[3px] ${borderColor[agent.color]}`
                      : "bg-transparent hover:bg-slate-50 dark:hover:bg-slate-800/30 border-l-[3px] border-l-transparent"
                  }`}
                >
                  <div className="flex items-center gap-2.5">
                    <AgentIcon agent={agent.id} size="md" />
                    <div className="flex flex-col min-w-0">
                      <h4 className="text-[13px] font-semibold text-slate-900 dark:text-slate-200">{agent.label}</h4>
                      <p className="text-[10px] text-slate-500">{agent.subtitle}</p>
                    </div>
                    {isSelected && <div className="ml-auto size-1.5 bg-emerald-400 rounded-full animate-pulse" />}
                  </div>
                </button>
              );
            })}
          </div>

          <div className="mx-2 mb-2 p-4 rounded-lg border border-slate-200 dark:border-slate-700/50 bg-slate-50 dark:bg-slate-800/20">
            <p className="text-[13px] text-slate-700 dark:text-slate-300 leading-relaxed mb-4">{AGENT_INTROS[selectedAgent].greeting}</p>
            <div className="space-y-1.5 mb-4">
              {AGENT_INTROS[selectedAgent].capabilities.map((item) => (
                <div key={item} className="flex items-center gap-2.5 text-[12px] text-slate-600 dark:text-slate-400">
                  <span className="size-2 rounded-full bg-emerald-400 shrink-0" />
                  <span>{item}</span>
                </div>
              ))}
            </div>
            {selectedAgentSources.length > 0 && (
              <div>
                <p className="text-[11px] text-slate-500 font-medium mb-2">I have access to these data sources:</p>
                <div className="space-y-1.5">
                  {selectedAgentSources.map((source) => (
                    <div key={source.name} className="flex items-center gap-2.5 text-[11px] text-slate-600 dark:text-slate-400">
                      <span className="size-1.5 rounded-[2px] border border-slate-400/70 shrink-0" />
                      <span className="font-mono">{source.name}</span>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>

          <div className="mt-auto px-3 pb-3">
            <button
              onClick={cycleTheme}
              className="flex items-center gap-2 w-full px-3 py-2 rounded-lg text-slate-500 hover:text-slate-700 dark:hover:text-slate-300 hover:bg-slate-100 dark:hover:bg-slate-800/40 transition-colors"
            >
              <span className="material-symbols-outlined text-base">
                {theme === "light" ? "light_mode" : theme === "dark" ? "dark_mode" : "monitor"}
              </span>
              <span className="text-[11px] font-medium capitalize">{theme} mode</span>
            </button>
          </div>
        </aside>

        <section className="flex flex-col overflow-hidden bg-[#f6f6f8] dark:bg-[#101122]" style={{ flex: "0 0 52%" }}>
          <div className="px-4 py-2.5 border-b border-slate-200 dark:border-slate-800 flex justify-between items-center bg-white/50 dark:bg-slate-900/50">
            <h3 className="text-sm font-semibold flex items-center gap-2 text-slate-700 dark:text-slate-300">
              <span className={`material-symbols-outlined ${ACCENT_TEXT}`}>forum</span>
              Investigation Chat
            </h3>
          </div>

          <div className="flex-1 overflow-y-auto px-4 py-3 flex flex-col gap-4">
            {messages.length === 0 && (
              <div className="flex-1 flex items-center justify-center text-slate-600 text-sm text-center px-4">
                Ask a teammate a concrete question. Their answer stays in chat; save the useful findings to your board.
              </div>
            )}
            {messages.map((message) => (
              <div key={message.id} className="flex gap-2.5">
                {message.role === "user" ? (
                  <div className="size-7 rounded-lg bg-emerald-500/15 flex items-center justify-center text-emerald-400 shrink-0">
                    <span className="material-symbols-outlined text-sm">person</span>
                  </div>
                ) : (
                  <AgentIcon agent={message.agent || "analyst"} />
                )}
                <div className="flex flex-col gap-0.5 min-w-0 max-w-[92%]">
                  <div className="flex items-center gap-2">
                    <span className="text-[10px] font-bold text-slate-400">
                      {message.role === "user" ? "You" : AGENTS.find((item) => item.id === message.agent)?.label}
                    </span>
                    <span className="text-[9px] text-slate-600">{formatTime(message.timestamp)}</span>
                  </div>
                  <div className={`px-3 py-2 rounded-xl rounded-tl-sm text-[13px] leading-relaxed whitespace-pre-wrap ${
                    message.role === "user"
                      ? "bg-emerald-500/10 dark:bg-emerald-600/20 text-emerald-900 dark:text-emerald-100 border border-emerald-500/20"
                      : message.role === "agent" && !!message.warnings?.length && !message.artifacts?.length
                        ? "bg-amber-500/8 dark:bg-amber-900/20 text-slate-700 dark:text-slate-300 border border-amber-500/20"
                        : "bg-white dark:bg-slate-800/50 text-slate-700 dark:text-slate-300 border border-slate-200 dark:border-slate-700/50"
                  }`}>
                    {message.content}
                    {message.role === "agent" && message.artifacts?.map((artifact, artifactIndex) => {
                      const citation = message.citations?.find((item) => artifact.citation_ids.includes(item.citation_id));
                      const key = `${message.queryLogId}:${citation?.citation_id || artifact.citation_ids[0] || artifactIndex}`;
                      return (
                        <InlineArtifactCard
                          key={key}
                          artifact={artifact}
                          citation={citation}
                          queryLogId={message.queryLogId}
                          savedEvidenceMap={savedEvidenceMap}
                          draftAnnotation={saveDrafts[key] || ""}
                          onDraftChange={(value) => setSaveDrafts((prev) => ({ ...prev, [key]: value }))}
                          onSave={() => handleSaveArtifact(message, artifact, citation)}
                        />
                      );
                    })}
                    {/* Show View Log link on failure */}
                    {message.role === "agent" && !!message.warnings?.length && !message.artifacts?.length && message.queryLogId && (
                      <div className="mt-2">
                        <button
                          onClick={() => setLogModalQueryId(message.queryLogId!)}
                          className="flex items-center gap-1 text-[10px] font-medium text-amber-600 dark:text-amber-400 hover:text-amber-500"
                        >
                          <span className="material-symbols-outlined text-sm">troubleshoot</span>
                          View log for details
                        </button>
                      </div>
                    )}
                    {message.role === "agent" && message.queryLogId && (
                      <div className="mt-3 flex justify-end">
                        <button
                          onClick={() => setLogModalQueryId(message.queryLogId!)}
                          className="flex items-center gap-1 px-2 py-1 rounded-md text-[10px] font-medium text-slate-400 hover:text-emerald-500 hover:bg-emerald-500/10 transition-colors"
                        >
                          <span className="material-symbols-outlined text-sm">code</span>
                          View log
                        </button>
                      </div>
                    )}
                  </div>
                </div>
              </div>
            ))}
            {isQuerying && (
              <div className="flex gap-2.5 items-start">
                <AgentIcon agent={selectedAgent} />
                <div className="flex flex-col gap-1">
                  <div className="flex items-center gap-2 animate-pulse">
                    <span className="text-xs text-slate-500">
                      {agentStatus || `${selectedAgentInfo.label} is analyzing evidence`}
                    </span>
                    <span className="flex gap-0.5">
                      <span className="size-1 bg-slate-500 rounded-full animate-bounce" style={{ animationDelay: "0ms" }} />
                      <span className="size-1 bg-slate-500 rounded-full animate-bounce" style={{ animationDelay: "150ms" }} />
                      <span className="size-1 bg-slate-500 rounded-full animate-bounce" style={{ animationDelay: "300ms" }} />
                    </span>
                  </div>
                </div>
              </div>
            )}
            <div ref={chatEndRef} />
          </div>

          {currentPendingFollowUp && (
            <div className="px-4 py-3 border-t border-slate-200 dark:border-slate-800/30 bg-emerald-500/5 dark:bg-emerald-500/10">
              <p className="text-[11px] font-semibold text-emerald-600 dark:text-emerald-300">
                {selectedAgentInfo.label} needs one clarification
              </p>
              <p className="mt-1 text-xs text-slate-700 dark:text-slate-200">{currentPendingFollowUp.prompt}</p>
              {!!currentPendingFollowUp.choices?.length && (
                <div className="mt-2 flex gap-1.5 flex-wrap">
                  {currentPendingFollowUp.choices.slice(0, 3).map((choice) => (
                    <button
                      key={choice}
                      onClick={() => {
                        logUiEvent("suggestion_clicked", { agent: selectedAgent, suggestion: choice, type: "clarification" });
                        sendQuery(choice, "suggestion");
                      }}
                      disabled={isQuerying}
                      className="text-[10px] px-2.5 py-1 rounded-full border border-emerald-500/40 text-emerald-600 dark:text-emerald-300 hover:bg-emerald-500/10 transition-colors disabled:opacity-40"
                    >
                      {choice}
                    </button>
                  ))}
                </div>
              )}
              {currentPendingFollowUp.allow_free_text !== false && (
                <p className="mt-2 text-[10px] text-slate-500 dark:text-slate-400">
                  You can also answer in your own words below.
                </p>
              )}
            </div>
          )}

          <div className="px-4 py-1.5 border-t border-slate-200 dark:border-slate-800/30 flex gap-1.5 flex-wrap">
            {currentSuggestions.slice(0, 3).map((suggestion) => (
              <button
                key={suggestion}
                onClick={() => {
                  logUiEvent("suggestion_clicked", { agent: selectedAgent, suggestion });
                  sendQuery(suggestion, "suggestion");
                }}
                disabled={isQuerying}
                className="text-[10px] px-2.5 py-1 rounded-full border border-slate-300 dark:border-slate-700/60 text-slate-500 dark:text-slate-400 hover:text-slate-700 dark:hover:text-slate-200 hover:border-slate-400 dark:hover:border-slate-600 hover:bg-slate-100 dark:hover:bg-slate-800/40 transition-colors disabled:opacity-40"
              >
                {suggestion}
              </button>
            ))}
          </div>

          <div className="px-4 py-2.5 border-t border-slate-200 dark:border-slate-800 bg-white/50 dark:bg-slate-900/50">
            <div className="relative">
              <input
                className={`w-full bg-slate-100 dark:bg-slate-800 border border-slate-300 dark:border-slate-700/50 rounded-lg pl-3 pr-10 py-2.5 text-sm text-slate-900 dark:text-slate-200 placeholder-slate-400 dark:placeholder-slate-600 ${ACCENT_RING} focus:ring-2 focus:border-transparent outline-none`}
                placeholder={currentPendingFollowUp ? `Reply to ${selectedAgentInfo.label}'s clarification...` : `Ask ${selectedAgentInfo.label} a question...`}
                value={input}
                onChange={(event) => setInput(event.target.value)}
                onKeyDown={(event) => event.key === "Enter" && handleSend()}
                disabled={isQuerying}
              />
              <button
                onClick={handleSend}
                disabled={isQuerying || !input.trim()}
                className={`absolute right-1.5 top-1.5 size-7 ${ACCENT_BG} ${ACCENT_BG_HOVER} text-white rounded-md flex items-center justify-center disabled:opacity-30 transition-colors`}
              >
                <span className="material-symbols-outlined text-sm">send</span>
              </button>
            </div>
          </div>
        </section>

        <aside className="flex-1 flex flex-col border-l border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 overflow-y-auto">
          {/* Evidence Board header */}
          <div className="flex items-center gap-2 px-4 py-2.5 border-b border-slate-200 dark:border-slate-800">
            <span className={`material-symbols-outlined text-lg ${ACCENT_TEXT}`}>folder_data</span>
            <h3 className="text-[10px] font-bold uppercase tracking-widest text-slate-500">Evidence Board</h3>
            {savedEvidence.length > 0 && (
              <span
                key={savedEvidence.length}
                className="ml-auto text-[9px] bg-emerald-500/15 text-emerald-400 px-2 py-0.5 rounded-full font-bold animate-[pulse_0.6s_ease-out_1]"
              >
                {savedEvidence.length} saved
              </span>
            )}
          </div>

          {/* Agent filter tabs */}
          {savedEvidence.length > 0 && (() => {
            const agentCounts: Record<string, number> = {};
            savedEvidence.forEach((e) => { agentCounts[e.agent] = (agentCounts[e.agent] || 0) + 1; });
            const presentAgents = AGENTS.filter((a) => agentCounts[a.id]);
            if (presentAgents.length < 2) return null;
            return (
              <div className="flex gap-1 px-3 pt-2.5 pb-1 flex-wrap">
                <button
                  onClick={() => setEvidenceAgentFilter("all")}
                  className={`text-[10px] px-2.5 py-1 rounded-full border transition-colors ${evidenceAgentFilter === "all" ? "bg-slate-700 dark:bg-slate-200 text-white dark:text-slate-900 border-transparent" : "border-slate-300 dark:border-slate-700 text-slate-500 hover:text-slate-700 dark:hover:text-slate-200"}`}
                >
                  All ({savedEvidence.length})
                </button>
                {presentAgents.map((a) => (
                  <button
                    key={a.id}
                    onClick={() => setEvidenceAgentFilter(evidenceAgentFilter === a.id ? "all" : a.id)}
                    className={`text-[10px] px-2.5 py-1 rounded-full border transition-colors ${evidenceAgentFilter === a.id ? "bg-slate-700 dark:bg-slate-200 text-white dark:text-slate-900 border-transparent" : "border-slate-300 dark:border-slate-700 text-slate-500 hover:text-slate-700 dark:hover:text-slate-200"}`}
                  >
                    {a.label} ({agentCounts[a.id]})
                  </button>
                ))}
              </div>
            );
          })()}

          {/* Type filter */}
          {savedEvidence.length > 0 && (() => {
            const types = new Set(savedEvidence.map((e) => e.artifact.kind));
            if (types.size < 2) return null;
            const typeLabels: Record<string, string> = { chart: "Charts", vega_chart: "Charts", table: "Tables", metric: "Metrics" };
            return (
              <div className="flex gap-1 px-3 pb-2 flex-wrap">
                <button
                  onClick={() => setEvidenceTypeFilter("all")}
                  className={`text-[9px] px-2 py-0.5 rounded-full border transition-colors ${evidenceTypeFilter === "all" ? "bg-slate-600/80 dark:bg-slate-300/80 text-white dark:text-slate-900 border-transparent" : "border-slate-200 dark:border-slate-700/60 text-slate-400 hover:text-slate-600 dark:hover:text-slate-300"}`}
                >
                  All types
                </button>
                {Array.from(types).map((t) => (
                  <button
                    key={t}
                    onClick={() => setEvidenceTypeFilter(evidenceTypeFilter === t ? "all" : t)}
                    className={`text-[9px] px-2 py-0.5 rounded-full border transition-colors ${evidenceTypeFilter === t ? "bg-slate-600/80 dark:bg-slate-300/80 text-white dark:text-slate-900 border-transparent" : "border-slate-200 dark:border-slate-700/60 text-slate-400 hover:text-slate-600 dark:hover:text-slate-300"}`}
                  >
                    {typeLabels[t] || t}
                  </button>
                ))}
              </div>
            );
          })()}

          <div className="flex-1 overflow-y-auto px-4 py-3">
            {savedEvidence.length === 0 ? (
              <div className="flex flex-col items-center justify-center py-12 text-center px-6">
                <span className="material-symbols-outlined text-4xl text-slate-700 mb-3">folder_data</span>
                <p className="text-xs text-slate-600 leading-relaxed">
                  Save findings from the chat to build your case. This board reflects your judgment, not the system&apos;s defaults.
                </p>
              </div>
            ) : (() => {
              const orderedEvidence = evidenceOrder
                .map((id) => savedEvidence.find((e) => e.id === id))
                .filter((e): e is SavedEvidence => !!e)
                .filter((e) => evidenceAgentFilter === "all" || e.agent === evidenceAgentFilter)
                .filter((e) => evidenceTypeFilter === "all" || e.artifact.kind === evidenceTypeFilter);

              if (orderedEvidence.length === 0) {
                return (
                  <div className="flex flex-col items-center justify-center py-8 text-center px-4">
                    <p className="text-xs text-slate-500">No evidence matches the current filter.</p>
                  </div>
                );
              }

              return (
                <div className="flex flex-col gap-3">
                  {orderedEvidence.map((item) => (
                    <div
                      key={item.id}
                      draggable
                      onDragStart={(ev) => ev.dataTransfer.setData("evidenceId", String(item.id))}
                      onDragOver={(ev) => { ev.preventDefault(); setDragOverId(item.id); }}
                      onDragLeave={() => setDragOverId(null)}
                      onDrop={(ev) => {
                        ev.preventDefault();
                        setDragOverId(null);
                        const draggedId = parseInt(ev.dataTransfer.getData("evidenceId"), 10);
                        if (draggedId === item.id) return;
                        setEvidenceOrder((prev) => {
                          const next = [...prev];
                          const fromIdx = next.indexOf(draggedId);
                          const toIdx = next.indexOf(item.id);
                          if (fromIdx < 0 || toIdx < 0) return prev;
                          next.splice(fromIdx, 1);
                          next.splice(toIdx, 0, draggedId);
                          return next;
                        });
                      }}
                      className={`transition-all ${dragOverId === item.id ? "ring-2 ring-emerald-500/50 rounded-xl" : ""}`}
                    >
                      <SavedEvidenceCard
                        item={item}
                        onRemove={async () => {
                          await removeEvidence(sessionId, item.id);
                          refreshSavedEvidence();
                          getSessionStatus(sessionId).then(setStatus).catch(console.error);
                        }}
                        onUpdate={async (annotation) => {
                          await updateEvidenceAnnotation(sessionId, item.id, annotation);
                          refreshSavedEvidence();
                        }}
                      />
                    </div>
                  ))}
                  <div ref={evidenceEndRef} />
                </div>
              );
            })()}
          </div>

          <div className="border-t border-slate-200 dark:border-slate-800 px-4 py-4 shrink-0">
            <button
              onClick={() => router.push(`/complete/${sessionId}`)}
              className="w-full bg-slate-100 dark:bg-slate-800 hover:bg-slate-200 dark:hover:bg-slate-700/50 text-slate-700 dark:text-slate-300 font-semibold py-3 px-4 rounded-lg flex items-center justify-center gap-2 transition-colors border border-slate-300 dark:border-slate-700/50 text-sm"
            >
              Final Plan
              <span className="material-symbols-outlined text-base">description</span>
            </button>
          </div>
        </aside>
      </main>
    </div>
  );
}

function getAgentSources(agent: string, reference?: ReferencePanel) {
  return reference?.source_catalog?.find((domain) => domain.agent === agent)?.sources || [];
}

function formatCell(value: string | number | null | undefined) {
  if (value === null || value === undefined || value === "") return "—";
  if (typeof value === "number") return value.toLocaleString();
  return value;
}

function formatTime(timestamp: string) {
  try {
    return new Date(timestamp).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
  } catch {
    return "";
  }
}

function formatCountdown(seconds: number) {
  const minutes = Math.floor(seconds / 60);
  const remainder = Math.floor(seconds % 60);
  return `${minutes.toString().padStart(2, "0")}:${remainder.toString().padStart(2, "0")}`;
}
