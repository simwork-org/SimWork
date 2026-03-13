"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import {
  getQueryHistory,
  getSavedEvidence,
  getScenarioDetails,
  getSessionStatus,
  logSessionEvent,
  queryAgent,
  removeEvidence,
  saveEvidence,
  updateEvidenceAnnotation,
  type Artifact,
  type Citation,
  type PendingFollowUp,
  type QueryHistoryItem,
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
  const series = artifact.series[0];
  if (!series || artifact.labels.length === 0) return null;
  const values = series.values;
  const max = Math.max(...values, 1);
  return (
    <div className="flex flex-col gap-2">
      {artifact.labels.map((label, index) => {
        const value = values[index] ?? 0;
        const pct = Math.max(6, (value / max) * 100);
        return (
          <div key={`${label}-${index}`} className="flex items-center gap-3">
            <span className="w-28 shrink-0 truncate text-[11px] text-slate-500">{label}</span>
            <div className="flex-1 h-4 rounded-full bg-slate-200 dark:bg-slate-800 overflow-hidden">
              <div className="h-full rounded-full bg-gradient-to-r from-emerald-500 to-emerald-300" style={{ width: `${pct}%` }} />
            </div>
            <span className="w-16 shrink-0 text-right text-[11px] font-mono text-slate-500">
              {value.toLocaleString()}{artifact.unit === "%" ? "%" : ""}
            </span>
          </div>
        );
      })}
    </div>
  );
}

function LineChart({ artifact }: { artifact: Extract<Artifact, { kind: "chart" }> }) {
  if (artifact.labels.length < 2) return <BarChart artifact={artifact} />;
  const palette = ["#10B981", "#38BDF8", "#F59E0B", "#A855F7"];
  const flattened = artifact.series.flatMap((item) => item.values);
  const max = Math.max(...flattened, 1);
  const min = Math.min(...flattened, 0);
  const range = max - min || 1;
  const width = 320;
  const height = 120;
  const padX = 14;
  const padY = 18;

  return (
    <div className="space-y-3">
      <svg viewBox={`0 0 ${width} ${height}`} className="w-full" style={{ aspectRatio: `${width}/${height}` }}>
        {artifact.series.map((series, seriesIndex) => {
          const points = series.values.map((value, index) => {
            const x = padX + (index / Math.max(artifact.labels.length - 1, 1)) * (width - padX * 2);
            const y = padY + (1 - (value - min) / range) * (height - padY * 2);
            return `${x},${y}`;
          });
          return (
            <polyline
              key={series.name}
              fill="none"
              stroke={palette[seriesIndex % palette.length]}
              strokeWidth="2.5"
              strokeLinecap="round"
              strokeLinejoin="round"
              points={points.join(" ")}
            />
          );
        })}
      </svg>
      <div className="flex justify-between gap-2 overflow-x-auto">
        {artifact.labels.map((label, index) => (
          <div key={`${label}-${index}`} className="min-w-[56px] text-center">
            <p className="text-[10px] text-slate-500">{label}</p>
          </div>
        ))}
      </div>
      <div className="flex flex-wrap gap-3">
        {artifact.series.map((series, index) => (
          <div key={series.name} className="flex items-center gap-2 text-[11px] text-slate-500">
            <span className="size-2 rounded-full" style={{ backgroundColor: palette[index % palette.length] }} />
            <span>{series.name}</span>
          </div>
        ))}
      </div>
    </div>
  );
}

