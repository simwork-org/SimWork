"use client";

import { useState, useEffect, useRef, useCallback } from "react";
import { useParams, useRouter } from "next/navigation";
import {
  queryAgent,
  submitHypothesis,
  getSessionStatus,
  getQueryHistory,
  type SessionStatus,
  type ChartData,
} from "@/lib/api";

// Accent
const ACCENT_BG = "bg-emerald-500";
const ACCENT_BG_HOVER = "hover:bg-emerald-600";
const ACCENT_TEXT = "text-emerald-400";
const ACCENT_RING = "focus:ring-emerald-500";

const AGENTS = [
  {
    id: "analyst",
    label: "Data Analyst",
    subtitle: "SQL & Metrics Expert",
    icon: "database",
    color: "blue",
    skills: ["Funnel analysis", "Cohort splits", "Trend breakdowns", "Segment comparisons"],
  },
  {
    id: "ux_researcher",
    label: "UX Researcher",
    subtitle: "User Behavior Specialist",
    icon: "person_search",
    color: "purple",
    skills: ["User feedback themes", "Support ticket analysis", "Usability findings", "Sentiment patterns"],
  },
  {
    id: "developer",
    label: "Developer",
    subtitle: "Technical Systems Lead",
    icon: "terminal",
    color: "amber",
    skills: ["Service latency checks", "Error rate analysis", "Deployment history", "System health"],
  },
] as const;

const QUICK_SUGGESTIONS: Record<string, string[]> = {
  analyst: ["Show order trends", "Break down the funnel", "Compare segment performance"],
  ux_researcher: ["Recent user complaints", "Usability test findings", "Feedback sentiment analysis"],
  developer: ["Check service latency", "Recent deployments", "Error rate trends"],
};

interface ChatMessage {
  role: "user" | "agent";
  agent?: string;
  content: string;
  timestamp: string;
}

interface DashboardCard {
  id: string;
  agent: string;
  title: string;
  chart: ChartData;
  timestamp: string;
}

// ── Chart Components (use structured data from API) ──

function BarChart({ chart }: { chart: ChartData }) {
  if (!chart.labels.length) return null;
  const absValues = chart.values.map((v) => Math.abs(v));
  const maxAbs = Math.max(...absValues, 1);
  const hasNegative = chart.values.some((v) => v < 0);
  return (
    <div className="flex flex-col gap-1">
      {chart.labels.map((label, i) => {
        const val = chart.values[i];
        const pct = Math.max(6, (Math.abs(val) / maxAbs) * 100);
        const isNeg = val < 0;
        return (
          <div key={i} className="flex items-center gap-2">
            <span className="text-[9px] text-slate-500 w-24 truncate text-right shrink-0">{label}</span>
            <div className="flex-1 h-4 bg-slate-200 dark:bg-slate-800/40 rounded overflow-hidden">
              <div
                className={`h-full rounded transition-all duration-500 ${isNeg ? "bg-gradient-to-r from-red-500/70 to-red-400/50" : "bg-gradient-to-r from-emerald-500/80 to-emerald-400/60"}`}
                style={{ width: `${pct}%` }}
              />
            </div>
            <span className={`text-[9px] font-mono w-14 shrink-0 text-right ${isNeg ? "text-red-400" : "text-slate-400"}`}>
              {hasNegative && val > 0 ? "+" : ""}{val?.toLocaleString()}{chart.unit === "%" ? "%" : ""}
            </span>
          </div>
        );
      })}
    </div>
  );
}

