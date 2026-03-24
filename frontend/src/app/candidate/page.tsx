"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import { signOut } from "next-auth/react";
import { getMe, getMySessions, type UserSessionSummary } from "@/lib/api";
import { useAuthToken } from "@/lib/useAuthToken";

function extractInviteToken(value: string): string | null {
  const trimmed = value.trim();
  if (!trimmed) return null;

  try {
    const url = new URL(trimmed);
    const inviteIndex = url.pathname.split("/").filter(Boolean).indexOf("invite");
    if (inviteIndex >= 0) {
      return url.pathname.split("/").filter(Boolean)[inviteIndex + 1] ?? null;
    }
  } catch {
    // Treat as token below.
  }

  const normalized = trimmed.replace(/^\/+|\/+$/g, "");
  if (normalized.startsWith("invite/")) {
    return normalized.slice("invite/".length) || null;
  }

  return normalized || null;
}

function sessionLabel(session: UserSessionSummary): string {
  return session.assessment_title || session.scenario_id.replace(/_/g, " ");
}

export default function CandidateHomePage() {
  const authSession = useAuthToken();
  const router = useRouter();
  const [loading, setLoading] = useState(true);
  const [sessions, setSessions] = useState<UserSessionSummary[]>([]);
  const [inviteInput, setInviteInput] = useState("");
  const [inviteError, setInviteError] = useState("");
  const [notice, setNotice] = useState("");

  const assignedSessions = useMemo(
    () => sessions.filter((item) => item.assessment_id || item.invite_token),
    [sessions]
  );

  useEffect(() => {
    setNotice(new URLSearchParams(window.location.search).get("notice") || "");
  }, []);

  useEffect(() => {
    if (!authSession) return;

    let cancelled = false;

    async function load() {
      try {
        const me = await getMe();
        if (cancelled) return;

        if (me.role === "company") {
          router.replace("/dashboard?notice=candidate-access-company");
          return;
        }

        const { sessions: mySessions } = await getMySessions();
        if (cancelled) return;
        setSessions(mySessions);
      } catch {
        if (!cancelled) router.replace("/login");
      } finally {
        if (!cancelled) setLoading(false);
      }
    }

    load();

    return () => {
      cancelled = true;
    };
  }, [authSession, router]);

  const handleInviteSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    const token = extractInviteToken(inviteInput);
    if (!token) {
      setInviteError("Paste the invite URL or token your company sent you.");
      return;
    }
    setInviteError("");
    router.push(`/invite/${token}`);
  };

  if (!authSession) return null;

  return (
    <div className="min-h-screen text-white" style={{ backgroundColor: "#101122" }}>
      <nav className="sticky top-0 z-50 flex items-center justify-between px-6 md:px-12 py-4 bg-[#101122]/80 backdrop-blur-xl border-b border-slate-800">
        <div className="flex items-center gap-2.5">
          <div className="flex items-center justify-center size-9 bg-[#10B981] rounded-lg text-white">
            <span className="material-symbols-outlined text-xl">strategy</span>
          </div>
          <span className="text-lg font-bold tracking-tight">SimWork</span>
        </div>
        <button
          onClick={() => signOut({ callbackUrl: "/" })}
          className="text-sm text-slate-400 hover:text-white transition-colors"
        >
          Sign Out
        </button>
      </nav>

      <main className="max-w-5xl mx-auto px-6 py-12">
        {notice === "invite-required" && (
          <div className="mb-8 rounded-xl border border-amber-500/30 bg-amber-500/10 px-4 py-3 text-sm text-amber-200">
            Use the invite link your company sent you to begin a new assessment, or continue an existing one listed below.
          </div>
        )}
        <div className="mb-10 max-w-3xl">
          <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-[#10B981]/10 text-[#10B981] text-xs font-bold uppercase tracking-wider mb-4">
            <span className="material-symbols-outlined text-sm">pending_actions</span>
            Candidate Workspace
          </div>
          <h1 className="text-4xl font-black tracking-tight mb-3">Your assessments</h1>
          <p className="text-slate-400 text-lg leading-relaxed">
            Continue any assigned simulation, or enter a new invite link from your hiring team.
          </p>
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-[1.2fr_0.8fr] gap-8 items-start">
          <section className="rounded-2xl border border-slate-800 bg-slate-900/30 p-6">
            <div className="flex items-center justify-between mb-5">
              <h2 className="text-xl font-bold">Assigned assessments</h2>
              <span className="text-xs font-medium uppercase tracking-wider text-slate-500">
                {assignedSessions.length} active
              </span>
            </div>

            {loading ? (
              <p className="text-sm text-slate-400 animate-pulse">Loading your assignments...</p>
            ) : assignedSessions.length === 0 ? (
              <div className="rounded-xl border border-dashed border-slate-700 bg-slate-950/20 p-6">
                <p className="text-sm text-slate-300 mb-2">No assignments are visible yet.</p>
                <p className="text-sm text-slate-500 leading-relaxed">
                  Use the invite link your company sent you. Once claimed, the assessment will appear here automatically.
                </p>
              </div>
            ) : (
              <div className="space-y-4">
                {assignedSessions.map((session) => (
                  <div
                    key={session.session_id}
                    className="rounded-xl border border-slate-800 bg-[#101122] p-5"
                  >
                    <div className="flex flex-col gap-4 md:flex-row md:items-start md:justify-between">
                      <div>
                        <p className="text-xs font-bold uppercase tracking-wider text-[#10B981] mb-2">
                          {session.company_name || "SimWork Assessment"}
                        </p>
                        <h3 className="text-lg font-bold text-white">{sessionLabel(session)}</h3>
                        <p className="text-sm text-slate-400 mt-2">
                          Status: <span className="text-slate-200">{session.status.replace(/_/g, " ")}</span>
                        </p>
                        <p className="text-xs text-slate-500 mt-1">
                          Started {new Date(session.started_at).toLocaleString()}
                        </p>
                      </div>
                      <Link
                        href={`/briefing/${session.session_id}`}
                        className="inline-flex items-center justify-center rounded-lg px-4 py-2.5 bg-[#10B981] text-sm font-bold text-white hover:bg-emerald-600 transition-colors"
                      >
                        Continue
                      </Link>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </section>

          <section className="rounded-2xl border border-slate-800 bg-slate-900/30 p-6">
            <h2 className="text-xl font-bold mb-2">Enter an invite link</h2>
            <p className="text-sm text-slate-400 leading-relaxed mb-5">
              Paste the full assessment link or only the invite token from your company.
            </p>

            <form onSubmit={handleInviteSubmit} className="space-y-4">
              <textarea
                value={inviteInput}
                onChange={(e) => setInviteInput(e.target.value)}
                rows={4}
                placeholder="https://simwork.ai/invite/abc123 or abc123"
                className="w-full rounded-lg px-4 py-3 bg-slate-800/50 border border-slate-700 text-white text-sm placeholder:text-slate-500 focus:outline-none focus:border-[#10B981] transition-colors resize-none"
              />
              {inviteError && <p className="text-sm text-red-400">{inviteError}</p>}
              <button
                type="submit"
                className="w-full rounded-xl px-6 py-3 bg-[#10B981] text-sm font-bold text-white hover:bg-emerald-600 transition-colors"
              >
                Open Invite
              </button>
            </form>

          </section>
        </div>
      </main>
    </div>
  );
}