function FunnelChart({ artifact }: { artifact: Extract<Artifact, { kind: "chart" }> }) {
  const series = artifact.series[0];
  if (!series || artifact.labels.length === 0) return null;
  const max = Math.max(series.values[0] || 1, 1);
  return (
    <div className="space-y-2">
      {artifact.labels.map((label, index) => {
        const value = series.values[index] ?? 0;
        const previous = index === 0 ? null : series.values[index - 1];
        const pct = Math.max(18, (value / max) * 100);
        const drop = previous ? Math.round((1 - value / previous) * 100) : null;
        return (
          <div key={`${label}-${index}`} className="flex flex-col items-center">
            <div
              className="h-7 rounded-lg bg-gradient-to-r from-emerald-600 to-emerald-400 flex items-center justify-between px-3 text-white text-[11px] w-full"
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

function TableArtifactView({ artifact }: { artifact: Extract<Artifact, { kind: "table" }> }) {
  const numericColumns = new Set(artifact.columns.filter((column) => artifact.rows.some((row) => typeof row[column] === "number")));
  const monospaceColumns = new Set(
    artifact.columns.filter((column) => /(^|_)(id|code|version|status)$/.test(column.toLowerCase()) || numericColumns.has(column))
  );

  return (
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
  );
}

function ArtifactRenderer({ artifact }: { artifact: Artifact }) {
  if (artifact.kind === "metric") return <MetricArtifactView artifact={artifact} />;
  if (artifact.kind === "table") return <TableArtifactView artifact={artifact} />;
  if (artifact.chart_type === "line") return <LineChart artifact={artifact} />;
  if (artifact.chart_type === "funnel") return <FunnelChart artifact={artifact} />;
  return <BarChart artifact={artifact} />;
}

function InlineArtifactCard({
  artifact,
  citation,
  queryLogId,
  agent,
  savedEvidenceMap,
  draftAnnotation,
  onDraftChange,
  onSave,
}: {
  artifact: Artifact;
  citation: Citation | undefined;
  queryLogId?: number;
  agent: string;
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
          className="mt-3 w-full rounded-lg border border-slate-300 dark:border-slate-700 bg-white dark:bg-slate-800 px-3 py-2 text-[11px] text-slate-700 dark:text-slate-200 outline-none focus:ring-2 focus:ring-emerald-500"
          placeholder="Add a note before saving (optional)"
          value={draftAnnotation}
          onChange={(event) => onDraftChange(event.target.value)}
        />
      )}
      {savedItem?.annotation && <p className="mt-3 text-[11px] text-emerald-600 dark:text-emerald-400">{savedItem.annotation}</p>}
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
  const agentInfo = AGENTS.find((agent) => agent.id === item.agent);

  useEffect(() => {
    setAnnotation(item.annotation || "");
  }, [item.annotation]);

  return (
    <div className="bg-slate-50 dark:bg-slate-800/30 rounded-xl border border-slate-200 dark:border-slate-700/50 p-4">
      <div className="flex items-center gap-2 mb-3">
        <AgentIcon agent={item.agent} />
        <div className="min-w-0">
          <p className="text-[10px] font-semibold text-slate-500">{agentInfo?.label}</p>
          <p className="text-[12px] font-semibold text-slate-900 dark:text-slate-100 truncate">{item.artifact.title}</p>
        </div>
        <span className="text-[10px] text-slate-500 ml-auto">{formatTime(item.saved_at)}</span>
      </div>
      {editing ? (
        <div className="mb-3 flex gap-2">
          <input
            className="flex-1 rounded-lg border border-slate-300 dark:border-slate-700 bg-white dark:bg-slate-900 px-3 py-2 text-[11px] outline-none focus:ring-2 focus:ring-emerald-500"
            value={annotation}
            onChange={(event) => setAnnotation(event.target.value)}
            placeholder="Add a note about why this matters"
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
      ) : item.annotation ? (
        <p className="mb-3 text-[12px] leading-relaxed text-emerald-600 dark:text-emerald-400">{item.annotation}</p>
      ) : null}
      <ArtifactRenderer artifact={item.artifact} />
      <div className="mt-3 flex flex-wrap gap-2">
        <span className="px-2 py-1 rounded-full bg-slate-200 dark:bg-slate-800 text-[10px] text-slate-600 dark:text-slate-300">
          {item.citation.source}
        </span>
      </div>
      <div className="mt-3 flex gap-2">
        <button
          onClick={() => setEditing((value) => !value)}
          className="text-[10px] px-2.5 py-1 rounded-full border border-slate-300 dark:border-slate-700 text-slate-500 hover:text-slate-700 dark:hover:text-slate-200"
        >
          {editing ? "Cancel" : item.annotation ? "Edit note" : "Add note"}
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
  const sessionId = params.sessionId as string;

  const [selectedAgent, setSelectedAgent] = useState<string>("analyst");
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [savedEvidence, setSavedEvidence] = useState<SavedEvidence[]>([]);
  const [agentGuidance, setAgentGuidance] = useState<Record<string, AgentGuidance>>({});
  const [input, setInput] = useState("");
  const [isQuerying, setIsQuerying] = useState(false);
  const [status, setStatus] = useState<SessionStatus | null>(null);
  const [scenarioDetail, setScenarioDetail] = useState<ScenarioDetail | null>(null);
  const [timeLeft, setTimeLeft] = useState("30:00");
  const [referenceOpen, setReferenceOpen] = useState(false);
  const [referenceTab, setReferenceTab] = useState<"brief" | "sources">("brief");
  const [saveDrafts, setSaveDrafts] = useState<Record<string, string>>({});
  const [theme, setTheme] = useState<"light" | "dark" | "system">("system");
  const chatEndRef = useRef<HTMLDivElement>(null);
  const evidenceEndRef = useRef<HTMLDivElement>(null);

  const refreshSavedEvidence = useCallback(() => {
    getSavedEvidence(sessionId).then((data) => setSavedEvidence(data.evidence)).catch(console.error);
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
    getSessionStatus(sessionId).then(setStatus).catch(console.error);
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
    const interval = setInterval(() => {
      remaining -= 1;
      if (remaining <= 0) {
        clearInterval(interval);
        setTimeLeft("00:00");
        return;
      }
      setTimeLeft(formatCountdown(remaining));
    }, 1000);
    return () => clearInterval(interval);
  }, [status]);

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
  const currentSuggestions = QUICK_SUGGESTIONS[selectedAgent] || [];
  const queryCount = useMemo(() => messages.filter((item) => item.role === "user").length, [messages]);

  const sendQuery = useCallback(async (query: string, inputMode: "typed" | "suggestion" = "typed") => {
    if (!query.trim() || isQuerying) return;
    const now = new Date().toISOString();
    setMessages((prev) => [...prev, { id: `pending-user-${now}`, role: "user", content: query, agent: selectedAgent, timestamp: now }]);
    setIsQuerying(true);
    try {
      const result = await queryAgent(sessionId, selectedAgent, query, inputMode);
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

      <header className="flex items-center border-b border-slate-200 dark:border-slate-800 px-5 py-2 bg-white dark:bg-slate-900 shrink-0">
        <div className="flex items-center gap-3 shrink-0">
          <span className={`material-symbols-outlined text-2xl ${ACCENT_TEXT}`}>cognition</span>
          <h2 className="text-base font-bold tracking-tight text-slate-900 dark:text-white">SimWork</h2>
        </div>
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
                          agent={message.agent || "analyst"}
                          savedEvidenceMap={savedEvidenceMap}
                          draftAnnotation={saveDrafts[key] || ""}
                          onDraftChange={(value) => setSaveDrafts((prev) => ({ ...prev, [key]: value }))}
                          onSave={() => handleSaveArtifact(message, artifact, citation)}
                        />
                      );
                    })}
                    {message.role === "agent" && !!message.warnings?.length && (
                      <div className="mt-3 flex flex-wrap gap-2">
                        {message.warnings.map((warning, index) => (
                          <span key={`${message.id}-warning-${index}`} className="px-2 py-1 rounded-full bg-red-500/10 text-[10px] text-red-500">
                            {warning}
                          </span>
                        ))}
                      </div>
                    )}
                  </div>
                </div>
              </div>
            ))}
            {isQuerying && (
              <div className="flex gap-2.5 items-center">
                <AgentIcon agent={selectedAgent} />
                <div className="flex items-center gap-2 animate-pulse">
                  <span className="text-xs text-slate-500">{selectedAgentInfo.label} is analyzing evidence</span>
                  <span className="flex gap-0.5">
                    <span className="size-1 bg-slate-500 rounded-full animate-bounce" style={{ animationDelay: "0ms" }} />
                    <span className="size-1 bg-slate-500 rounded-full animate-bounce" style={{ animationDelay: "150ms" }} />
                    <span className="size-1 bg-slate-500 rounded-full animate-bounce" style={{ animationDelay: "300ms" }} />
                  </span>
                </div>
              </div>
            )}
            <div ref={chatEndRef} />
          </div>

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
                placeholder={`Ask ${selectedAgentInfo.label} a question...`}
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
          <div className="flex items-center gap-2 px-4 py-2.5 border-b border-slate-200 dark:border-slate-800">
            <span className={`material-symbols-outlined text-lg ${ACCENT_TEXT}`}>folder_data</span>
            <h3 className="text-[10px] font-bold uppercase tracking-widest text-slate-500">Evidence Board</h3>
            {savedEvidence.length > 0 && (
              <span className="ml-auto text-[9px] bg-emerald-500/15 text-emerald-400 px-2 py-0.5 rounded-full font-bold">{savedEvidence.length} saved</span>
            )}
          </div>

          <div className="flex-1 overflow-y-auto px-4 py-3">
            {savedEvidence.length === 0 ? (
              <div className="flex flex-col items-center justify-center py-12 text-center px-6">
                <span className="material-symbols-outlined text-4xl text-slate-700 mb-3">folder_data</span>
                <p className="text-xs text-slate-600 leading-relaxed">
                  Save findings from the chat to build your case. This board reflects your judgment, not the system’s defaults.
                </p>
              </div>
            ) : (
              <div className="flex flex-col gap-3">
                {savedEvidence.map((item) => (
                  <SavedEvidenceCard
                    key={item.id}
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
                ))}
                <div ref={evidenceEndRef} />
              </div>
            )}
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