function LineChart({ chart }: { chart: ChartData }) {
  const values = chart.values;
  if (values.length < 2) return <BarChart chart={chart} />;
  const max = Math.max(...values);
  const min = Math.min(...values);
  const range = max - min || 1;
  const w = 300;
  const h = 100;
  const padX = 10;
  const padY = 15;

  const points = values.map((v, i) => {
    const x = padX + (i / (values.length - 1)) * (w - padX * 2);
    const y = padY + (1 - (v - min) / range) * (h - padY * 2);
    return { x, y, v };
  });

  const polyline = points.map((p) => `${p.x},${p.y}`).join(" ");
  const area = `${points[0].x},${h - padY} ${polyline} ${points[points.length - 1].x},${h - padY}`;
  // Unique gradient id per chart to avoid SVG id collisions
  const gradId = `areaGrad_${chart.title?.replace(/\s/g, "") || "default"}`;

  return (
    <div className="flex flex-col gap-1">
      <svg viewBox={`0 0 ${w} ${h}`} className="w-full" style={{ aspectRatio: `${w}/${h}` }}>
        <defs>
          <linearGradient id={gradId} x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor="#10B981" stopOpacity="0.3" />
            <stop offset="100%" stopColor="#10B981" stopOpacity="0.02" />
          </linearGradient>
        </defs>
        <polygon fill={`url(#${gradId})`} points={area} />
        <polyline fill="none" stroke="#10B981" strokeWidth="2" points={polyline} strokeLinejoin="round" strokeLinecap="round" />
        {points.map((p, i) => (
          <circle key={i} cx={p.x} cy={p.y} r="3.5" fill="white" stroke="#10B981" strokeWidth="1.5" className="dark:fill-[#101122]" />
        ))}
      </svg>
      <div className="flex justify-between px-1">
        {chart.labels.map((l, i) => (
          <div key={i} className="flex flex-col items-center">
            <span className="text-[8px] text-slate-500 leading-tight">{l}</span>
            <span className="text-[9px] text-slate-400 font-mono">{values[i]?.toLocaleString()}</span>
          </div>
        ))}
      </div>
    </div>
  );
}

function FunnelChart({ chart }: { chart: ChartData }) {
  if (!chart.labels.length) return null;
  const max = chart.values[0] || 1;
  return (
    <div className="flex flex-col gap-1">
      {chart.labels.map((label, i) => {
        const pct = Math.max(15, (chart.values[i] / max) * 100);
        const prevVal = i > 0 ? chart.values[i - 1] : null;
        const dropPct = prevVal ? Math.round((1 - chart.values[i] / prevVal) * 100) : 0;
        return (
          <div key={i} className="flex flex-col items-center">
            <div
              className="h-6 rounded bg-gradient-to-r from-emerald-600/80 to-emerald-400/50 flex items-center justify-between px-2.5 transition-all"
              style={{ width: `${pct}%` }}
            >
              <span className="text-[9px] text-white font-medium truncate">{label}</span>
              <span className="text-[9px] text-white/80 font-mono ml-2">{chart.values[i]?.toLocaleString()}</span>
            </div>
            {dropPct > 0 && (
              <span className="text-[8px] text-red-400/70 mt-0.5">-{dropPct}% drop</span>
            )}
          </div>
        );
      })}
    </div>
  );
}

function TableChart({ chart }: { chart: ChartData }) {
  return (
    <div className="border border-slate-200 dark:border-slate-700/50 rounded-lg overflow-hidden">
      {chart.labels.map((label, i) => (
        <div key={i} className={`flex items-center justify-between px-3 py-1.5 ${i % 2 === 0 ? "bg-slate-100 dark:bg-slate-800/20" : "bg-transparent"}`}>
          <span className="text-[10px] text-slate-500 dark:text-slate-400">{label}</span>
          <span className="text-[10px] text-slate-900 dark:text-slate-200 font-mono font-semibold">
            {chart.values[i]?.toLocaleString()}{chart.unit === "%" ? "%" : chart.unit ? ` ${chart.unit}` : ""}
          </span>
        </div>
      ))}
    </div>
  );
}

function ChartRenderer({ chart }: { chart: ChartData }) {
  switch (chart.type) {
    case "line": return <LineChart chart={chart} />;
    case "funnel": return <FunnelChart chart={chart} />;
    case "table": return <TableChart chart={chart} />;
    case "bar": default: return <BarChart chart={chart} />;
  }
}

