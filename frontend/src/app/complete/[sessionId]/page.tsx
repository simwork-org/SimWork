"use client";

import { useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { submitSolution } from "@/lib/api";

export default function CompletionPage() {
  const params = useParams();
  const router = useRouter();
  const sessionId = params.sessionId as string;

  const [rootCause, setRootCause] = useState("");
  const [actions, setActions] = useState("");
  const [summary, setSummary] = useState("");
  const [submitted, setSubmitted] = useState(false);
  const [submitting, setSubmitting] = useState(false);

  const handleSubmit = async () => {
    if (!rootCause.trim() || !summary.trim()) return;
    setSubmitting(true);
    try {
      const actionList = actions.split("\n").map((a) => a.trim()).filter(Boolean);
      await submitSolution(sessionId, rootCause.trim(), actionList, summary.trim());
      setSubmitted(true);
    } catch (err) {
      console.error(err);
    } finally {
      setSubmitting(false);
    }
  };

  if (!submitted) {
    return (
      <div className="relative flex min-h-screen w-full flex-col overflow-x-hidden" style={{ fontFamily: "'Inter', sans-serif" }}>
        <div className="layout-container flex h-full grow flex-col">
          <header className="flex items-center justify-between border-b border-slate-200 dark:border-slate-800 px-6 py-4 lg:px-20">
            <div className="flex items-center gap-3">
              <div className="flex h-8 w-8 items-center justify-center rounded bg-[#10B981] text-white">
                <span className="material-symbols-outlined text-xl">cognition</span>
              </div>
              <h2 className="text-slate-900 dark:text-slate-100 text-lg font-bold tracking-tight">SimWork</h2>
            </div>
          </header>
          <main className="flex flex-1 items-center justify-center px-4 py-12">
            <div className="w-full max-w-2xl flex flex-col gap-8">
              <div className="text-center">
                <h1 className="text-3xl font-bold text-slate-900 dark:text-white tracking-tight mb-2">Submit Your Findings</h1>
                <p className="text-slate-600 dark:text-slate-400">Provide your root cause analysis and proposed recovery plan.</p>
              </div>
              <div className="bg-white dark:bg-slate-900/50 border border-slate-200 dark:border-slate-800 rounded-xl p-8 space-y-6">
                <div>
                  <label className="text-sm font-bold text-slate-700 dark:text-slate-300 mb-2 block">Root Cause</label>
                  <input
                    className="w-full bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-lg px-4 py-3 text-sm focus:ring-2 focus:ring-[#10B981] outline-none"
                    placeholder="e.g., Payment service latency increase"
                    value={rootCause}
                    onChange={(e) => setRootCause(e.target.value)}
                  />
                </div>
                <div>
                  <label className="text-sm font-bold text-slate-700 dark:text-slate-300 mb-2 block">Proposed Actions (one per line)</label>
                  <textarea
                    className="w-full bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-lg px-4 py-3 text-sm focus:ring-2 focus:ring-[#10B981] outline-none min-h-[100px]"
                    placeholder={"Reduce payment gateway latency\nAdd payment retry logic\nImprove payment UX feedback"}
                    value={actions}
                    onChange={(e) => setActions(e.target.value)}
                  />
                </div>
                <div>
                  <label className="text-sm font-bold text-slate-700 dark:text-slate-300 mb-2 block">Summary</label>
                  <textarea
                    className="w-full bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-lg px-4 py-3 text-sm focus:ring-2 focus:ring-[#10B981] outline-none min-h-[80px]"
                    placeholder="Brief summary of your analysis..."
                    value={summary}
                    onChange={(e) => setSummary(e.target.value)}
                  />
                </div>
                <button
                  onClick={handleSubmit}
                  disabled={submitting || !rootCause.trim() || !summary.trim()}
                  className="w-full bg-[#10B981] hover:bg-[#10B981]/90 text-white font-bold py-4 rounded-xl flex items-center justify-center gap-2 transition-all disabled:opacity-50"
                >
                  <span>{submitting ? "Submitting..." : "Submit Final Solution"}</span>
                  <span className="material-symbols-outlined">send</span>
                </button>
              </div>
            </div>
          </main>
        </div>
      </div>
    );
  }

  // Post-submission: completion screen
  return (
    <div className="relative flex min-h-screen w-full flex-col overflow-x-hidden" style={{ fontFamily: "'Inter', sans-serif" }}>
      <div className="layout-container flex h-full grow flex-col">
        <header className="flex items-center justify-between border-b border-slate-200 dark:border-slate-800 px-6 py-4 lg:px-20">
          <div className="flex items-center gap-3">
            <div className="flex h-8 w-8 items-center justify-center rounded bg-[#10B981] text-white">
              <span className="material-symbols-outlined text-xl">cognition</span>
            </div>
            <h2 className="text-slate-900 dark:text-slate-100 text-lg font-bold tracking-tight">SimWork</h2>
          </div>
          <button
            onClick={() => router.push("/")}
            className="flex items-center justify-center rounded-lg h-10 w-10 bg-slate-200 dark:bg-slate-800 text-slate-600 dark:text-slate-400 hover:bg-slate-300 dark:hover:bg-slate-700 transition-colors"
          >
            <span className="material-symbols-outlined">close</span>
          </button>
        </header>

        <main className="flex flex-1 items-center justify-center px-4 py-12">
          <div className="w-full max-w-2xl flex flex-col items-center">
            {/* Success Header */}
            <div className="flex flex-col items-center text-center gap-6 mb-12">
              <div className="relative">
                <div className="absolute inset-0 bg-[#10B981]/20 blur-3xl rounded-full" />
                <div className="relative flex h-24 w-24 items-center justify-center rounded-full bg-[#10B981]/10 border-4 border-[#10B981]/20">
                  <span className="material-symbols-outlined text-[#10B981] text-5xl font-bold">check_circle</span>
                </div>
              </div>
              <div className="flex flex-col gap-3">
                <h1 className="text-3xl font-bold text-slate-900 dark:text-white tracking-tight">
                  Simulation completed successfully
                </h1>
                <p className="text-slate-600 dark:text-slate-400 text-lg max-w-md mx-auto leading-relaxed">
                  Your responses have been recorded for evaluation. Thank you for participating in this simulation.
                </p>
              </div>
              <div className="flex gap-4">
                <button className="flex items-center justify-center rounded-lg h-11 px-6 bg-[#10B981] text-white font-semibold hover:opacity-90 transition-opacity">
                  View Feedback
                </button>
                <button className="flex items-center justify-center rounded-lg h-11 px-6 bg-slate-200 dark:bg-slate-800 text-slate-900 dark:text-slate-100 font-semibold hover:bg-slate-300 dark:hover:bg-slate-700 transition-colors">
                  Download Transcript
                </button>
              </div>
            </div>

            {/* Submission Summary */}
            <div className="w-full bg-white dark:bg-slate-900/50 border border-slate-200 dark:border-slate-800 rounded-xl p-8 shadow-sm">
              <h3 className="text-slate-900 dark:text-white text-lg font-bold mb-6 flex items-center gap-2">
                <span className="material-symbols-outlined text-[#10B981]">analytics</span>
                Submission Summary
              </h3>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-y-6 gap-x-12">
                <div className="flex items-center justify-between border-b border-slate-100 dark:border-slate-800 pb-3">
                  <div className="flex items-center gap-2">
                    <span className="material-symbols-outlined text-slate-400 text-sm">schedule</span>
                    <p className="text-slate-500 dark:text-slate-400 text-sm font-medium">Duration</p>
                  </div>
                  <p className="text-slate-900 dark:text-slate-100 text-sm font-bold">30 minutes</p>
                </div>
                <div className="flex items-center justify-between border-b border-slate-100 dark:border-slate-800 pb-3">
                  <div className="flex items-center gap-2">
                    <span className="material-symbols-outlined text-slate-400 text-sm">checklist</span>
                    <p className="text-slate-500 dark:text-slate-400 text-sm font-medium">Root Cause</p>
                  </div>
                  <p className="text-slate-900 dark:text-slate-100 text-sm font-bold">{rootCause}</p>
                </div>
                <div className="flex items-center justify-between border-b border-slate-100 dark:border-slate-800 pb-3">
                  <div className="flex items-center gap-2">
                    <span className="material-symbols-outlined text-slate-400 text-sm">cloud_done</span>
                    <p className="text-slate-500 dark:text-slate-400 text-sm font-medium">Status</p>
                  </div>
                  <span className="inline-flex items-center rounded-full bg-emerald-500/10 px-2.5 py-0.5 text-xs font-bold text-emerald-500">
                    Submitted
                  </span>
                </div>
                <div className="flex items-center justify-between border-b border-slate-100 dark:border-slate-800 pb-3">
                  <div className="flex items-center gap-2">
                    <span className="material-symbols-outlined text-slate-400 text-sm">event</span>
                    <p className="text-slate-500 dark:text-slate-400 text-sm font-medium">Date</p>
                  </div>
                  <p className="text-slate-900 dark:text-slate-100 text-sm font-bold">
                    {new Date().toLocaleDateString("en-US", { month: "short", day: "numeric", year: "numeric" })}
                  </p>
                </div>
              </div>
              <div className="mt-8">
                <div className="p-4 rounded-lg bg-slate-50 dark:bg-slate-800/50 border border-slate-100 dark:border-slate-700/50">
                  <div className="flex gap-3">
                    <span className="material-symbols-outlined text-[#10B981]">info</span>
                    <p className="text-sm text-slate-600 dark:text-slate-400 leading-relaxed">
                      Our AI evaluation engine is currently processing your analytical thinking and communication scores. You will receive a notification once your full report is ready.
                    </p>
                  </div>
                </div>
              </div>
            </div>

            <div className="mt-12 flex justify-center w-full">
              <button
                onClick={() => router.push("/")}
                className="flex items-center gap-2 text-slate-500 dark:text-slate-400 hover:text-[#10B981] dark:hover:text-[#10B981] transition-colors font-medium"
              >
                <span className="material-symbols-outlined">arrow_back</span>
                Back to Dashboard
              </button>
            </div>
          </div>
        </main>

        <footer className="px-6 py-6 border-t border-slate-200 dark:border-slate-800 flex justify-center">
          <p className="text-slate-400 dark:text-slate-600 text-xs">
            &copy; 2025 SimWork. All rights reserved. Professional Grade Simulations.
          </p>
        </footer>
      </div>
    </div>
  );
}
