"use client";

import { useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { useAuthToken } from "@/lib/useAuthToken";
import { getScenarioDetails, getSessionStatus, type ScenarioDetail, type SessionStatus } from "@/lib/api";

const AGENTS = [
  { label: "Data Analyst", desc: "SQL queries, metrics, trends, funnel analysis", icon: "database", color: "bg-sky-500/15 text-sky-400" },
  { label: "UX Researcher", desc: "User feedback, support tickets, usability studies", icon: "person_search", color: "bg-violet-500/15 text-violet-400" },
  { label: "Engineering Lead", desc: "Deployments, error patterns, service health", icon: "terminal", color: "bg-amber-500/15 text-amber-400" },
];

function getCookie(name: string): string {
  if (typeof document === "undefined") return "";
  const match = document.cookie.match(new RegExp(`(?:^|; )${name}=([^;]*)`));
  return match ? decodeURIComponent(match[1]) : "";
}

function clearCookie(name: string) {
  document.cookie = `${name}=;path=/;max-age=0`;
}

export default function BriefingPage() {
  const session = useAuthToken();
  const router = useRouter();
  const { sessionId } = useParams<{ sessionId: string }>();

  const [scenario, setScenario] = useState<ScenarioDetail | null>(null);
  const [status, setStatus] = useState<SessionStatus | null>(null);
  const [companyName, setCompanyName] = useState("");
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!session || !sessionId) return;

    const name = getCookie("simwork_company");
    if (name) {
      setCompanyName(name);
      clearCookie("simwork_company");
    }

    Promise.all([
      getScenarioDetails(sessionId),
      getSessionStatus(sessionId),
    ])
      .then(([scenarioData, statusData]) => {
        setScenario(scenarioData);
        setStatus(statusData);
      })
      .catch(() => {
        router.replace(`/workspace/${sessionId}`);
      })
      .finally(() => setLoading(false));
  }, [session, sessionId, router]);

  if (!session || loading) {
    return (
      <div className="min-h-screen flex items-center justify-center" style={{ backgroundColor: "#101122" }}>
        <div className="text-center">
          <div className="flex items-center justify-center size-14 bg-[#10B981] rounded-2xl text-white mx-auto mb-4 animate-pulse">
            <span className="material-symbols-outlined text-3xl">strategy</span>
          </div>
          <p className="text-slate-400 text-sm">Loading assessment details...</p>
        </div>
      </div>
    );
  }

  const brief = scenario?.reference_panel?.mission_brief;
  const timeMinutes = status?.time_remaining_minutes ?? 30;

  return (
    <div
      className="min-h-screen text-white"
      style={{
        backgroundColor: "#101122",
        backgroundImage: [
          "radial-gradient(rgba(255,255,255,0.07) 1px, transparent 1px)",
          "radial-gradient(circle at 25% 50%, rgba(16,185,129,0.15) 0%, transparent 50%)",
          "radial-gradient(circle at 80% 15%, rgba(99,102,241,0.12) 0%, transparent 40%)",
        ].join(", "),
        backgroundSize: "24px 24px, 100% 100%, 100% 100%",
      }}
    >
      {/* Header */}
      <nav className="flex items-center justify-center px-6 py-4 border-b border-slate-800 bg-[#101122]/80 backdrop-blur-xl">
        <div className="flex items-center gap-2.5">
          <div className="flex items-center justify-center size-9 bg-[#10B981] rounded-lg text-white">
            <span className="material-symbols-outlined text-xl">strategy</span>
          </div>
          <span className="text-lg font-bold tracking-tight">SimWork</span>
        </div>
      </nav>

      <div className="max-w-2xl mx-auto px-6 py-12">
        {/* Company badge */}
        {companyName && (
          <div className="flex items-center gap-2 mb-6">
            <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full bg-[#10B981]/10 text-[#10B981] text-xs font-bold border border-[#10B981]/20">
              <span className="material-symbols-outlined text-sm">business</span>
              {companyName} Assessment
            </span>
          </div>
        )}

        {/* Title */}
        <h1 className="text-3xl font-black mb-2">{scenario?.title || "Assessment"}</h1>
        <p className="text-sm text-slate-400 mb-10">Read the briefing carefully before you begin.</p>

        {/* Mission */}
        <section className="mb-8">
          <h2 className="text-xs font-bold uppercase tracking-widest text-[#10B981] mb-3">Your Mission</h2>
          <div className="rounded-xl border border-slate-800 bg-slate-900/40 p-6">
            <p className="text-sm text-slate-300 leading-relaxed">
              {brief?.problem || scenario?.problem_statement || "Investigate the issue and propose a recovery plan."}
            </p>
          </div>
        </section>

        {/* Objective */}
        {brief?.objective && (
          <section className="mb-8">
            <h2 className="text-xs font-bold uppercase tracking-widest text-[#10B981] mb-3">Objective</h2>
            <div className="rounded-xl border border-slate-800 bg-slate-900/40 p-6">
              <p className="text-sm text-slate-300 leading-relaxed">{brief.objective}</p>
            </div>
          </section>
        )}

        {/* What to Expect */}
        <section className="mb-8">
          <h2 className="text-xs font-bold uppercase tracking-widest text-[#10B981] mb-3">What to Expect</h2>
          <div className="rounded-xl border border-slate-800 bg-slate-900/40 p-6 space-y-4">
            {/* Time */}
            <div className="flex items-start gap-3">
              <div className="flex items-center justify-center size-9 rounded-lg bg-[#10B981]/10 shrink-0">
                <span className="material-symbols-outlined text-lg text-[#10B981]">timer</span>
              </div>
              <div>
                <p className="text-sm font-bold text-white">{timeMinutes} Minute Time Limit</p>
                <p className="text-xs text-slate-400">The timer starts when you click &quot;Begin Assessment&quot; below.</p>
              </div>
            </div>

            {/* Agents */}
            <div className="flex items-start gap-3">
              <div className="flex items-center justify-center size-9 rounded-lg bg-[#10B981]/10 shrink-0">
                <span className="material-symbols-outlined text-lg text-[#10B981]">groups</span>
              </div>
              <div>
                <p className="text-sm font-bold text-white mb-2">3 AI Teammates</p>
                <div className="space-y-2">
                  {AGENTS.map((agent) => (
                    <div key={agent.label} className="flex items-center gap-2">
                      <div className={`flex items-center justify-center size-7 rounded-md ${agent.color}`}>
                        <span className="material-symbols-outlined text-sm">{agent.icon}</span>
                      </div>
                      <span className="text-xs text-slate-300">
                        <span className="font-medium text-white">{agent.label}</span> — {agent.desc}
                      </span>
                    </div>
                  ))}
                </div>
              </div>
            </div>

            {/* Deliverable */}
            <div className="flex items-start gap-3">
              <div className="flex items-center justify-center size-9 rounded-lg bg-[#10B981]/10 shrink-0">
                <span className="material-symbols-outlined text-lg text-[#10B981]">assignment_turned_in</span>
              </div>
              <div>
                <p className="text-sm font-bold text-white">Your Deliverable</p>
                <p className="text-xs text-slate-400">Query agents, save evidence, then submit a root cause analysis with a prioritized recovery plan.</p>
              </div>
            </div>
          </div>
        </section>

        {/* Notes */}
        {brief?.notes && brief.notes.length > 0 && (
          <section className="mb-10">
            <h2 className="text-xs font-bold uppercase tracking-widest text-[#10B981] mb-3">Important Notes</h2>
            <div className="rounded-xl border border-slate-800 bg-slate-900/40 p-6">
              <ul className="space-y-2">
                {brief.notes.map((note, i) => (
                  <li key={i} className="flex items-start gap-2 text-sm text-slate-300">
                    <span className="mt-1.5 size-1.5 rounded-full bg-[#10B981] shrink-0" />
                    <span>{note}</span>
                  </li>
                ))}
              </ul>
            </div>
          </section>
        )}

        {/* CTA */}
        <button
          onClick={() => router.push(`/workspace/${sessionId}`)}
          className="w-full rounded-xl px-8 py-4 bg-[#10B981] text-base font-bold shadow-lg shadow-[#10B981]/25 hover:shadow-[#10B981]/40 transition-shadow"
        >
          Begin Assessment
        </button>
        <p className="text-xs text-slate-500 text-center mt-3">
          The timer will start once you enter the workspace.
        </p>
      </div>
    </div>
  );
}
