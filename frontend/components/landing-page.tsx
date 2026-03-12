"use client";

import { useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";

import { listScenarios, startSession } from "@/lib/api";
import type { ScenarioSummary } from "@/lib/types";

const fallbackScenario: ScenarioSummary = {
  id: "checkout_conversion_drop",
  title: "Checkout Conversion Drop",
  difficulty: "medium",
  industry: "food_delivery",
  product: "FoodDash"
};

function getCandidateId() {
  if (typeof window === "undefined") {
    return "candidate_local";
  }
  const existing = window.localStorage.getItem("simwork_candidate_id");
  if (existing) {
    return existing;
  }
  const created = `candidate_${crypto.randomUUID().slice(0, 8)}`;
  window.localStorage.setItem("simwork_candidate_id", created);
  return created;
}

export function LandingPage({
  initialScenarios
}: {
  initialScenarios?: ScenarioSummary[];
}) {
  const router = useRouter();
  const [scenarios, setScenarios] = useState<ScenarioSummary[]>(initialScenarios?.length ? initialScenarios : [fallbackScenario]);
  const [selectedScenario, setSelectedScenario] = useState<string>((initialScenarios?.[0] ?? fallbackScenario).id);
  const [isStarting, setIsStarting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (initialScenarios?.length) {
      return;
    }
    void listScenarios()
      .then((loaded) => {
        if (loaded.length) {
          setScenarios(loaded);
          setSelectedScenario(loaded[0].id);
        }
      })
      .catch(() => undefined);
  }, [initialScenarios]);

  const scenario = useMemo(
    () => scenarios.find((item) => item.id === selectedScenario) ?? scenarios[0] ?? fallbackScenario,
    [scenarios, selectedScenario]
  );

  async function handleStart() {
    setIsStarting(true);
    setError(null);
    try {
      const session = await startSession(getCandidateId(), scenario.id);
      router.push(`/workspace/${session.session_id}`);
    } catch (startError) {
      setError(startError instanceof Error ? startError.message : "Unable to start session");
    } finally {
      setIsStarting(false);
    }
  }

  return (
    <div className="relative flex min-h-screen flex-col overflow-x-hidden text-slate-100">
      <div className="layout-container flex h-full grow flex-col">
        <header className="sticky top-0 z-50 flex items-center justify-between border-b border-slate-800 bg-background-dark/95 px-6 py-4 backdrop-blur md:px-20">
          <div className="flex items-center gap-3">
            <div className="flex size-10 items-center justify-center rounded-lg bg-primary text-white">
              <span className="material-symbols-outlined">strategy</span>
            </div>
            <div className="flex flex-col">
              <h1 className="text-lg font-bold tracking-tight text-white">SimWork</h1>
              <span className="text-xs font-medium text-slate-400">Professional Suite</span>
            </div>
          </div>
          <div className="flex items-center gap-6">
            <nav className="hidden items-center gap-8 md:flex">
              <span className="text-sm font-medium text-slate-300">Dashboard</span>
              <span className="text-sm font-medium text-slate-300">Case Studies</span>
              <span className="text-sm font-medium text-slate-300">Resources</span>
            </nav>
            <button className="hidden rounded-lg bg-primary px-5 py-2 text-sm font-bold text-white md:inline-flex">
              Profile
            </button>
          </div>
        </header>

        <main className="mx-auto flex w-full max-w-6xl flex-1 flex-col px-6 py-12">
          <div className="mb-10">
            <div className="mb-4 inline-flex items-center gap-2 rounded-full bg-primary/10 px-3 py-1 text-xs font-bold uppercase tracking-wider text-primary">
              <span className="material-symbols-outlined text-sm">trending_down</span>
              Critical Incident
            </div>
            <h2 className="text-4xl font-black tracking-tight text-white md:text-5xl">
              Food Delivery: <span className="text-primary">The Retention Crisis</span>
            </h2>
            <p className="mt-2 text-lg text-slate-400">
              {scenario.product ?? "Simulation Module"} • Strategy & Analytics Focus
            </p>
          </div>

          <div className="grid grid-cols-1 gap-8 lg:grid-cols-3">
            <div className="space-y-6 lg:col-span-2">
              <div className="overflow-hidden rounded-xl border border-slate-800 bg-slate-900 shadow-panel">
                <div className="group relative aspect-video w-full overflow-hidden bg-slate-800">
                  <div className="absolute inset-0 bg-gradient-to-t from-slate-950/80 to-transparent" />
                  <div className="absolute inset-x-0 bottom-0 flex items-end p-8">
                    <div className="flex items-center gap-4 text-white">
                      <span className="material-symbols-outlined text-4xl">monitoring</span>
                      <div>
                        <p className="text-xs font-bold uppercase opacity-70">Internal Metrics Dashboard</p>
                        <p className="font-medium">Active Orders: -18% MoM</p>
                      </div>
                    </div>
                  </div>
                  <img
                    className="h-full w-full object-cover opacity-60 transition-transform duration-700 group-hover:scale-105"
                    alt="Analytical dashboard"
                    src="https://lh3.googleusercontent.com/aida-public/AB6AXuCRQW1FPwHVaPLN5uCGhnKVwJlHW10ukrr-ERAN6pEp2NF45Mam72zibwoWJ_9tEVPaeinWf0HvhUE8INpFI_wrjcUKBm97fzAjLp8UKVL5aO1-bEnJEGOlR2xYrHnReRQ7rz-L74GVotrLvrFY6DjbKyEyHlCpUz_CBKwSeHnAa7-XVk06bpKbE_UcZriok-c7dnqV2x4FWVwl25UiXvnvfE3eGomIxcUXA69DW5MxlygYsFjwlx9k_ThEUZH6kJFbo_ndQgbMt3sf"
                  />
                </div>

                <div className="p-8">
                  <h3 className="mb-4 flex items-center gap-3 text-2xl font-bold text-white">
                    <span className="material-symbols-outlined text-primary">description</span>
                    The Scenario
                  </h3>
                  <p className="mb-8 text-lg leading-relaxed text-slate-300">
                    You are the Product Manager for a high-growth food delivery platform. Weekly orders have dropped by{" "}
                    <span className="font-semibold text-white">18%</span> over the past month. Your mission is to investigate
                    the root cause, identify the leaking segments, and propose a data-backed recovery plan.
                  </p>

                  <div className="mb-5">
                    <label className="mb-2 block text-sm font-semibold text-slate-300">Scenario</label>
                    <select
                      value={selectedScenario}
                      onChange={(event) => setSelectedScenario(event.target.value)}
                      className="w-full rounded-lg border border-slate-700 bg-slate-950 px-4 py-3 text-sm text-white outline-none transition focus:border-primary"
                    >
                      {scenarios.map((item) => (
                        <option key={item.id} value={item.id}>
                          {item.title} · {item.difficulty}
                        </option>
                      ))}
                    </select>
                  </div>

                  <div className="flex flex-wrap items-center gap-4">
                    <button
                      onClick={handleStart}
                      disabled={isStarting}
                      className="flex h-14 items-center justify-center gap-2 rounded-lg bg-primary px-8 text-lg font-bold text-white shadow-lg shadow-primary/25 transition-transform hover:scale-[1.02] disabled:cursor-not-allowed disabled:opacity-60"
                    >
                      <span>{isStarting ? "Starting..." : "Start Investigation"}</span>
                      <span className="material-symbols-outlined">arrow_forward</span>
                    </button>
                    <button className="flex h-14 items-center justify-center gap-2 rounded-lg border border-slate-800 px-6 font-bold text-slate-300 transition-colors hover:bg-slate-800">
                      <span className="material-symbols-outlined">bookmark</span>
                      <span>Save for later</span>
                    </button>
                  </div>
                  {error ? <p className="mt-4 text-sm text-red-400">{error}</p> : null}
                </div>
              </div>

              <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
                <div className="rounded-xl border border-slate-800 bg-slate-900/60 p-6">
                  <span className="material-symbols-outlined mb-3 text-primary">timer</span>
                  <p className="text-sm font-medium text-slate-400">Estimated Duration</p>
                  <p className="text-2xl font-bold tracking-tight text-white">30 minutes</p>
                </div>
                <div className="rounded-xl border border-slate-800 bg-slate-900/60 p-6">
                  <span className="material-symbols-outlined mb-3 text-primary">signal_cellular_alt</span>
                  <p className="text-sm font-medium text-slate-400">Complexity Level</p>
                  <p className="text-2xl font-bold tracking-tight text-white">Intermediate</p>
                </div>
              </div>
            </div>

            <div className="space-y-6">
              <div className="rounded-xl border border-slate-800 bg-slate-900 p-6">
                <h4 className="mb-6 flex items-center gap-2 font-bold text-white">
                  <span className="material-symbols-outlined text-primary text-xl">target</span>
                  Key Objectives
                </h4>
                <ul className="space-y-4">
                  {[
                    "Hypothesis generation for traffic decline",
                    "Data-driven funnel analysis",
                    "Prioritization of high-impact fixes",
                    "Stakeholder communication strategy"
                  ].map((objective) => (
                    <li key={objective} className="flex items-start gap-3">
                      <span className="material-symbols-outlined mt-0.5 text-green-500">check_circle</span>
                      <span className="text-sm text-slate-300">{objective}</span>
                    </li>
                  ))}
                </ul>
              </div>

              <div className="rounded-xl border border-primary/20 bg-primary/10 p-6">
                <h4 className="mb-2 font-bold text-primary">Sim Tip</h4>
                <p className="text-xs leading-relaxed text-slate-300">
                  Pay close attention to the <span className="font-bold">user feedback logs</span>. In this scenario,
                  qualitative complaints arrive before the final diagnosis becomes obvious.
                </p>
              </div>

              <div className="rounded-xl bg-gradient-to-br from-primary via-primary/60 to-purple-500 p-1">
                <div className="rounded-[calc(0.75rem-4px)] bg-slate-950 p-6">
                  <p className="mb-1 text-sm font-bold text-white">Ready to prove your skills?</p>
                  <p className="mb-4 text-xs text-slate-400">Start now to capture a full investigation transcript.</p>
                  <div className="flex -space-x-2">
                    {[
                      "https://lh3.googleusercontent.com/aida-public/AB6AXuBYgpHbKQkp8lA3xg7aH6j77TrGn5-vbRp6Ez9bDqDyZC8PDsMR31L2PPJ1y7-Gn42u9STFLUDCrS30kDkehkTs_m8uwHOANoY7UueK5vNbSTU1PFNudE0tY5LGJkpY7w8nU-YDJGqfP52ViTeVgEiUcBwqWLDK8LEVy5V7Dv9LbnQvS6N_XIKFmGXJkUeSiLID_TWb3aEvYJD5p5OmC4aAG6ZuvGwWXQoYZYCSt3mxUCfn5QwufoexGnKmxZIXizzJdJq14ckYZhf2",
                      "https://lh3.googleusercontent.com/aida-public/AB6AXuDVTYQFXFwAph7hDfqVXW2grFVqwHbwuiKklfibIJCh6f8J6vxGbrvxLAYnw-J7Jf5hjfCEWIeBOqZm7W6hKdCpEL8bfPSMzWEEqVvz7nNumtst2qUpKeCxIwYvIqVBFru9GipmwoNE0pKuywqXAZ_8_c4AACacpKUxcscNC4aBbrfyLdF1dDE2ZKJpbiWjgUhYRQhF5d3Eny_NuOkWOpzflx8MDaH291Tq_hx_Da1LpEPTXgF5o7iCOPzmB2UkafJJsEdpia9xgbQK",
                      "https://lh3.googleusercontent.com/aida-public/AB6AXuCsB8vYdHmzt_NOfyoF7ERZnrVE0kLrZjteIzUTXTiOwaKFhnr9I69Nm1o7TBpLnhySrBuUDludA6meZITb3XSlLYCHCkSxtGUK2T2PRMkoKR838ZKcCsF5bGk5nGIxy7Kdw2cIqfkGsYNSUOnKz4zLIF62Bg7XWhOOP6LyBLQiH3ckwXCSzatSFmVqthZLmwRBL_Vgp4YrJ0trB4S3WjNv9UuZBFWrlk0nVw3auN-Piuxgzea6N4UmnR_dXXnBJe1wzgzuyUzBb_Fo"
                    ].map((avatarUrl, index) => (
                      <img
                        key={avatarUrl}
                        src={avatarUrl}
                        alt={`User avatar ${index + 1}`}
                        className="size-8 rounded-full border-2 border-slate-950 object-cover"
                      />
                    ))}
                    <div className="flex size-8 items-center justify-center rounded-full border-2 border-slate-950 bg-slate-800 text-[10px] font-bold text-slate-400">
                      +12
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </main>
      </div>
    </div>
  );
}
