"use client";

import Link from "next/link";
import { Suspense, useEffect, useRef, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { signIn } from "next-auth/react";
import { useAuthToken } from "@/lib/useAuthToken";
import { getMe, getMySessions } from "@/lib/api";
import {
  clearPendingAuthState,
  findAssignedSession,
  setPendingAuthState,
  type PendingAuthState,
  type AuthIntent,
} from "@/lib/auth-routing";

const STEPS = [
  {
    icon: "assignment_add",
    title: "Create an Assessment",
    desc: "Set up a realistic scenario, choose the challenge, and generate an invite link for the candidate.",
  },
  {
    icon: "desktop_windows",
    title: "Candidate Completes the Simulation",
    desc: "The candidate investigates a live problem with evidence, AI teammates, and time pressure inside SimWork.",
  },
  {
    icon: "analytics",
    title: "Review the Results",
    desc: "Evaluate the submission, process signals, and scorecard from one employer workflow.",
  },
];

const DIFFERENTIATORS = [
  {
    icon: "verified",
    title: "Observe Real Work, Not Rehearsed Answers",
    desc: "Stop relying on typical interview questions. See how candidates actually navigate ambiguity and make data-driven decisions.",
  },
  {
    icon: "smart_toy",
    title: "AI Teammates, Not Chatbots",
    desc: "Candidates collaborate with specialized AI agents who push back on logic, provide data, and simulate real stakeholder conflict.",
  },
  {
    icon: "speed",
    title: "30 Minutes, Not 30 Days",
    desc: "Get better signal in a single 30-minute simulation than through weeks of traditional interview rounds and homework assignments.",
  },
];

const STATS = [
  { value: "30 min", label: "AVERAGE ASSESSMENT TIME" },
  { value: "5x", label: "MORE SIGNAL THAN CASE INTERVIEWS" },
  { value: "Zero", label: "SETUP REQUIRED" },
];

const BG_STYLE = {
  backgroundColor: "#101122",
  backgroundImage: [
    "radial-gradient(rgba(255,255,255,0.07) 1px, transparent 1px)",
    "radial-gradient(circle at 25% 50%, rgba(16,185,129,0.15) 0%, transparent 50%)",
    "radial-gradient(circle at 80% 15%, rgba(99,102,241,0.12) 0%, transparent 40%)",
  ].join(", "),
  backgroundSize: "24px 24px, 100% 100%, 100% 100%",
};

type NavDropdownItem = {
  label: string;
  action: () => void;
};

function NavDropdown({
  label,
  items,
}: {
  label: string;
  items: NavDropdownItem[];
}) {
  const [open, setOpen] = useState(false);
  const rootRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    if (!open) return;

    const handlePointerDown = (event: MouseEvent) => {
      if (!rootRef.current?.contains(event.target as Node)) {
        setOpen(false);
      }
    };

    const handleEscape = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        setOpen(false);
      }
    };

    document.addEventListener("mousedown", handlePointerDown);
    document.addEventListener("keydown", handleEscape);
    return () => {
      document.removeEventListener("mousedown", handlePointerDown);
      document.removeEventListener("keydown", handleEscape);
    };
  }, [open]);

  return (
    <div ref={rootRef} className="relative hidden md:block">
      <button
        type="button"
        className="inline-flex items-center gap-1 text-sm text-slate-300 hover:text-white transition-colors"
        onClick={() => setOpen((current) => !current)}
        aria-expanded={open}
      >
        {label}
        <span className="material-symbols-outlined text-base">expand_more</span>
      </button>
      {open && (
        <div className="absolute left-0 top-full mt-3 min-w-[220px] rounded-xl border border-slate-800 bg-[#101122] p-2 shadow-2xl shadow-black/30">
          {items.map((item) => (
            <button
              key={item.label}
              type="button"
              onClick={() => {
                item.action();
                setOpen(false);
              }}
              className="flex w-full items-center justify-between rounded-lg px-3 py-2.5 text-left text-sm text-slate-300 hover:bg-slate-800 hover:text-white transition-colors"
            >
              <span>{item.label}</span>
              <span className="material-symbols-outlined text-base text-slate-500">north_east</span>
            </button>
          ))}
        </div>
      )}
    </div>
  );
}