function AgentIcon({ agent, size = "sm" }: { agent: string; size?: "sm" | "md" }) {
  const a = AGENTS.find((x) => x.id === agent);
  if (!a) return null;
  const colorMap: Record<string, string> = {
    blue: "bg-sky-500/15 text-sky-400",
    purple: "bg-violet-500/15 text-violet-400",
    amber: "bg-amber-500/15 text-amber-400",
  };
  const sizeClass = size === "md" ? "size-10" : "size-8";
  return (
    <div className={`${sizeClass} rounded-lg ${colorMap[a.color]} flex items-center justify-center shrink-0`}>
      <span className={`material-symbols-outlined ${size === "sm" ? "text-sm" : ""}`}>{a.icon}</span>
    </div>
  );
}

/** Combined Mission card — shows problem + objective on hover/click. */
function MissionCard() {
  const [open, setOpen] = useState(false);
  return (
    <div
      className="relative"
      onMouseEnter={() => setOpen(true)}
      onMouseLeave={() => setOpen(false)}
      onClick={() => setOpen((p) => !p)}
    >
      <div className="flex items-center gap-3 px-5 py-2 rounded-lg bg-slate-100 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 cursor-pointer hover:border-emerald-500/50 transition-colors">
        <span className={`material-symbols-outlined text-xl ${ACCENT_TEXT}`}>assignment</span>
        <div className="flex flex-col">
          <span className="text-sm font-bold text-slate-900 dark:text-slate-200">Checkout Conversion Drop</span>
          <span className="text-[9px] text-slate-500 font-medium">Orders -18% · Find Root Cause · <span className="text-emerald-500/70">click for brief</span></span>
        </div>
      </div>
      {open && (
        <div className="absolute top-full left-0 mt-2 z-50 w-[440px] p-5 bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-700 rounded-xl shadow-2xl shadow-black/20 dark:shadow-black/40">
          <div className="flex items-center gap-2 mb-3">
            <span className={`material-symbols-outlined text-lg ${ACCENT_TEXT}`}>assignment</span>
            <h4 className="text-sm font-bold text-slate-900 dark:text-slate-200">Mission Brief</h4>
          </div>
          <div className="space-y-3">
            <div>
              <p className="text-[10px] uppercase tracking-widest text-slate-500 font-bold mb-1">Problem</p>
              <p className="text-sm text-slate-700 dark:text-slate-300 leading-relaxed">
                Weekly orders have dropped by 18% over the past month. Competitors are maintaining steady volume. Leadership needs a data-backed explanation and recovery plan.
              </p>
            </div>
            <div>
              <p className="text-[10px] uppercase tracking-widest text-slate-500 font-bold mb-1">Objective</p>
              <p className="text-sm text-slate-700 dark:text-slate-300 leading-relaxed">
                Investigate the checkout conversion drop by querying AI teammates across analytics, UX research, and engineering. Form hypotheses, gather evidence, and submit a root-cause analysis with proposed recovery actions.
              </p>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

export default function WorkspacePage() {
  const params = useParams();
  const router = useRouter();
  const sessionId = params.sessionId as string;

  const [selectedAgent, setSelectedAgent] = useState<string>("analyst");
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [dashCards, setDashCards] = useState<DashboardCard[]>([]);
  const [suggestions, setSuggestions] = useState<string[]>([]);
  const [input, setInput] = useState("");
  const [hypothesis, setHypothesis] = useState("");
  const [savedHypotheses, setSavedHypotheses] = useState<string[]>([]);
  const [isQuerying, setIsQuerying] = useState(false);
  const [status, setStatus] = useState<SessionStatus | null>(null);
  const [timeLeft, setTimeLeft] = useState("30:00");
  const chatEndRef = useRef<HTMLDivElement>(null);
  const dashEndRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    getSessionStatus(sessionId).then(setStatus).catch(console.error);
    getQueryHistory(sessionId).then((data) => {
      const msgs: ChatMessage[] = [];
      for (const q of data.queries) {
        msgs.push({ role: "user", content: q.query, agent: q.agent, timestamp: q.timestamp });
        msgs.push({ role: "agent", agent: q.agent, content: q.response, timestamp: q.timestamp });
      }
      setMessages(msgs);
      // Note: history doesn't preserve chart data, so dashboard only shows charts from current session
    }).catch(console.error);
  }, [sessionId]);

  useEffect(() => {
    if (!status) return;
    let remaining = status.time_remaining_minutes * 60;
    const interval = setInterval(() => {
      remaining -= 1;
      if (remaining <= 0) { clearInterval(interval); setTimeLeft("00:00"); return; }
      const m = Math.floor(remaining / 60);
      const s = Math.floor(remaining % 60);
      setTimeLeft(`${m.toString().padStart(2, "0")}:${s.toString().padStart(2, "0")}`);
    }, 1000);
    return () => clearInterval(interval);
  }, [status]);

  useEffect(() => { chatEndRef.current?.scrollIntoView({ behavior: "smooth" }); }, [messages]);
  useEffect(() => { dashEndRef.current?.scrollIntoView({ behavior: "smooth" }); }, [dashCards]);

  const sendQuery = useCallback(async (query: string) => {
    if (!query.trim() || isQuerying) return;
    const now = new Date().toISOString();
    setMessages((prev) => [...prev, { role: "user", content: query, agent: selectedAgent, timestamp: now }]);
    setIsQuerying(true);
    try {
      const res = await queryAgent(sessionId, selectedAgent, query);
      const ts = new Date().toISOString();

      // Chat shows the concise insight (not raw data)
      setMessages((prev) => [...prev, { role: "agent", agent: selectedAgent, content: res.response, timestamp: ts }]);

      // Dashboard gets the chart if present
      if (res.chart && res.chart.labels && res.chart.labels.length > 0) {
        setDashCards((prev) => [...prev, {
          id: `${ts}-${selectedAgent}`,
          agent: selectedAgent,
          title: res.chart!.title || query,
          chart: res.chart!,
          timestamp: ts,
        }]);
      }

      // Update suggestions from agent's next_steps
      if (res.next_steps && res.next_steps.length > 0) {
        setSuggestions(res.next_steps);
      }
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : "Query failed";
      setMessages((prev) => [...prev, { role: "agent", agent: selectedAgent, content: `Error: ${message}`, timestamp: new Date().toISOString() }]);
    } finally {
      setIsQuerying(false);
    }
  }, [isQuerying, selectedAgent, sessionId]);

  const handleSend = useCallback(() => {
    if (!input.trim()) return;
    const q = input.trim();
    setInput("");
    sendQuery(q);
  }, [input, sendQuery]);

  const handleHypothesisSubmit = async () => {
    if (!hypothesis.trim()) return;
    try {
      await submitHypothesis(sessionId, hypothesis.trim());
      setSavedHypotheses((prev) => [...prev, hypothesis.trim()]);
      setHypothesis("");
    } catch (err) {
      console.error(err);
    }
  };

  const formatTime = (ts: string) => {
    try { return new Date(ts).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }); }
    catch { return ""; }
  };

  const selectedAgentInfo = AGENTS.find((a) => a.id === selectedAgent)!;
  const queryCount = messages.filter((m) => m.role === "user").length;

  // Show agent's next_steps as suggestions, fall back to defaults
  const currentSuggestions = suggestions.length > 0 ? suggestions : (QUICK_SUGGESTIONS[selectedAgent] || []);

  return (
    <div className="h-screen flex flex-col overflow-hidden bg-[#f6f6f8] dark:bg-[#101122] text-slate-900 dark:text-slate-100" style={{ fontFamily: "'Inter', sans-serif" }}>
      {/* ── Header ── */}
      <header className="flex items-center border-b border-slate-200 dark:border-slate-800 px-5 py-2 bg-white dark:bg-slate-900 shrink-0">
        <div className="flex items-center gap-3 shrink-0">
          <span className={`material-symbols-outlined text-2xl ${ACCENT_TEXT}`}>cognition</span>
          <h2 className="text-base font-bold tracking-tight text-slate-900 dark:text-white">SimWork</h2>
        </div>
        {/* Combined mission card — centered */}
        <div className="flex-1 flex justify-center">
          <MissionCard />
        </div>
        <div className="flex items-center gap-3 shrink-0">
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

      {/* ── Main 3-column layout ── */}
      <main className="flex flex-1 overflow-hidden">
        {/* ── Left: Team Panel (wider) ── */}
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
                  onClick={() => { setSelectedAgent(agent.id); setSuggestions([]); }}
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
                  {isSelected && (
                    <div className="mt-2.5 flex flex-wrap gap-1">
                      {agent.skills.map((skill) => (
                        <span key={skill} className="text-[9px] px-1.5 py-0.5 rounded bg-slate-100 dark:bg-slate-800/80 text-slate-500 dark:text-slate-400 font-medium">{skill}</span>
                      ))}
                    </div>
                  )}
                </button>
              );
            })}
          </div>

          {/* Session Stats */}
          <div className="mt-auto border-t border-slate-200 dark:border-slate-800">
            <div className="px-4 py-3">
              <h4 className="text-[10px] font-bold uppercase tracking-widest text-slate-500 mb-2.5">Session Stats</h4>
              <div className="space-y-2">
                {[
                  { label: "Queries", value: String(queryCount), icon: "chat" },
                  { label: "Agent", value: selectedAgentInfo.label, icon: "person" },
                  { label: "Hypotheses", value: String(savedHypotheses.length), icon: "lightbulb" },
                  { label: "Charts", value: String(dashCards.length), icon: "monitoring" },
                ].map((row) => (
                  <div key={row.label} className="flex items-center gap-2">
                    <span className="material-symbols-outlined text-slate-600 text-xs">{row.icon}</span>
                    <span className="text-[10px] text-slate-500 flex-1">{row.label}</span>
                    <span className="text-[10px] font-semibold text-slate-700 dark:text-slate-300 truncate max-w-[80px]">{row.value}</span>
                  </div>
                ))}
              </div>
            </div>
            <div className="px-3 pb-3">
              <div className="p-2.5 bg-slate-50 dark:bg-slate-800/30 rounded-lg border border-slate-200 dark:border-slate-800">
                <p className="text-[9px] text-slate-500 leading-relaxed">
                  Each teammate has their own data domain. Ask focused questions to get the best charts.
                </p>
              </div>
            </div>
          </div>
        </aside>

        {/* ── Center: Investigation Chat ── */}
        <section className="flex flex-col overflow-hidden bg-[#f6f6f8] dark:bg-[#101122]" style={{ flex: "0 0 44%" }}>
          <div className="px-4 py-2.5 border-b border-slate-200 dark:border-slate-800 flex justify-between items-center bg-white/50 dark:bg-slate-900/50">
            <h3 className="text-sm font-semibold flex items-center gap-2 text-slate-700 dark:text-slate-300">
              <span className={`material-symbols-outlined ${ACCENT_TEXT}`}>forum</span>
              Investigation Chat
            </h3>
          </div>

          {/* Messages */}
          <div className="flex-1 overflow-y-auto px-4 py-3 flex flex-col gap-4">
            {messages.length === 0 && (
              <div className="flex-1 flex items-center justify-center text-slate-600 text-sm text-center px-4">
                Select a teammate and ask a question to start investigating.
              </div>
            )}
            {messages.map((msg, i) => (
              <div key={i} className="flex gap-2.5">
                {msg.role === "user" ? (
                  <div className="size-7 rounded-lg bg-emerald-500/15 flex items-center justify-center text-emerald-400 shrink-0">
                    <span className="material-symbols-outlined text-sm">person</span>
                  </div>
                ) : (
                  <AgentIcon agent={msg.agent || "analyst"} />
                )}
                <div className="flex flex-col gap-0.5 min-w-0 max-w-[90%]">
                  <div className="flex items-center gap-2">
                    <span className="text-[10px] font-bold text-slate-400">
                      {msg.role === "user" ? "You" : AGENTS.find((a) => a.id === msg.agent)?.label}
                    </span>
                    <span className="text-[9px] text-slate-600">{formatTime(msg.timestamp)}</span>
                  </div>
                  <div className={`px-3 py-2 rounded-xl rounded-tl-sm text-[13px] leading-relaxed whitespace-pre-wrap ${
                    msg.role === "user"
                      ? "bg-emerald-500/10 dark:bg-emerald-600/20 text-emerald-900 dark:text-emerald-100 border border-emerald-500/20"
                      : "bg-white dark:bg-slate-800/50 text-slate-700 dark:text-slate-300 border border-slate-200 dark:border-slate-700/50"
                  }`}>
                    {msg.content}
                  </div>
                </div>
              </div>
            ))}
            {isQuerying && (
              <div className="flex gap-2.5 items-center">
                <AgentIcon agent={selectedAgent} />
                <div className="flex items-center gap-2 animate-pulse">
                  <span className="text-xs text-slate-500">{selectedAgentInfo.label} is analyzing data</span>
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

          {/* Dynamic suggestions (from agent or defaults) */}
          <div className="px-4 py-1.5 border-t border-slate-200 dark:border-slate-800/30 flex gap-1.5 flex-wrap">
            {currentSuggestions.slice(0, 3).map((s) => (
              <button
                key={s}
                onClick={() => sendQuery(s)}
                disabled={isQuerying}
                className="text-[10px] px-2.5 py-1 rounded-full border border-slate-300 dark:border-slate-700/60 text-slate-500 dark:text-slate-400 hover:text-slate-700 dark:hover:text-slate-200 hover:border-slate-400 dark:hover:border-slate-600 hover:bg-slate-100 dark:hover:bg-slate-800/40 transition-colors disabled:opacity-40"
              >
                {s}
              </button>
            ))}
          </div>

          {/* Input */}
          <div className="px-4 py-2.5 border-t border-slate-200 dark:border-slate-800 bg-white/50 dark:bg-slate-900/50">
            <div className="relative">
              <input
                className={`w-full bg-slate-100 dark:bg-slate-800 border border-slate-300 dark:border-slate-700/50 rounded-lg pl-3 pr-10 py-2.5 text-sm text-slate-900 dark:text-slate-200 placeholder-slate-400 dark:placeholder-slate-600 ${ACCENT_RING} focus:ring-2 focus:border-transparent outline-none`}
                placeholder={`Ask ${selectedAgentInfo.label} a question...`}
                value={input}
                onChange={(e) => setInput(e.target.value)}
                onKeyDown={(e) => e.key === "Enter" && handleSend()}
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

        {/* ── Right: Dashboard ── */}
        <aside className="flex-1 flex flex-col border-l border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 overflow-y-auto">
          <div className="flex items-center gap-2 px-4 py-2.5 border-b border-slate-200 dark:border-slate-800">
            <span className={`material-symbols-outlined text-lg ${ACCENT_TEXT}`}>dashboard</span>
            <h3 className="text-[10px] font-bold uppercase tracking-widest text-slate-500">Dashboard</h3>
            {dashCards.length > 0 && (
              <span className="ml-auto text-[9px] bg-emerald-500/15 text-emerald-400 px-2 py-0.5 rounded-full font-bold">{dashCards.length} charts</span>
            )}
          </div>

          <div className="flex-1 overflow-y-auto px-4 py-3">
            {dashCards.length === 0 ? (
              <div className="flex flex-col items-center justify-center h-full text-center px-6">
                <span className="material-symbols-outlined text-4xl text-slate-700 mb-3">monitoring</span>
                <p className="text-xs text-slate-600 leading-relaxed">
                  Charts will appear here as your teammates analyze data. Ask about trends, funnels, or comparisons.
                </p>
              </div>
            ) : (
              <div className="flex flex-col gap-3">
                {dashCards.map((card) => {
                  const agentInfo = AGENTS.find((a) => a.id === card.agent);
                  const borderAccent: Record<string, string> = {
                    analyst: "border-t-sky-500/60",
                    ux_researcher: "border-t-violet-500/60",
                    developer: "border-t-amber-500/60",
                  };
                  const chartIcon: Record<string, string> = {
                    bar: "bar_chart",
                    line: "show_chart",
                    funnel: "filter_alt",
                    table: "table_rows",
                  };
                  return (
                    <div key={card.id} className={`bg-slate-50 dark:bg-slate-800/30 rounded-lg border border-slate-200 dark:border-slate-700/50 border-t-2 ${borderAccent[card.agent] || ""} p-4`}>
                      <div className="flex items-center gap-2 mb-3">
                        <span className="material-symbols-outlined text-slate-500 text-sm">{chartIcon[card.chart.type] || "bar_chart"}</span>
                        <span className="text-[10px] font-semibold text-slate-400">{agentInfo?.label}</span>
                        <span className="text-[9px] text-slate-600 ml-auto">{formatTime(card.timestamp)}</span>
                      </div>
                      <p className="text-[12px] text-slate-900 dark:text-slate-200 font-semibold mb-3">{card.title}</p>
                      <ChartRenderer chart={card.chart} />
                    </div>
                  );
                })}
                <div ref={dashEndRef} />
              </div>
            )}
          </div>

          {/* Hypotheses */}
          <div className="border-t border-slate-200 dark:border-slate-800 px-4 py-4 shrink-0 min-h-[140px]">
            <div className="flex items-center justify-between mb-3">
              <h4 className="text-xs font-bold uppercase tracking-widest text-slate-500 flex items-center gap-2">
                <span className="material-symbols-outlined text-base text-emerald-500">lightbulb</span>
                Saved Hypotheses
              </h4>
              {savedHypotheses.length > 0 && (
                <span className="text-[10px] bg-emerald-500/15 text-emerald-500 px-2.5 py-0.5 rounded-full font-bold">{savedHypotheses.length}</span>
              )}
            </div>
            {savedHypotheses.length === 0 ? (
              <p className="text-xs text-slate-400">Submit hypotheses below to track them here.</p>
            ) : (
              <div className="flex flex-col gap-2 max-h-[30vh] overflow-y-auto">
                {savedHypotheses.map((h, i) => (
                  <div key={i} className="bg-slate-50 dark:bg-slate-800/30 rounded-lg p-3 border border-slate-200 dark:border-slate-700/50 flex items-start gap-2.5">
                    <span className="text-emerald-500 text-xs font-bold mt-0.5 shrink-0">H{i + 1}</span>
                    <p className="text-xs text-slate-700 dark:text-slate-300 leading-relaxed">{h}</p>
                  </div>
                ))}
              </div>
            )}
          </div>
        </aside>
      </main>

      {/* ── Bottom: Hypothesis bar ── */}
      <footer className="px-5 py-2 bg-white dark:bg-slate-900 border-t border-slate-200 dark:border-slate-800 flex items-center gap-3">
        <span className={`material-symbols-outlined text-base ${ACCENT_TEXT}`}>lightbulb</span>
        <span className="text-[9px] font-bold uppercase tracking-widest text-slate-500 shrink-0">Hypothesis</span>
        <input
          className={`flex-1 bg-slate-100 dark:bg-slate-800 border border-slate-300 dark:border-slate-700/50 rounded-lg px-4 py-2 text-sm text-slate-900 dark:text-slate-200 placeholder-slate-400 dark:placeholder-slate-600 ${ACCENT_RING} focus:ring-2 focus:border-transparent outline-none`}
          placeholder="I believe the order drop is caused by [reason] because [evidence]..."
          value={hypothesis}
          onChange={(e) => setHypothesis(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && handleHypothesisSubmit()}
        />
        <button
          onClick={handleHypothesisSubmit}
          disabled={!hypothesis.trim()}
          className={`${ACCENT_BG} ${ACCENT_BG_HOVER} text-white font-semibold py-2 px-4 rounded-lg flex items-center gap-2 transition-colors disabled:opacity-40 text-sm shrink-0`}
        >
          Submit Hypothesis
          <span className="material-symbols-outlined text-base">rocket_launch</span>
        </button>
        <button
          onClick={() => router.push(`/complete/${sessionId}`)}
          className="bg-slate-100 dark:bg-slate-800 hover:bg-slate-200 dark:hover:bg-slate-700/50 text-slate-700 dark:text-slate-300 font-semibold py-2 px-4 rounded-lg flex items-center gap-2 transition-colors border border-slate-300 dark:border-slate-700/50 text-sm shrink-0"
        >
          Final Plan
          <span className="material-symbols-outlined text-base">description</span>
        </button>
      </footer>
    </div>
  );
}
