"use client";

import { signIn } from "next-auth/react";

const FEATURES = [
  {
    icon: "cases",
    title: "Real-World Scenarios",
    desc: "Investigate realistic business problems with data, documents, and stakeholders.",
  },
  {
    icon: "smart_toy",
    title: "AI-Powered Team",
    desc: "Collaborate with specialized AI agents: data analysts, researchers, and engineering leads.",
  },
  {
    icon: "timer",
    title: "Timed Assessment",
    desc: "Work under realistic time pressure, just like on the job.",
  },
];

export default function LoginPage() {
  return (
    <div
      className="flex min-h-screen"
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
      {/* Left — Hero */}
      <div className="hidden lg:flex flex-col justify-center flex-1 px-16 xl:px-24">
        <div className="flex items-center gap-3 mb-8">
          <div className="flex items-center justify-center size-12 bg-[#10B981] rounded-xl text-white">
            <span className="material-symbols-outlined text-2xl">strategy</span>
          </div>
          <span className="text-2xl font-bold text-white tracking-tight">SimWork</span>
        </div>

        <h1 className="text-4xl xl:text-5xl font-black text-white leading-tight tracking-tight mb-4">
          Simulate Real Work.
          <br />
          <span className="text-[#10B981]">Prove Real Skills.</span>
        </h1>

        <p className="text-slate-400 text-lg max-w-lg mb-10 leading-relaxed">
          SimWork drops you into realistic business simulations where you investigate problems,
          analyze data, collaborate with AI teammates, and deliver actionable recommendations —
          all under time pressure.
        </p>

        <div className="space-y-5">
          {FEATURES.map((f) => (
            <div key={f.icon} className="flex items-start gap-4">
              <div className="flex items-center justify-center size-10 rounded-lg bg-[#10B981]/10 text-[#10B981] shrink-0">
                <span className="material-symbols-outlined text-xl">{f.icon}</span>
              </div>
              <div>
                <h3 className="text-sm font-bold text-white mb-0.5">{f.title}</h3>
                <p className="text-sm text-slate-400 leading-relaxed">{f.desc}</p>
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Right — Sign-in */}
      <div className="flex flex-col items-center justify-center flex-1 lg:max-w-md px-6">
        {/* Mobile branding */}
        <div className="flex flex-col items-center gap-3 mb-8 lg:hidden">
          <div className="flex items-center justify-center size-14 bg-[#10B981] rounded-2xl text-white">
            <span className="material-symbols-outlined text-3xl">strategy</span>
          </div>
          <h1 className="text-2xl font-bold text-white tracking-tight">SimWork</h1>
          <p className="text-sm text-slate-400 text-center max-w-xs">
            Simulate real work. Prove real skills.
          </p>
        </div>

        <div className="w-full max-w-sm rounded-xl border border-slate-800 bg-slate-900/50 p-8">
          <h2 className="text-lg font-semibold text-white mb-2">Welcome</h2>
          <p className="text-sm text-slate-400 mb-6">Sign in to start your simulation</p>

          <button
            onClick={() => signIn("google", { callbackUrl: "/" })}
            className="flex w-full items-center justify-center gap-3 rounded-lg bg-white px-4 py-3 text-sm font-medium text-slate-900 transition hover:bg-slate-100"
          >
            <svg className="size-5" viewBox="0 0 24 24">
              <path
                d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92a5.06 5.06 0 0 1-2.2 3.32v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.1z"
                fill="#4285F4"
              />
              <path
                d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z"
                fill="#34A853"
              />
              <path
                d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z"
                fill="#FBBC05"
              />
              <path
                d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z"
                fill="#EA4335"
              />
            </svg>
            Continue with Google
          </button>
        </div>

        <p className="text-xs text-slate-500 mt-6 text-center max-w-sm">
          By signing in, you agree to participate in the simulation assessment.
        </p>
      </div>
    </div>
  );
}
