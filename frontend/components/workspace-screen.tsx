"use client";

import { FormEvent, useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";

import { DataVisualization } from "@/components/data-visualization";
import {
  flattenConversation,
  getHistory,
  getScenario,
  getStatus,
  sendQuery,
  submitHypothesis,
  submitSolution
} from "@/lib/api";
import type {
  AgentName,
  HistoryResponse,
  QueryHistoryItem,
  ScenarioDetails,
  SessionStatus,
  Visualization
} from "@/lib/types";

const agentMeta: Record<
  AgentName,
  { label: string; subtitle: string; icon: string; accent: string; suggestions: string[] }
> = {
  analyst: {
    label: "Data Analyst",
    subtitle: "SQL & Metrics Expert",
    icon: "database",
    accent: "text-blue-400 bg-blue-500/10",
    suggestions: ["Show order trends", "Break down the funnel", "Compare segment performance"]
  },
  ux_researcher: {
    label: "UX Researcher",
    subtitle: "User Behavior Specialist",
    icon: "person_search",
    accent: "text-purple-400 bg-purple-500/10",
    suggestions: ["Review support tickets", "Summarize user feedback", "Share usability findings"]
  },
  developer: {
    label: "Developer",
    subtitle: "Technical Systems Lead",
    icon: "terminal",
    accent: "text-amber-400 bg-amber-500/10",
    suggestions: ["Check service latency", "Were there deployments?", "Show error rates"]
  }
};

export function WorkspaceScreen({ sessionId }: { sessionId: string }) {
  const router = useRouter();
  const [scenario, setScenario] = useState<ScenarioDetails | null>(null);
  const [history, setHistory] = useState<HistoryResponse>({ queries: [], hypotheses: [], final_submission: null });
  const [status, setStatus] = useState<SessionStatus | null>(null);
  const [activeAgent, setActiveAgent] = useState<AgentName>("analyst");
  const [query, setQuery] = useState("");
  const [hypothesis, setHypothesis] = useState("");
  const [latestVisualization, setLatestVisualization] = useState<Visualization | null>(null);
  const [loadingQuery, setLoadingQuery] = useState(false);
  const [loadingPage, setLoadingPage] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [showFinalPlan, setShowFinalPlan] = useState(false);
  const [rootCause, setRootCause] = useState("");
  const [actionsText, setActionsText] = useState("Reduce payment latency\nAdd payment retry flow\nImprove payment failure feedback");
  const [summary, setSummary] = useState("");

  useEffect(() => {
    let cancelled = false;
    async function load() {
      setLoadingPage(true);
      setError(null);
      try {
        const [scenarioResponse, historyResponse, statusResponse] = await Promise.all([
          getScenario(sessionId),
          getHistory(sessionId),
          getStatus(sessionId)
        ]);
        if (cancelled) {
          return;
        }
        setScenario(scenarioResponse);
        setHistory(historyResponse);
        setStatus(statusResponse);
        const newestViz =
          [...historyResponse.queries].reverse().find((item) => item.data_visualization)?.data_visualization ?? null;
        setLatestVisualization(newestViz);
        if (statusResponse.current_hypothesis) {
          setHypothesis(statusResponse.current_hypothesis);
        }
        if (historyResponse.final_submission?.summary) {
          setSummary(historyResponse.final_submission.summary);
        }
      } catch (loadError) {
        if (!cancelled) {
          setError(loadError instanceof Error ? loadError.message : "Unable to load session");
        }
      } finally {
        if (!cancelled) {
          setLoadingPage(false);
        }
      }
    }
    void load();

    const interval = window.setInterval(() => {
      void getStatus(sessionId).then(setStatus).catch(() => undefined);
    }, 30000);

    return () => {
      cancelled = true;
      window.clearInterval(interval);
    };
  }, [sessionId]);

  const conversation = useMemo(() => flattenConversation(history.queries), [history.queries]);
  const suggestions = agentMeta[activeAgent].suggestions;

  async function handleSendQuery(event?: FormEvent) {
    event?.preventDefault();
    if (!query.trim()) {
      return;
    }
    setLoadingQuery(true);
    setError(null);
    try {
      const response = await sendQuery(sessionId, activeAgent, query.trim());
      const newItem: QueryHistoryItem = {
        timestamp: new Date().toISOString(),
        agent: response.agent,
        query: query.trim(),
        response: response.response,
        data_visualization: response.data_visualization ?? null
      };
      setHistory((current) => ({ ...current, queries: [...current.queries, newItem] }));
      setLatestVisualization(response.data_visualization ?? null);
      setQuery("");
      const nextStatus = await getStatus(sessionId);
      setStatus(nextStatus);
    } catch (queryError) {
      setError(queryError instanceof Error ? queryError.message : "Unable to send query");
    } finally {
      setLoadingQuery(false);
    }
  }

  async function handleHypothesisSubmit() {
    if (!hypothesis.trim()) {
      return;
    }
    setError(null);
    try {
      const response = await submitHypothesis(sessionId, hypothesis.trim());
      setHistory((current) => ({
        ...current,
        hypotheses: [
          ...current.hypotheses,
          {
            timestamp: new Date().toISOString(),
            hypothesis: hypothesis.trim(),
            hypothesis_version: response.hypothesis_version
          }
        ]
      }));
      setStatus((current) =>
        current ? { ...current, current_hypothesis: hypothesis.trim() } : current
      );
    } catch (submissionError) {
      setError(submissionError instanceof Error ? submissionError.message : "Unable to save hypothesis");
    }
  }

  async function handleFinalSubmit() {
    const proposedActions = actionsText
      .split("\n")
      .map((value) => value.trim())
      .filter(Boolean);
    if (!rootCause.trim() || !summary.trim() || proposedActions.length === 0) {
      setError("Complete the final plan before submitting.");
      return;
    }
    setError(null);
    try {
      await submitSolution(sessionId, {
        root_cause: rootCause.trim(),
        proposed_actions: proposedActions,
        summary: summary.trim()
      });
      router.push(`/completion/${sessionId}`);
    } catch (submissionError) {
      setError(submissionError instanceof Error ? submissionError.message : "Unable to submit final plan");
    }
  }

  if (loadingPage) {
    return (
      <div className="flex min-h-screen items-center justify-center text-slate-300">
        Loading investigation workspace...
      </div>
    );
  }

  return (
    <div className="flex h-screen flex-col overflow-hidden bg-background-dark text-slate-100">
      <header className="flex shrink-0 items-center justify-between border-b border-slate-800 bg-background-dark px-6 py-3">
        <div className="flex items-center gap-4">
          <div className="text-primary">
            <span className="material-symbols-outlined text-3xl">query_stats</span>
          </div>
          <h2 className="text-lg font-bold tracking-tight">SimWork</h2>
        </div>
        <div className="flex items-center gap-6">
          <div className="hidden items-center gap-8 rounded-xl border border-slate-800 bg-slate-900/70 px-6 py-2 md:flex">
            <div className="flex flex-col">
              <span className="text-[10px] font-bold uppercase tracking-widest text-slate-500">Problem</span>
              <span className="text-sm font-bold text-red-400">Orders dropped 18%</span>
            </div>
            <div className="h-8 w-px bg-slate-700" />
            <div className="flex flex-col">
              <span className="text-[10px] font-bold uppercase tracking-widest text-slate-500">Objective</span>
              <span className="text-sm font-bold text-slate-100">Identify Root Cause</span>
            </div>
            <div className="h-8 w-px bg-slate-700" />
            <div className="flex min-w-[80px] flex-col">
              <span className="text-[10px] font-bold uppercase tracking-widest text-slate-500">Time Left</span>
              <span className="font-mono text-sm font-bold text-primary">
                {String(status?.time_remaining_minutes ?? 0).padStart(2, "0")}:00
              </span>
            </div>
          </div>
          <button
            onClick={() => setShowFinalPlan(true)}
            className="rounded-lg bg-primary px-4 py-2 text-sm font-bold text-white transition hover:bg-primary/90"
          >
            End Interview
          </button>
        </div>
      </header>

      <main className="flex flex-1 gap-4 overflow-hidden bg-background-dark/60 p-4">
        <aside className="flex w-full max-w-72 flex-col gap-4 overflow-y-auto">
          <div className="flex items-center gap-2 px-2">
            <span className="material-symbols-outlined text-primary text-xl">groups</span>
            <h3 className="text-sm font-bold uppercase tracking-wider text-slate-500">Team Panel</h3>
          </div>

          {(["analyst", "ux_researcher", "developer"] as AgentName[]).map((agent) => {
            const meta = agentMeta[agent];
            const selected = activeAgent === agent;
            return (
              <button
                key={agent}
                onClick={() => setActiveAgent(agent)}
                className={`rounded-xl border bg-slate-900/60 p-4 text-left transition-colors ${
                  selected ? "border-primary border-l-4" : "border-slate-800 hover:border-primary/40"
                }`}
              >
                <div className="flex items-center gap-3">
                  <div className={`flex size-10 items-center justify-center rounded-full ${meta.accent}`}>
                    <span className="material-symbols-outlined">{meta.icon}</span>
                  </div>
                  <div className="flex flex-col">
                    <h4 className="text-sm font-bold text-white">{meta.label}</h4>
                    <p className="text-[11px] text-slate-500">{meta.subtitle}</p>
                  </div>
                  {selected ? <div className="ml-auto size-2 animate-pulse rounded-full bg-green-500" /> : null}
                </div>
              </button>
            );
          })}

          <div className="mt-auto rounded-xl border border-primary/20 bg-primary/5 p-4">
            <p className="text-xs italic leading-relaxed text-slate-400">
              Ask one domain at a time. If you mix telemetry systems in the same question, the backend rejects it.
            </p>
          </div>
        </aside>

        <section className="flex flex-1 flex-col overflow-hidden rounded-xl border border-slate-800 bg-slate-900 shadow-sm">
          <div className="flex items-center justify-between border-b border-slate-800 bg-slate-800/20 px-4 py-3">
            <h3 className="flex items-center gap-2 text-sm font-bold">
              <span className="material-symbols-outlined text-primary">forum</span>
              Investigation Chat
            </h3>
            <span className="font-mono text-[10px] text-slate-500">SESSION ID: {sessionId}</span>
          </div>

          <div className="flex-1 overflow-y-auto p-6">
            <div className="mb-6 rounded-xl border border-slate-800 bg-slate-950/80 p-4">
              <p className="text-[10px] font-bold uppercase tracking-[0.24em] text-slate-500">Problem Statement</p>
              <p className="mt-3 text-sm leading-relaxed text-slate-300">
                {scenario?.problem_statement ?? "Loading problem statement..."}
              </p>
            </div>

            <div className="space-y-6">
              {conversation.map((item, index) => {
                const meta = agentMeta[item.agent];
                const isCandidate = item.kind === "candidate";
                return (
                  <div key={`${item.timestamp}-${index}`} className="flex gap-4">
                    <div
                      className={`flex size-8 shrink-0 items-center justify-center rounded-lg ${
                        isCandidate ? "bg-primary/20 text-primary" : meta.accent
                      }`}
                    >
                      <span className="material-symbols-outlined text-sm">
                        {isCandidate ? "person" : meta.icon}
                      </span>
                    </div>
                    <div className="flex max-w-[80%] flex-col gap-1">
                      <div className="flex items-center gap-2">
                        <span className="text-xs font-bold text-white">
                          {isCandidate ? "Candidate (You)" : meta.label}
                        </span>
                        <span className="text-[10px] text-slate-500">
                          {new Date(item.timestamp).toLocaleTimeString([], {
                            hour: "2-digit",
                            minute: "2-digit"
                          })}
                        </span>
                      </div>
                      <div
                        className={`rounded-xl px-4 py-3 text-sm ${
                          isCandidate
                            ? "rounded-tl-none bg-primary text-white"
                            : "rounded-tl-none bg-slate-800 text-slate-200"
                        }`}
                      >
                        {item.text}
                      </div>
                    </div>
                  </div>
                );
              })}

              {loadingQuery ? (
                <div className="flex items-center gap-4 animate-pulse">
                  <div className={`flex size-8 shrink-0 items-center justify-center rounded-lg ${agentMeta[activeAgent].accent}`}>
                    <span className="material-symbols-outlined text-sm">{agentMeta[activeAgent].icon}</span>
                  </div>
                  <div className="flex items-center gap-2">
                    <span className="text-xs font-medium text-slate-400">{agentMeta[activeAgent].label} is typing...</span>
                    <div className="flex gap-1">
                      <div className="size-1 rounded-full bg-slate-400" />
                      <div className="size-1 rounded-full bg-slate-400" />
                      <div className="size-1 rounded-full bg-slate-400" />
                    </div>
                  </div>
                </div>
              ) : null}
            </div>
          </div>

          <div className="border-t border-slate-800 bg-slate-800/30 p-4">
            <div className="mb-3 flex flex-wrap gap-2">
              {suggestions.map((suggestion) => (
                <button
                  key={suggestion}
                  onClick={() => setQuery(suggestion)}
                  className="rounded-full border border-slate-700 bg-slate-950 px-3 py-1 text-xs text-slate-300 transition hover:border-primary hover:text-white"
                >
                  {suggestion}
                </button>
              ))}
            </div>
            <form onSubmit={handleSendQuery} className="relative">
              <input
                value={query}
                onChange={(event) => setQuery(event.target.value)}
                placeholder={`Ask ${agentMeta[activeAgent].label} a question...`}
                className="w-full rounded-lg border border-slate-800 bg-slate-950 py-3 pl-4 pr-12 text-sm text-white outline-none transition focus:border-primary"
              />
              <button
                type="submit"
                disabled={loadingQuery}
                className="absolute right-2 top-2 flex size-8 items-center justify-center rounded-md bg-primary text-white disabled:opacity-50"
              >
                <span className="material-symbols-outlined text-sm">send</span>
              </button>
            </form>
            {error ? <p className="mt-3 text-sm text-red-400">{error}</p> : null}
          </div>
        </section>

        <section className="flex w-full max-w-sm flex-col gap-4 overflow-y-auto">
          <div className="flex items-center gap-2 px-2">
            <span className="material-symbols-outlined text-primary text-xl">monitoring</span>
            <h3 className="text-sm font-bold uppercase tracking-wider text-slate-500">Data Panel</h3>
          </div>

          <DataVisualization visualization={latestVisualization} />

          <div className="rounded-xl border border-slate-800 bg-slate-900/70 p-5">
            <div className="flex items-center justify-between">
              <h4 className="text-xs font-bold uppercase tracking-[0.24em] text-slate-400">Hypotheses</h4>
              <span className="text-[10px] font-mono text-slate-500">v{history.hypotheses.length}</span>
            </div>
            <div className="mt-4 space-y-3">
              {history.hypotheses.length ? (
                history.hypotheses.map((item) => (
                  <div key={item.hypothesis_version} className="rounded-lg border border-slate-800 bg-slate-950/70 p-4">
                    <p className="text-[10px] uppercase tracking-[0.22em] text-slate-500">Version {item.hypothesis_version}</p>
                    <p className="mt-2 text-sm text-slate-300">{item.hypothesis}</p>
                  </div>
                ))
              ) : (
                <p className="text-sm text-slate-400">No saved hypotheses yet.</p>
              )}
            </div>
          </div>

          <div className="rounded-xl border border-slate-800 bg-slate-900/70 p-5">
            <h4 className="text-xs font-bold uppercase tracking-[0.24em] text-slate-400">Session Status</h4>
            <div className="mt-4 space-y-3 text-sm text-slate-300">
              <div className="flex justify-between">
                <span className="text-slate-500">Queries made</span>
                <span>{status?.queries_made ?? 0}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-slate-500">Current agent</span>
                <span>{agentMeta[activeAgent].label}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-slate-500">Current hypothesis</span>
                <span className="max-w-[180px] text-right">{status?.current_hypothesis ?? "None"}</span>
              </div>
            </div>
          </div>
        </section>
      </main>

      <footer className="border-t border-slate-800 bg-background-dark p-4">
        <div className="mx-auto flex max-w-6xl flex-col gap-4 md:flex-row md:items-end">
          <div className="flex-1">
            <div className="mb-2 flex items-center gap-2 px-1">
              <span className="material-symbols-outlined text-sm text-primary">lightbulb</span>
              <h3 className="text-xs font-bold uppercase tracking-wider text-slate-500">Hypothesis Formation</h3>
            </div>
            <input
              value={hypothesis}
              onChange={(event) => setHypothesis(event.target.value)}
              placeholder="I believe the order drop is caused by [reason] because [evidence]..."
              className="w-full rounded-xl border border-slate-800 bg-slate-950 px-4 py-4 text-sm text-white outline-none transition focus:border-primary"
            />
          </div>
          <div className="flex gap-3">
            <button
              onClick={handleHypothesisSubmit}
              className="flex items-center gap-2 rounded-xl bg-primary px-8 py-4 font-bold text-white shadow-lg shadow-primary/20 transition hover:bg-primary/90"
            >
              <span>Submit Hypothesis</span>
              <span className="material-symbols-outlined">rocket_launch</span>
            </button>
            <button
              onClick={() => setShowFinalPlan(true)}
              className="flex items-center gap-2 rounded-xl border border-slate-700 px-6 py-4 font-bold text-slate-200 transition hover:border-primary hover:text-white"
            >
              <span>Final Plan</span>
              <span className="material-symbols-outlined">assignment</span>
            </button>
          </div>
        </div>
      </footer>

      {showFinalPlan ? (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-950/70 p-4 backdrop-blur-sm">
          <div className="w-full max-w-2xl rounded-2xl border border-slate-800 bg-slate-950 p-6 shadow-panel">
            <div className="flex items-start justify-between gap-4">
              <div>
                <p className="text-xs font-bold uppercase tracking-[0.24em] text-slate-500">Final Submission</p>
                <h3 className="mt-2 text-2xl font-bold text-white">Submit your conclusion</h3>
              </div>
              <button
                onClick={() => setShowFinalPlan(false)}
                className="rounded-lg border border-slate-800 p-2 text-slate-400 transition hover:text-white"
              >
                <span className="material-symbols-outlined">close</span>
              </button>
            </div>

            <div className="mt-6 space-y-4">
              <div>
                <label className="mb-2 block text-sm font-semibold text-slate-300">Root Cause</label>
                <input
                  value={rootCause}
                  onChange={(event) => setRootCause(event.target.value)}
                  className="w-full rounded-xl border border-slate-800 bg-slate-900 px-4 py-3 text-sm text-white outline-none transition focus:border-primary"
                  placeholder="Describe the most likely root cause"
                />
              </div>

              <div>
                <label className="mb-2 block text-sm font-semibold text-slate-300">Proposed Actions</label>
                <textarea
                  value={actionsText}
                  onChange={(event) => setActionsText(event.target.value)}
                  className="min-h-32 w-full rounded-xl border border-slate-800 bg-slate-900 px-4 py-3 text-sm text-white outline-none transition focus:border-primary"
                  placeholder="One action per line"
                />
              </div>

              <div>
                <label className="mb-2 block text-sm font-semibold text-slate-300">Summary</label>
                <textarea
                  value={summary}
                  onChange={(event) => setSummary(event.target.value)}
                  className="min-h-28 w-full rounded-xl border border-slate-800 bg-slate-900 px-4 py-3 text-sm text-white outline-none transition focus:border-primary"
                  placeholder="Summarize the evidence and plan"
                />
              </div>
            </div>

            <div className="mt-6 flex justify-end gap-3">
              <button
                onClick={() => setShowFinalPlan(false)}
                className="rounded-xl border border-slate-700 px-5 py-3 font-semibold text-slate-300 transition hover:text-white"
              >
                Continue investigating
              </button>
              <button
                onClick={handleFinalSubmit}
                className="rounded-xl bg-primary px-5 py-3 font-semibold text-white transition hover:bg-primary/90"
              >
                Submit Final Plan
              </button>
            </div>
          </div>
        </div>
      ) : null}
    </div>
  );
}
