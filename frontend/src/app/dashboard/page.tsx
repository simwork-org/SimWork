"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import {
  Assessment,
  Scenario,
  Challenge,
  getMe,
  getMyCompany,
  createCompany,
  listAssessments,
  listScenarios,
  getChallenges,
  createAssessment,
  generateInvite,
} from "@/lib/api";
import { useAuthToken } from "@/lib/useAuthToken";

export default function DashboardPage() {
  const session = useAuthToken();
  const router = useRouter();

  const [companyName, setCompanyName] = useState("");
  const [needsCompany, setNeedsCompany] = useState(false);
  const [companyInput, setCompanyInput] = useState("");

  const [assessments, setAssessments] = useState<Assessment[]>([]);
  const [loading, setLoading] = useState(true);

  // New assessment modal
  const [showCreate, setShowCreate] = useState(false);
  const [scenarios, setScenarios] = useState<Scenario[]>([]);
  const [challenges, setChallenges] = useState<Challenge[]>([]);
  const [selectedScenario, setSelectedScenario] = useState("");
  const [selectedChallenge, setSelectedChallenge] = useState("");
  const [assessmentTitle, setAssessmentTitle] = useState("");
  const [creating, setCreating] = useState(false);

  // Quick invite copy
  const [copiedToken, setCopiedToken] = useState("");

  useEffect(() => {
    if (!session) return;

    async function init() {
      try {
        const me = await getMe();
        if (me.role !== "company") {
          router.replace("/");
          return;
        }

        try {
          const company = await getMyCompany();
          setCompanyName(company.name);
        } catch {
          setNeedsCompany(true);
          setLoading(false);
          return;
        }

        const { assessments: list } = await listAssessments();
        setAssessments(list);
      } catch {
        router.replace("/login");
      } finally {
        setLoading(false);
      }
    }

    init();
  }, [session, router]);

  const handleCreateCompany = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!companyInput.trim()) return;
    await createCompany(companyInput.trim());
    setCompanyName(companyInput.trim());
    setNeedsCompany(false);
    setLoading(true);
    const { assessments: list } = await listAssessments();
    setAssessments(list);
    setLoading(false);
  };

  const openCreateModal = async () => {
    setShowCreate(true);
    const { scenarios: list } = await listScenarios();
    setScenarios(list);
  };

  const handleScenarioChange = async (scenarioId: string) => {
    setSelectedScenario(scenarioId);
    setSelectedChallenge("");
    if (scenarioId) {
      const { challenges: list } = await getChallenges(scenarioId);
      setChallenges(list);
    } else {
      setChallenges([]);
    }
  };

  const handleCreateAssessment = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedScenario) return;
    setCreating(true);
    await createAssessment(
      selectedScenario,
      selectedChallenge || null,
      assessmentTitle || null,
    );
    setShowCreate(false);
    setSelectedScenario("");
    setSelectedChallenge("");
    setAssessmentTitle("");
    setCreating(false);
    const { assessments: list } = await listAssessments();
    setAssessments(list);
  };

  const handleQuickInvite = async (assessmentId: string) => {
    const { invite_url } = await generateInvite(assessmentId);
    const fullUrl = `${window.location.origin}${invite_url}`;
    await navigator.clipboard.writeText(fullUrl);
    setCopiedToken(assessmentId);
    setTimeout(() => setCopiedToken(""), 2000);
  };

  if (!session) return null;

  if (needsCompany) {
    return (
      <div className="min-h-screen flex items-center justify-center" style={{ backgroundColor: "#101122" }}>
        <div className="w-full max-w-md rounded-2xl border border-slate-800 bg-slate-900/60 p-10 text-center">
          <div className="flex items-center justify-center size-14 bg-[#10B981] rounded-2xl text-white mx-auto mb-6">
            <span className="material-symbols-outlined text-3xl">business</span>
          </div>
          <h2 className="text-2xl font-bold text-white mb-2">Set Up Your Company</h2>
          <p className="text-sm text-slate-400 mb-6">Enter your company name to get started.</p>
          <form onSubmit={handleCreateCompany} className="space-y-4">
            <input
              type="text"
              required
              value={companyInput}
              onChange={(e) => setCompanyInput(e.target.value)}
              placeholder="Company name"
              className="w-full rounded-lg px-4 py-3 bg-slate-800/50 border border-slate-700 text-white text-sm placeholder:text-slate-500 focus:outline-none focus:border-[#10B981] transition-colors"
            />
            <button
              type="submit"
              className="w-full rounded-xl px-8 py-4 bg-[#10B981] text-base font-bold text-white shadow-lg shadow-[#10B981]/25 hover:shadow-[#10B981]/40 transition-shadow"
            >
              Continue
            </button>
          </form>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen text-white" style={{ backgroundColor: "#101122" }}>
      {/* Header */}
      <nav className="sticky top-0 z-50 flex items-center justify-between px-6 md:px-12 py-4 bg-[#101122]/80 backdrop-blur-xl border-b border-slate-800">
        <div className="flex items-center gap-2.5">
          <div className="flex items-center justify-center size-9 bg-[#10B981] rounded-lg text-white">
            <span className="material-symbols-outlined text-xl">strategy</span>
          </div>
          <span className="text-lg font-bold tracking-tight">SimWork</span>
          {companyName && (
            <span className="text-sm text-slate-400 ml-2">/ {companyName}</span>
          )}
        </div>
        <Link href="/login" className="text-sm text-slate-400 hover:text-white transition-colors">
          Sign Out
        </Link>
      </nav>

      <div className="max-w-5xl mx-auto px-6 py-10">
        <div className="flex items-center justify-between mb-8">
          <h1 className="text-2xl font-bold">Your Assessments</h1>
          <button
            onClick={openCreateModal}
            className="flex items-center gap-2 rounded-lg px-5 py-2.5 bg-[#10B981] text-sm font-bold hover:bg-emerald-600 transition-colors"
          >
            <span className="material-symbols-outlined text-lg">add</span>
            New Assessment
          </button>
        </div>

        {loading ? (
          <p className="text-slate-400 text-sm animate-pulse">Loading...</p>
        ) : assessments.length === 0 ? (
          <div className="text-center py-20">
            <div className="flex items-center justify-center size-16 rounded-2xl bg-slate-800 mx-auto mb-4">
              <span className="material-symbols-outlined text-3xl text-slate-500">assignment</span>
            </div>
            <h3 className="text-lg font-bold text-white mb-2">No assessments yet</h3>
            <p className="text-sm text-slate-400 mb-6">Create your first assessment to start evaluating candidates.</p>
            <button
              onClick={openCreateModal}
              className="rounded-lg px-5 py-2.5 bg-[#10B981] text-sm font-bold hover:bg-emerald-600 transition-colors"
            >
              Create Assessment
            </button>
          </div>
        ) : (
          <div className="space-y-4">
            {assessments.map((a) => (
              <div
                key={a.id}
                className="rounded-xl border border-slate-800 bg-slate-900/30 p-6 hover:border-[#10B981]/30 transition-colors"
              >
                <div className="flex items-start justify-between">
                  <div>
                    <h3 className="text-base font-bold text-white mb-1">
                      {a.title || a.scenario_id}
                    </h3>
                    <p className="text-sm text-slate-400">
                      Scenario: {a.scenario_id}
                      {a.challenge_id && ` / ${a.challenge_id}`}
                    </p>
                    <p className="text-xs text-slate-500 mt-1">
                      Created {new Date(a.created_at).toLocaleDateString()}
                    </p>
                  </div>
                  <div className="flex items-center gap-3 text-sm">
                    <span className="text-slate-400">
                      {a.candidate_completed} completed, {a.candidate_active} active
                    </span>
                  </div>
                </div>
                <div className="flex items-center gap-3 mt-4">
                  <Link
                    href={`/dashboard/assessment/${a.id}`}
                    className="rounded-lg px-4 py-2 text-sm font-medium border border-slate-700 text-slate-300 hover:border-[#10B981]/50 hover:text-white transition-colors"
                  >
                    View Results
                  </Link>
                  <button
                    onClick={() => handleQuickInvite(a.id)}
                    className="flex items-center gap-1.5 rounded-lg px-4 py-2 text-sm font-medium bg-[#10B981]/10 text-[#10B981] hover:bg-[#10B981]/20 transition-colors"
                  >
                    <span className="material-symbols-outlined text-base">
                      {copiedToken === a.id ? "check" : "link"}
                    </span>
                    {copiedToken === a.id ? "Copied!" : "Copy Invite Link"}
                  </button>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Create Assessment Modal */}
      {showCreate && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm px-6">
          <div className="w-full max-w-lg rounded-2xl border border-slate-800 bg-[#101122] p-8">
            <div className="flex items-center justify-between mb-6">
              <h2 className="text-xl font-bold">New Assessment</h2>
              <button
                onClick={() => setShowCreate(false)}
                className="flex items-center justify-center size-8 rounded-full bg-slate-800 text-slate-400 hover:text-white hover:bg-slate-700 transition-colors"
              >
                <span className="material-symbols-outlined text-lg">close</span>
              </button>
            </div>
            <form onSubmit={handleCreateAssessment} className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-slate-300 mb-1.5">
                  Assessment Title <span className="text-slate-500">(optional)</span>
                </label>
                <input
                  type="text"
                  value={assessmentTitle}
                  onChange={(e) => setAssessmentTitle(e.target.value)}
                  placeholder="e.g. PM Analyst Evaluation Q1"
                  className="w-full rounded-lg px-4 py-3 bg-slate-800/50 border border-slate-700 text-white text-sm placeholder:text-slate-500 focus:outline-none focus:border-[#10B981] transition-colors"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-slate-300 mb-1.5">
                  Scenario <span className="text-red-400">*</span>
                </label>
                <select
                  required
                  value={selectedScenario}
                  onChange={(e) => handleScenarioChange(e.target.value)}
                  className="w-full rounded-lg px-4 py-3 bg-slate-800/50 border border-slate-700 text-white text-sm focus:outline-none focus:border-[#10B981] transition-colors"
                >
                  <option value="">Select a scenario...</option>
                  {scenarios.map((s) => (
                    <option key={s.id} value={s.id}>
                      {s.title} ({s.difficulty})
                    </option>
                  ))}
                </select>
              </div>
              {challenges.length > 0 && (
                <div>
                  <label className="block text-sm font-medium text-slate-300 mb-1.5">
                    Challenge <span className="text-slate-500">(optional)</span>
                  </label>
                  <select
                    value={selectedChallenge}
                    onChange={(e) => setSelectedChallenge(e.target.value)}
                    className="w-full rounded-lg px-4 py-3 bg-slate-800/50 border border-slate-700 text-white text-sm focus:outline-none focus:border-[#10B981] transition-colors"
                  >
                    <option value="">All challenges</option>
                    {challenges.map((c) => (
                      <option key={c.id} value={c.id}>
                        {c.challenge_title}
                      </option>
                    ))}
                  </select>
                </div>
              )}
              <div className="flex gap-3 pt-2">
                <button
                  type="button"
                  onClick={() => setShowCreate(false)}
                  className="flex-1 rounded-lg px-4 py-3 text-sm font-medium border border-slate-700 text-slate-300 hover:border-slate-600 transition-colors"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={creating || !selectedScenario}
                  className="flex-1 rounded-lg px-4 py-3 bg-[#10B981] text-sm font-bold disabled:opacity-50 transition-opacity"
                >
                  {creating ? "Creating..." : "Create Assessment"}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