function DemoForm() {
  const [email, setEmail] = useState("");
  const [company, setCompany] = useState("");
  const [message, setMessage] = useState("");
  const [submitted, setSubmitted] = useState(false);
  const [submitting, setSubmitting] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setSubmitting(true);
    await new Promise((r) => setTimeout(r, 800));
    setSubmitted(true);
    setSubmitting(false);
  };

  if (submitted) {
    return (
      <div className="text-center py-8">
        <div className="flex items-center justify-center size-14 rounded-full bg-[#10B981]/10 mx-auto mb-4">
          <span className="material-symbols-outlined text-3xl text-[#10B981]">check_circle</span>
        </div>
        <h3 className="text-xl font-bold text-white mb-2">Thank you!</h3>
        <p className="text-sm text-slate-400">We&apos;ll reach out to you shortly.</p>
      </div>
    );
  }

  return (
    <div className="w-full max-w-md mx-auto">
      <form onSubmit={handleSubmit} className="space-y-4 text-left">
        <div>
          <label htmlFor="email" className="block text-sm font-medium text-slate-300 mb-1.5">
            Work Email <span className="text-red-400">*</span>
          </label>
          <input
            id="email"
            type="email"
            required
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            placeholder="you@company.com"
            className="w-full rounded-lg px-4 py-3 bg-slate-800/50 border border-slate-700 text-white text-sm placeholder:text-slate-500 focus:outline-none focus:border-[#10B981] transition-colors"
          />
        </div>
        <div>
          <label htmlFor="company" className="block text-sm font-medium text-slate-300 mb-1.5">
            Company <span className="text-red-400">*</span>
          </label>
          <input
            id="company"
            type="text"
            required
            value={company}
            onChange={(e) => setCompany(e.target.value)}
            placeholder="Company name"
            className="w-full rounded-lg px-4 py-3 bg-slate-800/50 border border-slate-700 text-white text-sm placeholder:text-slate-500 focus:outline-none focus:border-[#10B981] transition-colors"
          />
        </div>
        <div>
          <label htmlFor="message" className="block text-sm font-medium text-slate-300 mb-1.5">
            Message <span className="text-slate-500">(optional)</span>
          </label>
          <textarea
            id="message"
            rows={3}
            value={message}
            onChange={(e) => setMessage(e.target.value)}
            placeholder="Tell us about your hiring needs..."
            className="w-full rounded-lg px-4 py-3 bg-slate-800/50 border border-slate-700 text-white text-sm placeholder:text-slate-500 focus:outline-none focus:border-[#10B981] transition-colors resize-none"
          />
        </div>
        <button
          type="submit"
          disabled={submitting}
          className="w-full rounded-xl px-8 py-4 bg-[#10B981] text-base font-bold shadow-lg shadow-[#10B981]/25 hover:shadow-[#10B981]/40 transition-shadow disabled:opacity-60"
        >
          {submitting ? "Submitting..." : "Request a Demo"}
        </button>
      </form>
    </div>
  );
}

function CTASection({ showForm, setShowForm }: { showForm: boolean; setShowForm: (v: boolean) => void }) {
  return (
    <section id="cta" className="max-w-4xl mx-auto px-6 py-24">
      <div className="relative rounded-2xl overflow-hidden">
        <div className="absolute inset-0 bg-gradient-to-r from-[#10B981]/20 via-transparent to-[#10B981]/10 blur-xl" />
        <div className="relative rounded-2xl border border-slate-800 bg-[#101122] p-10 md:p-16 text-center">
          {showForm && (
            <button
              type="button"
              onClick={() => setShowForm(false)}
              className="absolute top-4 right-4 flex items-center justify-center size-8 rounded-full bg-slate-800 text-slate-400 hover:text-white hover:bg-slate-700 transition-colors z-10"
              title="Close"
            >
              <span className="material-symbols-outlined text-lg">close</span>
            </button>
          )}
          <h2 className="text-3xl md:text-4xl font-black mb-4">
            Ready to see candidates in action?
          </h2>
          <p className="text-slate-400 max-w-xl mx-auto mb-10">
            Join companies using SimWork to identify their next top performers with objective simulation data.
          </p>
          {showForm ? (
            <DemoForm />
          ) : (
            <button
              onClick={() => setShowForm(true)}
              className="rounded-xl px-8 py-4 bg-[#10B981] text-base font-bold shadow-lg shadow-[#10B981]/25 hover:shadow-[#10B981]/40 transition-shadow"
            >
              Request a Demo
            </button>
          )}
        </div>
      </div>
    </section>
  );
}

