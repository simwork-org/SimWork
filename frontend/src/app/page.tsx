"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import {
  listScenarios,
  getChallenges,
  startSession,
  type Scenario,
  type Challenge,
} from "@/lib/api";

const TYPE_BADGES: Record<string, { label: string; color: string }> = {
  diagnostic: { label: "Diagnostic", color: "bg-red-500/10 text-red-600 dark:text-red-400" },
  strategic: { label: "Strategic", color: "bg-amber-500/10 text-amber-600 dark:text-amber-400" },
};

const FALLBACK_ICON = "assignment";

export default function LandingPage() {
  const router = useRouter();
  const [scenarios, setScenarios] = useState<Scenario[]>([]);
  const [challengeMap, setChallengeMap] = useState<Record<string, string>>({});
  const [loadingId, setLoadingId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    listScenarios()
      .then(async (res) => {
        setScenarios(res.scenarios);
        const map: Record<string, string> = {};
        await Promise.all(
          res.scenarios.map(async (s) => {
            try {
              const ch = await getChallenges(s.id);
              if (ch.challenges.length > 0) {
                map[s.id] = ch.challenges[0].id;
              }
            } catch {
              // ignore per-scenario challenge fetch errors
            }
          })
        );
        setChallengeMap(map);
      })
      .catch(() => setError("Failed to load scenarios. Is the backend running?"));
  }, []);

  const handleStart = async (scenarioId: string) => {
    const challengeId = challengeMap[scenarioId];
    if (!challengeId) return;
    setLoadingId(scenarioId);
    try {
      const session = await startSession("candidate_default", scenarioId, challengeId);
      router.push(`/workspace/${session.session_id}`);
    } catch (err) {
      console.error(err);
      setLoadingId(null);
    }
  };

  return (
    <div className="relative flex min-h-screen flex-col overflow-x-hidden">
      <div className="layout-container flex h-full grow flex-col">
        {/* Header */}
        <header className="flex items-center justify-between border-b border-slate-200 dark:border-slate-800 px-6 md:px-20 py-4 bg-[#f6f6f8] dark:bg-[#101122] sticky top-0 z-50">
          <div className="flex items-center gap-3">
            <div className="flex items-center justify-center size-10 bg-[#10B981] rounded-lg text-white">
              <span className="material-symbols-outlined">strategy</span>
            </div>
            <div className="flex flex-col">
              <h1 className="text-slate-900 dark:text-white text-lg font-bold leading-tight tracking-tight">
                SimWork
              </h1>
              <span className="text-xs text-slate-500 dark:text-slate-400 font-medium">
                Professional Suite
              </span>
            </div>
          </div>
          <div className="flex flex-1 justify-end gap-6 items-center">
            <nav className="hidden md:flex items-center gap-8">
              <a className="text-slate-600 dark:text-slate-300 text-sm font-medium hover:text-[#10B981] transition-colors" href="#">Dashboard</a>
              <a className="text-slate-600 dark:text-slate-300 text-sm font-medium hover:text-[#10B981] transition-colors" href="#">Case Studies</a>
              <a className="text-slate-600 dark:text-slate-300 text-sm font-medium hover:text-[#10B981] transition-colors" href="#">Resources</a>
            </nav>
            <div className="h-6 w-px bg-slate-200 dark:bg-slate-800 mx-2 hidden md:block" />
            <button className="flex items-center justify-center rounded-lg h-10 px-5 bg-[#10B981] text-white text-sm font-bold hover:opacity-90 transition-opacity">
              Profile
            </button>
          </div>
        </header>

        {/* Main */}
        <main className="flex-1 max-w-5xl mx-auto w-full px-6 py-12">
          {/* Hero */}
          <div className="mb-10">
            <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-[#10B981]/10 text-[#10B981] text-xs font-bold uppercase tracking-wider mb-4">
              <span className="material-symbols-outlined text-sm">workspace_premium</span>
              Simulation Scenarios
            </div>
            <h2 className="text-slate-900 dark:text-white text-4xl md:text-5xl font-black leading-tight tracking-tight mb-2">
              Choose Your <span className="text-[#10B981]">Scenario</span>
            </h2>
            <p className="text-slate-500 dark:text-slate-400 text-lg max-w-2xl">
              Select a simulation to begin. Each scenario tests different product management skills using real-world data from ZaikaNow, an India-native food delivery marketplace.
            </p>
          </div>

          {/* Error State */}
          {error && (
            <div className="mb-8 p-4 rounded-xl border border-red-200 dark:border-red-800 bg-red-50 dark:bg-red-900/20 text-red-700 dark:text-red-300 text-sm">
              {error}
            </div>
          )}

          {/* Loading State */}
          {scenarios.length === 0 && !error && (
            <div className="flex items-center justify-center py-20">
              <div className="flex items-center gap-3 text-slate-400">
                <span className="material-symbols-outlined animate-spin">progress_activity</span>
                <span>Loading scenarios...</span>
              </div>
            </div>
          )}

          {/* Scenario Cards */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-8 mb-12">
            {scenarios.map((scenario) => {
              const icon = scenario.icon || FALLBACK_ICON;
              const badge = TYPE_BADGES[scenario.scenario_type || "diagnostic"] || TYPE_BADGES.diagnostic;
              const isLoading = loadingId === scenario.id;
              const isDisabled = loadingId !== null || !challengeMap[scenario.id];

              return (
                <div
                  key={scenario.id}
                  className="group flex flex-col overflow-hidden rounded-xl bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 shadow-sm hover:shadow-xl hover:border-[#10B981]/40 transition-all duration-200"
                >
                  {/* Icon Banner */}
                  <div className="h-36 bg-gradient-to-br from-slate-800 via-slate-900 to-slate-950 flex items-center justify-center relative overflow-hidden">
                    <div className="absolute inset-0 bg-[#10B981]/5 group-hover:bg-[#10B981]/10 transition-colors" />
                    <span className="material-symbols-outlined text-6xl text-[#10B981]/60 group-hover:text-[#10B981] transition-colors">
                      {icon}
                    </span>
                  </div>

                  {/* Card Body */}
                  <div className="flex flex-col flex-1 p-8">
                    {/* Badge */}
                    <div className="mb-4">
                      <span className={`inline-flex items-center gap-1 px-2.5 py-1 rounded-full text-xs font-bold uppercase tracking-wider ${badge.color}`}>
                        {badge.label}
                      </span>
                    </div>

                    <h3 className="text-slate-900 dark:text-white text-2xl font-bold mb-3 tracking-tight">
                      {scenario.title}
                    </h3>
                    <p className="text-slate-500 dark:text-slate-400 text-sm leading-relaxed flex-1 mb-6">
                      {scenario.description}
                    </p>

                    {/* Meta */}
                    <div className="flex items-center gap-4 mb-6 text-xs text-slate-400">
                      <span className="flex items-center gap-1">
                        <span className="material-symbols-outlined text-sm">timer</span>
                        30 min
                      </span>
                      <span className="flex items-center gap-1">
                        <span className="material-symbols-outlined text-sm">groups</span>
                        3 agents
                      </span>
                    </div>

                    <button
                      onClick={() => handleStart(scenario.id)}
                      disabled={isDisabled}
                      className="flex items-center justify-center gap-2 rounded-lg h-12 px-6 bg-[#10B981] text-white text-sm font-bold hover:scale-[1.02] transition-transform shadow-md shadow-[#10B981]/20 disabled:opacity-50 disabled:hover:scale-100"
                    >
                      <span>{isLoading ? "Starting..." : "Begin Scenario"}</span>
                      <span className="material-symbols-outlined text-lg">arrow_forward</span>
                    </button>
                  </div>
                </div>
              );
            })}
          </div>
        </main>

        <footer className="border-t border-slate-200 dark:border-slate-800 py-8 px-6 mt-auto">
          <div className="max-w-5xl mx-auto flex flex-col md:flex-row justify-between items-center gap-4 text-slate-500 dark:text-slate-400 text-sm">
            <p>&copy; 2025 SimWork Platform. All rights reserved.</p>
            <div className="flex gap-6">
              <a className="hover:text-[#10B981]" href="#">Privacy Policy</a>
              <a className="hover:text-[#10B981]" href="#">Terms of Service</a>
              <a className="hover:text-[#10B981]" href="#">Support</a>
            </div>
          </div>
        </footer>
      </div>
    </div>
  );
}
