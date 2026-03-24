"use client";

import Image from "next/image";
import { useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import Link from "next/link";
import {
  Assessment,
  AssessmentCandidate,
  InviteInfo,
  getAssessmentDetail,
  generateInvite,
  getMe,
  getMySessions,
} from "@/lib/api";
import { useAuthToken } from "@/lib/useAuthToken";
import { findAssignedSession } from "@/lib/auth-routing";

export default function AssessmentDetailPage() {
  const session = useAuthToken();
  const router = useRouter();
  const { id } = useParams<{ id: string }>();

  const [assessment, setAssessment] = useState<Assessment | null>(null);
  const [candidates, setCandidates] = useState<AssessmentCandidate[]>([]);
  const [invites, setInvites] = useState<InviteInfo[]>([]);
  const [loading, setLoading] = useState(true);
  const [copiedLink, setCopiedLink] = useState("");
  const [candidateEmail, setCandidateEmail] = useState("");

  useEffect(() => {
    if (!session || !id) return;

    async function load() {
      try {
        const me = await getMe();
        if (me.role !== "company") {
          const { sessions } = await getMySessions();
          const assignedSession = findAssignedSession(sessions);
          router.replace(assignedSession ? `/briefing/${assignedSession.session_id}` : "/candidate");
          return;
        }
        const data = await getAssessmentDetail(id);
        setAssessment(data.assessment);
        setCandidates(data.candidates);
        setInvites(data.invites);
      } catch {
        router.replace("/dashboard");
      } finally {
        setLoading(false);
      }
    }

    load();
  }, [session, id, router]);

  const handleGenerateInvite = async (email?: string) => {
    const { invite_url } = await generateInvite(id, email);
    const fullUrl = `${window.location.origin}${invite_url}`;
    await navigator.clipboard.writeText(fullUrl);
    setCopiedLink(fullUrl);
    if (email) setCandidateEmail("");
    // Refresh invites
    const data = await getAssessmentDetail(id);
    setInvites(data.invites);
    setTimeout(() => setCopiedLink(""), 3000);
  };

  if (!session || loading) {
    return (
      <div className="min-h-screen flex items-center justify-center" style={{ backgroundColor: "#101122" }}>
        <p className="text-slate-400 text-sm animate-pulse">Loading...</p>
      </div>
    );
  }

  if (!assessment) return null;

  return (
    <div className="min-h-screen text-white" style={{ backgroundColor: "#101122" }}>
      <nav className="sticky top-0 z-50 flex items-center justify-between px-6 md:px-12 py-4 bg-[#101122]/80 backdrop-blur-xl border-b border-slate-800">
        <div className="flex items-center gap-2.5">
          <div className="flex items-center justify-center size-9 bg-[#10B981] rounded-lg text-white">
            <span className="material-symbols-outlined text-xl">strategy</span>
          </div>
          <span className="text-lg font-bold tracking-tight">SimWork</span>
        </div>
        <Link href="/dashboard" className="text-sm text-slate-400 hover:text-white transition-colors flex items-center gap-1">
          <span className="material-symbols-outlined text-base">arrow_back</span>
          Back to Dashboard
        </Link>
      </nav>

      <div className="max-w-5xl mx-auto px-6 py-10">
        {/* Assessment Header */}
        <div className="mb-10">
          <h1 className="text-2xl font-bold mb-1">{assessment.title || assessment.scenario_id}</h1>
          <p className="text-sm text-slate-400">
            Scenario: {assessment.scenario_id}
            {assessment.challenge_id && ` / Challenge: ${assessment.challenge_id}`}
          </p>
          <p className="text-xs text-slate-500 mt-1">
            Created {new Date(assessment.created_at).toLocaleDateString()}
          </p>
        </div>

        {/* Invite Links Section */}
        <div className="mb-10">
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-lg font-bold">Invite Links</h2>
            <button
              onClick={() => handleGenerateInvite()}
              className="flex items-center gap-1.5 rounded-lg px-4 py-2 text-sm font-medium bg-[#10B981] hover:bg-emerald-600 transition-colors"
            >
              <span className="material-symbols-outlined text-base">add_link</span>
              Generate New Link
            </button>
          </div>

          <div className="rounded-xl border border-slate-800 bg-slate-900/20 p-4 mb-4">
            <p className="text-xs font-bold uppercase tracking-wider text-slate-500 mb-3">
              Optional email restriction
            </p>
            <div className="flex flex-col gap-3 md:flex-row">
              <input
                type="email"
                value={candidateEmail}
                onChange={(e) => setCandidateEmail(e.target.value)}
                placeholder="candidate@company.com"
                className="flex-1 rounded-lg px-4 py-2.5 bg-slate-800/50 border border-slate-700 text-white text-sm placeholder:text-slate-500 focus:outline-none focus:border-[#10B981] transition-colors"
              />
              <button
                onClick={() => handleGenerateInvite(candidateEmail.trim() || undefined)}
                className="rounded-lg px-4 py-2.5 text-sm font-medium border border-slate-700 text-slate-300 hover:border-[#10B981]/50 hover:text-white transition-colors"
              >
                Copy Restricted Invite
              </button>
            </div>
            <p className="text-xs text-slate-500 mt-2">
              Restricted invites can only be claimed by the candidate with that exact email address.
            </p>
          </div>

          {copiedLink && (
            <div className="rounded-lg bg-[#10B981]/10 border border-[#10B981]/20 px-4 py-3 mb-4 flex items-center gap-2">
              <span className="material-symbols-outlined text-[#10B981] text-base">check_circle</span>
              <span className="text-sm text-[#10B981]">Link copied to clipboard!</span>
            </div>
          )}

          {invites.length === 0 ? (
            <p className="text-sm text-slate-400">No invite links generated yet.</p>
          ) : (
            <div className="space-y-2">
              {invites.map((inv) => (
                <div
                  key={inv.token}
                  className="flex items-center justify-between rounded-lg border border-slate-800 bg-slate-900/30 px-4 py-3"
                >
                  <div className="flex items-center gap-3">
                    <span className="material-symbols-outlined text-base text-slate-500">link</span>
                    <code className="text-xs text-slate-400 font-mono">/invite/{inv.token}</code>
                    {inv.candidate_email && (
                      <span className="text-xs px-2 py-0.5 rounded bg-slate-800 text-slate-300">
                        {inv.candidate_email}
                      </span>
                    )}
                    {inv.used_at ? (
                      <span className="text-xs px-2 py-0.5 rounded bg-slate-800 text-slate-400">
                        Claimed by {inv.claimed_by_name || inv.claimed_by_email}
                      </span>
                    ) : (
                      <span className="text-xs px-2 py-0.5 rounded bg-[#10B981]/10 text-[#10B981]">
                        Available
                      </span>
                    )}
                  </div>
                  <span className="text-xs text-slate-500">
                    {new Date(inv.created_at).toLocaleDateString()}
                  </span>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Candidates Section */}
        <div>
          <h2 className="text-lg font-bold mb-4">Candidates</h2>
          {candidates.length === 0 ? (
            <div className="text-center py-12 rounded-xl border border-slate-800 bg-slate-900/30">
              <span className="material-symbols-outlined text-3xl text-slate-500 mb-2">group</span>
              <p className="text-sm text-slate-400">No candidates have taken this assessment yet.</p>
              <p className="text-xs text-slate-500 mt-1">Generate an invite link and share it to get started.</p>
            </div>
          ) : (
            <div className="rounded-xl border border-slate-800 overflow-hidden">
              <table className="w-full text-sm">
                <thead>
                  <tr className="bg-slate-900/50 border-b border-slate-800">
                    <th className="text-left px-4 py-3 font-medium text-slate-400">Candidate</th>
                    <th className="text-left px-4 py-3 font-medium text-slate-400">Status</th>
                    <th className="text-left px-4 py-3 font-medium text-slate-400">Score</th>
                    <th className="text-left px-4 py-3 font-medium text-slate-400">Date</th>
                    <th className="text-right px-4 py-3 font-medium text-slate-400">Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {candidates.map((c) => (
                    <tr key={c.session_id} className="border-b border-slate-800/50 hover:bg-slate-900/30">
                      <td className="px-4 py-3">
                        <div className="flex items-center gap-2">
                          {c.picture && (
                            <Image
                              src={c.picture}
                              alt=""
                              className="size-7 rounded-full"
                              width={28}
                              height={28}
                              unoptimized
                            />
                          )}
                          <div>
                            <p className="text-white font-medium">{c.name || "Unknown"}</p>
                            <p className="text-xs text-slate-500">{c.email}</p>
                          </div>
                        </div>
                      </td>
                      <td className="px-4 py-3">
                        <span
                          className={`text-xs px-2 py-0.5 rounded ${
                            c.status === "completed"
                              ? "bg-[#10B981]/10 text-[#10B981]"
                              : "bg-amber-500/10 text-amber-400"
                          }`}
                        >
                          {c.status}
                        </span>
                      </td>
                      <td className="px-4 py-3">
                        {c.overall_score != null ? (
                          <span className="font-bold">{Math.round(c.overall_score)}/100</span>
                        ) : (
                          <span className="text-slate-500">—</span>
                        )}
                      </td>
                      <td className="px-4 py-3 text-slate-400">
                        {new Date(c.started_at).toLocaleDateString()}
                      </td>
                      <td className="px-4 py-3 text-right">
                        {c.status === "completed" && (
                          <Link
                            href={`/review/${c.session_id}`}
                            className="text-[#10B981] text-xs font-medium hover:underline"
                          >
                            View Score
                          </Link>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