function AuthModal({
  intent,
  nextPath,
  invite,
  onClose,
  onCompanyCandidateConflict,
}: {
  intent: AuthIntent;
  nextPath: string;
  invite: string;
  onClose: () => void;
  onCompanyCandidateConflict: () => void;
}) {
  const [candidateInvite, setCandidateInvite] = useState(invite);
  const [candidateError, setCandidateError] = useState("");
  const title =
    intent === "company"
      ? "Sign in to your hiring workspace"
      : "Start with your invite";
  const subtitle =
    intent === "company"
      ? "Access dashboards, assessment setup, invite links, and candidate review."
      : "Candidate access is invite-first. Use your company’s invite link to begin, or sign in only if you already have an assigned assessment.";

  const startGoogleAuth = (state: PendingAuthState) => {
    setPendingAuthState(state);
    signIn("google", { callbackUrl: "/auth/redirect" });
  };

  const normalizeInviteToken = (value: string): string | null => {
    const trimmed = value.trim();
    if (!trimmed) return null;

    try {
      const url = new URL(trimmed);
      const parts = url.pathname.split("/").filter(Boolean);
      const inviteIndex = parts.indexOf("invite");
      if (inviteIndex >= 0) return parts[inviteIndex + 1] ?? null;
    } catch {
      // fall through
    }

    const normalized = trimmed.replace(/^\/+|\/+$/g, "");
    if (normalized.startsWith("invite/")) {
      return normalized.slice("invite/".length) || null;
    }
    return normalized || null;
  };

  const handleCompanySignIn = () => {
    startGoogleAuth({
      role: "company",
      next: nextPath || "",
    });
  };

  const handleInviteFirst = () => {
    const token = normalizeInviteToken(candidateInvite);
    if (!token) {
      setCandidateError("Paste the invite URL or token your company sent you.");
      return;
    }
    setCandidateError("");
    startGoogleAuth({
      invite: token,
      next: "/candidate",
    });
  };

  const handleContinueAssessment = () => {
    startGoogleAuth({
      next: nextPath || "/candidate",
    });
  };

  return (
    <div className="fixed inset-0 z-[70] flex items-center justify-center bg-slate-950/70 p-6 backdrop-blur-sm">
      <div className="w-full max-w-md rounded-2xl border border-slate-800 bg-[#101122] p-8 shadow-2xl">
        <div className="mb-6 flex items-start justify-between gap-4">
          <div>
            <p className="text-xs font-bold uppercase tracking-widest text-[#10B981]">
              {intent === "company" ? "Company Sign In" : "Candidate Access"}
            </p>
            <h2 className="mt-2 text-2xl font-black text-white">{title}</h2>
            <p className="mt-3 text-sm leading-relaxed text-slate-400">{subtitle}</p>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="flex size-9 items-center justify-center rounded-full bg-slate-800 text-slate-400 hover:bg-slate-700 hover:text-white transition-colors"
            aria-label="Close"
          >
            <span className="material-symbols-outlined text-lg">close</span>
          </button>
        </div>

        {intent === "company" ? (
          <>
            <button
              onClick={handleCompanySignIn}
              className="flex w-full items-center justify-center gap-3 rounded-lg bg-white px-4 py-3 text-sm font-medium text-slate-900 transition hover:bg-slate-100"
            >
              <svg className="size-5" viewBox="0 0 24 24">
                <path d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92a5.06 5.06 0 0 1-2.2 3.32v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.1z" fill="#4285F4" />
                <path d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z" fill="#34A853" />
                <path d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z" fill="#FBBC05" />
                <path d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z" fill="#EA4335" />
              </svg>
              Continue with Google
            </button>

            <p className="mt-4 text-xs text-slate-500">
              New or existing company users use the same sign-in entry. Onboarding intent is preserved after authentication.
            </p>
          </>
        ) : (
          <div className="space-y-5">
            <div className="rounded-xl border border-slate-800 bg-slate-900/30 p-4">
              <p className="text-xs font-bold uppercase tracking-widest text-[#10B981] mb-2">
                I have an invite link
              </p>
              <p className="text-sm text-slate-400 mb-4">
                Paste the full invite URL or only the token from your company to begin directly.
              </p>
              <textarea
                value={candidateInvite}
                onChange={(e) => setCandidateInvite(e.target.value)}
                rows={3}
                placeholder="https://simwork.ai/invite/abc123 or abc123"
                className="w-full rounded-lg px-4 py-3 bg-slate-800/50 border border-slate-700 text-white text-sm placeholder:text-slate-500 focus:outline-none focus:border-[#10B981] transition-colors resize-none"
              />
              {candidateError && <p className="mt-2 text-sm text-red-400">{candidateError}</p>}
              <button
                onClick={handleInviteFirst}
                className="mt-4 w-full rounded-lg bg-[#10B981] px-4 py-3 text-sm font-bold text-white transition hover:bg-emerald-600"
              >
                Continue with invite
              </button>
            </div>

            <div className="rounded-xl border border-slate-800 bg-slate-900/20 p-4">
              <p className="text-xs font-bold uppercase tracking-widest text-slate-400 mb-2">
                Continue an existing assessment
              </p>
              <p className="text-sm text-slate-400 mb-4">
                Sign in only if you already have an assigned assessment in progress.
              </p>
              <button
                onClick={handleContinueAssessment}
                className="flex w-full items-center justify-center gap-3 rounded-lg border border-slate-700 bg-white px-4 py-3 text-sm font-medium text-slate-900 transition hover:bg-slate-100"
              >
                <svg className="size-5" viewBox="0 0 24 24">
                  <path d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92a5.06 5.06 0 0 1-2.2 3.32v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.1z" fill="#4285F4" />
                  <path d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z" fill="#34A853" />
                  <path d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z" fill="#FBBC05" />
                  <path d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z" fill="#EA4335" />
                </svg>
                Sign in to continue
              </button>
            </div>

            <button
              type="button"
              onClick={onCompanyCandidateConflict}
              className="text-xs text-slate-500 hover:text-white transition-colors"
            >
              Using a company account? Return to the employer dashboard instead.
            </button>
          </div>
        )}
      </div>
    </div>
  );
}

