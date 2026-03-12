"use client";

import { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import { listScenarios, startSession, type Scenario } from "@/lib/api";

export default function LandingPage() {
  const router = useRouter();
  const [scenarios, setScenarios] = useState<Scenario[]>([]);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    listScenarios()
      .then((data) => setScenarios(data.scenarios))
      .catch(console.error);
  }, []);

  const handleStart = async () => {
    setLoading(true);
    try {
      const session = await startSession("candidate_default", "checkout_conversion_drop");
      router.push(`/workspace/${session.session_id}`);
    } catch (err) {
      console.error(err);
      setLoading(false);
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
          <div className="mb-10">
            <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-[#10B981]/10 text-[#10B981] text-xs font-bold uppercase tracking-wider mb-4">
              <span className="material-symbols-outlined text-sm">trending_down</span>
              Critical Incident
            </div>
            <h2 className="text-slate-900 dark:text-white text-4xl md:text-5xl font-black leading-tight tracking-tight mb-2">
              Food Delivery: <span className="text-[#10B981]">The Retention Crisis</span>
            </h2>
            <p className="text-slate-500 dark:text-slate-400 text-lg">
              Simulation Module #124 &bull; Strategy &amp; Analytics Focus
            </p>
          </div>

          <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
            <div className="lg:col-span-2 space-y-6">
              <div className="overflow-hidden rounded-xl bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 shadow-xl">
                <div className="aspect-video w-full bg-slate-100 dark:bg-slate-800 relative group overflow-hidden">
                  <div className="absolute inset-0 bg-gradient-to-t from-slate-900/80 to-transparent flex items-end p-8 z-10">
                    <div className="flex items-center gap-4 text-white">
                      <span className="material-symbols-outlined text-4xl">monitoring</span>
                      <div>
                        <p className="text-xs font-bold uppercase opacity-70">Internal Metrics Dashboard</p>
                        <p className="font-medium">Active Orders: -18% MoM</p>
                      </div>
                    </div>
                  </div>
                  <div className="w-full h-full bg-gradient-to-br from-slate-700 via-slate-800 to-slate-900" />
                </div>
                <div className="p-8">
                  <h3 className="text-slate-900 dark:text-white text-2xl font-bold mb-4 flex items-center gap-3">
                    <span className="material-symbols-outlined text-[#10B981]">description</span>
                    The Scenario
                  </h3>
                  <p className="text-slate-600 dark:text-slate-300 text-lg leading-relaxed mb-8">
                    You are the Product Manager for a high-growth food delivery platform. Recently, your executive dashboard flagged a concerning trend:{" "}
                    <span className="text-slate-900 dark:text-white font-semibold">Weekly orders have dropped by 18%</span>{" "}
                    over the past month. Preliminary data shows competitors are maintaining steady volume. Your mission is to investigate the root cause, identify the leaking segments, and propose a data-backed recovery plan to the leadership team.
                  </p>
                  <div className="flex flex-wrap items-center gap-4">
                    <button
                      onClick={handleStart}
                      disabled={loading}
                      className="flex items-center justify-center gap-2 rounded-lg h-14 px-8 bg-[#10B981] text-white text-lg font-bold hover:scale-[1.02] transition-transform shadow-lg shadow-[#10B981]/25 disabled:opacity-50"
                    >
                      <span>{loading ? "Starting..." : "Start Investigation"}</span>
                      <span className="material-symbols-outlined">arrow_forward</span>
                    </button>
                    <button className="flex items-center justify-center gap-2 rounded-lg h-14 px-6 border border-slate-200 dark:border-slate-800 text-slate-600 dark:text-slate-300 font-bold hover:bg-slate-50 dark:hover:bg-slate-800 transition-colors">
                      <span className="material-symbols-outlined">bookmark</span>
                      <span>Save for later</span>
                    </button>
                  </div>
                </div>
              </div>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div className="p-6 rounded-xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900/50">
                  <span className="material-symbols-outlined text-[#10B981] mb-3">timer</span>
                  <p className="text-slate-500 dark:text-slate-400 text-sm font-medium">Estimated Duration</p>
                  <p className="text-slate-900 dark:text-white text-2xl font-bold tracking-tight">30 minutes</p>
                </div>
                <div className="p-6 rounded-xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900/50">
                  <span className="material-symbols-outlined text-[#10B981] mb-3">signal_cellular_alt</span>
                  <p className="text-slate-500 dark:text-slate-400 text-sm font-medium">Complexity Level</p>
                  <p className="text-slate-900 dark:text-white text-2xl font-bold tracking-tight">Intermediate</p>
                </div>
              </div>
            </div>

            <div className="lg:col-span-1 space-y-6">
              <div className="p-6 rounded-xl bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800">
                <h4 className="text-slate-900 dark:text-white font-bold mb-6 flex items-center gap-2">
                  <span className="material-symbols-outlined text-[#10B981] text-xl">target</span>
                  Key Objectives
                </h4>
                <ul className="space-y-4">
                  {["Hypothesis generation for traffic decline", "Data-driven funnel analysis", "Prioritization of high-impact fixes", "Stakeholder communication strategy"].map((obj) => (
                    <li key={obj} className="flex items-start gap-3">
                      <span className="material-symbols-outlined text-green-500 mt-0.5">check_circle</span>
                      <span className="text-slate-600 dark:text-slate-300 text-sm">{obj}</span>
                    </li>
                  ))}
                </ul>
              </div>
              <div className="p-6 rounded-xl bg-[#10B981]/10 border border-[#10B981]/20">
                <h4 className="text-[#10B981] font-bold mb-2">Sim Tip</h4>
                <p className="text-slate-600 dark:text-slate-400 text-xs leading-relaxed">
                  Pay close attention to the <span className="font-bold">user feedback logs</span> in the resource section. Often, quantitative drops are preceded by qualitative shifts in sentiment.
                </p>
              </div>
              <div className="p-1 rounded-xl bg-gradient-to-br from-[#10B981] via-[#10B981]/50 to-teal-500">
                <div className="bg-white dark:bg-slate-900 rounded-[calc(0.75rem-4px)] p-6">
                  <p className="text-slate-900 dark:text-white font-bold text-sm mb-1">Ready to prove your skills?</p>
                  <p className="text-slate-500 dark:text-slate-400 text-xs mb-4">Start now to appear on the weekly leaderboard.</p>
                  <div className="flex -space-x-2">
                    {[1, 2, 3].map((i) => (
                      <div key={i} className="size-8 rounded-full border-2 border-white dark:border-slate-900 bg-gradient-to-br from-[#10B981] to-teal-500" />
                    ))}
                    <div className="size-8 rounded-full border-2 border-white dark:border-slate-900 bg-slate-200 dark:bg-slate-800 flex items-center justify-center text-[10px] font-bold text-slate-500">+12</div>
                  </div>
                </div>
              </div>
            </div>
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