function HomePageContent() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const authSession = useAuthToken();
  const [showDemoForm, setShowDemoForm] = useState(false);

  const authIntentParam = searchParams.get("auth");
  const authIntent: AuthIntent | null =
    authIntentParam === "company" || authIntentParam === "candidate" ? authIntentParam : null;
  const nextPath = searchParams.get("next") || "";
  const invite = searchParams.get("invite") || "";

  useEffect(() => {
    if (authIntent) return;
    if (!authSession) return;

    let cancelled = false;

    async function routeAuthenticatedUser() {
      try {
        const me = await getMe();
        if (cancelled) return;

        if (me.role === "company") {
          clearPendingAuthState();
          router.replace("/dashboard");
          return;
        }

        const { sessions } = await getMySessions();
        if (cancelled) return;

        const assignedSession = findAssignedSession(sessions);
        clearPendingAuthState();
        router.replace(assignedSession ? `/briefing/${assignedSession.session_id}` : "/candidate");
      } catch {
        if (!cancelled) {
          clearPendingAuthState();
        }
      }
    }

    routeAuthenticatedUser();

    return () => {
      cancelled = true;
    };
  }, [authIntent, authSession, router]);

  const openDemoForm = () => {
    setShowDemoForm(true);
    setTimeout(() => {
      document.getElementById("cta")?.scrollIntoView({ behavior: "smooth", block: "center" });
    }, 100);
  };

  const scrollToHowItWorks = () => {
    document.getElementById("how-it-works")?.scrollIntoView({ behavior: "smooth", block: "start" });
  };

  const scrollToSection = (id: string) => {
    document.getElementById(id)?.scrollIntoView({ behavior: "smooth", block: "start" });
  };

  const openModal = (intent: AuthIntent) => {
    const params = new URLSearchParams(searchParams.toString());
    params.set("auth", intent);
    if (intent === "candidate" && !params.get("next")) {
      params.set("next", "/candidate");
    }
    const query = params.toString();
    router.replace(query ? `/?${query}` : "/", { scroll: false });
  };

  const closeModal = () => {
    const params = new URLSearchParams(searchParams.toString());
    params.delete("auth");
    params.delete("next");
    params.delete("invite");
    const query = params.toString();
    router.replace(query ? `/?${query}` : "/", { scroll: false });
  };

  const handleCompanyCandidateConflict = () => {
    clearPendingAuthState();
    router.push("/dashboard?notice=candidate-access-company");
  };

  const aboutDropdownItems: NavDropdownItem[] = [
    { label: "Why SimWork", action: () => scrollToSection("why-simwork") },
    { label: "How It Works", action: scrollToHowItWorks },
    { label: "Assessment Metrics", action: () => scrollToSection("impact-metrics") },
  ];

  const contactDropdownItems: NavDropdownItem[] = [
    { label: "Request a Demo", action: openDemoForm },
    { label: "Email Sales", action: () => (window.location.href = "mailto:sales@simwork.ai") },
    { label: "Contact Support", action: () => (window.location.href = "mailto:support@simwork.ai") },
  ];

  const productDropdownItems: NavDropdownItem[] = [
    { label: "Hiring Assessments", action: scrollToHowItWorks },
    { label: "Candidate Workspace", action: () => scrollToSection("why-simwork") },
    { label: "Review Scorecards", action: () => scrollToSection("impact-metrics") },
  ];

  return (
    <div className="min-h-screen text-white" style={BG_STYLE}>
      <nav className="sticky top-0 z-50 flex items-center justify-between px-6 md:px-12 py-4 bg-[#101122]/80 backdrop-blur-xl border-b border-slate-800">
        <div className="flex items-center gap-8">
          <div className="flex items-center gap-2.5">
            <div className="flex items-center justify-center size-9 bg-[#10B981] rounded-lg text-white">
              <span className="material-symbols-outlined text-xl">strategy</span>
            </div>
            <span className="text-lg font-bold tracking-tight">SimWork</span>
          </div>
          <div className="items-center gap-6 hidden lg:flex">
            <NavDropdown label="About Us" items={aboutDropdownItems} />
            <NavDropdown label="Contact Us" items={contactDropdownItems} />
            <NavDropdown label="Products" items={productDropdownItems} />
          </div>
        </div>
        <div className="flex items-center gap-6">
          <button
            onClick={() => openModal("candidate")}
            className="text-sm text-slate-300 hover:text-white transition-colors"
          >
            Candidate Access
          </button>
          <button
            onClick={() => openModal("company")}
            className="rounded-lg px-5 py-2.5 bg-[#10B981] text-sm font-bold text-white hover:bg-emerald-600 transition-colors"
          >
            Company Sign In
          </button>
        </div>
      </nav>

      <section className="relative min-h-[90vh] flex flex-col items-center justify-center text-center px-6 overflow-hidden">
        <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[600px] h-[600px] rounded-full bg-[#10B981]/[0.08] blur-[120px] pointer-events-none" />

        <div className="relative z-10 max-w-3xl">
          <span className="inline-flex items-center gap-2 px-4 py-1.5 rounded-full bg-[#10B981]/10 text-[#10B981] text-xs font-bold uppercase tracking-wider border border-[#10B981]/20 mb-8">
            <span className="size-2 rounded-full bg-[#10B981]" />
            AI-Powered Hiring Assessments
          </span>

          <h1 className="text-4xl sm:text-5xl md:text-6xl lg:text-7xl font-black leading-tight tracking-tight mb-6">
            See How Candidates
            <br />
            <span className="text-[#10B981]">Actually Work.</span>
          </h1>

          <p className="text-lg md:text-xl text-slate-400 max-w-2xl mx-auto leading-relaxed mb-10">
            SimWork helps hiring teams create realistic assessments, invite candidates, and review
            how they investigate, reason, and communicate before the hire is made.
          </p>

          <div className="flex flex-col sm:flex-row items-center justify-center gap-4 mb-8">
            <button
              onClick={openDemoForm}
              className="rounded-xl px-8 py-4 bg-[#10B981] text-base font-bold shadow-lg shadow-[#10B981]/25 hover:shadow-[#10B981]/40 transition-shadow"
            >
              Request a Demo
            </button>
            <button
              onClick={scrollToHowItWorks}
              className="rounded-xl px-8 py-4 border border-slate-700 text-slate-300 text-base font-semibold hover:border-[#10B981]/50 hover:text-white transition-colors"
            >
              How It Works
            </button>
          </div>
        </div>
      </section>

      <section id="how-it-works" className="max-w-6xl mx-auto px-6 py-24">
        <h2 className="text-3xl md:text-4xl font-black text-center mb-16">
          How It Works
        </h2>

        <div className="relative grid grid-cols-1 md:grid-cols-3 gap-12 md:gap-8">
          <div className="hidden md:block absolute top-[52px] left-[16.67%] right-[16.67%] border-t-2 border-dashed border-[#10B981]/30 -z-0" />

          {STEPS.map((step, i) => (
            <div key={step.icon} className="relative flex flex-col items-center text-center">
              <div className="relative z-10 flex items-center justify-center size-16 rounded-2xl bg-[#10B981]/10 mb-6">
                <span className="material-symbols-outlined text-3xl text-[#10B981]">
                  {step.icon}
                </span>
              </div>
              <h3 className="text-base font-bold mb-2">
                {i + 1}. {step.title}
              </h3>
              <p className="text-sm text-slate-400 leading-relaxed max-w-xs">
                {step.desc}
              </p>
            </div>
          ))}
        </div>
      </section>

      <section id="why-simwork" className="max-w-6xl mx-auto px-6 py-24">
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
          {DIFFERENTIATORS.map((d) => (
            <div
              key={d.icon}
              className="p-8 rounded-2xl border border-slate-800 bg-slate-900/30 hover:border-[#10B981]/30 transition-colors"
            >
              <div className="flex items-center justify-center size-12 rounded-xl bg-[#10B981]/10 mb-6">
                <span className="material-symbols-outlined text-2xl text-[#10B981]">
                  {d.icon}
                </span>
              </div>
              <h3 className="text-lg font-bold mb-3">{d.title}</h3>
              <p className="text-sm text-slate-400 leading-relaxed">{d.desc}</p>
            </div>
          ))}
        </div>
      </section>

      <section id="impact-metrics" className="max-w-5xl mx-auto px-6 py-16">
        <div className="flex flex-col md:flex-row items-center justify-center gap-12 md:gap-0">
          {STATS.map((s, i) => (
            <div key={s.label} className="flex items-center gap-0">
              {i > 0 && (
                <div className="hidden md:block w-px h-14 bg-slate-800 mx-16" />
              )}
              <div className="text-center">
                <p className="text-4xl md:text-5xl font-black">{s.value}</p>
                <p className="text-[10px] font-bold uppercase tracking-widest text-[#10B981] mt-2">
                  {s.label}
                </p>
              </div>
            </div>
          ))}
        </div>
      </section>

      <CTASection showForm={showDemoForm} setShowForm={setShowDemoForm} />

      <footer className="border-t border-slate-800 py-8 px-6">
        <div className="max-w-6xl mx-auto flex flex-col md:flex-row justify-between items-center gap-4 text-slate-500 text-sm">
          <p>&copy; 2026 SimWork Inc. All rights reserved.</p>
          <div className="flex gap-6">
            <Link className="hover:text-[#10B981] transition-colors" href="/privacy-policy">
              Privacy Policy
            </Link>
            <Link className="hover:text-[#10B981] transition-colors" href="/terms-of-use">
              Terms of Use
            </Link>
            <a className="hover:text-[#10B981] transition-colors" href="mailto:support@simwork.ai">
              Contact
            </a>
          </div>
          <div className="flex gap-3">
            <a
              className="size-8 rounded-full bg-slate-800 flex items-center justify-center hover:bg-slate-700 transition-colors"
              href="https://www.simwork.ai"
              aria-label="SimWork website"
            >
              <span className="material-symbols-outlined text-sm text-slate-400">
                language
              </span>
            </a>
            <a
              className="size-8 rounded-full bg-slate-800 flex items-center justify-center hover:bg-slate-700 transition-colors"
              href="mailto:support@simwork.ai"
              aria-label="Email SimWork support"
            >
              <span className="material-symbols-outlined text-sm text-slate-400">
                mail
              </span>
            </a>
          </div>
        </div>
      </footer>

      {authIntent && (
        <AuthModal
          key={`${authIntent}-${invite}-${nextPath}`}
          intent={authIntent}
          nextPath={nextPath}
          invite={invite}
          onClose={closeModal}
          onCompanyCandidateConflict={handleCompanyCandidateConflict}
        />
      )}
    </div>
  );
}

export default function HomePage() {
  return (
    <Suspense>
      <HomePageContent />
    </Suspense>
  );
}
